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

# Refuse to start on top of a running environment. `compose up -d` reuses
# running core containers, so the AMF/SMF keep the previous run's UE contexts
# and PDU sessions: the new UEs get shifted addresses and the run is not clean.
# It must run BEFORE preclean, which would remove the mn.* containers of the
# running topology. onos-controller is left out on purpose: down keeps it when
# FAIR5G_KEEP_ONOS=1, and a reused ONOS holds no UE state.
refuse_if_running() {
  local running
  running="$(sudo docker ps --format '{{.Names}}' \
    | grep -E '^(amf|nrf|gnb|mn\..+)$' || true)"
  if [[ -n "$running" ]]; then
    echo "[ERROR] The environment is already running. Containers found:"
    echo "$running" | sed 's/^/          /'
    echo "        Run './fair5g down' first. Nothing was changed."
    exit 1
  fi
}

need_cmd docker
sudo docker compose version >/dev/null 2>&1 || {
  echo "[ERRO] Docker Compose plugin não encontrado."
  echo "Rode primeiro: ./scripts/bootstrap_ubuntu.sh"
  exit 1
}

if [[ ! -f "$REPO_ROOT/.env" ]]; then
  echo "[v0] .env não encontrado — copiando de .env.example"
  cp "$REPO_ROOT/.env.example" "$REPO_ROOT/.env"
fi

if [[ ! -f "$REPO_ROOT/containernet/mininet/net.py" ]]; then
  echo "[v0] Submodule containernet/ não inicializado — rodando git submodule update --init"
  git -C "$REPO_ROOT" submodule update --init
fi

echo "[v0] Repo: $REPO_ROOT"

export FAIR5G_SLICE_COUNT="${FAIR5G_SLICE_COUNT:-2}"
echo "[v0] Quantidade de fatias: $FAIR5G_SLICE_COUNT"

refuse_if_running
preclean

cd "$REPO_ROOT"

echo "[v0] Renderizando configs das $FAIR5G_SLICE_COUNT fatia(s)..."
python3 "$REPO_ROOT/scripts/render_slice_configs.py" --slices "$FAIR5G_SLICE_COUNT"

echo "[v0] Subindo Open5GS via compose file..."
sudo docker compose \
  -f compose-files/network-slicing/docker-compose.yaml \
  -f compose-files/network-slicing/docker-compose.slices.generated.yaml \
  --env-file .env up -d --build --remove-orphans

echo "[v0] Seed subscribers (idempotente)..."
SEED_FILE="$REPO_ROOT/open5gs/seed/subscribers.generated.js" ./scripts/seed_subscribers.sh

# Render runtime UE configs (atualiza gnbSearchList com IP real do container gnb)
if [[ -f "$REPO_ROOT/scripts/render_ue_configs.sh" ]]; then
  echo "[v0] Renderizando configs runtime do UE (gnbSearchList)..."
  ./scripts/render_ue_configs.sh
else
  echo "[ERRO] scripts/render_ue_configs.sh não encontrado."
  exit 1
fi
export FAIR5G_CONFIG_DIR="$REPO_ROOT/configs/runtime"


echo "[v0] Subindo SDN + UEs (Containernet + ONOS)..."
# sudo drops the caller's environment: every variable auto_sdn.py reads must be
# passed explicitly here, or it silently falls back to its default.
sudo FAIR5G_CONFIG_DIR="$FAIR5G_CONFIG_DIR" \
  FAIR5G_SLICE_COUNT="$FAIR5G_SLICE_COUNT" \
  FAIR5G_UES_PER_SLICE="${FAIR5G_UES_PER_SLICE:-}" \
  PYTHONPATH="$REPO_ROOT/containernet" \
  python3 "$REPO_ROOT/sdn/auto_sdn.py"
