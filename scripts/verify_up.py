#!/usr/bin/env python3
"""Post-condition checks for a FAIR-5G bring-up.

WHY THIS EXISTS
---------------
A zero exit status only means "the commands ran". It does not mean the
environment is usable: containers can be up while a UE never obtained a PDU
session, the switch can be missing from the controller, or Prometheus can be
unreachable. Declaring success on exit status alone is how a measurement
campaign ends up collecting data from a half-built environment without anyone
noticing.

These checks turn "[ok]" from an assumption into a verified statement.

STRICTNESS
----------
Strict mode (FAIR5G_STRICT=1, set automatically for scripted runs) exits
non-zero when any check fails: automation must not proceed against a broken
environment. Interactive runs only warn, because a partially built environment
is sometimes exactly what one wants to inspect while debugging.
"""

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from fair5gctl.core.slicing import build_slice_specs  # noqa: E402

# ── saida organizada (ver patch_verify_output.py) ────────────────────────────
# O CLI do Mininet deixa o terminal em modo raw: '\n' nao volta a coluna 0 e a
# saida sai escalonada, alem de se intercalar com o prompt. Acumulamos tudo e
# despejamos num bloco unico com '\r\n' no final da execucao.
import atexit as _atexit
import builtins as _builtins
import io as _io

_print_original = _builtins.print
_relatorio = _io.StringIO()
_LARGURA = 64
_ARQUIVO_RELATORIO = "/tmp/fair5g_verify.txt"


def print(*args, **kwargs):  # noqa: A001 - sombreia o print do modulo de proposito
    kwargs["file"] = _relatorio
    kwargs.pop("flush", None)
    _print_original(*args, **kwargs)


def _despejar_relatorio():
    corpo = _relatorio.getvalue().splitlines()
    if not corpo:
        return
    borda = "=" * _LARGURA
    linhas = ["", borda, "  VERIFICACAO DE POS-CONDICOES DO AMBIENTE", borda]
    linhas += corpo
    linhas += [borda, ""]
    try:
        with open(_ARQUIVO_RELATORIO, "w") as fh:
            fh.write("\n".join(linhas) + "\n")
    except OSError:
        pass
    # '\r\n' porque o terminal pode estar em modo raw; escrita unica para nao
    # se intercalar com o prompt do CLI.
    _print_original("\r\n".join(linhas) + "\r\n", end="", flush=True)


_atexit.register(_despejar_relatorio)
# ─────────────────────────────────────────────────────────────────────────────

ONOS_URL = "http://localhost:8181/onos/v1"
ONOS_AUTH = ("onos", "rocks")
PROM_URL = "http://localhost:9090"

CORE_CONTAINERS = ["nrf", "amf", "ausf", "udm", "udr", "pcf", "bsf", "nssf",
                   "db", "gnb", "prometheus", "grafana", "blackbox"]


def _sh(cmd: str) -> str:
    return subprocess.run(cmd, shell=True, capture_output=True,
                          text=True).stdout


def _running_containers() -> set:
    return set(_sh("sudo docker ps --format '{{.Names}}'").split())


def check_containers(specs) -> tuple:
    """Every expected container must be running.

    Missing core functions break registration; a missing UPF or SMF breaks one
    slice specifically, which would silently turn a two-slice experiment into a
    one-slice one.
    """
    running = _running_containers()
    expected = list(CORE_CONTAINERS)
    for spec in specs:
        expected += [f"smf{spec.index}", f"upf{spec.index}"]
        expected += [ue.container for ue in spec.ues]

    missing = [c for c in expected if c not in running]
    if missing:
        return False, f"containers ausentes: {', '.join(missing)}"
    return True, f"{len(expected)} containers esperados em execucao"


PDU_TIMEOUT_S = int(os.getenv("FAIR5G_PDU_TIMEOUT", "90"))


def check_pdu_sessions(specs, timeout_s: int = None) -> tuple:
    """Each UE must hold an address on its tunnel interface.

    This is the real test of whether the UE registered and established a PDU
    session. A running container proves nothing: nr-ue can be up and still have
    failed to attach.

    Registration is asynchronous: it takes seconds after nr-ue starts, and more
    with several UEs, which attach one after another. A single snapshot taken
    right after bring-up reports failure for a UE that is merely still
    attaching — a false negative that makes the whole report untrustworthy.
    So this polls until every UE holds a tunnel address, and returns as soon as
    the last one comes up rather than waiting out the timeout.
    """
    if timeout_s is None:
        timeout_s = PDU_TIMEOUT_S

    pendentes = [ue for spec in specs for ue in spec.ues]
    limite = time.time() + timeout_s
    while True:
        ainda = [
            ue for ue in pendentes
            if "inet " not in _sh(
                f"sudo docker exec {ue.container} "
                f"ip addr show uesimtun0 2>/dev/null"
            )
        ]
        pendentes = ainda
        if not pendentes or time.time() >= limite:
            break
        time.sleep(2)

    if pendentes:
        nomes = ", ".join(ue.name for ue in pendentes)
        return False, f"UEs sem sessao PDU apos {timeout_s}s: {nomes}"
    total = sum(len(s.ues) for s in specs)
    return True, f"{total} UE(s) com sessao PDU ativa"


