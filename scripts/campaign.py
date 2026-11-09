#!/usr/bin/env python3
"""Run ONE round of the FAIR-5G measurement campaign protocol (issue #21).

A round, in order:

  1. down               clean slate, whatever the previous round left behind
  2. up                 scripts/up_v0.sh in detached mode (FAIR5G_DETACH=1)
  3. verify             scripts/verify_up.py in strict mode
  4. session check      one tunnel per UE, tunnel addresses where expected
  5. settle   (60 s)    let registration traffic and caches calm down
  6. idle     (120 s)   ping through each UE's tunnel, no load
  7. per_slice          each slice alone: iperf3 uplink 30 s, then downlink 30 s
  8. concurrent         every slice at once, uplink then downlink, ping in parallel
  9. collect            M4 counters, OVS flows/meters, ONOS meters, logs, images
 10. down               always, even after a failure or Ctrl-C

Everything lands in runs/<campaign>/rNNN/ with a manifest.json describing the
round: commit, configuration, timestamps, per-phase CPU/memory/IO pressure and
steal time, the result of every check, every test, and whether the round is
VALID. Invalid rounds are kept and counted, never deleted: dropping them would
hide exactly the failures (#30 stall, shifted UE addresses) the campaign must
quantify.

Usage (from the repository root, inside tmux, as root):

    sudo python3 scripts/campaign.py --campaign baseline
    sudo python3 scripts/campaign.py --campaign baseline --ues-per-slice 2,1

Short smoke test (rounds are marked protocol_conformant=false):

    sudo python3 scripts/campaign.py --campaign smoke --settle 5 --idle 10 --duration 5

Exit status, for the loop that will drive several rounds:

    0    round valid
    3    round INVALID (recorded; the next round may proceed)
    1    runner error (environment may be dirty: stop the loop and look)
    130  interrupted

Only the standard library is used: `sudo python3` does not see a virtualenv.
"""

import argparse
import base64
import fcntl
import ipaddress
import json
import os
import platform
import re
import shutil
import signal
import subprocess
import sys
import time
import urllib.request
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from fair5gctl.core.slicing import build_slice_specs  # noqa: E402

SCHEMA_VERSION = 1

# Values approved for the protocol on #21. Any round run with other values is
# still recorded, but flagged protocol_conformant=false so it never ends up in
# the aggregated statistics by accident.
PROTOCOL = {
    "settle_s": 60,
    "idle_s": 120,
    "iperf_duration_s": 30,
    "ping_interval_s": 0.2,
}

PID_FILE = REPO_ROOT / ".fair5g_topology.pid"
RUNS_DIR = REPO_ROOT / "runs"
LOCK_FILE = RUNS_DIR / ".campaign.lock"

# Files that up_v0.sh generates. When the runner runs as root they come out
# owned by root, and the next `./fair5g up` run as the normal user fails to
# rewrite them. Ownership is handed back at the end of every round.
GENERATED_PATHS = [
    REPO_ROOT / ".env",
    REPO_ROOT / "configs" / "runtime",
    REPO_ROOT / "compose-files" / "network-slicing" / "docker-compose.slices.generated.yaml",
    REPO_ROOT / "open5gs" / "seed" / "subscribers.generated.js",
    REPO_ROOT / ".fair5g_state.json",
]

IPERF_BASE_PORT = 5201          # UE k of a slice uses port 5201 + k - 1 on its UPF
STALL_MIN_ZERO_INTERVALS = 3    # #30: >= 3 consecutive 1-s intervals at zero
GAP_S = 5                       # pause between iperf3 batches
UP_TIMEOUT_S = 900
DOWN_TIMEOUT_S = 300
TOPOLOGY_STOP_TIMEOUT_S = 30

EXIT_VALID, EXIT_ERROR, EXIT_INVALID, EXIT_INTERRUPTED = 0, 1, 3, 130

CAMPAIGN_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,63}$")
ROUND_DIR_RE = re.compile(r"^r(\d{3,})$")

# Kill iperf3 inside a container without relying on procps, which the UPF image
# (plain ubuntu + open5gs) does not ship.
KILL_IPERF_SH = (
    'for p in /proc/[0-9]*; do '
    '[ "$(cat "$p/comm" 2>/dev/null)" = iperf3 ] && kill "${p#/proc/}" 2>/dev/null; '
    'done; true'
)


class RunnerError(Exception):
    """The runner itself could not proceed (not a property of the round)."""


class RoundInvalid(Exception):
    """The round cannot produce usable data; stop measuring, keep the record."""


class Interrupted(Exception):
    pass


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


# ── host counters ────────────────────────────────────────────────────────────

