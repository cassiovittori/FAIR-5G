#!/usr/bin/env python3
"""Instala/remove flows que desviam o trafego de uma fatia dos meters.

Serve ao experimento de controle do "teto do ambiente": medir a vazao maxima
que a fatia alcanca quando NENHUM limite de QoS esta aplicado, para separar o
que e limite configurado do que e limite do ambiente.

COMO OS FLOWS DE BYPASS SAO MONTADOS
------------------------------------
Nao chutamos o seletor. O script LE a tabela de flows do ONOS, acha os flows de
producao que carregam instrucao METER para a fatia alvo, e CLONA cada um deles
em prioridade 600 removendo so o METER. O seletor do clone e byte a byte igual
ao do original, entao o bypass casa exatamente o mesmo trafego que o flow
metrado casava — nem mais, nem menos.

A versao anterior deste script montava o seletor a mao com o IP do tunel
(10.45.0.2). Esse IP nao aparece no switch: o trafego do uesimtun0 sobe
encapsulado em GTP-U entre o IP de acesso da UE (10.34.0.x) e o gNB. Os flows
de producao casam `ue_mininet_ip`, nao o IP do tunel. Resultado: o bypass nao
casava nada, a medicao continuava metrada, e o numero medido nao valia.

DUAS DIRECOES. O trafego TCP do iperf3 passa pelo switch nos dois sentidos: os
dados sobem (UE -> core) e os ACKs descem (core -> UE). O flow de downlink
tambem carrega METER. Clonar so o uplink deixa os ACKs metrados e o teste
continua limitado — foi o erro da primeira tentativa deste experimento. Como o
script clona TODO flow com METER da fatia, as duas direcoes vem junto.

Uso (na raiz do repositorio, com o ambiente no ar):

    sudo python3 scripts/bypass_meters.py flows     # o que carrega trafego hoje
    sudo python3 scripts/bypass_meters.py status    # contadores dos meters
    sudo python3 scripts/bypass_meters.py on
    ... rode o iperf3 ...
    sudo python3 scripts/bypass_meters.py status    # meters devem estar parados
    sudo python3 scripts/bypass_meters.py off
"""
import argparse
import base64
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

PRIORIDADE = 600  # acima dos flows de producao (100/150/200/300)

USER = os.getenv("FAIR5G_ONOS_USER", "onos")
PASSWORD = os.getenv("FAIR5G_ONOS_PASS", "rocks")
SWITCH = os.getenv("FAIR5G_SWITCH", "s1")


def onos(method, path, payload=None):
    url = f"http://localhost:8181{path}"
    creds = base64.b64encode(f"{USER}:{PASSWORD}".encode()).decode()
    headers = {"Authorization": f"Basic {creds}"}
    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            body = r.read()
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        print(f"[ERRO] ONOS {method} {path}: HTTP {e.code} — {e.read().decode()[:200]}")
        return None
    except urllib.error.URLError as e:
        print(f"[ERRO] ONOS {method} {path}: {e.reason}")
        return None


def ovs(comando):
    """Le direto do switch. A visao do ONOS pode divergir da do switch, e quem
    aplica o enforcement e o switch."""
    try:
        r = subprocess.run(f"ovs-ofctl -O OpenFlow13 {comando} {SWITCH}",
                           shell=True, capture_output=True, text=True, timeout=15)
        return r.stdout
    except Exception as e:
        return f"[ERRO] ovs-ofctl: {e}"


def pegar_dpid():
    data = onos("GET", "/onos/v1/devices") or {}
    for d in data.get("devices", []):
        if d.get("available"):
            return d["id"]
    print("[ERRO] nenhum switch disponivel no ONOS. O ambiente esta no ar?")
    sys.exit(1)


def meter_do_flow(flow):
    for i in flow.get("treatment", {}).get("instructions", []):
        if i.get("type") == "METER":
            return str(i.get("meterId"))
    return None


def resumo_selector(flow):
    partes = []
    for c in flow.get("selector", {}).get("criteria", []):
        if c.get("type") in ("IPV4_SRC", "IPV4_DST"):
            partes.append(f"{c['type'].split('_')[1].lower()}={c.get('ip')}")
    saida = [i.get("port") for i in flow.get("treatment", {}).get("instructions", [])
             if i.get("type") == "OUTPUT"]
    return f"{' '.join(partes) or '(sem match de IP)'} -> porta {saida or '?'}"


