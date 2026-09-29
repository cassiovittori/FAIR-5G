import json, math, os, re, sys, time
from urllib import parse, request as urlrequest

PROMETHEUS_URL = os.environ.get("PROMETHEUS_URL", "http://localhost:9090")
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

# nome -> PromQL. Se o upstream renomear uma métrica, edita só aqui.
QUERIES = {
    "ues":         "ran_ue",                                            # global (AMF)
    "gnbs":        "gnb",                                               # global (AMF)
    "sessions":    "fivegs_smffunction_sm_sessionnbr",                  # por SMF
    "ping_ok":     "probe_success",                                     # por IP de UE
    "rtt_ms":      'probe_icmp_duration_seconds{phase="rtt"} * 1000',   # por IP de UE
    "upf_in_pps":  "rate(fivegs_ep_n3_gtp_indatapktn3upf[30s])",        # por UPF (pacotes/s)
    "upf_out_pps": "rate(fivegs_ep_n3_gtp_outdatapktn3upf[30s])",       # por UPF (pacotes/s)
}
QUERIES.update({
    "packet_loss":   '(1 - avg_over_time(probe_success{job="blackbox-ping-slices"}[30s])) * 100',
    "jitter_ms":     'stddev_over_time(probe_icmp_duration_seconds{job="blackbox-ping-slices",phase="rtt"}[30s]) * 1000',
    "smf_qos_flows": 'sum by (instance) (fivegs_smffunction_sm_qos_flow_nbr{job="smf"})',
    "upf_qos_flows": 'sum by (instance) (fivegs_upffunction_upf_qosflows{job="upf"})',
})
QUERIES.update({
    "amf_reg_req":     "sum(rate(fivegs_amffunction_rm_reginitreq[1m]))",
    "amf_reg_succ":    "sum(rate(fivegs_amffunction_rm_reginitsucc[1m]))",
    "amf_auth_req":    "sum(rate(fivegs_amffunction_amf_authreq[1m]))",
    "amf_auth_reject": "sum(rate(fivegs_amffunction_amf_authreject[1m]))",
    "amf_auth_fail":   "sum(rate(fivegs_amffunction_amf_authfail[1m]))",
    "amf_registered":  "sum(fivegs_amffunction_rm_registeredsubnbr)",
})
QUERIES["amf_registered_by_slice"] = "fivegs_amffunction_rm_registeredsubnbr"  # label snssai = fatia

# quais queries entram no /metrics/network (valor atual)
CURRENT = ["ues", "gnbs", "sessions", "ping_ok", "rtt_ms", "upf_in_pps", "upf_out_pps"]


def _query(promql: str) -> list:
    url = f"{PROMETHEUS_URL}/api/v1/query?" + parse.urlencode({"query": promql})
    with urlrequest.urlopen(url, timeout=3) as r:
        return json.load(r)["data"]["result"]


def _num(v):
    x = float(v)
    return x if math.isfinite(x) else None  # JSON não aceita NaN


def _by_key(result, key_fn) -> dict:
    out = {}
    for r in result:
        k = key_fn(r["metric"])
        if k is not None:
            out[k] = _num(r["value"][1])
    return out


def _slice_from_instance(metric):
    m = re.match(r"(?:smf|upf)(\d+)\.", metric.get("instance", ""))
    return int(m.group(1)) if m else None


def collect_network_metrics(slice_count: int) -> dict:
    if REPO_ROOT not in sys.path:
        sys.path.insert(0, REPO_ROOT)
    from fair5gctl.core.slicing import build_slice_specs

    all_specs = build_slice_specs(slice_count)
    ip_to_slice = {s.ue_mininet_ip: s.index for s in all_specs}
    specs = {s.index: s for s in all_specs}
    by_ip = lambda m: ip_to_slice.get(m.get("instance"))

    raw = {name: _query(QUERIES[name]) for name in CURRENT}
    sessions = _by_key(raw["sessions"], _slice_from_instance)
    ping_ok  = _by_key(raw["ping_ok"], by_ip)
    rtt      = _by_key(raw["rtt_ms"], by_ip)
    upf_in   = _by_key(raw["upf_in_pps"], _slice_from_instance)
    upf_out  = _by_key(raw["upf_out_pps"], _slice_from_instance)

    def first(name):
        return _num(raw[name][0]["value"][1]) if raw[name] else None

    # a lista é guiada pelo slice_count do run, não pelo que o Prometheus devolveu:
    # fatia sem métrica aparece com null em vez de sumir
    slices = [
        {
            "id": i,
            "sessions": sessions.get(i),
            "ping_ok": None if ping_ok.get(i) is None else ping_ok[i] == 1,
            "rtt_ms": rtt.get(i),
            "upf_in_pps": upf_in.get(i),
            "upf_out_pps": upf_out.get(i),
            "ambr_down_mbps": specs[i].ambr_down_mbps,
            "ambr_up_mbps": specs[i].ambr_up_mbps,
            "qos_index": specs[i].qos_index,
        }
        for i in range(1, slice_count + 1)
    ]
    return {"global": {"ues": first("ues"), "gnbs": first("gnbs")}, "slices": slices}


