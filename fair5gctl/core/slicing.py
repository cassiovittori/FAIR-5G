from dataclasses import dataclass

DEFAULT_SLICE_COUNT = 2
MIN_SLICE_COUNT = 1
# SD is formatted as hex (%06x); above 9 the letters a-f show up, and the
# Open5GS/UERANSIM YAML parsers for that field were never tested with letters —
# keeping it <=8 avoids the ambiguity.
MAX_SLICE_COUNT = 8

DEFAULT_UES_PER_SLICE = 1
MIN_UES_PER_SLICE = 1
# Each UE is a container running UERANSIM's nr-ue process, which is
# single-threaded and saturates one core under load (measured 2026-09-10: ~100%
# of a core with iperf3 saturating the tunnel). On a 4 vCPU VM, more than ~4 UEs
# transmitting at once saturate the host, and the degradation observed then
# reflects CPU contention rather than slice behaviour — which would invalidate
# any conclusion about isolation. The cap below is a methodological safety
# limit, not a technical restriction of Open5GS.
MAX_UES_PER_SLICE = 4

# Profiles calibrated from the measured capacity of the emulated environment.
#
# ENVIRONMENT CEILING: 8.3 Mbps on a single slice's user plane.
#
# Measured on 2026-09-23 with the slice meters fully bypassed
# (scripts/experiments/bypass_meters.py clones the production flows at priority
# 600 without the METER instruction, covering uplink AND downlink). The control
# was verified on the switch itself, not from the tool's own message:
#   - 31,029 packets through the meterless flow against 26 through the metered
#     one;
#   - meter band counters at zero (no drops during the test);
#   - iperf3/TCP delivered 8.13 and 8.26 Mbps, ABOVE the 8000 kbps meter.
# Saturation confirmed with UDP: offering 20 Mbps delivers 8.33 Mbps; offering
# 40 Mbps delivers 8.34 Mbps. Doubling the load does not move what arrives —
# a hard ceiling.
#
# WHERE THE BOTTLENECK IS: UERANSIM's user plane, not the SDN layer. In the same
# test the OpenFlow switch received and forwarded the 42.7 Mbps offered with
# drop=0 and errs=0 on every port, while the emulated gNB relayed ~20% of what
# it received, with no socket errors (RcvbufErrors=0) and at ~10% of one core.
# It is not a CPU limit: adding vCPUs to the VM does not move the ceiling.
#
# HISTORICAL NOTE: an earlier measurement (2026-09-10) recorded a 12.7 Mbps
# ceiling and was the basis for the 8/3 profiles. That value does NOT reproduce
# and has been discarded. The control back then diverted only the uplink out of
# the meters, leaving the downlink metered — the measurement was never free of
# enforcement.
#
# SELECTION CRITERION: the sum of every slice's AMBR should stay around two
# thirds of the measured ceiling. That way, when all slices saturate, each one
# receives its own AMBR and the observed distribution is ATTRIBUTABLE to the
# meters. If the sum exceeded the ceiling, slices would compete for the
# emulator's bottleneck, which would resolve the contention on its own — and
# there would be no way to separate the effect of the policy from the effect of
# the environment.
#
# With 2 / 1 Mbps: 2 slices sum to 3 Mbps (36% of the ceiling); 4 slices, the
# maximum the tutorial covers, sum to 6 Mbps (72%). A single set of profiles
# serves every scenario, with no recalibration as a function of N.
#
# The contrast that supports the isolation claim is between these profiles and
# the control run with NO meters, in which one slice consumes the whole ceiling
# and starves the others.
QOS_PROFILES = [
    {"index": 9, "ambr_down_mbps": 100, "ambr_up_mbps": 50},   # eMBB-like profile
    {"index": 2, "ambr_down_mbps": 10, "ambr_up_mbps": 10},   # URLLC-like profile
]

# UEs live on the ACCESS network (10.34.0.0/24), separate from the core's
# transport network (10.33.33.0/24). The gNB is dual-homed and bridges at the
# application level (it terminates RLS on one side and originates NGAP/GTP-U on
# the other). The blackbox container also has a leg on both networks, out of
# observability necessity — so the gNB is NOT the only crossing. Both run with
# ip_forward=0, which prevents them from being used as a pivot router between
# access and core.
ACCESS_SUBNET = "10.34.0.0/24"
_UE_ACCESS_PREFIX = "10.34.0"
_UE_ACCESS_BASE_OCTET = 199
_UPF_SUBNET_BASE_OCTET = 44
_IMSI_PREFIX_1_9 = "123456789"
_IMSI_PREFIX_10_99 = "12345678"


@dataclass(frozen=True)
class UESpec:
    """A user equipment inside a slice."""
    slice_index: int
    ue_index: int          # 1..N within the slice
    name: str              # e.g. "ue1_2" (slice 1, second UE)
    imsi: str
    access_ip: str         # IP on the access network (10.34.0.x)

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
    imsi: str              # first UE's IMSI; kept for compatibility
    upf_subnet: str
    upf_gateway: str
    ue_mininet_ip: str     # first UE's IP; kept for compatibility
    qos_index: int
    ambr_down_mbps: int
    ambr_up_mbps: int
    ues: tuple = ()        # tuple[UESpec], every UE in this slice


