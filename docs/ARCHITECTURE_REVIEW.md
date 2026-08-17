# Revisão Arquitetural — Open5GS-Mininet (FAIR-5G)

**Data:** 2026-06-19  
**Escopo:** Avaliação de conformidade com Network Slicing 3GPP e utilização do SDN como ferramenta de controle

---

## 1. Sumário Executivo

O projeto combina Open5GS (núcleo 5G), UERANSIM (simulação de gNB/UE), ONOS (controlador SDN) e Containernet (topologia virtual). A análise revela dois problemas centrais:

1. **Network Slicing**: implementação **parcialmente correta** — plano de controle bem configurado, mas sem isolamento efetivo no plano de dados.
2. **SDN**: **gravemente subutilizado** — ONOS está rodando mas age apenas como bridge L2 reativa, sem nenhuma regra de fluxo orientada a fatias.

---

## 2. Avaliação do Network Slicing

### 2.1 Configuração de S-NSSAI

**Status: Bom**

As duas fatias estão configuradas com S-NSSAI distintos nos arquivos de configuração:

| Fatia | SST | SD     | Subnet UPF     |
|-------|-----|--------|----------------|
| 1     | 1   | 000001 | 10.45.0.0/16   |
| 2     | 1   | 000002 | 10.46.0.0/16   |

- [configs/network-slicing/amf.yaml](../configs/network-slicing/amf.yaml) — AMF declara suporte a ambas as fatias
- [configs/network-slicing/gnb.yaml](../configs/network-slicing/gnb.yaml) — gNB expõe os dois S-NSSAIs ao UE
- [configs/network-slicing/ue1.yaml](../configs/network-slicing/ue1.yaml) e [ue2.yaml](../configs/network-slicing/ue2.yaml) — cada UE tem `configured-nssai` e `default-nssai` distintos

### 2.2 Separação de Funções de Rede por Fatia

**Status: Bom**

| Função | Fatia 1 | Fatia 2 |
|--------|---------|---------|
| SMF    | smf1 → smf1.open5gs.org | smf2 → smf2.open5gs.org |
| UPF    | upf1 → 10.45.0.0/16 | upf2 → 10.46.0.0/16 |

Cada SMF é configurado com o S-NSSAI que serve:
- [configs/network-slicing/smf1.yaml](../configs/network-slicing/smf1.yaml) — SST=1, SD=000001
- [configs/network-slicing/smf2.yaml](../configs/network-slicing/smf2.yaml) — SST=1, SD=000002

O `docker-compose.yaml` garante que cada SMF depende do seu UPF correspondente, provendo isolamento de falhas por container.

### 2.3 NSSF (Network Slice Selection Function)

**Status: Presente mas sem impacto funcional**

O NSSF está instanciado como container com dois NSIs mapeados:

```yaml
# configs/network-slicing/nssf.yaml
nsi:
  - uri: http://nrf.open5gs.org:80
    s_nssai: { sst: 1, sd: "000001" }
  - uri: http://nrf.open5gs.org:80
    s_nssai: { sst: 1, sd: "000002" }
```

**Problema:** Não há evidência na configuração do AMF de que ele está consultando o NSSF antes de selecionar o SMF. A lógica de seleção de fatia no Open5GS padrão usa NRF para descoberta de SMF; o NSSF seria relevante para implementar NSSP (Network Slice Selection Policy) com critérios mais complexos. Atualmente, o NSSF existe como processo mas sua influência na seleção é nula ou indireta.

### 2.4 Dados de Assinatura do UE

**Status: Bom**

O script [open5gs/seed/subscribers.js](../open5gs/seed/subscribers.js) seed o MongoDB com o S-NSSAI correto por UE, incluindo configuração de QoS:

```javascript
// UE1
slice: [{ sst: 1, sd: "000001", default_indicator: true,
  session: [{ name: "internet", qos: { index: 9 },
    ambr: { downlink: { value: 1, unit: 3 }, uplink: { value: 1, unit: 3 } }
  }]
}]
```

**Observação:** Ambas as fatias têm o mesmo 5QI (9) e o mesmo AMBR (1 Gbps). Se o propósito da segunda fatia é simular um perfil diferente (ex: URLLC vs eMBB), os parâmetros de QoS precisam divergir para que o exercício seja válido.

### 2.5 Mecanismos de Isolamento de Fatia

**Status: Fraco — isolamento por coincidência, não por política**

