# Configuração Manual vs. Automatizada — FAIR-5G Testbed

Este documento apoia dois pontos de avaliação do artigo:
- **Redução do esforço de configuração** — contagem de comandos manuais vs. automatizados
- **Comparação do tempo de implantação** — estimativas baseadas nas documentações oficiais de cada componente

---

## Lado Automatizado (este repositório)

```bash
git clone <repo-url> open5gs-mininet
cd open5gs-mininet
./fair5g   # selecionar "bootstrap" no menu interativo
./fair5g   # selecionar "up" no menu interativo
```

| Métrica | Valor |
|---|---|
| Comandos necessários | **4** |
| Tempo estimado | **~15 min** (dominado pelo pull das imagens Docker na primeira execução) |
| Configuração de rede/flows | Automática via `auto_sdn.py` |
| Perfis de assinante (MongoDB) | Seeding automático via `open5gs/seed/subscribers.js` |
| Repetibilidade | Idempotente — `./fair5g` → "up" restaura o estado completo a qualquer momento |

> Na segunda execução em diante (imagens já em cache), o tempo cai para **~3–5 min**.

---

## Lado Manual — Instalação Componente a Componente

Fonte de cada seção: documentação oficial do projeto (Getting Started / Quickstart).
Sistema-alvo: **Ubuntu 22.04 LTS (AMD64)**.

---

### 1. Open5GS (Core 5G SA)

**Fonte:** https://open5gs.org/open5gs/docs/guide/01-quickstart/

```bash
# MongoDB 8.0
sudo apt update
sudo apt install gnupg
curl -fsSL https://pgp.mongodb.com/server-8.0.asc | \
  sudo gpg -o /usr/share/keyrings/mongodb-server-8.0.gpg --dearmor
echo "deb [ arch=amd64,arm64 signed-by=/usr/share/keyrings/mongodb-server-8.0.gpg] \
  https://repo.mongodb.org/apt/ubuntu jammy/mongodb-org/8.0 multiverse" | \
  sudo tee /etc/apt/sources.list.d/mongodb-org-8.0.list
sudo apt update
sudo apt install -y mongodb-org
sudo systemctl start mongod
sudo systemctl enable mongod

# Open5GS
sudo add-apt-repository ppa:open5gs/latest
sudo apt update
sudo apt install open5gs

# Node.js 20.x (dependência da WebUI)
sudo apt install -y ca-certificates curl gnupg
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | \
  sudo gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg
echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] \
  https://deb.nodesource.com/node_20.x nodistro main" | \
  sudo tee /etc/apt/sources.list.d/nodesource.list
sudo apt update
sudo apt install nodejs -y

# WebUI
curl -fsSL https://open5gs.org/open5gs/assets/webui/install | sudo -E bash -

# Roteamento e firewall
sudo sysctl -w net.ipv4.ip_forward=1
sudo sysctl -w net.ipv6.conf.all.forwarding=1
sudo iptables -t nat -A POSTROUTING -s 10.45.0.0/16 ! -o ogstun -j MASQUERADE
sudo ip6tables -t nat -A POSTROUTING -s 2001:db8:cafe::/48 ! -o ogstun -j MASQUERADE
sudo ufw disable
```

Após a instalação: configurar manualmente cada NF (AMF, SMF, UPF, NSSF…)
editando os arquivos em `/etc/open5gs/*.yaml` e cadastrar assinantes via WebUI
ou CLI do MongoDB.

**Comandos:** 23 | **Tempo estimado:** ~35 min
**Gargalo:** três repositórios externos separados (MongoDB, Open5GS PPA, Node.js), cada um com importação de chave GPG e `apt update` independente.

---

### 2. UERANSIM (gNB + UE Simulator)

**Fonte:** https://github.com/aligungr/UERANSIM/wiki/Installation

```bash
sudo apt update
sudo apt upgrade
sudo apt install make
sudo apt install gcc
sudo apt install g++
sudo apt install libsctp-dev lksctp-tools
sudo apt install iproute2
sudo snap install cmake --classic   # versão do apt é incompatível
git clone https://github.com/aligungr/UERANSIM
cd UERANSIM
make
```

Após a build: editar manualmente `config/open5gs-gnb.yaml` e
`config/open5gs-ue.yaml` com PLMN, TAC, AMF address e NSSAI de cada UE.

