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
  * 2 UEs docker (`ue1`, `ue2`) ligados ao switch
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
git clone <seu_repo>
cd open5gs-mininet-hotfix-refactor

# 1) instalar prereqs
./fair5g bootstrap

# 2) (recomendado) logout/login para aplicar grupo docker
# ou continue usando sudo docker

# 3) subir o ambiente
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
./fair5gctl.py down --wipe
```

* `--wipe`: remove volumes do compose e remove o container do ONOS (se habilitado no script).

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

Como o IP do gNB pode mudar a cada `up`, o script:

* Obtém o IP do container `gnb` na rede `open5gs`
* Gera:

  * `configs/runtime/ue1.yaml`
  * `configs/runtime/ue2.yaml`
* Substitui `gnbSearchList` com o IP correto do gNB

`configs/runtime/` é gerado automaticamente e está no `.gitignore`.

---

## Estrutura do repo (resumo)

* `compose-files/network-slicing/` — docker compose do Open5GS + métricas + gNB
* `configs/network-slicing/` — configs base (templates)
* `configs/runtime/` (gerado) — configs finais dos UEs (com IP do gNB renderizado)
* `scripts/` — bootstrap/up/down/seed/render
* `containernet/auto_sdn.py` — ONOS + veth/iptables + topologia + start UEs
* `runs/` (gerado) — logs das execuções (`runs/<run_id>/up.log`)

---

## Variável de ambiente

`FAIR5G_CONFIG_DIR`: força o diretório de configs usado pelo `auto_sdn.py`.

Exemplo:

```bash
export FAIR5G_CONFIG_DIR="$PWD/configs/runtime"
sudo PYTHONPATH="$PWD/containernet" python3 containernet/auto_sdn.py
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

Se aparecer aviso **“adding embedded git repository: openflow”**, é porque `openflow/` contém outro `.git`.

Sugestões:

* transformar em submodule, **ou**
* remover do tracking e/ou colocar no `.gitignore` (se não for necessário no repo final)

---

## Roadmap

* Orquestrador/CLI para padronizar comandos, estados e logs
* Módulo de métricas (coleta/snapshots durante testes)
* Módulo de testes de segurança (cenários/ataques) integrado ao pipeline
