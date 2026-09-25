#!/usr/bin/env bash
# Collects, in one pass, everything needed to diagnose the stall of a slice's
# data plane (traffic stops after ~15-30 s and never comes back).
#
# Run this on the HOST terminal, with the environment UP, RIGHT AFTER the flow
# stalls — several of the signals are volatile and disappear on `down`.
#
# Usage:  sudo bash scripts/experiments/diag_stall.sh 2
#         (the argument is the slice index; default 1)
#
# The report is written to runs/diag_stall_<timestamp>.txt

set -u
SLICE="${1:-1}"
UE="mn.ue${SLICE}"
UPF="upf${SLICE}"
SMF="smf${SLICE}"
UE_IP="10.34.0.$((199 + SLICE))"
TUNNEL_GW="10.$((44 + SLICE)).0.1"
GNB_IP="10.34.0.3"

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
OUT="$ROOT/runs/diag_stall_$(date +%Y-%m-%d_%H%M%S).txt"
mkdir -p "$(dirname "$OUT")"

# Bail out early if the topology is gone: without it half the report is just
# "No such container" and the run is wasted.
if ! ovs-vsctl br-exists s1 2>/dev/null || ! docker ps --format '{{.Names}}' | grep -q "^${UE}$"; then
  echo "[ERROR] switch s1 or container ${UE} not found."
  echo "        The environment must still be UP. Nothing was collected."
  exit 1
fi

section() { printf '\n===== %s =====\n' "$1" >> "$OUT"; }
capture() { echo "\$ $*" >> "$OUT"; eval "$@" >> "$OUT" 2>&1; }

{
  echo "Stall diagnostics — slice $SLICE"
  echo "date: $(date -Iseconds)"
  echo "UE=$UE  UPF=$UPF  SMF=$SMF  ue_ip=$UE_IP  tunnel_gw=$TUNNEL_GW"
} > "$OUT"

# 1) Is traffic still leaving the UE? Two samples with traffic in between reveal
#    whether the counters are frozen — a single snapshot says nothing.
section "flows: sample 1"
capture "ovs-ofctl -O OpenFlow13 dump-flows s1 | grep $UE_IP"
section "generating traffic for 5s (ping through the tunnel, expected to fail)"
capture "docker exec $UE ping -c 5 -W 1 $TUNNEL_GW"
section "flows: sample 2 (compare n_packets against sample 1)"
capture "ovs-ofctl -O OpenFlow13 dump-flows s1 | grep $UE_IP"

# 2) UE state
section "UE: tunnel interface"
capture "docker exec $UE ip -br addr show uesimtun0"
section "UE: route to the tunnel"
capture "docker exec $UE ip route get $TUNNEL_GW"
section "UE: access network reachability (outside the tunnel — should work)"
capture "docker exec $UE ping -c 3 -W 1 $GNB_IP"
section "UE: nr-ue log"
capture "docker exec $UE sh -c 'tail -60 /tmp/*.log'"

# 3) Core — where the packet most likely dies
section "UPF: isolation rule counters (M4)"
# A DROP rule with a high counter makes the in-UPF isolation the culprit.
capture "docker exec $UPF iptables -L -n -v"
section "UPF: NAT (masquerade)"
capture "docker exec $UPF iptables -t nat -L -n -v"
section "UPF: interfaces and drops"
capture "docker exec $UPF ip -s link"
section "UPF: log"
capture "docker logs --tail 60 $UPF"
section "SMF: log (look for session release / PFCP)"
capture "docker logs --tail 60 $SMF"
section "AMF: log"
capture "docker logs --tail 40 amf"
section "gNB: log (look for 'Discarding RRC Setup Request' and 'signal lost')"
capture "docker logs --tail 40 gnb"

echo
echo "[ok] report at: $OUT"
echo
echo "Quick reading:"
echo "  - n_packets UNCHANGED between samples -> the UE stopped transmitting"
echo "  - n_packets GREW                      -> the UE transmits, the packet dies downstream"
echo "  - UPF DROP rule with a high counter   -> M4 isolation is the culprit"
echo "  - 'session release' in the SMF        -> the core tore the session down"
echo "  - 'Discarding RRC Setup Request'      -> the UE lost the radio link and could not re-attach"
