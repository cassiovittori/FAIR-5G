#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "[v0] Limpando Mininet/Containernet..."
cd "$REPO_ROOT"
sudo python3 - <<'PY'
import sys
sys.path.insert(0, "./containernet")
from mininet.clean import cleanup
cleanup()
print("cleanup OK")
PY

echo "[v0] Derrubando Open5GS (docker compose)..."
cd "$REPO_ROOT/compose-files/network-slicing"
sudo docker compose down