def _query_range(promql: str, minutes: int, step: int, since: float | None = None) -> list:
    end = time.time()
    start = end - minutes * 60
    if since:
        start = max(start, since)  # nunca antes do início do run
    params = parse.urlencode({"query": promql, "start": start, "end": end, "step": step})
    with urlrequest.urlopen(f"{PROMETHEUS_URL}/api/v1/query_range?{params}", timeout=5) as r:
        return json.load(r)["data"]["result"]


# quais métricas têm histórico, e como identificar a fatia de cada uma
#   by_ip = IP do UE | by_instance = smfN/upfN | by_snssai = label do AMF | global = uma série só
HISTORY = {
    "rtt_ms":      "by_ip",
    "upf_in_pps":  "by_instance",
    "upf_out_pps": "by_instance",
}
HISTORY.update({
    "packet_loss":   "by_ip",
    "jitter_ms":     "by_ip",
    "sessions":      "by_instance",
    "smf_qos_flows": "by_instance",
    "upf_qos_flows": "by_instance",
})
HISTORY.update({
    "amf_reg_req": "global", "amf_reg_succ": "global",
    "amf_auth_req": "global", "amf_auth_reject": "global",
    "amf_auth_fail": "global", "amf_registered": "global",
})
HISTORY["amf_registered_by_slice"] = "by_snssai"


def collect_network_history(slice_count: int, minutes: int = 15, since: float | None = None, names=None) -> dict:
    if REPO_ROOT not in sys.path:
        sys.path.insert(0, REPO_ROOT)
    from fair5gctl.core.slicing import build_slice_specs

    all_specs = build_slice_specs(slice_count)
    ip_to_slice = {s.ue_mininet_ip: s.index for s in all_specs}
    sd_to_slice = {f"{s.sst}-{s.sd_hex}": s.index for s in all_specs}
    step = max(5, minutes * 60 // 120)  # ~120 pontos por série, no mínimo 5s

    out = {}
    for name, kind in HISTORY.items():
        if names and name not in names:
            continue
        if kind == "global":
            key_fn = lambda m: 0
        elif kind == "by_ip":
            key_fn = lambda m: ip_to_slice.get(m.get("instance"))
        elif kind == "by_snssai":
            key_fn = lambda m: sd_to_slice.get(m.get("snssai"))
        else:
            key_fn = _slice_from_instance
        series = {}
        for r in _query_range(QUERIES[name], minutes, step, since):
            sid = key_fn(r["metric"])
            if sid is not None:
                series[sid] = [{"t": int(t), "v": _num(v)} for t, v in r["values"]]
        ids = [0] if kind == "global" else range(1, slice_count + 1)
        out[name] = [{"id": i, "points": series.get(i, [])} for i in ids]
    return {"step": step, "minutes": minutes, "series": out}


NF_JOBS = "amf|smf|upf|pcf"


def collect_nfs() -> list:
    up  = _query(f'up{{job=~"{NF_JOBS}"}}')
    mem = _query(f'process_resident_memory_bytes{{job=~"{NF_JOBS}"}}')
    mem_by = {
        (r["metric"]["job"], r["metric"]["instance"]): _num(r["value"][1])
        for r in mem
    }
    out = []
    for r in up:
        m = r["metric"]
        b = mem_by.get((m["job"], m["instance"]))
        out.append({
            "job": m["job"],
            "instance": m["instance"],
            "up": _num(r["value"][1]) == 1,
            "memory_mb": None if b is None else round(b / 1048576, 1),
        })
    return sorted(out, key=lambda x: (x["job"], x["instance"]))