O isolamento atual depende inteiramente de:
- **Roteamento IP**: subnets diferentes (10.45 vs 10.46) fazem o tráfego ir para UPFs distintos via rotas de host
- **Instâncias separadas de SMF/UPF**: um UE não pode usar a sessão PDU do outro

**O que está ausente:**
- Nenhuma regra OVS impedindo UE1 de alcançar 10.46.0.0/16 (subnet do UPF2)
- Nenhuma regra SDN de `drop` para tráfego cross-slice
- Nenhuma política de isolamento garantida por fluxos OpenFlow

---

## 3. Avaliação do SDN

### 3.1 Arquitetura SDN Atual

```
UERANSIM UE1 (10.33.33.200)
       │
       ▼
   OVS s1 (OpenFlow 1.3)          ← único switch, sem regras proativas
       │                               conectado ao ONOS via porta 6653
       ├─── veth-sdn → br-ogs (Docker bridge) → UPF1 / UPF2
       │
UERANSIM UE2 (10.33.33.201)
       │
       ▼
   OVS s1 ──────────────────────────────────────────────────────────┘

        ONOS 2.7.0
        - org.onosproject.openflow (habilitado)
        - org.onosproject.fwd      (habilitado) ← bridge reativa L2
```

### 3.2 O que está implementado

**Arquivo central:** [sdn/auto_sdn.py](../sdn/auto_sdn.py)

| Componente | Status |
|------------|--------|
| Container ONOS 2.7.0 | Deployado |
| OVS com OpenFlow 1.3 | Criado |
| API REST ONOS | Ativa (porta 8181) |
| App `openflow` | Ativado |
| App `fwd` (reactive L2) | Ativado |

### 3.3 O que está ausente — gaps críticos

**1. Nenhuma regra de fluxo proativa**

No [sdn/auto_sdn.py](../sdn/auto_sdn.py), após criar o switch e ligar os UEs, não há nenhuma chamada à API do ONOS para instalar flows:

```python
# auto_sdn.py — o que existe:
activate_app_rest("org.onosproject.fwd", user, password)

# O que deveria existir (exemplo):
# POST /onos/v1/flows/of:switch_id
# { "selector": { "criteria": [{"type":"IPV4_SRC","ip":"10.33.33.200/32"}] },
#   "treatment": { "instructions": [{"type":"OUTPUT","port":"3"}] } }
```

**2. Nenhum isolamento de fatia no plano de dados**

O `fwd` app aprende MACs reativamente. Isso significa:
- Quando UE1 envia pacotes, o OVS aprende a porta de saída via flood
- Nenhuma política impede UE1 de atingir UPF2
- O "isolamento" depende apenas do roteamento IP do host

**3. Nenhuma regra de QoS via OpenFlow**

As métricas de "QoS Flows" no Grafana ([configs/network-slicing/grafana/dashboards/dashboard_slicesv3.json](../configs/network-slicing/grafana/dashboards/dashboard_slicesv3.json)) vêm do **Open5GS UPF**, não do OVS. O SDN não aplica nenhum meter, band ou queue.

**4. Nenhum código de app ONOS customizado**

Não existe:
- App Java/Kotlin para ONOS
- Código Ryu
- Lógica de controlador que processe S-NSSAI ou TEID

**5. Diretório `openflow/` não utilizado**

O repositório contém um diretório `openflow/` com uma implementação de referência antiga (OpenFlow 0.1). Não tem relação com o comportamento atual do sistema.

### 3.4 Consequência Prática

Dado que apenas o app `fwd` está ativo, o switch OVS funciona como um **hub inteligente L2**:

1. Primeiro pacote de UE1 → flood para todas as portas
2. OVS aprende MAC de UE1 na porta correspondente
3. Pacotes subsequentes são encaminhados diretamente (L2 unicast)
4. **Fatia 1 e Fatia 2 compartilham o mesmo domínio de broadcast**

O SDN, neste estado, não agrega nenhum valor além de um switch não gerenciado.

---

## 4. Matriz de Conformidade

### 4.1 Network Slicing (3GPP TS 23.501)

| Requisito | Implementado | Observação |
|-----------|:---:|---------|
| S-NSSAI por UE (subscrito e requisitado) | Sim | ue1.yaml, ue2.yaml, subscribers.js |
| AMF com suporte multi-slice | Sim | amf.yaml expõe dois S-NSSAIs |
| SMF dedicado por fatia | Sim | smf1, smf2 em containers separados |
| UPF dedicado por fatia | Sim | upf1 (10.45), upf2 (10.46) |
| NSSF com política de seleção | Parcial | Container existe, política inativa |
| QoS diferenciado por fatia | Não | Ambas as fatias com 5QI=9, AMBR=1Gbps |
| Isolamento de plano de dados | Não | Apenas IP routing, sem enforcement SDN |
| Monitoramento por fatia | Sim | Grafana dashboards funcionais |