def read_pressure() -> dict:
    """PSI counters: {"cpu_some": {"avg10":..., "total":...}, ...}.

    `total` is cumulative stall time in microseconds; its delta over a phase is
    an exact measure of contention during that phase, unlike the avgN values,
    which are moving averages.
    """
    out = {}
    for resource in ("cpu", "memory", "io"):
        try:
            text = Path(f"/proc/pressure/{resource}").read_text()
        except OSError:
            continue
        for line in text.splitlines():
            kind, *fields = line.split()
            out[f"{resource}_{kind}"] = {
                k: float(v) for k, v in (f.split("=", 1) for f in fields)
            }
    return out


CPU_FIELDS = ["user", "nice", "system", "idle", "iowait", "irq", "softirq", "steal"]


def read_cpu_jiffies() -> dict:
    with open("/proc/stat") as fh:
        first = fh.readline().split()
    # guest/guest_nice are already accounted inside user/nice: leave them out.
    return dict(zip(CPU_FIELDS, (int(v) for v in first[1:1 + len(CPU_FIELDS)])))


def pressure_delta_pct(before: dict, after: dict, seconds: float) -> dict:
    if seconds <= 0:
        return {}
    result = {}
    for key, fields in after.items():
        if key in before and "total" in fields:
            stalled_us = fields["total"] - before[key]["total"]
            result[f"{key}_pct"] = round(100.0 * stalled_us / (seconds * 1e6), 3)
    return result


def cpu_delta_pct(before: dict, after: dict) -> dict:
    total = sum(after[k] - before[k] for k in CPU_FIELDS)
    if total <= 0:
        return {}
    busy = total - (after["idle"] - before["idle"]) - (after["iowait"] - before["iowait"])
    return {
        "steal_pct": round(100.0 * (after["steal"] - before["steal"]) / total, 3),
        "busy_pct": round(100.0 * busy / total, 3),
        "iowait_pct": round(100.0 * (after["iowait"] - before["iowait"]) / total, 3),
    }


# ── statistics and parsers ───────────────────────────────────────────────────

def percentile(sorted_values: list, q: float) -> float:
    """Linear interpolation between closest ranks (numpy's default)."""
    if not sorted_values:
        return None
    pos = (len(sorted_values) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(sorted_values) - 1)
    return sorted_values[lo] + (sorted_values[hi] - sorted_values[lo]) * (pos - lo)


def describe(values: list) -> dict:
    if not values:
        return {"n": 0}
    s = sorted(values)
    n = len(s)
    mean = sum(s) / n
    std = (sum((v - mean) ** 2 for v in s) / (n - 1)) ** 0.5 if n > 1 else 0.0
    return {
        "n": n,
        "mean": round(mean, 4),
        "std": round(std, 4),
        "min": round(s[0], 4),
        "median": round(percentile(s, 0.5), 4),
        "p95": round(percentile(s, 0.95), 4),
        "max": round(s[-1], 4),
    }


PING_REPLY_RE = re.compile(r"icmp_seq=(\d+).*?time=([\d.]+) ms")
PING_SUMMARY_RE = re.compile(r"(\d+) packets transmitted, (\d+) received")


def summarize_ping(text: str) -> dict:
    replies = PING_REPLY_RE.findall(text)
    seqs = sorted({int(s) for s, _ in replies})
    rtts = [float(t) for _, t in replies]
    m = PING_SUMMARY_RE.search(text)
    tx, rx = (int(m.group(1)), int(m.group(2))) if m else (None, None)

    # Longest run of consecutive lost probes: a stall shows up here as a long
    # gap, even when the overall loss percentage looks small.
    max_lost_run = 0
    if tx:
        received = set(seqs)
        run = 0
        for seq in range(1, tx + 1):
            run = 0 if seq in received else run + 1
            max_lost_run = max(max_lost_run, run)

    return {
        "transmitted": tx,
        "received": rx,
        "loss_pct": round(100.0 * (tx - rx) / tx, 3) if tx else None,
        "max_consecutive_lost": max_lost_run,
        "rtt_ms": describe(rtts),
    }


def longest_zero_run(values: list) -> int:
    best = run = 0
    for v in values:
        run = run + 1 if v == 0 else 0
        best = max(best, run)
    return best


def summarize_iperf(data: dict) -> dict:
    intervals = [iv.get("sum", {}) for iv in data.get("intervals", [])]
    interval_bytes = [iv.get("bytes", 0) for iv in intervals if not iv.get("omitted")]
    interval_bps = [iv.get("bits_per_second", 0.0) for iv in intervals if not iv.get("omitted")]
    end = data.get("end", {})
    sent = end.get("sum_sent", {})
    received = end.get("sum_received", {})
    zero_run = longest_zero_run(interval_bytes)
    error = data.get("error")
    return {
        "ok": error is None and bool(sent) and bool(received),
        "error": error,
        "sent_bps": sent.get("bits_per_second"),
        "received_bps": received.get("bits_per_second"),
        "retransmits": sent.get("retransmits"),
        "intervals": len(interval_bytes),
        "interval_bps": describe(interval_bps),
        "longest_zero_run": zero_run,
        "stall": zero_run >= STALL_MIN_ZERO_INTERVALS,
    }


