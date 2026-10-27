#!/usr/bin/env python3
"""Install/remove flows that divert a slice's traffic away from the meters.

This serves the "environment ceiling" control experiment: measuring the maximum
throughput a slice reaches when NO QoS limit is applied, so that what is a
configured limit can be told apart from what is an environment limit.

HOW THE BYPASS FLOWS ARE BUILT
------------------------------
The selector is not guessed. The script READS the flow table from ONOS, finds
the production flows carrying a METER instruction for the target slice, and
CLONES each of them at priority 600 with only the METER removed. The clone's
selector is byte for byte the original's, so the bypass matches exactly what the
metered flow matched — no more, no less.

An earlier version of this script built the selector by hand from the tunnel IP
(10.45.0.2). That address never appears on the switch: uesimtun0 traffic goes up
encapsulated in GTP-U between the UE's access address (10.34.0.x) and the gNB.
The production flows match `ue_mininet_ip`, not the tunnel address. The result
was a bypass that matched nothing, a measurement that was still metered, and a
number that meant nothing.

BOTH DIRECTIONS. An iperf3 TCP run crosses the switch both ways: data goes up
(UE -> core) and ACKs come down (core -> UE). The downlink flow also carries a
METER. Cloning the uplink alone leaves the ACKs metered and the test stays
limited — that was the mistake in the first attempt at this experiment. Because
the script clones EVERY metered flow of the slice, both directions come along.

Usage (from the repository root, with the environment up):

    sudo python3 scripts/experiments/bypass_meters.py flows    # what carries traffic now
    sudo python3 scripts/experiments/bypass_meters.py status   # meter counters
    sudo python3 scripts/experiments/bypass_meters.py on
    ... run iperf3 ...
    sudo python3 scripts/experiments/bypass_meters.py status   # meters must be idle
    sudo python3 scripts/experiments/bypass_meters.py off
"""
import argparse
import base64
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

PRIORITY = 600  # above the production flows (100/150/200/300)

USER = os.getenv("FAIR5G_ONOS_USER", "onos")
PASSWORD = os.getenv("FAIR5G_ONOS_PASS", "rocks")
SWITCH = os.getenv("FAIR5G_SWITCH", "s1")


def onos(method, path, payload=None):
    url = f"http://localhost:8181{path}"
    creds = base64.b64encode(f"{USER}:{PASSWORD}".encode()).decode()
    headers = {"Authorization": f"Basic {creds}"}
    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            body = r.read()
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        print(f"[ERROR] ONOS {method} {path}: HTTP {e.code} — {e.read().decode()[:200]}")
        return None
    except urllib.error.URLError as e:
        print(f"[ERROR] ONOS {method} {path}: {e.reason}")
        return None


def ovs(command):
    """Read straight from the switch. ONOS's view can diverge from the switch's,
    and the switch is what actually enforces."""
    try:
        r = subprocess.run(f"ovs-ofctl -O OpenFlow13 {command} {SWITCH}",
                           shell=True, capture_output=True, text=True, timeout=15)
        return r.stdout
    except Exception as e:
        return f"[ERROR] ovs-ofctl: {e}"


def get_dpid():
    data = onos("GET", "/onos/v1/devices") or {}
    for d in data.get("devices", []):
        if d.get("available"):
            return d["id"]
    print("[ERROR] no switch available in ONOS. Is the environment up?")
    sys.exit(1)


def meter_of(flow):
    for i in flow.get("treatment", {}).get("instructions", []):
        if i.get("type") == "METER":
            return str(i.get("meterId"))
    return None


def selector_summary(flow):
    parts = []
    for c in flow.get("selector", {}).get("criteria", []):
        if c.get("type") in ("IPV4_SRC", "IPV4_DST"):
            parts.append(f"{c['type'].split('_')[1].lower()}={c.get('ip')}")
    out = [i.get("port") for i in flow.get("treatment", {}).get("instructions", [])
           if i.get("type") == "OUTPUT"]
    return f"{' '.join(parts) or '(no IP match)'} -> port {out or '?'}"


