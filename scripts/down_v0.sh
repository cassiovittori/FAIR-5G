#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "[v0] Limpando Containernet/Mininet + resíduos Docker..."

# remove containers do containernet (responde pelo erro 409 /mn.ue1 já existe)
sudo docker rm -f $(sudo docker ps -aq --filter 'name=^mn\.') 2>/dev/null || true

# cleanup do mininet
cd "$REPO_ROOT"
sudo python3 - <<'PY'
import sys
sys.path.insert(0, "./containernet")
from mininet.clean import cleanup
cleanup()
print("cleanup OK")
PY

# remove veth e regras duplicadas
sudo ip link delete veth-sdn 2>/dev/null || true
while sudo iptables -D DOCKER-USER -j ACCEPT 2>/dev/null; do :; done

echo "[v0] Derrubando Open5GS (docker compose)..."
cd "$REPO_ROOT/compose-files/network-slicing"

compose_files=(-f docker-compose.yaml)
if [[ -f docker-compose.slices.generated.yaml ]]; then
  compose_files+=(-f docker-compose.slices.generated.yaml)
fi

if [[ "${FAIR5G_WIPE:-0}" == "1" ]]; then
  echo "[v0] FAIR5G_WIPE=1: removendo volumes também (-v)."
  sudo docker compose "${compose_files[@]}" down -v --remove-orphans
else
  sudo docker compose "${compose_files[@]}" down --remove-orphans
fi

# ONOS: por padrão, remove para ficar determinístico; se quiser manter, set FAIR5G_KEEP_ONOS=1
if [[ "${FAIR5G_KEEP_ONOS:-0}" != "1" ]]; then
  echo "[v0] Removendo ONOS (onos-controller)..."
  sudo docker rm -f onos-controller 2>/dev/null || true
else
  echo "[v0] Mantendo ONOS (FAIR5G_KEEP_ONOS=1)."
fi

echo "[v0] Down concluído."