**Comandos:** 11 | **Tempo estimado:** ~20 min
**Gargalo:** compilação C++ (~8 min). A wiki exige `snap` para o CMake pois a versão APT do Ubuntu 22.04 é antiga demais.

---

### 3. ONOS 2.7 (Controlador SDN)

**Fonte:** https://github.com/opennetworkinglab/onos (README)

```bash
# Java 11
sudo apt-get install openjdk-11-jdk

# Bazel (sistema de build)
sudo apt install apt-transport-https curl gnupg -y
curl -fsSL https://bazel.build/bazel-release.pub.gpg | gpg --dearmor > bazel.gpg
sudo mv bazel.gpg /etc/apt/trusted.gpg.d/
echo "deb [arch=amd64] https://storage.googleapis.com/bazel-apt stable jdk1.8" | \
  sudo tee /etc/apt/sources.list.d/bazel.list
sudo apt update && sudo apt install bazel

# Dependências adicionais
sudo apt install git zip curl unzip python3 python-is-python3 -y

# Clone do repositório (~1 GB)
git clone https://gerrit.onosproject.org/onos
cd onos

# Ambiente de desenvolvimento
cat << 'EOF' >> ~/.bash_profile
export ONOS_ROOT="$HOME/onos"
source $ONOS_ROOT/tools/dev/bash_profile
EOF
source ~/.bash_profile

# Build (primeira execução: 35-40 min)
bazel build onos

# Execução
bazel run onos-local -- clean
```

**Comandos:** 13 | **Tempo estimado:** ~75 min
**Gargalo:** primeiro `bazel build onos` baixa o grafo completo de dependências Maven e compila o monorepo (~35–40 min). O clone do repositório somam ~10 min adicionais.

---

### 4. Open vSwitch (OVS)

**Fonte:** https://docs.openvswitch.org/en/latest/intro/install/general/

```bash
# Dependências de build
sudo apt-get update
sudo apt-get install -y build-essential git autoconf automake libtool
sudo apt-get install -y libssl-dev libcap-ng-dev python3

# Código-fonte
git clone https://github.com/openvswitch/ovs.git
cd ovs

# Configuração e build
./boot.sh
./configure --prefix=/usr --localstatedir=/var --sysconfdir=/etc
make
sudo make install

# Banco de dados e inicialização dos daemons
sudo mkdir -p /etc/openvswitch
sudo mkdir -p /var/run/openvswitch
sudo ovsdb-tool create /etc/openvswitch/conf.db vswitchd/vswitch.ovsschema
sudo ovsdb-server \
    --remote=punix:/var/run/openvswitch/db.sock \
    --remote=db:Open_vSwitch,Open_vSwitch,manager_options \
    --pidfile --detach --log-file
sudo ovs-vsctl --no-wait init
sudo ovs-vswitchd --pidfile --detach --log-file
```

Após a instalação: criar bridges, adicionar portas, configurar o controlador
OpenFlow e verificar com `ovs-vsctl show` e `ovs-ofctl dump-flows <bridge>`.

**Comandos:** 15 | **Tempo estimado:** ~30 min
**Gargalo:** build a partir do código-fonte (~10 min) + inicialização manual dos daemons (sem unit systemd gerado automaticamente pela instalação por fonte).

---

### 5. Containernet (Mininet com suporte a Docker)

**Fonte:** https://github.com/containernet/containernet (README)

```bash
sudo apt-get install ansible
git clone https://github.com/containernet/containernet.git
sudo ansible-playbook -i "localhost," -c local \
    containernet/ansible/install.yml
python3 -m venv venv
source venv/bin/activate
cd containernet
pip install -e . --no-binary :all:
sudo make test
```

O playbook Ansible instala automaticamente Docker Engine, Mininet e todas
as dependências Python — não é necessário instalar Docker separadamente.

**Comandos:** 8 | **Tempo estimado:** ~30 min
**Gargalo:** playbook Ansible (~18 min) puxando Docker CE, Mininet e dependências Python.

---

### 6. Grafana (observabilidade)

**Fonte:** https://grafana.com/docs/grafana/latest/setup-grafana/installation/debian/

```bash
sudo apt-get install -y apt-transport-https wget gnupg
sudo mkdir -p /etc/apt/keyrings
sudo wget -O /etc/apt/keyrings/grafana.asc https://apt.grafana.com/gpg-full.key
sudo chmod 644 /etc/apt/keyrings/grafana.asc
echo "deb [signed-by=/etc/apt/keyrings/grafana.asc] \
  https://apt.grafana.com stable main" | \
  sudo tee -a /etc/apt/sources.list.d/grafana.list
sudo apt-get update
sudo apt-get install grafana
sudo systemctl daemon-reload
sudo systemctl start grafana-server
sudo systemctl enable grafana-server.service
sudo systemctl status grafana-server
```

