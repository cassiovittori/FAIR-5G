#!/usr/bin/env bash
# Coleta, de uma vez so, tudo que e necessario para diagnosticar o travamento
# do fluxo de uma fatia (o fluxo para depois de ~15-30 s e nao volta).
#
# Rode no terminal do HOSPEDEIRO, com o ambiente no ar, LOGO DEPOIS de o fluxo
# travar — varias das evidencias sao volateis e somem no `down`.
#
# Uso:  sudo bash scripts/experiments/diag_stall.sh 2
#       (o argumento e o indice da fatia; padrao 1)
#
# O relatorio sai em runs/diag_stall_<timestamp>.txt

set -u
FATIA="${1:-1}"
UE="mn.ue${FATIA}"
UPF="upf${FATIA}"
SMF="smf${FATIA}"
UE_IP="10.34.0.$((199 + FATIA))"
GW_TUNEL="10.$((44 + FATIA)).0.1"
GNB_IP="10.34.0.3"

RAIZ="$(cd "$(dirname "$0")/../.." && pwd)"
SAIDA="$RAIZ/runs/diag_stall_$(date +%Y-%m-%d_%H%M%S).txt"
mkdir -p "$(dirname "$SAIDA")"

secao() { printf '\n===== %s =====\n' "$1" >> "$SAIDA"; }
rodar() { echo "\$ $*" >> "$SAIDA"; eval "$@" >> "$SAIDA" 2>&1; }

{
  echo "Diagnostico de travamento — fatia $FATIA"
  echo "data: $(date -Iseconds)"
  echo "UE=$UE  UPF=$UPF  SMF=$SMF  ue_ip=$UE_IP  gw_tunel=$GW_TUNEL"
} > "$SAIDA"

# 1) O trafego ainda sai da UE? Duas amostras separadas revelam se os
#    contadores estao congelados — uma foto unica nao diz nada.
secao "flows: amostra 1"
rodar "ovs-ofctl -O OpenFlow13 dump-flows s1 | grep $UE_IP"
secao "gerando trafego por 5s (ping no tunel, deve falhar)"
rodar "docker exec $UE ping -c 5 -W 1 $GW_TUNEL"
secao "flows: amostra 2 (compare n_packets com a amostra 1)"
rodar "ovs-ofctl -O OpenFlow13 dump-flows s1 | grep $UE_IP"

# 2) Estado da UE
secao "UE: interface do tunel"
rodar "docker exec $UE ip -br addr show uesimtun0"
secao "UE: rota para o tunel"
rodar "docker exec $UE ip route get $GW_TUNEL"
secao "UE: alcance da rede de acesso (fora do tunel — deve funcionar)"
rodar "docker exec $UE ping -c 3 -W 1 $GNB_IP"
secao "UE: log do nr-ue"
rodar "docker exec $UE sh -c 'tail -60 /tmp/*.log'"

# 3) Nucleo — onde o pacote provavelmente morre
secao "UPF: contadores das regras de isolamento (M4)"
# Se uma regra DROP tiver contador alto, o isolamento dentro do UPF e o culpado.
rodar "docker exec $UPF iptables -L -n -v"
secao "UPF: NAT (masquerade)"
rodar "docker exec $UPF iptables -t nat -L -n -v"
secao "UPF: interfaces e descartes"
rodar "docker exec $UPF ip -s link"
secao "UPF: log"
rodar "docker logs --tail 60 $UPF"
secao "SMF: log (procure por session release / PFCP)"
rodar "docker logs --tail 60 $SMF"
secao "AMF: log"
rodar "docker logs --tail 40 amf"
secao "gNB: log"
rodar "docker logs --tail 40 gnb"

echo
echo "[ok] relatorio em: $SAIDA"
echo
echo "Leitura rapida:"
echo "  - n_packets IGUAL nas duas amostras -> a UE parou de transmitir"
echo "  - n_packets CRESCEU                 -> a UE transmite e o pacote morre adiante"
echo "  - regra DROP no UPF com contador alto -> isolamento M4 e o culpado"
echo "  - 'session release' no SMF          -> o core derrubou a sessao"
