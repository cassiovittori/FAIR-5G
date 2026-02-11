#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "[ERRO] '$1' não encontrado."
    echo "Rode primeiro: ./scripts/bootstrap_ubuntu.sh"
    exit 1
  }
}

preclean() {
  echo "[v0] Pre-clean: removendo resíduos do Containernet (mn.*), veth e iptables..."

  # remove containers criados por rodadas anteriores do containernet
  sudo docker rm -f $(sudo docker ps -aq --filter 'name=^mn\.') 2>/dev/null || true

  # remove veth caso tenha ficado
  sudo ip link delete veth-sdn 2>/dev/null || true

  # remove TODAS as ocorrências da regra ACCEPT no DOCKER-USER (evita duplicatas)
  while sudo iptables -D DOCKER-USER -j ACCEPT 2>/dev/null; do :; done
}

need_cmd docker
sudo docker compose version >/dev/null 2>&1 || {
  echo "[ERRO] Docker Compose plugin não encontrado."
  echo "Rode primeiro: ./scripts/bootstrap_ubuntu.sh"
  exit 1
}

echo "[v0] Repo: $REPO_ROOT"

preclean

echo "[v0] Subindo Open5GS (docker compose)..."
cd "$REPO_ROOT"

echo "[v0] Subindo Open5GS via compose file..."
sudo docker compose -f compose-files/network-slicing/docker-compose.yaml --env-file .env up -d --build --remove-orphans

echo "[v0] Seed subscribers (idempotente)..."
./scripts/seed_subscribers.sh

# Render runtime UE configs (atualiza gnbSearchList com IP real do container gnb)
if [[ -f "$REPO_ROOT/scripts/render_ue_configs.sh" ]]; then
  echo "[v0] Renderizando configs runtime do UE (gnbSearchList)..."
  ./scripts/render_ue_configs.sh
  export FAIR5G_CONFIG_DIR="$REPO_ROOT/configs/runtime"
else
  echo "[v0] scripts/render_ue_configs.sh não encontrado; usando configs/network-slicing direto."
  export FAIR5G_CONFIG_DIR="$REPO_ROOT/configs/network-slicing"
fi

echo "[v0] Subindo SDN + UEs (Containernet + ONOS)..."
sudo FAIR5G_CONFIG_DIR="$FAIR5G_CONFIG_DIR" \
  PYTHONPATH="$REPO_ROOT/containernet" \
  python3 "$REPO_ROOT/containernet/auto_sdn.py"