def slice_flows(dpid, meter_id):
    """Production flows that apply the target slice's meter."""
    data = onos("GET", f"/onos/v1/flows/{dpid}") or {}
    return [f for f in data.get("flows", [])
            if meter_of(f) == str(meter_id) and f.get("priority") != PRIORITY]


def show_meters(dpid):
    data = onos("GET", f"/onos/v1/meters/{dpid}") or {}
    meters = data.get("meters", [])
    if not meters:
        print("  (ONOS lists no meters)")
    for m in meters:
        for b in m.get("bands", []):
            print(f"  [onos]  meter id={m.get('id')} rate={b.get('rate')} kbps  "
                  f"drops: packets={b.get('packets')} bytes={b.get('bytes')}")
    # ONOS usually returns the band counters at zero even while the meter is
    # dropping packets. The numbers that count are the switch's.
    out = ovs("meter-stats")
    print("  [switch] ovs-ofctl meter-stats:")
    for line in (out or "").splitlines():
        if line.strip():
            print(f"    {line.rstrip()}")


def show_flows():
    print(f"Flows on switch {SWITCH} with counters (n_packets shows who carries traffic):")
    for line in (ovs("dump-flows") or "").splitlines():
        if "n_packets=0," in line or not line.strip():
            continue
        print(f"  {line.strip()}")
    print("\n(flows with n_packets=0 were omitted)")


def turn_on(dpid, meter_id):
    originals = slice_flows(dpid, meter_id)
    if not originals:
        print(f"[ERROR] no production flow uses meter {meter_id}.")
        print("        Check the id with 'status' and pass --meter-id.")
        sys.exit(1)

    print(f"Cloning {len(originals)} flow(s) of meter {meter_id} without the METER instruction:")
    installed = 0
    for f in originals:
        instructions = [i for i in f.get("treatment", {}).get("instructions", [])
                        if i.get("type") != "METER"]
        clone = {
            "priority": PRIORITY,
            "isPermanent": True,
            "selector": f.get("selector", {}),
            "treatment": {"instructions": instructions},
        }
        if onos("POST", f"/onos/v1/flows/{dpid}", payload=clone) is None:
            print(f"  [ERROR] failed: {selector_summary(f)}")
            print("          run 'off' before trying again.")
            sys.exit(1)
        print(f"  [ok] {selector_summary(f)}")
        installed += 1

    print(f"\n{installed} bypass flow(s) active at priority {PRIORITY}.")
    print("Run iperf3, then 'status': the meter drops must not grow.")


def turn_off(dpid):
    # The bypass is identified by SHAPE, not by appId: priority 600 and a
    # treatment with no METER. Production flows use 100/150/200/300, so there is
    # no way to confuse them.
    data = onos("GET", f"/onos/v1/flows/{dpid}") or {}
    removed = 0
    for f in data.get("flows", []):
        if f.get("priority") != PRIORITY or meter_of(f) is not None:
            continue
        if onos("DELETE", f"/onos/v1/flows/{dpid}/{f['id']}") is not None:
            removed += 1
    print(f"[ok] {removed} bypass flow(s) removed. The meters apply again.")
    if removed == 0:
        print("     (none found — they may already have been removed)")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("action", choices=["on", "off", "status", "flows"])
    ap.add_argument("--meter-id", default="1",
                    help="meter of the slice to bypass (default: 1, slice 1)")
    args = ap.parse_args()

    if args.action == "flows":
        show_flows()
        return

    dpid = get_dpid()
    if args.action == "status":
        print(f"Meters on {dpid}:")
        show_meters(dpid)
    elif args.action == "on":
        turn_on(dpid, args.meter_id)
    else:
        turn_off(dpid)


if __name__ == "__main__":
    main()
