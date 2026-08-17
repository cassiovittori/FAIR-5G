# FAIR-5G — Open5GS + UERANSIM + ONOS + Containernet

Ambiente automatizado (reprodutível) para subir um testbed 5G com **Open5GS (core)**, **UERANSIM (gNB e UEs)** e **SDN (ONOS + OpenFlow/OVS via Containernet)**, focado em experimentos e execução repetida em VMs “zeradas”.

> ⚠️ Projeto de laboratório/pesquisa. Não use em produção.
> O setup cria interfaces `veth` no host e altera `iptables` (chain `DOCKER-USER`).

---

## Sumário

* [O que este repo sobe](#o-que-este-repo-sobe)
* [Requisitos](#requisitos)
* [Quickstart (do zero)](#quickstart-do-zero)
* [Comandos](#comandos)
* [Endpoints](#endpoints)
* [Validação rápida no CLI do Containernet](#validação-rápida-no-cli-do-containernet)
* [Render de configs runtime dos UEs](#render-de-configs-runtime-dos-ues)
* [Estrutura do repo (resumo)](#estrutura-do-repo-resumo)
* [Variável de ambiente](#variável-de-ambiente)
* [Troubleshooting](#troubleshooting)
* [Nota sobre `openflow/` (Git)](#nota-sobre-openflow-git)
* [Roadmap](#roadmap)

---

## O que este repo sobe

* **Open5GS** via `docker compose` (inclui **WebUI**, **Prometheus**, **Grafana**)
* Seed idempotente de subscribers no MongoDB (`scripts/seed_subscribers.sh`)
* Render runtime dos UEs (`scripts/render_ue_configs.sh`) para ajustar `gnbSearchList` com o IP real do gNB
* **ONOS** em container + apps ativadas via REST (openflow + fwd)
* **Containernet/Mininet** com:

  * 1 switch OVS (OpenFlow13)
  * N UEs docker (`ue1`, `ue2`, ...) ligados ao switch — quantidade de fatias configurável via `--slices` (ver [Comandos](#comandos))
  * “cabo” `veth-sdn` conectado à bridge da rede docker `open5gs`

---

## Requisitos

* Ubuntu 22.04 (recomendado)
* `sudo` habilitado
* Internet (pull/build de imagens)
* Docker + Compose plugin, OVS, deps do Mininet (instalados pelo `bootstrap`)

---

## Quickstart (do zero)

```bash
git clone --recurse-submodules <seu_repo>
cd open5gs-mininet

# se clonou sem --recurse-submodules:
# git submodule update --init

# 1) configs locais (versões de imagem, etc.) — opcional, o `up` cria
#    automaticamente a partir do .env.example se você pular este passo
cp .env.example .env

# 2) instalar prereqs
./fair5g bootstrap

# 3) (recomendado) logout/login para aplicar grupo docker
# ou continue usando sudo docker

# 4) subir o ambiente
./fair5g up
```

---

## Comandos

### Wrapper (bash)

```bash
./fair5g bootstrap
./fair5g up
./fair5g down
./fair5g status
./fair5g logs amf
```

### Controller (Python) — recomendado (logs em `runs/`)

```bash
./fair5gctl.py status
./fair5gctl.py up
./fair5gctl.py up --slices 3
./fair5gctl.py down --wipe
```

* `--wipe`: remove volumes do compose e remove o container do ONOS (se habilitado no script).
* `--slices N`: quantidade de fatias a provisionar (padrão 2, máximo 8). Cada fatia gera um par SMF/UPF, um UE e um assinante próprios — configs renderizados por `scripts/render_slice_configs.py` a partir de `configs/templates/`.

---

## Endpoints

* Open5GS WebUI: `http://localhost:9999`
* Prometheus: `http://localhost:9090`
* Grafana: `http://localhost:3000`
* ONOS REST API: `http://localhost:8181/onos/v1/`

Credenciais usadas no script (ONOS): `onos:rocks`

---

## Validação rápida no CLI do Containernet

Quando cair no prompt `containernet>`:

### Logs do UE1

```bash
ue1 sh -c "tail -f /tmp/ue1.log"
```

### Ping entre UEs (topologia SDN/switch)

```bash
ue1 ping -c 3 10.33.33.201
```

### Ping do UE para o gNB

> O IP do gNB aparece no log do render (ou nos logs do container do gNB).

```bash
ue1 ping -c 3 <IP_DO_GNB>
```

**Nota:** ping UE↔UE valida links/switch. A conectividade “5G” (sessão PDU/rota via UPF) deve ser validada pelos logs do UERANSIM e serviços do Open5GS.

---

## Render de configs runtime dos UEs

O `up` roda dois passos de geração antes de subir os containers:

1. `scripts/render_slice_configs.py` — a partir dos templates Jinja2 em `configs/templates/`, gera os configs de todas as N fatias (`amf.yaml`, `nssf.yaml`, `gnb.yaml`, `smfN.yaml`, `upfN.yaml`, `ueN.yaml`, assinantes) em `configs/runtime/`.
2. `scripts/render_ue_configs.sh` — como o IP do gNB pode mudar a cada `up`, substitui o `gnbSearchList` de cada `configs/runtime/ueN.yaml` pelo IP real do container `gnb`.

`configs/runtime/` é gerado automaticamente e está no `.gitignore`.

---

## Estrutura do repo (resumo)

* `fair5gctl/` — pacote da CLI (`cli.py`, `metrics.py`, `tutorial.py`, `core/slicing.py`)
* `sdn/auto_sdn.py` — orquestração ONOS + veth/iptables + topologia Mininet/Containernet + start dos UEs
* `configs/templates/` — templates Jinja2 (fonte) dos configs por fatia
* `configs/network-slicing/` — configs fixos (não dependem da quantidade de fatias)
* `configs/runtime/` (gerado) — configs finais renderizados para N fatias
* `compose-files/network-slicing/` — docker compose do Open5GS + métricas + gNB
* `scripts/` — bootstrap/up/down/seed/render
* `docs/` — documentos de arquitetura e evolução do projeto
* `build/` — build local das imagens Open5GS (`Makefile`/`docker-bake.hcl`); não é necessário para rodar o testbed, que usa imagens prontas do `ghcr.io/borjis131`
* `containernet/` — submodule do [Containernet](https://github.com/containernet/containernet) (dependência externa, não é código do FAIR-5G)
* `runs/` (gerado) — logs das execuções (`runs/<run_id>/up.log`)

---

## Variável de ambiente

* `FAIR5G_CONFIG_DIR`: força o diretório de configs usado pelo `sdn/auto_sdn.py`.
* `FAIR5G_SLICE_COUNT`: quantidade de fatias (o `fair5gctl up --slices N` já define isso automaticamente).

Exemplo de execução manual (sem passar pelo `fair5gctl`):

```bash
export FAIR5G_CONFIG_DIR="$PWD/configs/runtime"
export FAIR5G_SLICE_COUNT=3
sudo -E PYTHONPATH="$PWD/containernet" python3 sdn/auto_sdn.py
```

---

## Troubleshooting

### “`/mn.ue1 already in use`” (resíduo do Containernet)

```bash
./fair5g down
sudo docker rm -f $(sudo docker ps -aq --filter 'name=^mn\.') 2>/dev/null || true
```

### ONOS não responde

```bash
docker ps | grep onos
curl -u onos:rocks -s http://localhost:8181/onos/v1/applications | head
```

### UE não encontra `ue1.yaml/ue2.yaml`

```bash
containernet> ue1 sh -c "ls -la /UERANSIM/config | head -n 40"
```

---

## Nota sobre `openflow/` (Git)

`openflow/` é gerado localmente por parte do processo de build do OVS/Containernet e já está no `.gitignore` — não é versionado.

---

## Roadmap

* Orquestrador/CLI para padronizar comandos, estados e logs
* Módulo de métricas (coleta/snapshots durante testes)
* Módulo de testes de segurança (cenários/ataques) integrado ao pipeline
