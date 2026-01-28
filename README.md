# FAIR-5G (V0) — Open5GS + ONOS + Containernet (UERANSIM UEs)

Este repositório fornece um **ambiente de testes 5G + SDN** executável em **uma única máquina Ubuntu 22.04**, com foco em praticidade (subir infra sem minúcias).

## O que o V0 sobe
- **Open5GS (5G Core)** via `docker compose`
- **UERANSIM gNB** (container) via compose
- **Grafana/Prometheus** (se presentes no compose)
- **ONOS** (controller SDN) via container Docker
- **Containernet/Mininet** com 1 switch (OVS OpenFlow13) e 2 UEs (containers UERANSIM)
- Integração SDN ↔ rede docker `open5gs` via veth + bridge (`br-ogs`)

> O script gera configs runtime para o UE automaticamente, detectando o IP do `gnb` e ajustando `gnbSearchList`.

---

## Requisitos (Ubuntu 22.04)
- Docker + Docker Compose plugin
- Python 3
- Dependências do Containernet/Mininet instaladas (via playbook/installer do repo)
- Pacotes Python do sistema:
  - `python3-docker`
  - `python3-iptables` (para cleanup)

### Observação
Recomendamos executar tudo em VM dedicada (VMware/VirtualBox), pois envolve bridge/iptables/veth.

---

## Como executar (V0)
Na raiz do repositório:

### 1) Subir ambiente (um comando)
```bash
chmod +x scripts/*.sh
./scripts/up_v0.sh