def check_onos_switch() -> tuple:
    """The switch must be present AND available in the controller.

    A switch that is registered but unavailable means flows and meters were
    never installed, so both QoS enforcement and isolation would be absent
    while the log claimed otherwise.
    """
    try:
        data = _onos_get("/devices")
    except Exception as e:
        return False, f"ONOS inacessivel: {e}"

    devices = data.get("devices", [])
    if not devices:
        return False, "nenhum switch registrado no ONOS"
    indisponiveis = [d.get("id") for d in devices if not d.get("available")]
    if indisponiveis:
        return False, f"switch indisponivel no ONOS: {indisponiveis}"
    return True, f"{len(devices)} switch(es) disponivel(is) no ONOS"


def check_meters(specs) -> tuple:
    """One distinct meter per slice.

    Fewer meters than slices means slices are sharing an aggregate limit — the
    collision bug fixed earlier. Worth checking on every bring-up so a
    regression shows up immediately instead of skewing an experiment.
    """
    try:
        data = _onos_get("/meters")
    except Exception as e:
        return False, f"nao foi possivel consultar meters: {e}"

    ids = {m.get("id") for m in data.get("meters", [])}
    if len(ids) < len(specs):
        return False, (f"{len(ids)} meter(s) distinto(s) para {len(specs)} "
                       f"fatia(s): ha fatias compartilhando limite")
    return True, f"{len(ids)} meter(s) distinto(s) instalado(s)"


def check_prometheus() -> tuple:
    """Prometheus must respond and its targets must be up.

    Without this the dashboards and the per-run reports come back empty, and the
    resource metrics that serve as control variables would be missing exactly
    when they matter.
    """
    try:
        with urllib.request.urlopen(f"{PROM_URL}/api/v1/targets", timeout=5) as r:
            data = json.loads(r.read())
    except Exception as e:
        return False, f"Prometheus inacessivel: {e}"

    alvos = data.get("data", {}).get("activeTargets", [])
    if not alvos:
        return False, "Prometheus sem alvos ativos"
    caidos = [f"{t['labels'].get('job')}/{t['labels'].get('instance')}"
              for t in alvos if t.get("health") != "up"]
    if caidos:
        return False, f"alvos fora do ar: {', '.join(caidos)}"
    return True, f"{len(alvos)} alvo(s) do Prometheus no ar"


def _onos_get(path: str) -> dict:
    import base64
    req = urllib.request.Request(f"{ONOS_URL}{path}")
    token = base64.b64encode(f"{ONOS_AUTH[0]}:{ONOS_AUTH[1]}".encode()).decode()
    req.add_header("Authorization", f"Basic {token}")
    with urllib.request.urlopen(req, timeout=8) as r:
        return json.loads(r.read())


def main() -> int:
    estrito = os.getenv("FAIR5G_STRICT") == "1"
    count = int(os.getenv("FAIR5G_SLICE_COUNT", "2"))
    ues = os.getenv("FAIR5G_UES_PER_SLICE") or None
    specs = build_slice_specs(count, ues)

    verificacoes = [
        ("containers", lambda: check_containers(specs)),
        ("sessoes PDU", lambda: check_pdu_sessions(specs)),
        ("switch no ONOS", check_onos_switch),
        ("meters por fatia", lambda: check_meters(specs)),
        ("Prometheus", check_prometheus),
    ]

    print("\n[verify] Validando pos-condicoes do ambiente...")
    falhas = []
    for nome, fn in verificacoes:
        try:
            ok, detalhe = fn()
        except Exception as e:
            ok, detalhe = False, f"erro na verificacao: {e}"
        marca = "OK  " if ok else "FALHA"
        print(f"  [{marca}] {nome}: {detalhe}")
        if not ok:
            falhas.append(f"{nome}: {detalhe}")

    if not falhas:
        print("[verify] ambiente validado.\n")
        return 0

    print(f"\n[verify] {len(falhas)} verificacao(oes) falhou(aram).")
    if estrito:
        print("[verify] modo estrito: o ambiente NAO esta apto para medicao.")
        print("         Rode './fair5g down' antes de tentar novamente.\n")
        return 1
    print("[verify] modo tolerante: seguindo, mas os dados coletados agora\n"
          "         nao sao confiaveis para analise.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
