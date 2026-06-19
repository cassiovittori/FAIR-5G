# Plano de Evolução — Open5GS-Mininet (FAIR-5G)

**Data:** 2026-06-19  
**Contexto:** Este documento parte dos achados do [ARCHITECTURE_REVIEW.md](ARCHITECTURE_REVIEW.md) e define a sequência de melhorias para consolidar o fatiamento de rede e o SDN como base sólida de pesquisa e validação.

---

## Visão Geral

A evolução segue duas trilhas paralelas que convergem em um sistema onde o núcleo 5G define política e o SDN a enforça no plano de dados:

```
Trilha SDN                          Trilha Slicing
──────────────────────────────────  ──────────────────────────────────
Fase 1 · Flows proativos estáticos
         + isolamento cross-slice
              │                      Fase 2 · QoS diferenciado por fatia
              │                               (5QI + AMBR distintos)
              ▼                               │
Fase 3 · SDN dinâmico ←────────────────────┘
         (reage a eventos do core)
              │                      Fase 4 · NSSF ativo + 3ª fatia (mMTC)
              │                               │
              ▼                               │
Fase 5 · GTP-U awareness ←──────────────────┘
         + Admission Control
              │
              ▼
        BASE SÓLIDA
  core define política,
  SDN enforça no plano de dados,
  Grafana observa ambos
```

---

## Fase 1 — Flows Proativos e Isolamento Cross-Slice

**Trilha:** SDN  
**Esforço:** Baixo  
**Impacto:** Alto — transforma o SDN de componente decorativo em ferramenta de enforcement

### Problema

O app `fwd` do ONOS age como bridge reativa L2. Nenhuma regra impede um UE de alcançar a subnet da fatia errada. O isolamento existe por coincidência de roteamento IP, não por política.

### O que implementar

**Arquivo:** [containernet/auto_sdn.py](containernet/auto_sdn.py)

1. Adicionar função `install_slice_flows()` que faz POST na API REST do ONOS (`/onos/v1/flows/{dpid}`) após `net.start()` com as seguintes regras:

| Prioridade | Match | Ação |
|------------|-------|------|
| 200 | src=UE1_IP, dst=10.46.0.0/16 | DROP |
| 200 | src=UE2_IP, dst=10.45.0.0/16 | DROP |
| 100 | src=UE1_IP | OUTPUT → porta do core |
| 100 | src=UE2_IP | OUTPUT → porta do core |
| 100 | dst=UE1_IP | OUTPUT → porta de UE1 |
| 100 | dst=UE2_IP | OUTPUT → porta de UE2 |

2. Desativar o app `fwd` após instalar os flows:
```python
deactivate_app_rest("org.onosproject.fwd", user, password)
```

### Critério de aceitação

- `ping` de UE1 para 10.46.x.x retorna `Destination Host Unreachable`
- `ping` de UE1 para seu gateway (10.45.x.x) funciona normalmente
- `ovs-ofctl dump-flows s1` exibe as regras instaladas

---

## Fase 2 — QoS Diferenciado por Fatia

**Trilha:** Slicing  
**Esforço:** Baixo  
**Impacto:** Alto — torna as fatias semanticamente distintas e os dashboards do Grafana informativos

### Problema

Ambas as fatias têm 5QI=9 e AMBR=1 Gbps. As fatias são estruturalmente separadas mas funcionalmente idênticas — qualquer métrica observada no Grafana será espelhada entre os dois painéis.

### O que implementar

**1. Diferenciar perfis de assinatura**

Arquivo: [open5gs/seed/subscribers.js](open5gs/seed/subscribers.js)

| Fatia | Perfil | 5QI | AMBR Down | AMBR Up |
|-------|--------|-----|-----------|---------|
| 1 (SD=000001) | eMBB | 9 | 100 Mbps | 50 Mbps |
| 2 (SD=000002) | URLLC | 2 | 10 Mbps | 10 Mbps |

O 5QI=2 mapeia para GBR com requisito de baixa latência segundo 3GPP TS 23.203 — sinalizando corretamente o perfil URLLC para o SMF/UPF.

**2. Adicionar OpenFlow Meters no OVS**

Via API do ONOS, após instalar os flows da Fase 1, adicionar meters para enforçar o AMBR no ponto de acesso da topologia Mininet:

```
Meter 1 (Fatia 1 / eMBB):  rate=100Mbps, burst=10MB
Meter 2 (Fatia 2 / URLLC): rate=10Mbps,  burst=1MB, drop-on-exceed
```

Associar cada meter às regras de forwarding do UE correspondente.

**3. Validar no Grafana**

Os dashboards existentes em [configs/network-slicing/grafana/dashboards/](configs/network-slicing/grafana/dashboards/) devem passar a exibir curvas de throughput e latência visivelmente diferentes entre as duas fatias durante testes de carga (ex: `iperf3`).

### Critério de aceitação

- `iperf3` de UE1 satura em ~100 Mbps; de UE2 em ~10 Mbps
- Dashboard `dashboard_slicesv3.json` exibe linhas divergentes por fatia
- `ovs-ofctl dump-meters s1` lista os dois meters

---

## Fase 3 — SDN Dinâmico

**Trilha:** SDN  
**Esforço:** Médio  
**Impacto:** Alto — elimina a dependência de IPs estáticos e torna o sistema operacional

### Problema

Os flows instalados na Fase 1 usam IPs de UE hardcoded no startup. Se um UE desconecta e reconecta com IP diferente (alocação dinâmica via SMF), as regras ficam obsoletas e o tráfego para.

### O que implementar

**1. Listener de eventos do core**

Criar um processo Python que subscreva a notificações do NRF ou faça polling na API do Open5GS WebUI para detectar:
- PDU Session Establishment → instalar flow com IP alocado pela SMF
- PDU Session Release → remover flow correspondente

**2. Módulo de reconciliação de flows**

O listener mantém um mapa `{UE_IP → flow_id_ONOS}` e chama a API REST do ONOS para instalar/remover flows ao vivo sem reiniciar a topologia Mininet.

**3. Integração no auto_sdn.py**

O processo listener é iniciado como thread após `net.start()`, eliminando a função `install_slice_flows()` estática da Fase 1 — que passa a ser o fallback de bootstrap para UEs já registrados.

### Critério de aceitação

- Reconectar um UE durante execução instala novo flow automaticamente em menos de 2 segundos
- Remover um UE remove o flow do OVS sem intervenção manual
- `ovs-ofctl dump-flows s1` reflete o estado real de UEs ativos

---

## Fase 4 — NSSF Ativo e Terceira Fatia (mMTC)

**Trilha:** Slicing  
**Esforço:** Médio  
**Impacto:** Médio — adiciona conformidade 3GPP e complexidade realista

### Problema

O NSSF em [configs/network-slicing/nssf.yaml](configs/network-slicing/nssf.yaml) existe como processo mas não há evidência de que o AMF o consulte. Com apenas duas fatias idênticas em perfil de acesso, o ambiente não exercita seleção de fatia baseada em política.

### O que implementar

**1. NSSF com NSSP**

Configurar o AMF em [configs/network-slicing/amf.yaml](configs/network-slicing/amf.yaml) para chamar o NSSF via `http://nssf.open5gs.org:80` na seleção de SMF. Definir no NSSF uma política básica de NSSP:

```
IMSIs 901700000000001–001 → S-NSSAI {sst:1, sd:000001} (eMBB)
IMSIs 901700000000002–002 → S-NSSAI {sst:1, sd:000002} (URLLC)
IMSIs 901700000000003–NNN → S-NSSAI {sst:1, sd:000003} (mMTC)
```

Isso simula o comportamento real de operadoras onde a fatia é determinada por contrato, não por solicitação do dispositivo.

**2. Terceira fatia — mMTC**

Adicionar SMF3, UPF3 e um pool de UEs para simular massive IoT:

| Parâmetro | Valor |
|-----------|-------|
| S-NSSAI | SST=1, SD=000003 |
| Subnet UPF3 | 10.47.0.0/16 |
| 5QI | 6 (non-GBR, best-effort) |
| AMBR | 1 Mbps down / 1 Mbps up |
| Nº de UEs | 5–10 (UERANSIM suporta múltiplos) |

A terceira fatia força o SDN (Fase 3) a gerenciar mais flows dinamicamente e o NSSF a distinguir três perfis — tornando erros de seleção imediatamente visíveis.

**3. Testes de isolamento automatizados**