def validate_slice_count(raw) -> int:
    try:
        count = int(raw)
    except (TypeError, ValueError):
        raise ValueError(f"Invalid slice count: {raw!r} is not an integer")

    if count < MIN_SLICE_COUNT or count > MAX_SLICE_COUNT:
        raise ValueError(
            f"Slice count outside the allowed range "
            f"[{MIN_SLICE_COUNT}, {MAX_SLICE_COUNT}]: {count}"
        )
    return count


def _msin(index: int) -> str:
    if index <= 9:
        return f"{_IMSI_PREFIX_1_9}{index}"
    return f"{_IMSI_PREFIX_10_99}{index:02d}"


def validate_ues_per_slice(raw, slice_count: int) -> list:
    """Normalise the number of UEs per slice.

    Accepts:
      - None            -> DEFAULT_UES_PER_SLICE on every slice
      - int / "3"       -> the same value on every slice
      - "3,1" / [3, 1]  -> one value per slice, in index order

    The per-slice form exists because isolation experiments need to concentrate
    load on ONE slice and observe another; a uniform distribution cannot express
    that scenario.
    """
    if raw is None:
        return [DEFAULT_UES_PER_SLICE] * slice_count

    if isinstance(raw, str) and "," in raw:
        parts = [p.strip() for p in raw.split(",") if p.strip()]
    elif isinstance(raw, (list, tuple)):
        parts = list(raw)
    else:
        parts = [raw] * slice_count

    if len(parts) == 1:
        parts = parts * slice_count

    if len(parts) != slice_count:
        raise ValueError(
            f"UE count given for {len(parts)} slice(s), "
            f"but {slice_count} slice(s) were requested"
        )

    values = []
    for i, part in enumerate(parts, start=1):
        try:
            n = int(part)
        except (TypeError, ValueError):
            raise ValueError(f"Invalid UE count for slice {i}: {part!r}")
        if n < MIN_UES_PER_SLICE or n > MAX_UES_PER_SLICE:
            raise ValueError(
                f"Slice {i}: UE count outside the range "
                f"[{MIN_UES_PER_SLICE}, {MAX_UES_PER_SLICE}]: {n}"
            )
        values.append(n)
    return values


def build_slice_specs(count, ues_per_slice=None) -> list[SliceSpec]:
    """Build the slice specifications, each with its N UEs.

    UE addressing and identity
    --------------------------
    Every UE needs a unique IMSI (the subscriber identity in the core) and a
    unique IP on the access network. With several UEs per slice the old scheme,
    which derived both from the slice index, no longer works. Here UE k of slice
    i gets a global sequential number, which keeps IMSIs and IPs unique no
    matter how the UEs are distributed across slices.

    Bandwidth limit
    ---------------
    Every UE in a slice shares the SAME meter, so the profile's AMBR is
    AGGREGATE per slice, not per UE. This follows 3GPP Session-AMBR semantics
    (the limit belongs to the slice) and is what enables the scenario where an
    abusive UE consumes the bandwidth of the others in its own slice — the
    intra-slice case that matters for the threat model.
    """
    count = validate_slice_count(count)
    per_slice = validate_ues_per_slice(ues_per_slice, count)

    specs = []
    global_number = 0  # keeps IMSIs and IPs unique across all slices
    for index in range(1, count + 1):
        profile = QOS_PROFILES[(index - 1) % len(QOS_PROFILES)]
        subnet_octet = _UPF_SUBNET_BASE_OCTET + index

        ues = []
        for ue_index in range(1, per_slice[index - 1] + 1):
            global_number += 1
            ues.append(
                UESpec(
                    slice_index=index,
                    ue_index=ue_index,
                    name=f"ue{index}_{ue_index}" if per_slice[index - 1] > 1 else f"ue{index}",
                    imsi=f"00101{_msin(global_number)}",
                    access_ip=f"{_UE_ACCESS_PREFIX}.{_UE_ACCESS_BASE_OCTET + global_number}",
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
    """Flat list of every UE in every slice, in creation order."""
    return [ue for spec in specs for ue in spec.ues]


def other_subnets(specs: list[SliceSpec], index: int) -> list[str]:
    return [s.upf_subnet for s in specs if s.index != index]


def meter_rate_kbps(ambr_down_mbps: int) -> int:
    # OpenFlow meters created with the "kbps" flag expect the rate in KILOBITS
    # per second. The previous conversion (* 125) produced kilobytes per second,
    # making enforcement 8x stricter than the intended AMBR.
    # Verified by measurement on 2026-09-08: a declared 100 Mbps profile produced
    # a 12500 kbps meter and iperf3 inside the tunnel measured 12.3 Mbps.
    return ambr_down_mbps * 1000
