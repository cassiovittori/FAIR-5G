from dataclasses import dataclass

DEFAULT_SLICE_COUNT = 2
MIN_SLICE_COUNT = 1
# SD é formatado em hex (%06x); acima de 9 aparecem letras a-f, e os parsers YAML
# do Open5GS/UERANSIM para esse campo nunca foram testados com letras — manter <=8 evita a ambiguidade.
MAX_SLICE_COUNT = 8

# Perfis calibrados pela capacidade medida do ambiente emulado.
#
# Teto de throughput do plano de usuario de uma fatia, medido em 2026-09-10 com
# iperf3/TCP de UE1 ate a UPF1 e flows de prioridade 600 desviando uplink E
# downlink para fora dos meters (controle): 12,7 Mbps, com dispersao de ~1,5%
# em seis execucoes. Verificado que o valor NAO decorre do enforcement de QoS —
# com os meters completamente contornados o resultado permanece identico, e os
# contadores de banda dos meters ficam em zero. O gargalo tambem nao e CPU: o
# processo nr-ue do UERANSIM opera em ~55% de um nucleo durante o teste.
# Atribuido a implementacao da interface de tunel (uesimtun0) do UERANSIM.
#
# Criterio de escolha dos valores: o perfil mais alto precisa ficar
# suficientemente abaixo do teto para que a limitacao observada seja
# ATRIBUIVEL ao meter e nao a capacidade do ambiente. Perfis proximos do teto
# tornam o enforcement indistinguivel da limitacao natural e nao sustentam
# afirmacao experimental.
#
# Para experimentos de isolamento sob disputa, note que 4 fatias (8+3+8+3 =
# 22 Mbps) ja excedem o teto de 12,7 Mbps, produzindo contencao sem exigir
# geracao de trafego massiva.
QOS_PROFILES = [
    {"index": 9, "ambr_down_mbps": 8, "ambr_up_mbps": 8},   # perfil tipo eMBB
    {"index": 2, "ambr_down_mbps": 3, "ambr_up_mbps": 3},   # perfil tipo URLLC
]

# Os UEs ficam na rede de ACESSO (10.34.0.0/24), separada da rede de transporte do
# core (10.33.33.0/24). O gNB e dual-homed e faz a ponte em nivel de aplicacao
# (termina o RLS de um lado, origina NGAP/GTP-U do outro). O container blackbox
# tambem tem perna nas duas redes, por necessidade de observabilidade — logo o
# gNB NAO e a unica travessia. Ambos rodam com ip_forward=0, o que impede que
# sejam usados como roteador de pivo entre acesso e core.
ACCESS_SUBNET = "10.34.0.0/24"
_UE_ACCESS_PREFIX = "10.34.0"
_UE_ACCESS_BASE_OCTET = 199
_UPF_SUBNET_BASE_OCTET = 44
_IMSI_PREFIX_1_9 = "123456789"
_IMSI_PREFIX_10_99 = "12345678"


@dataclass(frozen=True)
class SliceSpec:
    index: int
    sst: int
    sd_hex: str
    imsi: str
    upf_subnet: str
    upf_gateway: str
    ue_mininet_ip: str
    qos_index: int
    ambr_down_mbps: int
    ambr_up_mbps: int


def validate_slice_count(raw) -> int:
    try:
        count = int(raw)
    except (TypeError, ValueError):
        raise ValueError(f"Quantidade de fatias inválida: {raw!r} não é um inteiro")

    if count < MIN_SLICE_COUNT or count > MAX_SLICE_COUNT:
        raise ValueError(
            f"Quantidade de fatias fora do intervalo permitido "
            f"[{MIN_SLICE_COUNT}, {MAX_SLICE_COUNT}]: {count}"
        )
    return count


def _msin(index: int) -> str:
    if index <= 9:
        return f"{_IMSI_PREFIX_1_9}{index}"
    return f"{_IMSI_PREFIX_10_99}{index:02d}"


def build_slice_specs(count) -> list[SliceSpec]:
    count = validate_slice_count(count)
    specs = []
    for index in range(1, count + 1):
        profile = QOS_PROFILES[(index - 1) % len(QOS_PROFILES)]
        subnet_octet = _UPF_SUBNET_BASE_OCTET + index
        ue_octet = _UE_ACCESS_BASE_OCTET + index
        specs.append(
            SliceSpec(
                index=index,
                sst=1,
                sd_hex=f"{index:06x}",
                imsi=f"00101{_msin(index)}",
                upf_subnet=f"10.{subnet_octet}.0.0/16",
                upf_gateway=f"10.{subnet_octet}.0.1",
                ue_mininet_ip=f"{_UE_ACCESS_PREFIX}.{ue_octet}",
                qos_index=profile["index"],
                ambr_down_mbps=profile["ambr_down_mbps"],
                ambr_up_mbps=profile["ambr_up_mbps"],
            )
        )
    return specs


def other_subnets(specs: list[SliceSpec], index: int) -> list[str]:
    return [s.upf_subnet for s in specs if s.index != index]


def meter_rate_kbps(ambr_down_mbps: int) -> int:
    # Meters OpenFlow criados com a flag "kbps" esperam a taxa em KILOBITS por
    # segundo. A conversao anterior (* 125) produzia kilobytes por segundo,
    # tornando o enforcement 8x mais restritivo que o AMBR pretendido.
    # Verificado por medicao em 2026-09-08: perfil declarado de 100 Mbps gerou
    # meter de 12500 kbps e o iperf3 dentro do tunel mediu 12,3 Mbps.
    return ambr_down_mbps * 1000