### 4.2 SDN como Ferramenta de Controle

| Capacidade | Implementado | Observação |
|------------|:---:|---------|
| Controlador SDN deployado | Sim | ONOS 2.7.0 |
| Switch OpenFlow | Sim | OVS com OF1.3 |
| Regras proativas de forwarding | Não | Apenas reactive fwd |
| Isolamento de fatia via flows | Não | Nenhuma regra por slice |
| QoS meters/queues por fatia | Não | Não configurado |
| Traffic steering por S-NSSAI | Não | Nenhuma lógica de steering |
| App customizado ONOS | Não | Só apps built-in |
| Enforcement de política por UE | Não | Sem matching por IP/TEID/slice |

---

## 5. Achados e Recomendações

### 5.1 Achado Principal: SDN é decorativo

O ONOS está rodando e o OVS está criado, mas **todo o trabalho de roteamento é feito pelo kernel IP do host**. O SDN poderia — e deveria — ser o ponto central de enforcement de políticas de fatiamento no plano de dados. Hoje ele não cumpre esse papel.

### 5.2 Achado Secundário: Slicing sem QoS diferenciado

Ter duas fatias com S-NSSAIs distintos mas com **exatamente o mesmo perfil de QoS (5QI=9, AMBR 1Gbps down/up)** torna o exercício academicamente fraco. Se as fatias são indistinguíveis em termos de nível de serviço, a separação de SMF/UPF serve apenas para isolamento de falhas, não para diferenciação de serviço.

### 5.3 Achado Terciário: NSSF inativo

O NSSF existe mas não há evidência de que o AMF o consulte. Em uma implantação real, o NSSF implementaria NSSP (Network Slice Selection Policy) — por exemplo, redirecionar determinados UEs para fatias baseado em critérios de assinatura ou localização. Aqui ele é um processo idle.

---

## 6. Plano de Melhorias

### Fase 1 — SDN com enforcement básico (prioridade alta)

**Objetivo:** substituir o `fwd` reativo por regras proativas que direcionem tráfego por fatia.

1. Em [sdn/auto_sdn.py](../sdn/auto_sdn.py), após `net.start()`, adicionar uma função `install_slice_flows()`:

```python
def install_slice_flows(onos_url, switch_dpid, ue1_ip, ue2_ip,
                        port_ue1, port_ue2, port_core):
    flows = [
        # UE1 → Core (para UPF1)
        {"priority": 100,
         "selector": {"criteria": [
             {"type": "ETH_TYPE", "ethType": "0x0800"},
             {"type": "IPV4_SRC", "ip": f"{ue1_ip}/32"}
         ]},
         "treatment": {"instructions": [{"type": "OUTPUT", "port": port_core}]}},
        # UE2 → Core (para UPF2)
        {"priority": 100,
         "selector": {"criteria": [
             {"type": "ETH_TYPE", "ethType": "0x0800"},
             {"type": "IPV4_SRC", "ip": f"{ue2_ip}/32"}
         ]},
         "treatment": {"instructions": [{"type": "OUTPUT", "port": port_core}]}},
        # Core → UE1
        {"priority": 100,
         "selector": {"criteria": [
             {"type": "ETH_TYPE", "ethType": "0x0800"},
             {"type": "IPV4_DST", "ip": f"{ue1_ip}/32"}
         ]},
         "treatment": {"instructions": [{"type": "OUTPUT", "port": port_ue1}]}},
        # Core → UE2
        {"priority": 100,
         "selector": {"criteria": [
             {"type": "ETH_TYPE", "ethType": "0x0800"},
             {"type": "IPV4_DST", "ip": f"{ue2_ip}/32"}
         ]},
         "treatment": {"instructions": [{"type": "OUTPUT", "port": port_ue2}]}},
        # Isolamento: UE1 não acessa subnet de UPF2 (10.46.0.0/16)
        {"priority": 200,
         "selector": {"criteria": [
             {"type": "ETH_TYPE", "ethType": "0x0800"},
             {"type": "IPV4_SRC", "ip": f"{ue1_ip}/32"},
             {"type": "IPV4_DST", "ip": "10.46.0.0/16"}
         ]},
         "treatment": {"instructions": [{"type": "DROP"}]}},
        # Isolamento: UE2 não acessa subnet de UPF1 (10.45.0.0/16)
        {"priority": 200,
         "selector": {"criteria": [
             {"type": "ETH_TYPE", "ethType": "0x0800"},
             {"type": "IPV4_SRC", "ip": f"{ue2_ip}/32"},
             {"type": "IPV4_DST", "ip": "10.45.0.0/16"}
         ]},
         "treatment": {"instructions": [{"type": "DROP"}]}}
    ]
    for flow in flows:
        requests.post(
            f"{onos_url}/onos/v1/flows/{switch_dpid}",
            json={"flows": [flow]},
            auth=("onos", "rocks")
        )
```

