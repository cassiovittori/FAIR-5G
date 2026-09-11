from dataclasses import dataclass

DEFAULT_SLICE_COUNT = 2
MIN_SLICE_COUNT = 1
# SD é formatado em hex (%06x); acima de 9 aparecem letras a-f, e os parsers YAML
# do Open5GS/UERANSIM para esse campo nunca foram testados com letras — manter <=8 evita a ambiguidade.
MAX_SLICE_COUNT = 8

DEFAULT_UES_PER_SLICE = 1
MIN_UES_PER_SLICE = 1
# Cada UE e um container executando o processo nr-ue do UERANSIM, que e
# single-thread e satura um nucleo sob carga (medido em 2026-09-10: ~100% de um
# nucleo com iperf3 saturando o tunel). Em uma VM de 4 vCPUs, mais de ~4 UEs
# transmitindo ao mesmo tempo saturam o hospedeiro, e a degradacao observada
# passa a refletir contencao de CPU e nao comportamento de fatia — o que
# invalidaria qualquer conclusao sobre isolamento. O teto abaixo e um limite de
# seguranca metodologica, nao uma restricao tecnica do Open5GS.
MAX_UES_PER_SLICE = 4

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
class UESpec:
    """Um equipamento de usuario dentro de uma fatia."""
    slice_index: int
    ue_index: int          # 1..N dentro da fatia
    name: str              # ex.: "ue1_2" (fatia 1, segundo UE)
    imsi: str
    access_ip: str         # IP na rede de acesso (10.34.0.x)

    @property
    def container(self) -> str:
        return f"mn.{self.name}"

    @property
    def config_file(self) -> str:
        return f"{self.name}.yaml"


@dataclass(frozen=True)
class SliceSpec:
    index: int
    sst: int
    sd_hex: str
    imsi: str              # IMSI do primeiro UE; mantido por compatibilidade
    upf_subnet: str
    upf_gateway: str
    ue_mininet_ip: str     # IP do primeiro UE; mantido por compatibilidade
    qos_index: int
    ambr_down_mbps: int
    ambr_up_mbps: int
    ues: tuple = ()        # tuple[UESpec], todos os UEs desta fatia


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


def validate_ues_per_slice(raw, slice_count: int) -> list:
    """Normaliza a quantidade de UEs por fatia.

    Aceita:
      - None            -> DEFAULT_UES_PER_SLICE em todas as fatias
      - int / "3"       -> mesmo valor em todas as fatias
      - "3,1" / [3, 1]  -> valor por fatia, na ordem dos indices

    A forma por fatia existe porque os experimentos de isolamento precisam
    concentrar carga em UMA fatia e observar a outra; uma distribuicao uniforme
    nao consegue expressar esse cenario.
    """
    if raw is None:
        return [DEFAULT_UES_PER_SLICE] * slice_count

    if isinstance(raw, str) and "," in raw:
        partes = [p.strip() for p in raw.split(",") if p.strip()]
    elif isinstance(raw, (list, tuple)):
        partes = list(raw)
    else:
        partes = [raw] * slice_count

    if len(partes) == 1:
        partes = partes * slice_count

    if len(partes) != slice_count:
        raise ValueError(
            f"Quantidade de UEs informada para {len(partes)} fatia(s), "
            f"mas foram solicitadas {slice_count} fatia(s)"
        )

    valores = []
    for i, parte in enumerate(partes, start=1):
        try:
            n = int(parte)
        except (TypeError, ValueError):
            raise ValueError(f"Quantidade de UEs invalida para a fatia {i}: {parte!r}")
        if n < MIN_UES_PER_SLICE or n > MAX_UES_PER_SLICE:
            raise ValueError(
                f"Fatia {i}: quantidade de UEs fora do intervalo "
                f"[{MIN_UES_PER_SLICE}, {MAX_UES_PER_SLICE}]: {n}"
            )
        valores.append(n)
    return valores


def build_slice_specs(count, ues_per_slice=None) -> list[SliceSpec]:
    """Monta as especificacoes de fatia, cada uma com seus N UEs.

    Enderecamento e identidade dos UEs
    ----------------------------------
    Cada UE precisa de um IMSI unico (identidade do assinante no core) e de um IP
    unico na rede de acesso. Com multiplos UEs por fatia o esquema antigo, que
    derivava ambos do indice da fatia, deixa de servir. Aqui o UE k da fatia i
    recebe um numero sequencial global, o que mantem IMSIs e IPs unicos
    independentemente de como os UEs estejam distribuidos entre as fatias.

    Limite de banda
    ---------------
    Todos os UEs de uma fatia compartilham o MESMO meter, portanto o AMBR do
    perfil e AGREGADO por fatia, nao por UE. Isso segue a semantica de
    Session-AMBR do 3GPP (o limite pertence a fatia) e e o que permite o cenario
    em que um UE abusivo consome a banda dos demais da mesma fatia — caso
    intra-slice relevante para o modelo de ameacas.
    """
    count = validate_slice_count(count)
    por_fatia = validate_ues_per_slice(ues_per_slice, count)

    specs = []
    numero_global = 0  # garante IMSI e IP unicos entre todas as fatias
    for index in range(1, count + 1):
        profile = QOS_PROFILES[(index - 1) % len(QOS_PROFILES)]
        subnet_octet = _UPF_SUBNET_BASE_OCTET + index

        ues = []
        for ue_index in range(1, por_fatia[index - 1] + 1):
            numero_global += 1
            ues.append(
                UESpec(
                    slice_index=index,
                    ue_index=ue_index,
                    name=f"ue{index}_{ue_index}" if por_fatia[index - 1] > 1 else f"ue{index}",
                    imsi=f"00101{_msin(numero_global)}",
                    access_ip=f"{_UE_ACCESS_PREFIX}.{_UE_ACCESS_BASE_OCTET + numero_global}",
                )
            )

        specs.append(
            SliceSpec(
                index=index,
                sst=1,
                sd_hex=f"{index:06x}",
                imsi=ues[0].imsi,
                upf_subnet=f"10.{subnet_octet}.0.0/16",
                upf_gateway=f"10.{subnet_octet}.0.1",
                ue_mininet_ip=ues[0].access_ip,
                qos_index=profile["index"],
                ambr_down_mbps=profile["ambr_down_mbps"],
                ambr_up_mbps=profile["ambr_up_mbps"],
                ues=tuple(ues),
            )
        )
    return specs


def all_ues(specs) -> list:
    """Lista plana de todos os UEs de todas as fatias, na ordem de criacao."""
    return [ue for spec in specs for ue in spec.ues]


def other_subnets(specs: list[SliceSpec], index: int) -> list[str]:
    return [s.upf_subnet for s in specs if s.index != index]


def meter_rate_kbps(ambr_down_mbps: int) -> int:
    # Meters OpenFlow criados com a flag "kbps" esperam a taxa em KILOBITS por
    # segundo. A conversao anterior (* 125) produzia kilobytes por segundo,
    # tornando o enforcement 8x mais restritivo que o AMBR pretendido.
    # Verificado por medicao em 2026-09-08: perfil declarado de 100 Mbps gerou
    # meter de 12500 kbps e o iperf3 dentro do tunel mediu 12,3 Mbps.
    return ambr_down_mbps * 1000
