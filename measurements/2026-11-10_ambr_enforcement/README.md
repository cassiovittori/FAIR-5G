# Onde o AMBR é aplicado, e por que o meter OVS derruba o UE (#41)

Medições na VM de testes, de 09 a 10/11/2026, com o `main` em `ba948d4`.

Configuração: 2 fatias, 1 UE por fatia. A fatia 1 tem AMBR de 100/50 Mbps e a fatia 2 de 10/10 Mbps (ue2: acesso 10.34.0.201, túnel 10.46.0.2).

Todos os testes são downlink da fatia 2 (`iperf3 -R`, servidor na upf2, cliente `mn.ue2` ligado ao túnel).

## ANTES — meter OVS no enlace de acesso (comportamento até o #41)

### 1. Queda de rádio na rodada piloto (`runs/pilot/r001`, 09/11)

O teste `slice2/down` (TCP, 30 s) travou cerca de 20 s depois de começar. O nr-ue registrou:

```
[2026-11-10 00:20:16.120] [rrc] [debug] Signal lost for cell[1], total [0] cells in coverage
[2026-11-10 00:20:16.120] [nas] [error] Radio link failure detected
[2026-11-10 00:20:16.630] [rrc] [error] Cell selection failure, no suitable or acceptable cell found
```

O UE não se recuperou: nas fases seguintes, o ping deu 100% de perda e o iperf3 não conectou. A SMF e a UPF não registram release, então quem caiu foi o enlace UE↔gNB, não a sessão.

### 2. TCP com e sem meter (10/11)

| Condição | Duração | Vazão recebida | Retransmissões | Contador do meter 2 (`ovs-ofctl meter-stats`) |
|---|---|---|---|---|
| Com meter | 60 s | 8,93 Mbps (~8,8 estável) | 4.479 | descartes 2.135 → 6.514 (+4.379) |
| Sem meter (bypass) | 60 s | 9,79 Mbps (~9,6 estável) | 4.017 | — |
| Sem meter (bypass) | 20 s | 10,1 Mbps | 1.443 | parado: packet_in 125.775 → 125.775 |

No teste de 20 s, os flows de bypass (prioridade 600) carregaram 18.995 pacotes no downlink. O bypass funcionou de fato.

Nenhuma interface da upf2 ou do ue2 tem `tc` limitando (`tc -s qdisc show`: só `noqueue`/`fq_codel`, com 0 descartes).

### 3. UDP sem meter: onde o excesso é descartado (10/11)

`iperf3 -u -b 30M -t 20 -R`, com o bypass ligado:

```
sender    30.0 Mbits/sec  0/55771 (0%)
receiver  10.3 Mbits/sec  36671/55755 (66%)
```

Contadores do gNB (`/proc/net/dev`, diferença em 20 s):

```
eth0       RX    0,0 Mbps  TX   11,0 Mbps   <- acesso (rádio simulado, para o UE)
eth1       RX   32,0 Mbps  TX    0,0 Mbps   <- core (GTP-U vindo da upf2)
```

O gNB recebe ~32 Mbps da UPF e entrega ~11 Mbps ao UE. O descarte acontece **dentro do gNB**.

## Conclusões

1. **Quem aplica o AMBR é o gNB do UERANSIM.** O `RateLimiter` em `src/gnb/gtp/task.cpp` usa os valores de AMBR que o Open5GS envia pelo NGAP. Ele descarta o excesso em silêncio: no DL, antes do rádio; no UL, depois dele.
2. **A UPF do Open5GS v2.7.5 não aplica limite de taxa.** Ela guarda o QER, mas o caminho dos pacotes (`src/upf/gtp-path.c`, `lib/pfcp/handler.c`) não o usa.
3. **O meter OVS é um segundo limitador, no lugar errado.** Ele fica no enlace UE↔gNB, que no UERANSIM é o rádio simulado (RLS/UDP). Nesse canal passam dados e heartbeats juntos. O UE remove a célula se ficar mais de 2 s sem resposta (`HEARTBEAT_THRESHOLD = 2000`, `src/ue/rls/udp_task.cpp`), e daí vem o RLF. A queda é rara (não aconteceu em 60 s com ~7% de descarte), por isso estraga rodadas sem padrão.
4. **Os "tetos do ambiente" de 2026-09 eram esse limitador do gNB.** O bypass só tirava o meter OVS, não o AMBR (ver commit `93fa7c3`).

## DEPOIS — meter OVS desligado por padrão (branch `fix/41-ovs-meter-optional`)

> A preencher com o teste da correção: `./fair5g up` (sem `--ovs-meters`), o verify mostrando "OVS meters off", e a fatia 2 limitada a ~10 Mbps sem RLF.

## Arquivos brutos

Copiar de `~/rlf/` na VM:

- `com_antes.txt`, `com_depois.txt`: `meter-stats` antes e depois do TCP com meter.
- `com_iperf.txt`, `sem_iperf.txt`: saídas do iperf3 TCP.
- `gnb_antes.txt`, `gnb_depois.txt`: `/proc/net/dev` do gNB no teste UDP.