2. Desativar o app `fwd` após instalar as regras:

```python
deactivate_app_rest("org.onosproject.fwd", user, password)
```

### Fase 2 — QoS diferenciado por fatia (prioridade média)

1. Alterar [open5gs/seed/subscribers.js](../open5gs/seed/subscribers.js) para diferenciar o AMBR por fatia:
   - Fatia 1 (eMBB): AMBR 100 Mbps down / 50 Mbps up, 5QI=9
   - Fatia 2 (URLLC): AMBR 10 Mbps down / 10 Mbps up, 5QI=2 (baixa latência)

2. Adicionar OpenFlow meters no OVS via ONOS para enforcar os limites no plano de dados:
   - Meter 1: bucket rate=100Mbps (Fatia 1)
   - Meter 2: bucket rate=10Mbps (Fatia 2)

### Fase 3 — NSSF ativo e app ONOS customizado (prioridade baixa)

1. **NSSF**: configurar o AMF para chamar o NSSF via `nssf.open5gs.org:80` na seleção de SMF, validando se o Open5GS versão atual suporta essa integração ativa.

2. **App ONOS customizado**: desenvolver um microapp Java/Kotlin que:
   - Escuta eventos de registro de UE via webhook do AMF
   - Instala/remove flows dinamicamente conforme UEs se conectam/desconectam
   - Associa TEID do GTP-U ao S-NSSAI para steering mais preciso

---

## 7. Resumo de Arquivos Relevantes

| Arquivo | Relevância |
|---------|------------|
| [sdn/auto_sdn.py](../sdn/auto_sdn.py) | Orquestrador SDN — ponto central de melhorias |
| [configs/network-slicing/amf.yaml](../configs/network-slicing/amf.yaml) | Declaração de suporte a fatias no AMF |
| [configs/network-slicing/smf1.yaml](../configs/network-slicing/smf1.yaml) | SMF para fatia 1 |
| [configs/network-slicing/smf2.yaml](../configs/network-slicing/smf2.yaml) | SMF para fatia 2 |
| [configs/network-slicing/upf1.yaml](../configs/network-slicing/upf1.yaml) | UPF para fatia 1 (10.45.0.0/16) |
| [configs/network-slicing/upf2.yaml](../configs/network-slicing/upf2.yaml) | UPF para fatia 2 (10.46.0.0/16) |
| [configs/network-slicing/nssf.yaml](../configs/network-slicing/nssf.yaml) | NSSF — configurado mas inativo |
| [open5gs/seed/subscribers.js](../open5gs/seed/subscribers.js) | Dados de assinatura com S-NSSAI no MongoDB |
| [compose-files/network-slicing/docker-compose.yaml](../compose-files/network-slicing/docker-compose.yaml) | Definição dos 23 serviços |

---

## 8. Conclusão

O projeto tem uma **base sólida de network slicing no plano de controle**: dois S-NSSAIs configurados, SMFs e UPFs dedicados por fatia, UEs com assinaturas corretas no MongoDB e monitoramento funcional via Grafana.

O problema está em duas lacunas estratégicas:

- **O plano de dados não é controlado pelo SDN**. O ONOS existe mas não impõe nenhuma política. Qualquer isolamento hoje é acidental — depende de rotas IP, não de flows OpenFlow. Um UE poderia cruzar fatias sem que nada fosse detectado ou bloqueado.

- **As fatias não são diferenciadas por nível de serviço**. Com 5QI e AMBR iguais, os dois S-NSSAIs são funcionalmente idênticos — a separação é estrutural mas não semântica.

A correção de maior impacto com menor esforço é implementar as regras OpenFlow proativas na Fase 1, desativando o app `fwd` e adicionando flows de isolamento via API REST do ONOS. Isso transformaria o SDN de componente decorativo em ferramenta efetiva de enforcement de políticas de fatiamento.