def flows_da_fatia(dpid, meter_id):
    """Flows de producao que aplicam o meter da fatia alvo."""
    data = onos("GET", f"/onos/v1/flows/{dpid}") or {}
    return [f for f in data.get("flows", [])
            if meter_do_flow(f) == str(meter_id) and f.get("priority") != PRIORIDADE]


def mostrar_meters(dpid):
    data = onos("GET", f"/onos/v1/meters/{dpid}") or {}
    meters = data.get("meters", [])
    if not meters:
        print("  (o ONOS nao lista nenhum meter)")
    for m in meters:
        for b in m.get("bands", []):
            print(f"  [onos]  meter id={m.get('id')} rate={b.get('rate')} kbps  "
                  f"descartes: packets={b.get('packets')} bytes={b.get('bytes')}")
    # O ONOS costuma devolver os contadores de banda zerados mesmo com o meter
    # descartando pacotes. Os numeros que valem sao os do switch.
    saida = ovs("meter-stats")
    print("  [switch] ovs-ofctl meter-stats:")
    for linha in (saida or "").splitlines():
        if linha.strip():
            print(f"    {linha.rstrip()}")


def mostrar_flows():
    print(f"Flows no switch {SWITCH} com contadores (n_packets mostra quem carrega trafego):")
    for linha in (ovs("dump-flows") or "").splitlines():
        if "n_packets=0," in linha or not linha.strip():
            continue
        print(f"  {linha.strip()}")
    print("\n(flows com n_packets=0 foram omitidos)")


def ligar(dpid, meter_id):
    originais = flows_da_fatia(dpid, meter_id)
    if not originais:
        print(f"[ERRO] nenhum flow de producao usa o meter {meter_id}.")
        print("       Confira o id com 'status' e passe --meter-id.")
        sys.exit(1)

    print(f"Clonando {len(originais)} flow(s) do meter {meter_id} sem a instrucao METER:")
    instalados = 0
    for f in originais:
        instrs = [i for i in f.get("treatment", {}).get("instructions", [])
                  if i.get("type") != "METER"]
        clone = {
            "priority": PRIORIDADE,
            "isPermanent": True,
            "selector": f.get("selector", {}),
            "treatment": {"instructions": instrs},
        }
        if onos("POST", f"/onos/v1/flows/{dpid}", payload=clone) is None:
            print(f"  [ERRO] falhou: {resumo_selector(f)}")
            print("         rode 'off' antes de tentar de novo.")
            sys.exit(1)
        print(f"  [ok] {resumo_selector(f)}")
        instalados += 1

    print(f"\n{instalados} flow(s) de bypass ativos em prioridade {PRIORIDADE}.")
    print("Rode o iperf3 e depois 'status': os descartes do meter nao podem crescer.")


def desligar(dpid):
    # Identifica o bypass pela FORMA, nao pelo appId: prioridade 600 e treatment
    # sem METER. Os flows de producao usam 100/150/200/300, nao ha como confundir.
    data = onos("GET", f"/onos/v1/flows/{dpid}") or {}
    removidos = 0
    for f in data.get("flows", []):
        if f.get("priority") != PRIORIDADE or meter_do_flow(f) is not None:
            continue
        if onos("DELETE", f"/onos/v1/flows/{dpid}/{f['id']}") is not None:
            removidos += 1
    print(f"[ok] {removidos} flow(s) de bypass removido(s). Os meters voltam a valer.")
    if removidos == 0:
        print("     (nenhum encontrado — talvez ja estivessem removidos)")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("acao", choices=["on", "off", "status", "flows"])
    ap.add_argument("--meter-id", default="1",
                    help="meter da fatia a desviar (padrao: 1, fatia 1)")
    args = ap.parse_args()

    if args.acao == "flows":
        mostrar_flows()
        return

    dpid = pegar_dpid()
    if args.acao == "status":
        print(f"Meters em {dpid}:")
        mostrar_meters(dpid)
    elif args.acao == "on":
        ligar(dpid, args.meter_id)
    else:
        desligar(dpid)


if __name__ == "__main__":
    main()
