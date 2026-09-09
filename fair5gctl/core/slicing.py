from dataclasses import dataclass

DEFAULT_SLICE_COUNT = 2
MIN_SLICE_COUNT = 1
# SD é formatado em hex (%06x); acima de 9 aparecem letras a-f, e os parsers YAML
# do Open5GS/UERANSIM para esse campo nunca foram testados com letras — manter <=8 evita a ambiguidade.
MAX_SLICE_COUNT = 8

# Perfis calibrados pela capacidade medida do ambiente emulado.
#
# Teto do uplink de uma fatia, medido em 2026-09-08 com um flow de prioridade 600
# SEM meter (controle) e iperf3/TCP de UE1 ate a UPF1: 50,8 Mbps. Reintroduzindo
# o meter na mesma sessao, o throughput caiu para 12,4 Mbps, confirmando que o
# meter e o fator limitante e nao o ambiente.
#
# Criterio de escolha dos valores: (1) ambos abaixo do teto, para que o
# enforcement seja observavel; (2) soma de N fatias proxima do teto sem que uma
# unica fatia possa consumir toda a capacidade, permitindo operar varias fatias
# simultaneamente e atribuir efeitos com clareza; (3) razao suficiente entre os
# perfis para que a diferenciacao seja mensuravel.
#
# ATENCAO para os experimentos de isolamento: com a soma dos perfis abaixo do
# teto as fatias nunca competem por recurso, e o isolamento se sustenta
# trivialmente. Cenarios de disputa exigem sobre-subscricao deliberada (soma dos
# perfis acima do teto) — nesses casos, sobrescrever estes valores por execucao.
QOS_PROFILES = [
    {"index": 9, "ambr_down_mbps": 12, "ambr_up_mbps": 12},   # perfil tipo eMBB
    {"index": 2, "ambr_down_mbps": 4, "ambr_up_mbps": 4},     # perfil tipo URLLC
]

# Os UEs ficam na rede de ACESSO (10.34.0.0/24), separada da rede de transporte do
# core (10.33.33.0/24). O gNB e dual-homed e faz a ponte em nivel de aplicacao
# (termina o RLS de um lado, origina NGAP/GTP-U do outro). O container blackbox
# tambem tem perna nas duas redes, por necessidade de observabilidade — logo o
# gNB NAO e a unica travessia. Verificado em 2026-09-08: o blackbox tem
# ip_forward=1, e o UE o alcanca (whitelist do OVS). Uma tentativa de pivo com
# rota estatica UE -> blackbox -> AMF nao alcancou o core nas condicoes testadas,
# mas o caminho existe e deve ser tratado como superficie de ataque no modelo de
# ameacas, nao como impossibilidade topologica.
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
    # Verificado por medicao em 2026-09-08 (release 4134d33, VM 8GB/4vCPU):
    # perfil declarado de 100 Mbps -> meter gravado como 12500 kbps -> iperf3
    # dentro do tunel PDU mediu 12,3 Mbps. Fator 8 exato (1000/125).
    return ambr_down_mbps * 1000
