#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "[v0] Repo: $REPO_ROOT"

echo "[v0] Subindo Open5GS (docker compose)..."
cd "$REPO_ROOT/compose-files/network-slicing"
sudo docker compose up -d

cd "$REPO_ROOT"
echo "[v0] Seed subscribers (idempotente)..."
./scripts/seed_subscribers.sh

echo "[v0] Subindo SDN + UEs (Containernet + ONOS)..."
sudo python3 containernet/auto_sdn.py