# ── the round ────────────────────────────────────────────────────────────────

class Round:
    def __init__(self, campaign: str, args, specs):
        self.campaign = campaign
        self.args = args
        self.specs = specs
        self.dir = self._allocate_dir(RUNS_DIR / campaign)
        self.name = self.dir.name
        self._log = open(self.dir / "runner.log", "a", buffering=1)
        self._cmdlog = open(self.dir / "commands.log", "a", buffering=1)
        self.up_proc = None
        self.vmstat_proc = None
        self.tunnel_ips = {}   # ue name -> tunnel address
        conformant = {
            "settle_s": args.settle, "idle_s": args.idle,
            "iperf_duration_s": args.duration, "ping_interval_s": args.ping_interval,
        } == PROTOCOL
        self.manifest = {
            "schema_version": SCHEMA_VERSION,
            "campaign": campaign,
            "round": self.name,
            "status": "running",
            "started_at": utcnow(),
            "finished_at": None,
            "runner": {"script": "scripts/campaign.py", "argv": sys.argv[1:]},
            "git": {},
            "host": {},
            "config": {
                "slices": len(specs),
                "ues_per_slice": [len(s.ues) for s in specs],
                "settle_s": args.settle,
                "idle_s": args.idle,
                "iperf_duration_s": args.duration,
                "iperf_protocol": "tcp",
                "ping_interval_s": args.ping_interval,
                "gap_s": GAP_S,
                "stall_min_zero_intervals": STALL_MIN_ZERO_INTERVALS,
                "protocol_conformant": conformant,
                "slice_specs": [
                    {
                        "index": s.index,
                        "sst": s.sst,
                        "sd": s.sd_hex,
                        "upf_subnet": s.upf_subnet,
                        "upf_gateway": s.upf_gateway,
                        "ambr_down_mbps": s.ambr_down_mbps,
                        "ambr_up_mbps": s.ambr_up_mbps,
                        "ues": [
                            {"name": u.name, "imsi": u.imsi, "access_ip": u.access_ip}
                            for u in s.ues
                        ],
                    }
                    for s in specs
                ],
            },
            "images": {},
            "phases": [],
            "checks": {},
            "tests": [],
            "validity": {"valid": None, "reasons": []},
            "teardown": {},
            "errors": [],
        }
        self.save_manifest()

    @staticmethod
    def _allocate_dir(campaign_dir: Path) -> Path:
        campaign_dir.mkdir(parents=True, exist_ok=True)
        numbers = [int(m.group(1)) for p in campaign_dir.iterdir()
                   if (m := ROUND_DIR_RE.match(p.name))]
        n = max(numbers, default=0) + 1
        while True:
            path = campaign_dir / f"r{n:03d}"
            try:
                path.mkdir()          # exist_ok=False: never reuse a round dir
                return path
            except FileExistsError:
                n += 1

    # ── bookkeeping

    def log(self, msg: str) -> None:
        line = f"{utcnow()} [{self.campaign}/{self.name}] {msg}"
        print(line, flush=True)
        self._log.write(line + "\n")

    def save_manifest(self) -> None:
        # Write-then-rename: a crash mid-write must not leave a truncated JSON.
        tmp = self.dir / "manifest.json.tmp"
        tmp.write_text(json.dumps(self.manifest, indent=2, sort_keys=False) + "\n")
        os.replace(tmp, self.dir / "manifest.json")

    def invalidate(self, reason: str) -> None:
        reasons = self.manifest["validity"]["reasons"]
        if reason not in reasons:
            reasons.append(reason)
            self.log(f"[INVALID] {reason}")
        self.save_manifest()

    def error(self, msg: str) -> None:
        self.manifest["errors"].append({"at": utcnow(), "message": msg})
        self.log(f"[ERROR] {msg}")
        self.save_manifest()

    def run(self, cmd: list, *, timeout: float = 120, out: str = None,
            env: dict = None, cwd: Path = None) -> subprocess.CompletedProcess:
        """Run a command, log it, optionally save its output under the round dir.

        Never raises on a non-zero exit or a timeout: the caller decides what a
        failure means for the round.
        """
        t0 = time.monotonic()
        try:
            proc = subprocess.run(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                errors="replace", timeout=timeout, env=env, cwd=cwd,
            )
            rc, output = proc.returncode, proc.stdout
        except subprocess.TimeoutExpired as e:
            rc = 124
            output = (e.stdout.decode(errors="replace") if isinstance(e.stdout, bytes)
                      else (e.stdout or "")) + f"\n[campaign] TIMEOUT after {timeout}s\n"
        except FileNotFoundError as e:
            rc, output = 127, f"[campaign] {e}\n"
        self._cmdlog.write(f"{utcnow()} rc={rc} t={time.monotonic() - t0:.1f}s "
                           f"$ {' '.join(map(str, cmd))}\n")
        if out:
            (self.dir / out).write_text(output)
        return subprocess.CompletedProcess(cmd, rc, output, None)

    def spawn(self, cmd: list, out: str) -> subprocess.Popen:
        self._cmdlog.write(f"{utcnow()} spawn $ {' '.join(map(str, cmd))}\n")
        fh = open(self.dir / out, "w")
        proc = subprocess.Popen(cmd, stdout=fh, stderr=subprocess.STDOUT,
                                stdin=subprocess.DEVNULL)
        proc._campaign_out = fh  # closed by wait_all
        return proc

    @contextmanager
    def phase(self, name: str):
        rec = {"name": name, "start": utcnow()}
        self.manifest["phases"].append(rec)
        self.save_manifest()
        self.log(f"── phase {name}")
        t0 = time.monotonic()
        p0, j0 = read_pressure(), read_cpu_jiffies()
        try:
            yield rec
        finally:
            seconds = time.monotonic() - t0
            p1, j1 = read_pressure(), read_cpu_jiffies()
            rec.update({
                "end": utcnow(),
                "duration_s": round(seconds, 3),
                "pressure": pressure_delta_pct(p0, p1, seconds),
                "cpu": cpu_delta_pct(j0, j1),
            })
            with open(self.dir / "pressure.jsonl", "a") as fh:
                fh.write(json.dumps({"phase": name, "start": p0, "end": p1,
                                     "cpu_start": j0, "cpu_end": j1}) + "\n")
            self.save_manifest()


