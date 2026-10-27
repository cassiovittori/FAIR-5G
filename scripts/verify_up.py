#!/usr/bin/env python3
"""Post-condition checks for a FAIR-5G bring-up.

WHY THIS EXISTS
---------------
A zero exit status only means "the commands ran". It does not mean the
environment is usable: containers can be up while a UE never obtained a PDU
session, the switch can be missing from the controller, or Prometheus can be
unreachable. Declaring success on exit status alone is how a measurement
campaign ends up collecting data from a half-built environment without anyone
noticing.

These checks turn "[ok]" from an assumption into a verified statement.

STRICTNESS
----------
Strict mode (FAIR5G_STRICT=1, set automatically for scripted runs) exits
non-zero when any check fails: automation must not proceed against a broken
environment. Interactive runs only warn, because a partially built environment
is sometimes exactly what one wants to inspect while debugging.
"""

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from fair5gctl.core.slicing import build_slice_specs  # noqa: E402

# ── buffered report ──────────────────────────────────────────────────────────
# Mininet's CLI leaves the terminal in raw mode: '\n' no longer returns to
# column 0, so output comes out in a staircase and interleaves with the prompt.
# Everything printed here is accumulated and flushed as one block with '\r\n'
# at the end of the run. A single atomic write cannot interleave, and the '\r'
# brings the cursor back to column 0 whatever mode the terminal is in.
import atexit as _atexit
import builtins as _builtins
import io as _io

_print_original = _builtins.print
_report = _io.StringIO()
_WIDTH = 64
_REPORT_FILE = "/tmp/fair5g_verify.txt"


def print(*args, **kwargs):  # noqa: A001 - shadows the module's print on purpose
    kwargs["file"] = _report
    kwargs.pop("flush", None)
    _print_original(*args, **kwargs)


def _flush_report():
    body = _report.getvalue().splitlines()
    if not body:
        return
    border = "=" * _WIDTH
    lines = ["", border, "  ENVIRONMENT POST-CONDITION CHECKS", border]
    lines += body
    lines += [border, ""]
    try:
        with open(_REPORT_FILE, "w") as fh:
            fh.write("\n".join(lines) + "\n")
    except OSError:
        pass
    _print_original("\r\n".join(lines) + "\r\n", end="", flush=True)


_atexit.register(_flush_report)
# ─────────────────────────────────────────────────────────────────────────────

ONOS_URL = "http://localhost:8181/onos/v1"
ONOS_AUTH = ("onos", "rocks")
PROM_URL = "http://localhost:9090"

CORE_CONTAINERS = ["nrf", "amf", "ausf", "udm", "udr", "pcf", "bsf", "nssf",
                   "db", "gnb", "prometheus", "grafana", "blackbox"]


def _sh(cmd: str) -> str:
    return subprocess.run(cmd, shell=True, capture_output=True,
                          text=True).stdout


def _running_containers() -> set:
    return set(_sh("sudo docker ps --format '{{.Names}}'").split())


def check_containers(specs) -> tuple:
    """Every expected container must be running.

    Missing core functions break registration; a missing UPF or SMF breaks one
    slice specifically, which would silently turn a two-slice experiment into a
    one-slice one.
    """
    running = _running_containers()
    expected = list(CORE_CONTAINERS)
    for spec in specs:
        expected += [f"smf{spec.index}", f"upf{spec.index}"]
        expected += [ue.container for ue in spec.ues]

    missing = [c for c in expected if c not in running]
    if missing:
        return False, f"missing containers: {', '.join(missing)}"
    return True, f"{len(expected)} expected containers running"


PDU_TIMEOUT_S = int(os.getenv("FAIR5G_PDU_TIMEOUT", "90"))


def check_pdu_sessions(specs, timeout_s: int = None) -> tuple:
    """Each UE must hold an address on its tunnel interface.

    This is the real test of whether the UE registered and established a PDU
    session. A running container proves nothing: nr-ue can be up and still have
    failed to attach.

    Registration is asynchronous: it takes seconds after nr-ue starts, and more
    with several UEs, which attach one after another. A single snapshot taken
    right after bring-up reports failure for a UE that is merely still
    attaching — a false negative that makes the whole report untrustworthy.
    So this polls until every UE holds a tunnel address, and returns as soon as
    the last one comes up rather than waiting out the timeout.
    """
    if timeout_s is None:
        timeout_s = PDU_TIMEOUT_S

    pending = [ue for spec in specs for ue in spec.ues]
    deadline = time.time() + timeout_s
    while True:
        still_pending = [
            ue for ue in pending
            if "inet " not in _sh(
                f"sudo docker exec {ue.container} "
                f"ip addr show uesimtun0 2>/dev/null"
            )
        ]
        pending = still_pending
        if not pending or time.time() >= deadline:
            break
        time.sleep(2)

    if pending:
        names = ", ".join(ue.name for ue in pending)
        return False, f"UEs without a PDU session after {timeout_s}s: {names}"
    total = sum(len(s.ues) for s in specs)
    return True, f"{total} UE(s) with an active PDU session"


