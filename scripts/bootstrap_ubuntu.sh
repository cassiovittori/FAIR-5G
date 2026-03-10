#!/usr/bin/env bash
set -euo pipefail

log() { echo -e "\n[*] $*"; }

if [[ "${EUID}" -eq 0 ]]; then
  echo "Não rode como root. Rode como usuário normal (com sudo)."
  exit 1
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
log "Repo root detectado: $REPO_ROOT"

# --- sanity check: DNS / internet ---
log "Checando conectividade (DNS)..."
if ! getent hosts google.com >/dev/null 2>&1; then
  echo "[!] DNS parece quebrado (google.com não resolve)."
  echo "    Verifique VMware NAT / DNS da VM. Exemplo de fix rápido:"
  echo "    sudo resolvectl dns ens33 8.8.8.8 1.1.1.1 && sudo resolvectl flush-caches"
  echo "    (rode o comando acima e execute o bootstrap novamente)"
  exit 1
fi

log "Aguardando lock do apt (unattended-upgrades)..."
while sudo fuser /var/lib/dpkg/lock-frontend >/dev/null 2>&1; do
  echo "[*] apt/dpkg em uso... aguardando 10s"
  sleep 10
done

log "Atualizando apt e instalando pacotes base..."
sudo apt-get update -y

sudo apt-get install -y \
  ca-certificates curl gnupg lsb-release \
  git make \
  python3 python3-pip \
  ansible \
  netcat-openbsd \
  iproute2 iptables \
  openvswitch-switch \
  python3-docker python3-iptables

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

# --- Mininet/Containernet deps  ---
log "Instalando dependências extras (Mininet/Containernet)..."
sudo apt-get install -y \
  python3-setuptools python3-networkx python3-six \
  iputils-ping net-tools tcpdump \
  openvswitch-testcontroller || true

# (Opcional) Instalar Mininet do repositório (se quiser garantir o 'mn')
if ! command -v mn >/dev/null 2>&1; then
  log "Mininet não encontrado; instalando pacote 'mininet'..."
  sudo apt-get install -y mininet || true
else
  log "Mininet (mn) já está disponível. Pulando."
fi

# Instalar dependências do Containernet via playbook local do repo (recomendado)
if [[ -f "$REPO_ROOT/containernet/ansible/install.yml" ]]; then
  log "Instalando dependências do Containernet (playbook local)..."
  sudo ansible-playbook -i "localhost," -c local "$REPO_ROOT/containernet/ansible/install.yml"
else
  log "Playbook $REPO_ROOT/containernet/ansible/install.yml não encontrado. Pulando."
fi

# --- Dependências Python do FAIR-5G (metrics.py) ---
log "Instalando dependências Python do FAIR-5G..."
PIP_PACKAGES="rich pyfiglet requests questionary"

if pip3 install --help 2>&1 | grep -q 'break-system-packages'; then
  pip3 install $PIP_PACKAGES --break-system-packages
else
  pip3 install $PIP_PACKAGES --user
fi
log "Validando dependências Python..."
python3 -c "import rich, pyfiglet, requests, questionary; print('Python FAIR-5G deps OK')" || \
  echo "[!] Alguma dependência Python não foi instalada corretamente."

log "Validando versões instaladas..."
sudo docker --version || true
sudo docker compose version || true
ansible --version | head -n 1 || true
ovs-vsctl --version | head -n 1 || true
python3 -c "import docker, iptc; print('python deps OK')" || true

log "Concluído."
echo "Observação: para usar docker sem sudo, faça logout/login (ou reinicie a VM)."

