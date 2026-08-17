from dataclasses import dataclass

DEFAULT_SLICE_COUNT = 2
MIN_SLICE_COUNT = 1
# SD é formatado em hex (%06x); acima de 9 aparecem letras a-f, e os parsers YAML
# do Open5GS/UERANSIM para esse campo nunca foram testados com letras — manter <=8 evita a ambiguidade.
MAX_SLICE_COUNT = 8

QOS_PROFILES = [
    {"index": 9, "ambr_down_mbps": 100, "ambr_up_mbps": 50},
    {"index": 2, "ambr_down_mbps": 10, "ambr_up_mbps": 10},
]

_UE_MININET_BASE_OCTET = 199
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
        ue_octet = _UE_MININET_BASE_OCTET + index
        specs.append(
            SliceSpec(
                index=index,
                sst=1,
                sd_hex=f"{index:06x}",
                imsi=f"00101{_msin(index)}",
                upf_subnet=f"10.{subnet_octet}.0.0/16",
                upf_gateway=f"10.{subnet_octet}.0.1",
                ue_mininet_ip=f"10.33.33.{ue_octet}",
                qos_index=profile["index"],
                ambr_down_mbps=profile["ambr_down_mbps"],
                ambr_up_mbps=profile["ambr_up_mbps"],
            )
        )
    return specs


def other_subnets(specs: list[SliceSpec], index: int) -> list[str]:
    return [s.upf_subnet for s in specs if s.index != index]


def meter_rate_kbps(ambr_down_mbps: int) -> int:
    return ambr_down_mbps * 125
