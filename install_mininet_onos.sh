#!/usr/bin/env bash
# Script para instalar Mininet e ONOS em Ubuntu 22.04 (Jammy)
# Uso: sudo ./install_mininet_onos.sh

set -e

### Funções auxiliares #########################################

log() {
    echo -e "\n[INFO] $*\n"
}

err() {
    echo -e "\n[ERRO] $*\n" >&2
}

### Checagens iniciais ##########################################

if [ "$EUID" -ne 0 ]; then
  err "Por favor, execute o script como root: sudo $0"
  exit 1
fi

# Verifica se é Jammy (não para se não for, só avisa)
if grep -q "VERSION_CODENAME=jammy" /etc/os-release 2>/dev/null; then
  log "Ubuntu Jammy detectado. 👍"
else
  log "Aviso: este script foi pensado para Ubuntu 22.04 (Jammy)."
fi

export DEBIAN_FRONTEND=noninteractive

### Atualiza sistema ############################################

log "Atualizando listas de pacotes..."
apt update -y

log "Instalando pacotes básicos..."
apt install -y \
    git curl wget vim \
    python3 python3-pip \
    net-tools iproute2

### Instala Mininet #############################################

log "Instalando Mininet e Open vSwitch (via apt)..."
# mininet puxa boa parte das dependências automaticamente em 22.04
apt install -y mininet openvswitch-switch

# Garante que o serviço do OVS está ativo
systemctl enable --now openvswitch-switch || true

# Em algumas distros existe um serviço antigo openvswitch-controller
if systemctl list-unit-files | grep -q openvswitch-controller; then
  log "Desabilitando openvswitch-controller herdado (para usar ONOS como controlador)..."
  systemctl disable --now openvswitch-controller || true
fi

### Instala Docker ##############################################

log "Instalando Docker (docker.io)..."
apt install -y docker.io

log "Habilitando Docker no boot..."
systemctl enable --now docker

log "Adicionando o usuário atual ao grupo docker (se existir login interativo)..."
if id -u "$SUDO_USER" >/dev/null 2>&1; then
  usermod -aG docker "$SUDO_USER"
  DOCKER_USER="$SUDO_USER"
else
  DOCKER_USER="root"
fi

### Instala ONOS via Docker #####################################

log "Baixando imagem do ONOS (onosproject/onos)..."
docker pull onosproject/onos

# Porta padrão:
# 8181 -> GUI / REST
# 8101 -> CLI
# 6653 -> OpenFlow
# 6633 -> porta legada de OF em alguns exemplos
log "Criando/atualizando container do ONOS..."

EXISTS=$(docker ps -a --format '{{.Names}}' | grep -w onos || true)

if [ -z "$EXISTS" ]; then
  # Container novo
  docker run -d \
    --name onos \
    -p 8181:8181 \
    -p 8101:8101 \
    -p 6653:6653 \
    -p 6633:6633 \
    onosproject/onos
else
  # Se já existir, apenas garante que está rodando
  docker start onos || true
fi

log "Configurando container do ONOS para reiniciar automaticamente..."
docker update --restart unless-stopped onos >/dev/null

### Resumo / Testes rápidos #####################################

log "Instalação concluída!"

echo "----------------------------------------------------------"
echo "MININET:"
echo "  - Teste rápido: sudo mn --test pingall"
echo
echo "ONOS:"
echo "  - Verificar se está rodando: docker ps | grep onos"
echo "  - GUI: http://<IP_DA_MAQUINA>:8181/onos/ui"
echo "    Usuário: onos"
echo "    Senha  : rocks"
echo
echo "INTEGRAÇÃO BÁSICA ONOS + MININET:"
echo "  Exemplo de topologia simples:"
echo "    sudo mn --topo single,2 \\"
echo "           --controller=remote,ip=127.0.0.1,port=6653 \\"
echo "           --switch ovs,protocols=OpenFlow13"
echo
echo "Lembre-se de deslogar e logar de novo para o grupo 'docker'"
echo "ter efeito para o usuário $DOCKER_USER."
echo "----------------------------------------------------------"
