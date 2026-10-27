# Baseline - 2026-09-08

Release: 4134d33 (main, isolamento de plano de dados)
VM: Ubuntu 22.04, 8GB RAM, 4 vCPU, NAT
Fatias: 2 | Meters: 12500 / 1250 kbps (bug de unidade x125, nao corrigido nesta rodada)

## Resultados
- iperf_fatia1.txt: 12,3 Mbps (meter 12500 kbps)
- iperf_fatia2.txt: 1,19 Mbps (meter 1250 kbps)
- contadores.txt: isolamento cross-slice, regra FORWARD upf1 = 10 pkts / 840 bytes
- Core inalcancavel; regra -d 10.33.33.0/24 com contador zerado (mecanismo nao identificado)
- Pivo via blackbox testado com rota forcada: nao se concretizou