Adicionar script de validação que verifica automaticamente:
- UE da fatia 1 não alcança subnets de fatia 2 e 3
- Throughput de cada fatia permanece dentro dos limits do seu AMBR sob carga simultânea
- Falha de UPF1 não afeta tráfego de fatia 2

### Critério de aceitação

- NSSF consultado no registro (visível em logs do AMF com `--log-level=debug`)
- 10 UEs mMTC conectados simultaneamente na fatia 3 sem afetar QoS das fatias 1 e 2
- Script de validação passa todos os checks sem intervenção manual

---

## Fase 5 — GTP-U Awareness e Admission Control

**Trilha:** SDN + Slicing (convergência)  
**Esforço:** Alto  
**Impacto:** Alto — fecha o ciclo entre política do core e enforcement do SDN

### Problema

Nas fases anteriores o SDN enxerga IPs de UE (10.33.33.x). Mas no núcleo 5G o tráfego entre gNB e UPF viaja encapsulado em GTP-U com um TEID que identifica unicamente cada PDU session — e por consequência, cada fatia e cada 5QI.

Matching em IP não distingue múltiplas sessões PDU do mesmo UE em fatias diferentes.

### O que implementar

**1. Matching por TEID no OVS**

Configurar flows que inspecionam o header GTP-U (UDP porta 2152) e extraem o TEID para:
- Aplicar o meter correto por sessão (não por UE)
- Associar tráfego ao 5QI da PDU session
- Permitir que um mesmo UE tenha sessões em fatias diferentes com enforcement independente

Requer extensão `ovsdbapp` ou regras com `NXM_NX_TUN_ID` para matching em campos GTP.

**2. Admission Control no SDN**

O controlador mantém contadores de utilização por fatia (bytes/s, número de flows ativos). Quando uma fatia atinge sua capacidade configurada:
- Novas requisições de PDU session para aquela fatia são sinalizadas ao AMF via evento
- O AMF pode rejeitar a sessão ou redirecionar para outra fatia (se disponível)
- O OVS instala um flow temporário de DROP para o novo UE até que capacidade seja liberada

Isso simula o comportamento de um controlador de recursos de fatia (NSSMF) de forma simplificada.

**3. Dashboard de estado do SDN**

Adicionar ao Grafana um painel com métricas do OVS:
- Número de flows ativos por fatia
- Taxa de pacotes matched/dropped por meter
- Eventos de admission control (aceito/rejeitado)

### Critério de aceitação

- `ovs-ofctl dump-flows s1` exibe regras com matching em campos GTP-U/TEID
- Ao saturar a capacidade de uma fatia, novos UEs recebem rejeição de PDU session (sem afetar UEs já conectados)
- Dashboard do Grafana exibe métricas do OVS ao lado das métricas do Open5GS

---

## Resumo das Fases

| Fase | Trilha | Esforço | Impacto | Arquivo principal |
|------|--------|---------|---------|-------------------|
| 1 — Flows proativos + isolamento | SDN | Baixo | Alto | [auto_sdn.py](containernet/auto_sdn.py) |
| 2 — QoS diferenciado | Slicing | Baixo | Alto | [subscribers.js](open5gs/seed/subscribers.js) |
| 3 — SDN dinâmico | SDN | Médio | Alto | [auto_sdn.py](containernet/auto_sdn.py) |
| 4 — NSSF ativo + 3ª fatia | Slicing | Médio | Médio | [nssf.yaml](configs/network-slicing/nssf.yaml), [amf.yaml](configs/network-slicing/amf.yaml) |
| 5 — GTP-U awareness + Admission | SDN + Slicing | Alto | Alto | [auto_sdn.py](containernet/auto_sdn.py), ONOS |

---

## Definição de "Base Sólida"

O ambiente atinge maturidade suficiente para servir como plataforma de pesquisa e validação quando:

1. **Isolamento garantido por política** — nenhum UE pode cruzar fatias sem regra explícita de permissão no OVS
2. **QoS enforçado em dois pontos** — UPF (via PFCP/N4) e OVS (via OpenFlow meters) convergem nos mesmos limites
3. **SDN reage ao ciclo de vida do core** — flows instalados e removidos automaticamente conforme PDU sessions sobem e descem
4. **NSSF seleciona fatia por política** — a seleção de fatia não depende do que o UE solicita, mas do perfil de assinatura
5. **Validação automatizada** — script de testes verifica isolamento e QoS após cada alteração de configuração