def wait_all(procs: list, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    for p in procs:
        try:
            p.wait(timeout=max(1.0, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            p.kill()
            p.wait()
        p._campaign_out.close()


# ── steps ────────────────────────────────────────────────────────────────────

def preflight(args) -> dict:
    """Checks that need no environment. Returns the env for up_v0.sh."""
    if os.geteuid() != 0:
        raise RunnerError("run as root: sudo python3 scripts/campaign.py ...")
    missing = [t for t in ("docker", "git", "vmstat", "ovs-ofctl") if not shutil.which(t)]
    if missing:
        raise RunnerError(f"missing tools on the host: {', '.join(missing)}")

    env = dict(os.environ)
    env["FAIR5G_DETACH"] = "1"
    env["FAIR5G_SLICE_COUNT"] = str(args.slices)
    env.pop("FAIR5G_UES_PER_SLICE", None)
    if args.ues_per_slice:
        env["FAIR5G_UES_PER_SLICE"] = args.ues_per_slice

    # render_slice_configs.py needs jinja2. bootstrap_ubuntu.sh installs it with
    # `pip --user`, which root's python3 does not see. Borrow the invoking
    # user's site-packages rather than failing halfway through `up`.
    probe = [sys.executable, "-c", "import jinja2"]
    if subprocess.run(probe, capture_output=True, env=env).returncode != 0:
        user = os.environ.get("SUDO_USER")
        site = ""
        if user:
            site = subprocess.run(
                ["sudo", "-H", "-u", user, "python3", "-c",
                 "import site; print(site.getusersitepackages())"],
                capture_output=True, text=True).stdout.strip()
        if site:
            env["PYTHONPATH"] = site + (":" + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
        if subprocess.run(probe, capture_output=True, env=env).returncode != 0:
            raise RunnerError("jinja2 is not importable by root's python3 "
                              "(install it with: sudo apt-get install python3-jinja2)")
    return env


def record_git_and_host(rnd: Round) -> None:
    # safe.directory: as root, git refuses a repository owned by another user.
    # --no-optional-locks: `git status` must not rewrite .git/index as root,
    # or the user's next git command fails on a root-owned index.
    git = ["git", "-c", f"safe.directory={REPO_ROOT}", "--no-optional-locks",
           "-C", str(REPO_ROOT)]
    commit = rnd.run(git + ["rev-parse", "HEAD"]).stdout.strip()
    branch = rnd.run(git + ["rev-parse", "--abbrev-ref", "HEAD"]).stdout.strip()
    status = rnd.run(git + ["status", "--porcelain"]).stdout.splitlines()
    rnd.manifest["git"] = {"commit": commit, "branch": branch,
                           "dirty": bool(status), "dirty_files": status}
    if status:
        rnd.log(f"[WARN] working tree is dirty ({len(status)} file(s)); recorded in the manifest")

    meminfo = Path("/proc/meminfo").read_text().splitlines()
    mem_total = next((l.split()[1] for l in meminfo if l.startswith("MemTotal:")), None)
    rnd.manifest["host"] = {
        "kernel": platform.release(),
        "cpus": os.cpu_count(),
        "mem_total_kb": int(mem_total) if mem_total else None,
        "python": platform.python_version(),
        "docker": rnd.run(["docker", "version", "--format", "{{.Server.Version}}"]).stdout.strip(),
    }
    rnd.save_manifest()


def run_down(rnd: Round, out: str) -> bool:
    """`./fair5g down`: signals the detached topology, then down_v0.sh."""
    proc = rnd.run([sys.executable, str(REPO_ROOT / "fair5gctl.py"), "down"],
                   timeout=DOWN_TIMEOUT_S, out=out, cwd=REPO_ROOT)
    return proc.returncode == 0


def bring_up(rnd: Round, env: dict) -> None:
    try:
        PID_FILE.unlink()
    except FileNotFoundError:
        pass
    rnd.log("starting scripts/up_v0.sh (detached)")
    log = open(rnd.dir / "up.log", "w")
    # Own session: a Ctrl-C in the tmux pane reaches only this runner, which
    # then tears the topology down through the normal path in `finally`.
    rnd.up_proc = subprocess.Popen(
        ["bash", str(REPO_ROOT / "scripts" / "up_v0.sh")], cwd=REPO_ROOT, env=env,
        stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
        start_new_session=True,
    )
    deadline = time.monotonic() + UP_TIMEOUT_S
    while time.monotonic() < deadline:
        if PID_FILE.exists():
            rnd.log(f"topology up (pid {PID_FILE.read_text().strip()})")
            return
        if rnd.up_proc.poll() is not None:
            tail = "\n".join((rnd.dir / "up.log").read_text(errors="replace").splitlines()[-10:])
            rnd.log(f"up_v0.sh exited with {rnd.up_proc.returncode}; last lines:\n{tail}")
            raise RoundInvalid("up_failed")
        time.sleep(1)
    raise RoundInvalid("up_timeout")


def run_verify(rnd: Round, env: dict) -> None:
    venv = dict(env, FAIR5G_STRICT="1")
    venv.pop("FAIR5G_DETACH", None)
    proc = rnd.run([sys.executable, str(REPO_ROOT / "scripts" / "verify_up.py")],
                   timeout=300, out="verify.txt", env=venv, cwd=REPO_ROOT)
    ok = proc.returncode == 0
    rnd.manifest["checks"]["verify"] = {"ok": ok, "rc": proc.returncode}
    rnd.save_manifest()
    if not ok:
        raise RoundInvalid("verify_failed")


TUN_ADDR_RE = re.compile(r"^\d+:\s+(\S+)\s+inet\s+([\d.]+)/", re.M)


def check_sessions(rnd: Round) -> None:
    """Exactly one PDU session per UE, at the address a clean core assigns.

    Leftover contexts in the AMF/SMF show up as a second tunnel or as shifted
    addresses (.3 instead of .2): the round would then measure a core carrying
    state from a previous run.
    """
    per_ue, problems = {}, []
    for spec in rnd.specs:
        net = ipaddress.ip_network(spec.upf_subnet)
        # net[1] is the gateway on the UPF; a clean SMF hands out .2, .3, ...
        expected = {str(net[1 + k]) for k in range(1, len(spec.ues) + 1)}
        actual = set()
        for ue in spec.ues:
            out = rnd.run(["docker", "exec", ue.container, "ip", "-o", "-4", "addr", "show"]).stdout
            tunnels = [(i, a) for i, a in TUN_ADDR_RE.findall(out) if i.startswith("uesimtun")]
            per_ue[ue.name] = {"slice": spec.index, "tunnels": [f"{i}={a}" for i, a in tunnels]}
            if len(tunnels) != 1 or tunnels[0][0] != "uesimtun0":
                problems.append(f"{ue.name}: tunnels={tunnels}")
                continue
            addr = tunnels[0][1]
            if ipaddress.ip_address(addr) not in net:
                problems.append(f"{ue.name}: {addr} outside {spec.upf_subnet}")
            actual.add(addr)
            rnd.tunnel_ips[ue.name] = addr
        if actual != expected:
            problems.append(f"slice {spec.index}: addresses {sorted(actual)} != expected {sorted(expected)}")

    ok = not problems
    rnd.manifest["checks"]["sessions"] = {"ok": ok, "per_ue": per_ue, "problems": problems}
    rnd.save_manifest()
    if not ok:
        for p in problems:
            rnd.log(f"  session check: {p}")
        bad_count = any("tunnels=" in p for p in problems)
        raise RoundInvalid("pdu_session_count" if bad_count else "tunnel_ip_shift")


def record_images(rnd: Round) -> None:
    names = rnd.run(["docker", "ps", "--format", "{{.Names}}"]).stdout.split()
    if not names:
        return
    out = rnd.run(["docker", "inspect", "--format",
                   "{{.Name}}\t{{.Config.Image}}\t{{.Image}}"] + names,
                  out="containers.tsv").stdout
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) == 3:
            rnd.manifest["images"][parts[0].lstrip("/")] = {"image": parts[1], "id": parts[2]}
    ue = rnd.specs[0].ues[0].container
    rnd.manifest["host"]["iperf3_ue"] = rnd.run(
        ["docker", "exec", ue, "iperf3", "--version"]).stdout.splitlines()[:1]
    rnd.save_manifest()


def docker_stats(rnd: Round, out: str) -> None:
    rnd.run(["docker", "stats", "--no-stream", "--format", "{{json .}}"], timeout=60, out=out)


def restart_iperf_servers(rnd: Round, specs) -> None:
    """Fresh iperf3 servers before every batch.

    A test that dies mid-way can leave a -D server stuck in "busy", which would
    then fail every later test on that port. Restarting costs ~1 s, inside the
    gap between batches.
    """
    for spec in specs:
        upf = f"upf{spec.index}"
        rnd.run(["docker", "exec", upf, "sh", "-c", KILL_IPERF_SH])
        for k, _ue in enumerate(spec.ues):
            port = IPERF_BASE_PORT + k
            rnd.run(["docker", "exec", upf, "iperf3", "-s", "-D", "-p", str(port),
                     "--logfile", f"/tmp/iperf3_{port}.log"])
    time.sleep(1)
    for spec in specs:
        listening = rnd.run(["docker", "exec", f"upf{spec.index}", "ss", "-ltnH"]).stdout
        for k, _ue in enumerate(spec.ues):
            if f":{IPERF_BASE_PORT + k} " not in listening:
                rnd.error(f"iperf3 server not listening on upf{spec.index}:{IPERF_BASE_PORT + k}")
                raise RoundInvalid("iperf_server_failed")


def ping_cmd(rnd: Round, ue, gateway: str, seconds: int) -> list:
    count = max(1, int(round(seconds / rnd.args.ping_interval)))
    return ["docker", "exec", ue.container, "ping", "-I", "uesimtun0", "-D",
            "-i", str(rnd.args.ping_interval), "-c", str(count), "-w", str(seconds + 10),
            gateway]


def ping_record(rnd: Round, phase: str, direction, spec, ue, out: str) -> dict:
    text = (rnd.dir / out).read_text(errors="replace")
    return {"phase": phase, "kind": "ping", "direction": direction, "slice": spec.index,
            "ue": ue.name, "file": out, **summarize_ping(text)}


def run_idle(rnd: Round) -> None:
    procs, meta = [], []
    for spec in rnd.specs:
        for ue in spec.ues:
            out = f"idle_ping_{ue.name}.txt"
            procs.append(rnd.spawn(ping_cmd(rnd, ue, spec.upf_gateway, rnd.args.idle), out))
            meta.append((spec, ue, out))
    wait_all(procs, rnd.args.idle + 30)
    for spec, ue, out in meta:
        rnd.manifest["tests"].append(ping_record(rnd, "idle", None, spec, ue, out))
    rnd.save_manifest()


def run_iperf_batch(rnd: Round, phase: str, specs, direction: str, with_ping: bool) -> None:
    """Every UE of `specs` transmits at once in `direction` ("up" or "down").

    The caller restarts the iperf3 servers BEFORE opening the phase, so the
    restart does not count in the phase's pressure and steal figures.
    """
    dur = rnd.args.duration
    procs, meta = [], []
    for spec in specs:
        for k, ue in enumerate(spec.ues):
            tun = rnd.tunnel_ips[ue.name]
            out = f"{phase}_{direction}_{ue.name}.json"
            cmd = ["docker", "exec", ue.container, "iperf3", "-c", spec.upf_gateway,
                   "-p", str(IPERF_BASE_PORT + k), "-B", tun, "-t", str(dur), "-i", "1",
                   "-J", "--connect-timeout", "5000"]
            if direction == "down":
                cmd.append("-R")
            procs.append(rnd.spawn(cmd, out))
            meta.append(("iperf3", spec, ue, out))
            if with_ping:
                pout = f"{phase}_{direction}_{ue.name}_ping.txt"
                procs.append(rnd.spawn(ping_cmd(rnd, ue, spec.upf_gateway, dur), pout))
                meta.append(("ping", spec, ue, pout))
    wait_all(procs, dur + 60)

    for kind, spec, ue, out in meta:
        if kind == "ping":
            rnd.manifest["tests"].append(ping_record(rnd, phase, direction, spec, ue, out))
            continue
        test_id = f"{phase}/{direction}/{ue.name}"
        try:
            summary = summarize_iperf(json.loads((rnd.dir / out).read_text()))
        except (OSError, ValueError) as e:
            summary = {"ok": False, "error": f"unreadable iperf3 output: {e}", "stall": False}
        rnd.manifest["tests"].append({"phase": phase, "kind": "iperf3", "direction": direction,
                                      "slice": spec.index, "ue": ue.name, "file": out, **summary})
        if not summary["ok"]:
            rnd.invalidate(f"iperf_error:{test_id}")
        if summary.get("stall"):
            rnd.invalidate(f"stall:{test_id}")
        # A client killed by the timeout leaves its iperf3 running inside the UE.
        rnd.run(["docker", "exec", ue.container, "sh", "-c", KILL_IPERF_SH])
    rnd.save_manifest()


def collect(rnd: Round) -> None:
    """Snapshot of the enforcement state at the end of the round.

    Counters only mean something while the environment is up, so this runs
    before teardown, also for rounds that went invalid.
    """
    (rnd.dir / "collect").mkdir(exist_ok=True)
    c = "collect/"
    for spec in rnd.specs:
        upf = f"upf{spec.index}"
        rnd.run(["docker", "exec", upf, "iptables", "-L", "-n", "-v", "-x"], out=f"{c}m4_{upf}.txt")
        rnd.run(["docker", "exec", upf, "iptables", "-t", "nat", "-L", "-n", "-v", "-x"],
                out=f"{c}nat_{upf}.txt")
        for ue in spec.ues:
            rnd.run(["docker", "exec", ue.container, "cat", f"/tmp/{ue.name}.log"],
                    out=f"{c}nr-ue_{ue.name}.log")
    rnd.run(["ovs-ofctl", "-O", "OpenFlow13", "dump-flows", "s1"], out=f"{c}ovs_flows.txt")
    rnd.run(["ovs-ofctl", "-O", "OpenFlow13", "meter-stats", "s1"], out=f"{c}ovs_meter_stats.txt")
    rnd.run(["ovs-ofctl", "-O", "OpenFlow13", "dump-meters", "s1"], out=f"{c}ovs_meters.txt")
    rnd.run(["iptables-legacy", "-L", "FORWARD", "-n", "-v", "-x"], out=f"{c}host_forward_legacy.txt")
    for name in ["amf", "gnb"] + [f"smf{s.index}" for s in rnd.specs] + [f"upf{s.index}" for s in rnd.specs]:
        rnd.run(["docker", "logs", "--tail", "300", name], out=f"{c}log_{name}.txt")
    try:
        user = os.getenv("FAIR5G_ONOS_USER", "onos")
        password = os.getenv("FAIR5G_ONOS_PASS", "rocks")
        req = urllib.request.Request("http://localhost:8181/onos/v1/meters")
        token = base64.b64encode(f"{user}:{password}".encode()).decode()
        req.add_header("Authorization", f"Basic {token}")
        with urllib.request.urlopen(req, timeout=10) as r:
            (rnd.dir / c / "onos_meters.json").write_bytes(r.read())
    except Exception as e:
        rnd.error(f"could not read ONOS meters: {e}")


def teardown(rnd: Round) -> bool:
    proc = rnd.up_proc
    # Still bringing up (no pid file yet): stop up_v0.sh itself, or it would keep
    # creating containers while `down` removes them.
    if proc is not None and proc.poll() is None and not PID_FILE.exists():
        rnd.log("stopping up_v0.sh before it finished")
        try:
            os.killpg(proc.pid, signal.SIGTERM)
            proc.wait(timeout=TOPOLOGY_STOP_TIMEOUT_S)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait()
        except ProcessLookupError:
            pass

    rnd.log("down")
    ok = run_down(rnd, "down.log")

    if proc is not None and proc.poll() is None:
        try:
            proc.wait(timeout=60)
        except subprocess.TimeoutExpired:
            rnd.error("up_v0.sh still alive after down; killing its process group")
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            proc.wait()
    if not ok:
        rnd.error("down failed; see down.log")
    rnd.manifest["teardown"] = {"ok": ok, "up_rc": proc.returncode if proc else None}
    rnd.save_manifest()
    return ok


def restore_ownership(paths: list) -> None:
    uid, gid = os.environ.get("SUDO_UID"), os.environ.get("SUDO_GID")
    if not uid or not gid:
        return
    uid, gid = int(uid), int(gid)
    for root in paths:
        if not root.exists():
            continue
        targets = [root]
        if root.is_dir():
            targets += [Path(d) / n for d, dirs, files in os.walk(root) for n in dirs + files]
        for t in targets:
            try:
                os.chown(t, uid, gid, follow_symlinks=False)
            except OSError:
                pass


# ── main ─────────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(description="Run one round of the FAIR-5G campaign (#21).")
    p.add_argument("--campaign", required=True,
                   help="campaign name; the round goes to runs/<campaign>/rNNN/")
    p.add_argument("--slices", type=int, default=2)
    p.add_argument("--ues-per-slice", default=None, help='e.g. "1,1" or "2,1" (default: 1 per slice)')
    p.add_argument("--settle", type=int, default=PROTOCOL["settle_s"], help="seconds")
    p.add_argument("--idle", type=int, default=PROTOCOL["idle_s"], help="seconds")
    p.add_argument("--duration", type=int, default=PROTOCOL["iperf_duration_s"],
                   help="iperf3 seconds per test")
    p.add_argument("--ping-interval", type=float, default=PROTOCOL["ping_interval_s"])
    args = p.parse_args()
    if not CAMPAIGN_NAME_RE.match(args.campaign):
        # Starting with a letter also keeps campaigns apart from the
        # timestamped run ids that `./fair5g up` creates under runs/.
        p.error("--campaign must start with a letter and use only [A-Za-z0-9_.-]")
    if args.ping_interval < 0.2:
        p.error("--ping-interval below 0.2 s floods the tunnel and perturbs the measurement")
    return args


def _raise_interrupted(signum, _frame):
    raise Interrupted(f"signal {signum}")


def main() -> int:
    args = parse_args()
    try:
        specs = build_slice_specs(args.slices, args.ues_per_slice)
    except ValueError as e:
        print(f"[ERROR] {e}")
        return EXIT_ERROR
    try:
        up_env = preflight(args)
    except RunnerError as e:
        print(f"[ERROR] {e}")
        return EXIT_ERROR

    RUNS_DIR.mkdir(exist_ok=True)
    lock = open(LOCK_FILE, "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("[ERROR] another campaign round is running (runs/.campaign.lock is held)")
        return EXIT_ERROR

    for sig in (signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, _raise_interrupted)

    rnd = Round(args.campaign, args, specs)
    rnd.log(f"round dir: {rnd.dir}")
    exit_code = EXIT_ERROR
    vmstat_out = None
    try:
        record_git_and_host(rnd)
        vmstat_out = open(rnd.dir / "vmstat.txt", "w")
        rnd.vmstat_proc = subprocess.Popen(["vmstat", "-n", "-t", "1"], stdout=vmstat_out,
                                           stderr=subprocess.STDOUT)
        try:
            with rnd.phase("down_pre"):
                if not run_down(rnd, "down_pre.log"):
                    raise RunnerError("initial down failed; see down_pre.log")
            with rnd.phase("up"):
                bring_up(rnd, up_env)
            with rnd.phase("verify"):
                run_verify(rnd, up_env)
                check_sessions(rnd)
                record_images(rnd)
            with rnd.phase("settle"):
                time.sleep(args.settle)
            docker_stats(rnd, "docker_stats_idle_start.jsonl")
            with rnd.phase("idle"):
                run_idle(rnd)
            docker_stats(rnd, "docker_stats_idle_end.jsonl")
            for spec in specs:
                for direction in ("up", "down"):
                    restart_iperf_servers(rnd, [spec])
                    time.sleep(GAP_S)
                    with rnd.phase(f"per_slice_s{spec.index}_{direction}"):
                        run_iperf_batch(rnd, f"slice{spec.index}", [spec], direction,
                                        with_ping=False)
            for direction in ("up", "down"):
                restart_iperf_servers(rnd, specs)
                time.sleep(GAP_S)
                with rnd.phase(f"concurrent_{direction}"):
                    run_iperf_batch(rnd, "concurrent", specs, direction, with_ping=True)
        except RoundInvalid as e:
            rnd.invalidate(str(e))
        finally:
            # Collect whenever the environment got far enough to have counters.
            if PID_FILE.exists():
                try:
                    with rnd.phase("collect"):
                        collect(rnd)
                except Exception as e:  # noqa: BLE001 - collection is best effort
                    rnd.error(f"collect failed: {e}")
            with rnd.phase("down"):
                teardown_ok = teardown(rnd)

        valid = not rnd.manifest["validity"]["reasons"]
        rnd.manifest["validity"]["valid"] = valid
        rnd.manifest["status"] = "completed"
        exit_code = EXIT_VALID if valid else EXIT_INVALID
        if not teardown_ok:
            exit_code = EXIT_ERROR
    except (Interrupted, KeyboardInterrupt) as e:
        # The inner `finally` already tried to collect and tear down; a second
        # Ctrl-C during that teardown is the one case that leaves things up.
        rnd.invalidate("interrupted")
        rnd.manifest["status"] = "interrupted"
        torn_down = rnd.manifest["teardown"].get("ok")
        rnd.error(f"interrupted ({e or 'Ctrl-C'}); teardown "
                  f"{'completed' if torn_down else 'NOT confirmed: run ./fair5g down'}")
        exit_code = EXIT_INTERRUPTED
    except Exception as e:  # noqa: BLE001 - record any runner failure in the manifest
        rnd.invalidate("runner_error")
        rnd.manifest["status"] = "error"
        rnd.error(f"{type(e).__name__}: {e}")
        exit_code = EXIT_ERROR
    finally:
        if rnd.vmstat_proc is not None:
            rnd.vmstat_proc.terminate()
            rnd.vmstat_proc.wait()
        if vmstat_out is not None:
            vmstat_out.close()
        if rnd.manifest["validity"]["valid"] is None:
            rnd.manifest["validity"]["valid"] = False
        rnd.manifest["finished_at"] = utcnow()
        rnd.save_manifest()
        restore_ownership(GENERATED_PATHS + [RUNS_DIR / args.campaign, LOCK_FILE])
        verdict = "VALID" if rnd.manifest["validity"]["valid"] else \
            f"INVALID ({', '.join(rnd.manifest['validity']['reasons'])})"
        rnd.log(f"round finished: {verdict}; exit {exit_code}")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