def check_onos_switch() -> tuple:
    """The switch must be present AND available in the controller.

    A switch that is registered but unavailable means flows and meters were
    never installed, so both QoS enforcement and isolation would be absent
    while the log claimed otherwise.
    """
    try:
        data = _onos_get("/devices")
    except Exception as e:
        return False, f"ONOS unreachable: {e}"

    devices = data.get("devices", [])
    if not devices:
        return False, "no switch registered in ONOS"
    unavailable = [d.get("id") for d in devices if not d.get("available")]
    if unavailable:
        return False, f"switch unavailable in ONOS: {unavailable}"
    return True, f"{len(devices)} switch(es) available in ONOS"


def check_meters(specs) -> tuple:
    """One distinct meter per slice.

    Fewer meters than slices means slices are sharing an aggregate limit — the
    collision bug fixed earlier. Worth checking on every bring-up so a
    regression shows up immediately instead of skewing an experiment.
    """
    try:
        data = _onos_get("/meters")
    except Exception as e:
        return False, f"could not query meters: {e}"

    ids = {m.get("id") for m in data.get("meters", [])}
    if len(ids) < len(specs):
        return False, (f"{len(ids)} distinct meter(s) for {len(specs)} "
                       f"slice(s): slices are sharing a limit")
    return True, f"{len(ids)} distinct meter(s) installed"


def check_prometheus() -> tuple:
    """Prometheus must respond and its targets must be up.

    Without this the dashboards and the per-run reports come back empty, and the
    resource metrics that serve as control variables would be missing exactly
    when they matter.
    """
    try:
        with urllib.request.urlopen(f"{PROM_URL}/api/v1/targets", timeout=5) as r:
            data = json.loads(r.read())
    except Exception as e:
        return False, f"Prometheus unreachable: {e}"

    targets = data.get("data", {}).get("activeTargets", [])
    if not targets:
        return False, "Prometheus has no active targets"
    down = [f"{t['labels'].get('job')}/{t['labels'].get('instance')}"
            for t in targets if t.get("health") != "up"]
    if down:
        return False, f"targets down: {', '.join(down)}"
    return True, f"{len(targets)} Prometheus target(s) up"


def _onos_get(path: str) -> dict:
    import base64
    req = urllib.request.Request(f"{ONOS_URL}{path}")
    token = base64.b64encode(f"{ONOS_AUTH[0]}:{ONOS_AUTH[1]}".encode()).decode()
    req.add_header("Authorization", f"Basic {token}")
    with urllib.request.urlopen(req, timeout=8) as r:
        return json.loads(r.read())


def main() -> int:
    strict = os.getenv("FAIR5G_STRICT") == "1"
    count = int(os.getenv("FAIR5G_SLICE_COUNT", "2"))
    ues = os.getenv("FAIR5G_UES_PER_SLICE") or None
    specs = build_slice_specs(count, ues)

    checks = [
        ("containers", lambda: check_containers(specs)),
        ("PDU sessions", lambda: check_pdu_sessions(specs)),
        ("switch in ONOS", check_onos_switch),
        ("meters per slice", lambda: check_meters(specs)),
        ("Prometheus", check_prometheus),
    ]

    print("\n[verify] Checking environment post-conditions...")
    failures = []
    for name, fn in checks:
        try:
            ok, detail = fn()
        except Exception as e:
            ok, detail = False, f"check raised an error: {e}"
        mark = "OK  " if ok else "FAIL"
        print(f"  [{mark}] {name}: {detail}")
        if not ok:
            failures.append(f"{name}: {detail}")

    if not failures:
        print("[verify] environment validated.\n")
        return 0

    print(f"\n[verify] {len(failures)} check(s) failed.")
    if strict:
        print("[verify] strict mode: the environment is NOT fit for measurement.")
        print("         Run './fair5g down' before trying again.\n")
        return 1
    print("[verify] tolerant mode: continuing, but data collected now\n"
          "         is not trustworthy for analysis.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
