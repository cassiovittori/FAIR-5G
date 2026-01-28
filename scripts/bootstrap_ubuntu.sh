#!/usr/bin/env bash
set -euo pipefail

log() { echo -e "\n[*] $*"; }

if [[ "${EUID}" -eq 0 ]]; then
  echo "Não rode como root. Rode como usuário normal (com sudo)."
  exit 1
fi

log "Atualizando apt e instalando pacotes base..."
sudo apt-get update -y
sudo apt-get install -y \
  ca-certificates curl gnupg lsb-release \
  git make \
  python3 python3-pip \
  ansible \
  netcat-openbsd \
  iproute2 iptables \
  openvswitch-switch

# --- Docker (oficial) + Compose plugin ---
if ! command -v docker >/dev/null 2>&1; then
  log "Instalando Docker Engine + Compose plugin (repo oficial Docker)..."

  sudo install -m 0755 -d /etc/apt/keyrings

  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  sudo chmod a+r /etc/apt/keyrings/docker.gpg

  echo \
    "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
    $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
    sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

  sudo apt-get update -y
  sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
else
  log "Docker já está instalado. Pulando instalação."
fi

log "Habilitando e iniciando Docker..."
sudo systemctl enable --now docker

log "Adicionando usuário atual ao grupo docker (requer logout/login para valer)..."
sudo usermod -aG docker "$USER" || true

log "Validando versões instaladas..."
docker --version || true
docker compose version || true
ansible --version | head -n 1 || true
ovs-vsctl --version | head -n 1 || true
nc -h 2>&1 | head -n 1 || true

log "Concluído."
echo "Observação: para usar docker sem sudo, faça logout/login (ou reinicie a VM)."