Após a instalação: configurar datasource (Prometheus), importar dashboards
manualmente via UI (http://localhost:3000).

**Comandos:** 11 | **Tempo estimado:** ~12 min
**Gargalo:** velocidade de download. O processo é mecânico e raramente falha.

---

### 7. Prometheus (coleta de métricas)

**Fonte:** https://prometheus.io/docs/prometheus/latest/getting_started/

```bash
wget https://github.com/prometheus/prometheus/releases/download/v3.13.1/prometheus-3.13.1.linux-amd64.tar.gz
tar xvfz prometheus-3.13.1.linux-amd64.tar.gz
cd prometheus-3.13.1.linux-amd64
cat > prometheus.yml << 'EOF'
global:
  scrape_interval: 15s
scrape_configs:
  - job_name: 'prometheus'
    scrape_interval: 5s
    static_configs:
      - targets: ['localhost:9090']
EOF
./prometheus --config.file=prometheus.yml
```

Após a instalação: editar `prometheus.yml` manualmente para adicionar cada
target de scrape (AMF, SMF, UPF, PCF). Configurar systemd unit separadamente
se quiser início automático.

**Comandos:** 5 | **Tempo estimado:** ~12 min
**Gargalo:** download do binário (~100 MB).

---

## Comparação Consolidada

### Esforço de configuração (número de comandos)

| Componente | Manual | Automatizado |
|---|---:|---:|
| Open5GS | 23 | — |
| UERANSIM | 11 | — |
| ONOS | 13 | — |
| Open vSwitch | 15 | — |
| Containernet | 8 | — |
| Grafana | 11 | — |
| Prometheus | 5 | — |
| **Total instalação** | **86** | — |
| Integração / orquestração¹ | estimado ≥30 | — |
| **Total** | **≥116** | **4** |

¹ Integração manual inclui: conectar OVS ao ONOS (endereço do controlador),
configurar cada NF do Open5GS para apontar ao NRF, criar bridges e portas OVS,
cadastrar assinantes no MongoDB, configurar targets do Prometheus, importar
dashboards no Grafana — etapas não contabilizadas nos tutoriais individuais.

**Redução:** de ≥116 comandos para **4** — fator de redução superior a **29×**.

---

### Tempo de implantação

| Componente | Manual (sequencial) | Notas |
|---|---:|---|
| Open5GS | 35 min | 3 repos externos + config por NF |
| UERANSIM | 20 min | build C++ |
| ONOS | 75 min | primeiro build Bazel domina |
| Open vSwitch | 30 min | build por fonte + daemons manuais |
| Containernet | 30 min | playbook Ansible |
| Grafana | 12 min | APT direto |
| Prometheus | 12 min | binário pré-compilado |
| Integração manual | estimado ≥60 min | conectar serviços, testar, depurar |
| **Total sequencial** | **≥274 min (~4,6 h)** | |
| **Total paralelizado²** | **~120–150 min (~2–2,5 h)** | ONOS em background |
| **Automatizado (1ª execução)** | **~15 min** | pull de imagens Docker |
| **Automatizado (execuções seguintes)** | **~3–5 min** | imagens em cache; `./fair5g` → "up" |

²Com dois engenheiros: iniciar ONOS imediatamente (domina com 75 min),
executar Grafana + Prometheus em paralelo, UERANSIM durante o build do ONOS.

**Redução de tempo (primeira execução):** de ~274 min para ~15 min — **fator ~18×**.
**Redução de tempo (re-implantação):** de ~274 min para ~3–5 min — **fator ~55–90×**.

---

## Observações metodológicas

- Os tempos manuais assumem um engenheiro competente seguindo o tutorial pela
  primeira vez, sem erros. Problemas de dependência, versão ou firewall são
  comuns e não estão contabilizados.
- O lado automatizado não requer conhecimento prévio de nenhum dos componentes
  individuais — apenas Docker e Python instalados no host.
- A configuração dos perfis de assinante, flows SDN e políticas de QoS é
  inteiramente gerenciada pelos arquivos do repositório; no modo manual, cada
  uma dessas etapas exigiria leitura e edição manual de documentação específica
  de cada componente.
