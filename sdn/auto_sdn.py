#!/usr/bin/env python3
import os
import re
import time
import subprocess
import json
import sys
import base64
import threading
import urllib.request
import urllib.error

from mininet.net import Containernet
from mininet.node import RemoteController, OVSKernelSwitch
from mininet.cli import CLI
from mininet.link import Intf
from mininet.log import info, setLogLevel

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
sys.path.insert(0, REPO_ROOT)

from fair5gctl.core.slicing import (
    build_slice_specs,
    other_subnets,
    meter_rate_kbps,
    ACCESS_SUBNET,
    DEFAULT_SLICE_COUNT,
)


# Imagem do UE: por padrao a derivada local, que ja traz iperf3 e demais
# ferramentas de trafego. FAIR5G_UE_IMAGE permite voltar a oficial quando as
# ferramentas nao forem necessarias.
UE_IMAGE = os.getenv("FAIR5G_UE_IMAGE", "fair5g-ue:v3.2.7")

ACCESS_NETWORK = "fair5g-access"
CORE_NETWORK = "open5gs"


def get_slice_specs():
    count = int(os.getenv("FAIR5G_SLICE_COUNT", DEFAULT_SLICE_COUNT))
    ues = os.getenv("FAIR5G_UES_PER_SLICE") or None
    return build_slice_specs(count, ues)


def run(cmd: str, check: bool = True):
    p = subprocess.run(cmd, shell=True, text=True, capture_output=True)
    if check and p.returncode != 0:
        print(f"[ERRO] cmd falhou: {cmd}")
        if p.stdout:
            print(p.stdout.strip())
        if p.stderr:
            print(p.stderr.strip())
        raise RuntimeError(f"Command failed: {cmd}")
    return p


def detect_config_dir(specs=None):
    """Descobre o diretorio com as configs de UE.

    A checagem procura o arquivo do PRIMEIRO UE efetivamente provisionado, e nao
    um nome fixo: com multiplos UEs por fatia os arquivos passam a se chamar
    ue1_1.yaml, ue1_2.yaml etc., e um teste por "ue1.yaml" falharia mesmo com o
    diretorio correto.
    """
    esperado = specs[0].ues[0].config_file if specs and specs[0].ues else "ue1.yaml"

    env = os.getenv("FAIR5G_CONFIG_DIR")
    candidates = []
    if env:
        candidates.append(env)

    candidates += [
        os.path.join(REPO_ROOT, "configs", "runtime"),
        os.path.join(REPO_ROOT, "configs", "network-slicing"),
    ]

    for d in candidates:
        if os.path.isfile(os.path.join(d, esperado)):
            print(f"Usando CONFIG_DIR: {d}")
            return d

    print(f"\n[ERRO] Nao achei {esperado} em nenhum candidato.")
    print("Defina FAIR5G_CONFIG_DIR apontando para a pasta correta.")
    print("Candidatos testados:")
    for d in candidates:
        print(f" - {d}")
    sys.exit(1)


def preclean_mn_containers():
    run("docker rm -f $(docker ps -aq --filter 'name=^mn\\.') 2>/dev/null || true", check=False)


def get_docker_bridge_name(network_name: str = "open5gs"):
    print(f"Buscando ponte para rede: {network_name}")
    out = run(f"docker network inspect {network_name}").stdout
    data = json.loads(out)

    bridge_name = data[0].get("Options", {}).get("com.docker.network.bridge.name")
    if not bridge_name:
        net_id = data[0]["Id"][:12]
        bridge_name = f"br-{net_id}"

    print(f"Ponte encontrada: {bridge_name}")
    return bridge_name


def _onos_request(method: str, path: str, user: str, password: str, payload=None):
    url = f"http://localhost:8181{path}"
    creds = base64.b64encode(f"{user}:{password}".encode()).decode()
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
        body = e.read()
        print(f"[ERRO] ONOS {method} {path}: HTTP {e.code} — {body.decode()[:200]}")
        return None
    except urllib.error.URLError as e:
        print(f"[ERRO] ONOS {method} {path}: {e.reason}")
        return None


def activate_app_rest(app_name: str, user: str, password: str):
    print(f"Ativando App via API: {app_name}")
    cmd = (
        f"curl --fail -s -o /dev/null "
        f"-u {user}:{password} "
        f"-X POST http://localhost:8181/onos/v1/applications/{app_name}/active"
    )
    return run(cmd, check=False).returncode == 0


def deactivate_app_rest(app_name: str, user: str, password: str):
    print(f"Desativando App via API: {app_name}")
    result = _onos_request("DELETE", f"/onos/v1/applications/{app_name}/active", user, password)
    return result is not None


def wait_for_onos(user: str, password: str, port: int = 8181, max_retries: int = 60):
    print("Aguardando API do ONOS iniciar...")
    for i in range(max_retries):
        if run(f"nc -z localhost {port}", check=False).returncode == 0:
            if activate_app_rest("org.onosproject.openflow", user, password):
                print("ONOS API pronta e Apps ativados.")
                activate_app_rest("org.onosproject.fwd", user, password)
                return True
        time.sleep(2)
        print(f"Tentativa {i+1}/{max_retries}")
    return False


def wait_for_switch(user: str, password: str, max_retries: int = 30) -> str:
    print("Aguardando switch conectar ao ONOS...")
    for i in range(max_retries):
        data = _onos_request("GET", "/onos/v1/devices", user, password)
        if data:
            available = [d for d in data.get("devices", []) if d.get("available", False)]
            if available:
                dpid = available[0]["id"]
                print(f"Switch disponível no ONOS: {dpid}")
                return dpid
        time.sleep(2)
        print(f"  aguardando switch ({i+1}/{max_retries})...")
    raise RuntimeError("Switch não conectou ao ONOS no tempo esperado")


def get_port_by_name(user: str, password: str, dpid: str, intf_name: str):
    data = _onos_request("GET", f"/onos/v1/devices/{dpid}/ports", user, password)
    if not data:
        return None
    for port in data.get("ports", []):
        ann = port.get("annotations", {})
        if ann.get("portName") == intf_name or ann.get("interfaceName") == intf_name:
            return port["port"]
    return None


def _output_instrs(port, meter_id):
    instrs = []
    if meter_id is not None:
        instrs.append({"type": "METER", "meterId": int(meter_id)})
    instrs.append({"type": "OUTPUT", "port": str(port)})
    return instrs


def install_slice_flows(user: str, password: str, dpid: str, specs, ports: dict,
                        port_core: str, meter_ids: dict, gnb_ip: str = "",
                        probe_ips: list = None) -> bool:
    # Modelo whitelist: o único destino que um UE precisa alcançar é o gNB (o ue*.yaml
    # renderizado contém exatamente um IP, o do gNB — o UE não conhece endereço de AMF,
    # SMF, UPF ou NRF). Antes o uplink era `src=UE -> OUTPUT core` para qualquer destino,
    # o que deixava o UE alcançar todo o plano de gerência do core, que fica na mesma /24.
    # O probe do blackbox (job `blackbox-ping-slices`) manda ICMP para os UEs; a
    # RESPOSTA do UE sai como `src=UE, dst=blackbox` e cairia no deny-all. Exceção
    # explícita de observabilidade — sem ela os painéis de latência por fatia zeram.
    allowed_dsts = [gnb_ip] + list(probe_ips or [])
    allowed_dsts = [ip for ip in allowed_dsts if ip]

    def allow_flow(ue_ip, dst_ip, meter_id):
        return {
            "priority": 300, "isPermanent": True,
            "selector": {"criteria": [
                {"type": "ETH_TYPE", "ethType": "0x0800"},
                {"type": "IPV4_SRC", "ip": f"{ue_ip}/32"},
                {"type": "IPV4_DST", "ip": f"{dst_ip}/32"},
            ]},
            "treatment": {"instructions": _output_instrs(port_core, meter_id)},
        }

    def isolation_flow(ue_ip, deny_subnet):
        return {
            "priority": 200, "isPermanent": True,
            "selector": {"criteria": [
                {"type": "ETH_TYPE", "ethType": "0x0800"},
                {"type": "IPV4_SRC", "ip": f"{ue_ip}/32"},
                {"type": "IPV4_DST", "ip": deny_subnet},
            ]},
            "treatment": {"instructions": [{"type": "NOACTION"}]},
        }

    def uplink_flow(ue_ip, meter_id):
        # Sem gnb_ip conhecido cai no comportamento antigo (permissivo) para não
        # derrubar o ambiente; com gnb_ip vira o deny-all que fecha o whitelist.
        priority = 150 if gnb_ip else 100
        treatment = ({"instructions": [{"type": "NOACTION"}]} if gnb_ip
                     else {"instructions": _output_instrs(port_core, meter_id)})
        return {
            "priority": priority, "isPermanent": True,
            "selector": {"criteria": [
                {"type": "ETH_TYPE", "ethType": "0x0800"},
                {"type": "IPV4_SRC", "ip": f"{ue_ip}/32"},
            ]},
            "treatment": treatment,
        }

    def downlink_flow(ue_ip, port_ue, meter_id):
        return {
            "priority": 100, "isPermanent": True,
            "selector": {"criteria": [
                {"type": "ETH_TYPE", "ethType": "0x0800"},
                {"type": "IPV4_DST", "ip": f"{ue_ip}/32"},
            ]},
            "treatment": {"instructions": _output_instrs(port_ue, meter_id)},
        }

    if not gnb_ip:
        print("[AVISO] IP do gNB não informado — flows de uplink ficam permissivos "
              "(UE alcança todo o core). Whitelist desativado.")

    # Um conjunto de flows por UE. Todos os UEs de uma fatia referenciam o MESMO
    # meter: o AMBR e agregado por fatia (semantica de Session-AMBR do 3GPP), nao
    # por assinante. Assim, UEs da mesma fatia competem entre si pelo limite
    # dela — cenario intra-slice que interessa ao modelo de ameacas.
    flows = []
    for spec in specs:
        meter_id = meter_ids.get(spec.index)
        for ue in spec.ues:
            for dst_ip in allowed_dsts:
                flows.append(allow_flow(ue.access_ip, dst_ip, meter_id))
            for deny_subnet in other_subnets(specs, spec.index):
                flows.append(isolation_flow(ue.access_ip, deny_subnet))
    for spec in specs:
        meter_id = meter_ids.get(spec.index)
        for ue in spec.ues:
            flows.append(uplink_flow(ue.access_ip, meter_id))
            flows.append(downlink_flow(ue.access_ip, ports[ue.name], meter_id))

    print(f"Instalando {len(flows)} flows proativos no switch {dpid}...")
    failed = 0
    for i, flow in enumerate(flows):
        result = _onos_request("POST", f"/onos/v1/flows/{dpid}", user, password, payload=flow)
        if result is None:
            print(f"[ERRO] Flow {i+1}/{len(flows)} falhou.")
            failed += 1
        else:
            print(f"  flow {i+1}/{len(flows)} instalado.")
    if failed == 0:
        print("Flows de fatiamento instalados.")
        return True
    print(f"[ERRO] {failed} flow(s) não foram instalados.")
    return False


def install_slice_meters(user: str, password: str, dpid: str, specs) -> dict:
    existing = _onos_request("GET", f"/onos/v1/meters/{dpid}", user, password)
    if existing:
        for m in existing.get("meters", []):
            mid = m.get("id")
            if mid:
                _onos_request("DELETE", f"/onos/v1/meters/{dpid}/{mid}", user, password)

    # burst = rate * 0.8192 reproduz os valores originais hardcoded (12500→10240, 1250→1024)
    rate_by_index = {s.index: meter_rate_kbps(s.ambr_down_mbps) for s in specs}
    burst_by_index = {s.index: max(int(rate_by_index[s.index] * 0.8192), 1) for s in specs}

    # Aguarda a remocao dos meters anteriores antes de criar os novos: criar
    # sobre um estado ainda sujo faz o ONOS reaproveitar identificadores que o
    # switch ainda considera ocupados.
    for _ in range(20):
        atual = _onos_request("GET", f"/onos/v1/meters/{dpid}", user, password) or {}
        if not atual.get("meters"):
            break
        time.sleep(0.5)

    print(f"Instalando {len(specs)} meters no switch {dpid}...")

    # Criacao SERIALIZADA: cada meter e confirmado no ONOS antes do proximo.
    #
    # Disparar os POSTs em sequencia rapida gera condicao de corrida: o ONOS
    # aloca o identificador sem esperar a confirmacao do anterior, e dois meters
    # recebem o MESMO id. O switch instala o primeiro e rejeita o segundo por id
    # duplicado, mas o ONOS registra o segundo como criado — ficando com uma
    # visao divergente da do switch.
    #
    # Observado em 2026-09-23 com 2 fatias: o OVS mostrava meter id=1 com taxa
    # 8000 kbps (fatia 1) enquanto o ONOS mostrava meter id=1 com taxa 3000 kbps
    # (fatia 2). Efeito pratico: a fatia 1 ficava SEM enforcement e a fatia 2
    # recebia um limite que nao era o seu — com o log anunciando sucesso.
    vistos = set()
    for spec in specs:
        taxa = rate_by_index[spec.index]
        payload = {
            "deviceId": dpid,
            "unit": "KB_PER_SEC",
            "burst": True,
            "bands": [{
                "type": "DROP",
                "rate": taxa,
                "burstSize": burst_by_index[spec.index],
            }],
        }
        result = _onos_request("POST", f"/onos/v1/meters/{dpid}", user, password, payload=payload)
        if result is None:
            print(f"[AVISO] POST meter da fatia {spec.index} falhou.")
            continue

        # Confirma que ESTE meter apareceu antes de criar o proximo.
        confirmado = None
        for _ in range(20):
            dados = _onos_request("GET", f"/onos/v1/meters/{dpid}", user, password) or {}
            for m in dados.get("meters", []):
                mid = m.get("id")
                if mid in vistos:
                    continue
                for band in m.get("bands", []):
                    if band.get("rate") == taxa:
                        confirmado = mid
                        break
                if confirmado:
                    break
            if confirmado:
                break
            time.sleep(0.5)

        if confirmado is None:
            print(f"[AVISO] meter da fatia {spec.index} (taxa {taxa} kbps) nao foi "
                  f"confirmado no ONOS apos 10s.")
        else:
            vistos.add(confirmado)

    meters_data = _onos_request("GET", f"/onos/v1/meters/{dpid}", user, password)
    if not meters_data:
        print("[AVISO] Não foi possível obter IDs dos meters — flows sem QoS enforcement.")
        return {}

    # Mapeia cada fatia ao SEU meter, consumindo cada id uma unica vez.
    #
    # A versao anterior montava um dicionario taxa -> id. Como os QOS_PROFILES
    # se repetem ciclicamente, duas fatias com o mesmo AMBR colapsavam na mesma
    # chave e passavam a compartilhar um unico meter — ou seja, dividiam um
    # limite agregado em vez de terem um limite cada, enquanto o log informava
    # que N meters haviam sido instalados. Observado em 2026-09-09 com 4 fatias:
    # "Meter fatia 1: id=3" e "Meter fatia 3: id=3", com dois meters orfaos.
    available = []
    for m in meters_data.get("meters", []):
        for band in m.get("bands", []):
            r = band.get("rate")
            if r in rate_by_index.values():
                available.append((m.get("id"), r))
                break

    meter_ids = {}
    used = set()
    for spec in specs:
        target_rate = rate_by_index[spec.index]
        meter_id = None
        for mid, r in available:
            if r == target_rate and mid not in used:
                meter_id = mid
                used.add(mid)
                break
        if meter_id is None:
            print(
                f"[AVISO] nenhum meter disponivel para a fatia {spec.index} "
                f"(taxa {target_rate} kbps) — esta fatia ficara SEM enforcement de QoS."
            )
        meter_ids[spec.index] = meter_id
        print(f"Meter fatia {spec.index}: id={meter_id} rate={target_rate} kbps")

    distintos = len({v for v in meter_ids.values() if v is not None})
    if distintos != len(specs):
        print(
            f"[AVISO] {distintos} meter(s) distinto(s) para {len(specs)} fatia(s): "
            f"ha fatias compartilhando limite agregado."
        )

    # Confere a visao do ONOS contra a do switch. As duas podem divergir (o ONOS
    # registra como criado um meter que o switch rejeitou), e nesse caso o
    # enforcement real e o do switch — o que o ONOS relata nao vale como
    # evidencia.
    try:
        dump = run("ovs-ofctl -O OpenFlow13 dump-meters s1", check=False)
        if dump.stdout:
            taxas_switch = sorted(int(m) for m in re.findall(r"rate=(\d+)", dump.stdout))
            taxas_esperadas = sorted(rate_by_index.values())
            if taxas_switch != taxas_esperadas:
                print(f"[AVISO] divergencia ONOS x switch — taxas no switch: "
                      f"{taxas_switch} kbps, esperadas: {taxas_esperadas} kbps. "
                      f"O enforcement efetivo e o do switch.")
            else:
                print(f"Meters confirmados no switch: {taxas_switch} kbps")
    except Exception as e:
        print(f"[AVISO] nao foi possivel conferir os meters no switch: {e}")

    return meter_ids


def get_container_network_ip(container_name: str, network_name: str = "open5gs") -> str:
    result = run(
        f"docker inspect -f '{{{{index .NetworkSettings.Networks \"{network_name}\" \"IPAddress\"}}}}' {container_name}",
        check=False,
    )
    return result.stdout.strip()


def get_docker_network_subnet(network_name: str = "open5gs") -> str:
    out = run(f"docker network inspect {network_name}", check=False).stdout
    try:
        return json.loads(out)[0]["IPAM"]["Config"][0]["Subnet"]
    except (json.JSONDecodeError, KeyError, IndexError):
        print(f"[AVISO] não consegui descobrir a subnet da rede {network_name}")
        return ""


def get_container_bridge_ip(container_name: str) -> str:
    result = run(
        f"docker inspect -f '{{{{.NetworkSettings.Networks.bridge.IPAddress}}}}' {container_name}",
        check=False,
    )
    return result.stdout.strip()


def install_mgmt_isolation_rules(specs, bridge_ips: dict):
    # Chave por NOME de UE: com multiplos UEs por fatia, cada container tem seu
    # proprio IP na bridge docker0 e precisa da regra correspondente.
    for spec in specs:
        for ue in spec.ues:
            src = bridge_ips.get(ue.name)
            if not src:
                print(f"[AVISO] IP Docker nao encontrado para {ue.container}, pulando regras.")
                continue
            _mgmt_rules_for(src, other_subnets(specs, spec.index))
    print(f"Isolamento mgmt plane: {bridge_ips}")


def _mgmt_rules_for(src, destinos):
    for dst in destinos:
        run(
            f"while iptables-legacy -D FORWARD -s {src} -d {dst} "
            "-m comment --comment FAIR5G-SLICE-ISO-MGMT 2>/dev/null; do :; done",
            check=False,
        )
        run(
            f"iptables-legacy -I FORWARD 1 -s {src} -d {dst} "
            "-m comment --comment FAIR5G-SLICE-ISO-MGMT -j DROP"
        )


def install_upf_isolation_rules(specs, core_subnet: str = ""):
    # O isolamento precisa ser aplicado DENTRO do container da UPF, não no host: a UPF
    # tem uma regra própria de MASQUERADE em POSTROUTING (`!ogstun 10.4X.0.0/16 -> 0.0.0.0/0`)
    # que reescreve o IP de origem da sessão PDU antes do pacote chegar ao host. Regras no
    # FORWARD do host casando em `-s 10.4X.0.0/16` nunca veem esse tráfego. Dentro da UPF o
    # FORWARD roda antes do POSTROUTING, então o IP original ainda está visível.
    for spec in specs:
        cname = f"upf{spec.index}"
        # Além das outras fatias, a subnet do próprio core: tráfego de sessão PDU não deve
        # alcançar o plano de gerência (AMF/SMF/NRF/UPFs vizinhas). Bloquear o destino não
        # afeta a saída para a internet — o gateway em 10.33.33.1 é só next-hop, o campo de
        # destino do pacote continua sendo o endereço externo.
        deny_targets = list(other_subnets(specs, spec.index))
        if core_subnet:
            deny_targets.append(core_subnet)

        # FORWARD cobre o que ATRAVESSA a UPF; INPUT cobre o que é destinado À PRÓPRIA
        # UPF (ex.: um UE pingando o IP de gerência da UPF onde sua sessão termina —
        # esse tráfego é entregue localmente e nunca passa pelo FORWARD).
        for chain in ("FORWARD", "INPUT"):
            for target in deny_targets:
                docker_exec(
                    cname,
                    f"while iptables -D {chain} -s {spec.upf_subnet} -d {target} "
                    "-m comment --comment FAIR5G-SLICE-ISO-UPF -j DROP 2>/dev/null; do :; done",
                    check=False,
                )
                result = docker_exec(
                    cname,
                    f"iptables -I {chain} 1 -s {spec.upf_subnet} -d {target} "
                    "-m comment --comment FAIR5G-SLICE-ISO-UPF -j DROP",
                    check=False,
                )
                if result.returncode != 0:
                    print(f"[AVISO] não consegui aplicar isolamento em {cname} {chain} → {target}")
    print(f"Isolamento aplicado dentro das UPFs (antes do masquerade) em {len(specs)} fatia(s).")


def cleanup_mgmt_isolation_rules():
    specs = get_slice_specs()
    for spec in specs:
        for ue in spec.ues:
            ip = get_container_bridge_ip(ue.container)
            if not ip:
                continue
            _cleanup_mgmt_for(ip, other_subnets(specs, spec.index))


def _cleanup_mgmt_for(ip, destinos):
    for deny_subnet in destinos:
        run(
            f"while iptables-legacy -D FORWARD -s {ip} -d {deny_subnet} "
            "-m comment --comment FAIR5G-SLICE-ISO-MGMT 2>/dev/null; do :; done",
            check=False,
        )


def ensure_onos():
    name = "onos-controller"
    image = os.getenv("FAIR5G_ONOS_IMAGE", "onosproject/onos:2.7.0")
    user = os.getenv("FAIR5G_ONOS_USER", "onos")
    password = os.getenv("FAIR5G_ONOS_PASS", "rocks")

    cid = run(f"docker ps -aq -f name=^{name}$", check=False).stdout.strip()
    if cid:
        running = run(f"docker inspect -f '{{{{.State.Running}}}}' {name}", check=False).stdout.strip() == "true"
        if not running:
            print("ONOS existe (parado). Iniciando...")
            run(f"docker start {name}")
        else:
            print("ONOS já está rodando. OK.")
    else:
        print("Iniciando container ONOS (novo)...")
        run(
            "docker run -d --name onos-controller "
            "-p 8181:8181 -p 8101:8101 -p 6653:6653 -p 6633:6633 "
            f"{image}"
        )

    if not wait_for_onos(user, password):
        raise RuntimeError("ONOS não respondeu via API")


def ensure_veth_and_iptables(bridge_name: str):
    run("ip link delete veth-sdn 2>/dev/null || true", check=False)
    run("ip link add veth-sdn type veth peer name veth-docker")
    run(f"ip link set veth-docker master {bridge_name}")
    run("ip link set veth-sdn up")
    run("ip link set veth-docker up")

    run(
        "while iptables -D DOCKER-USER -m comment --comment FAIR5G -j ACCEPT 2>/dev/null; do :; done",
        check=False,
    )
    run("iptables -I DOCKER-USER 1 -m comment --comment FAIR5G -j ACCEPT", check=False)

    specs = get_slice_specs()
    for spec in specs:
        for other in other_subnets(specs, spec.index):
            run(
                f"while iptables-legacy -D FORWARD -s {spec.upf_subnet} -d {other} "
                "-m comment --comment FAIR5G-SLICE-ISO 2>/dev/null; do :; done",
                check=False,
            )
            run(
                f"iptables-legacy -I FORWARD 1 -s {spec.upf_subnet} -d {other} "
                "-m comment --comment FAIR5G-SLICE-ISO -j DROP"
            )
    print(f"Isolamento cross-slice aplicado entre {len(specs)} fatia(s): "
          f"{', '.join(s.upf_subnet for s in specs)}")


def docker_exec(cname: str, cmd: str, check: bool = True):
    return run(f"docker exec {cname} sh -c {json.dumps(cmd)}", check=check)


def configure_ue(container_suffix: str, cfg_file: str):
    cname = f"mn.{container_suffix}"
    cfg_path = f"/UERANSIM/config/{cfg_file}"
    log_file = f"/tmp/{container_suffix}.log"

    if docker_exec(cname, f"test -f {cfg_path}", check=False).returncode != 0:
        print(f"[ERRO] {cname}: {cfg_path} não é arquivo.")
        docker_exec(cname, "ls -la /UERANSIM/config | head -n 120", check=False)
        raise RuntimeError("Config de UE inválida (mount errado)")

    docker_exec(cname, "mkdir -p /dev/net")
    docker_exec(cname, "test -e /dev/net/tun || mknod /dev/net/tun c 10 200", check=False)
    docker_exec(cname, "chmod 666 /dev/net/tun || true", check=False)
    docker_exec(cname, f"ip link set {container_suffix}-eth0 up", check=False)

    docker_exec(cname, f"rm -f {log_file} && touch {log_file}")
    docker_exec(cname, "pkill -f /UERANSIM/nr-ue 2>/dev/null || true", check=False)

    docker_exec(cname, f"nohup /UERANSIM/nr-ue -c {cfg_path} >> {log_file} 2>&1 &")
    print(f"{container_suffix} iniciado. Log: {log_file}")


def cleanup_host_artifacts():
    run("ip link delete veth-sdn 2>/dev/null || true", check=False)
    run(
        "while iptables -D DOCKER-USER -m comment --comment FAIR5G -j ACCEPT 2>/dev/null; do :; done",
        check=False,
    )
    specs = get_slice_specs()
    for spec in specs:
        for other in other_subnets(specs, spec.index):
            run(
                f"while iptables-legacy -D FORWARD -s {spec.upf_subnet} -d {other} "
                "-m comment --comment FAIR5G-SLICE-ISO 2>/dev/null; do :; done",
                check=False,
            )
    cleanup_mgmt_isolation_rules()
    preclean_mn_containers()


def run_topology():
    setLogLevel("info")

    specs = get_slice_specs()
    print(f"Provisionando {len(specs)} fatia(s): {[s.index for s in specs]}")

    config_dir = detect_config_dir(specs)
    preclean_mn_containers()

    print("Configurando Controlador ONOS...")
    ensure_onos()

    print("Configurando Cabos Virtuais...")
    # O veth liga o switch OVS (onde ficam os UEs) a rede de ACESSO. O core fica em
    # outra bridge, sem caminho L2/L3 a partir daqui — a isolacao do Docker entre redes
    # bloqueia access<->core, e o gNB e a unica travessia (em nivel de aplicacao).
    bridge_name = get_docker_bridge_name(ACCESS_NETWORK)
    ensure_veth_and_iptables(bridge_name)

    user = os.getenv("FAIR5G_ONOS_USER", "onos")
    password = os.getenv("FAIR5G_ONOS_PASS", "rocks")

    net = None
    try:
        print("Iniciando Topologia Mininet...")
        net = Containernet(controller=RemoteController)

        info("*** Adicionando Controlador\n")
        net.addController("c0", controller=RemoteController, ip="127.0.0.1", port=6653)

        info("*** Adicionando Switch\n")
        s1 = net.addSwitch("s1", cls=OVSKernelSwitch, protocols="OpenFlow13")

        ues = {}
        for spec in specs:
            for ue in spec.ues:
                info(f"*** Adicionando {ue.name.upper()} (fatia {spec.index})\n")
                ues[ue.name] = net.addDocker(
                    ue.name,
                    ip=f"{ue.access_ip}/24",
                    dimage=UE_IMAGE,
                    privileged=True,
                    volumes=[f"{config_dir}:/UERANSIM/config:ro"],
                    dcmd="sleep infinity",
                )

        info("*** Conectando Componentes\n")
        for spec in specs:
            for ue in spec.ues:
                net.addLink(ues[ue.name], s1)

        Intf("veth-sdn", node=s1)

        info("*** Iniciando a Rede\n")
        net.start()

        print("Configurando flows de fatiamento no SDN...")
        dpid = wait_for_switch(user, password)

        # As interfaces do switch seguem a ordem em que os links foram criados
        # (s1-eth1, s1-eth2, ...), que e a ordem dos UEs em `all_ues`. Com
        # multiplos UEs por fatia o indice da fatia deixa de servir como chave;
        # a chave passa a ser o nome do UE.
        ordem_ues = [ue for spec in specs for ue in spec.ues]
        ports = {
            ue.name: get_port_by_name(user, password, dpid, f"s1-eth{posicao}")
            for posicao, ue in enumerate(ordem_ues, start=1)
        }
        port_core = get_port_by_name(user, password, dpid, "veth-sdn")

        missing = [nome for nome, p in ports.items() if not p]
        if not port_core:
            missing.append("core")
        if missing:
            raise RuntimeError(f"Portas não encontradas no ONOS: {missing} (ports={ports}, core={port_core})")

        gnb_ip = get_container_network_ip("gnb", ACCESS_NETWORK)
        probe_ip = get_container_network_ip("blackbox", ACCESS_NETWORK)
        print(f"gNB na rede de acesso: {gnb_ip or 'NÃO DESCOBERTO'}")
        print(f"Probe (blackbox) na rede de acesso: {probe_ip or 'ausente'}")

        meter_ids = install_slice_meters(user, password, dpid, specs)
        install_slice_flows(user, password, dpid, specs, ports, port_core, meter_ids,
                            gnb_ip, [probe_ip] if probe_ip else [])
        # fwd fica ativo: nossos flows proativos já casam com todo pacote IPv4 de/para
        # um UE (table-miss nunca ocorre para esse tráfego), então o forwarding reativo
        # só é de fato acionado para ARP — que não tem flow próprio e travava o
        # registro NGAP de todos os UEs (ver diagnóstico da sessão de 2026-08-17).
        #
        # Não há re-instalação dinâmica de flows por sessão PDU: o tráfego do UE, mesmo
        # depois da sessão PDU ativa, sai do container sempre reencapsulado com o mesmo
        # endereçamento externo (IP Mininet do UE -> IP do gNB) — o IP do túnel
        # (uesimtun0) nunca aparece como cabeçalho externo no switch. Uma versão anterior
        # tentava trocar os flows para casar no IP do túnel a cada sessão, o que removia
        # as flows estáticas (que são as únicas que de fato batem) e deixava o fwd
        # reativo — sem noção de isolamento — assumir esse tráfego. Resultado: isolamento
        # cross-slice furado depois da primeira sessão PDU (confirmado em 2026-08-18 com
        # contadores de pacote do ONOS zerados nas flows dinâmicas e ping cross-slice
        # passando). As flows estáticas instaladas acima já cobrem 100% do tráfego real
        # do UE permanentemente — não removê-las.

        print("Configurando isolamento mgmt plane...")
        bridge_ips = {ue.name: get_container_bridge_ip(ue.container)
                      for spec in specs for ue in spec.ues}
        install_mgmt_isolation_rules(specs, bridge_ips)

        print("Configurando isolamento do plano de dados nas UPFs...")
        install_upf_isolation_rules(specs, get_docker_network_subnet("open5gs"))

        print("Iniciando Conexao 5G (UERANSIM)...")
        for spec in specs:
            for ue in spec.ues:
                configure_ue(ue.name, ue.config_file)

        print("\nAmbiente Pronto (Mininet)")
        primeiro = specs[0].ues[0].name
        print(f'Logs: {primeiro} sh -c "tail -f /tmp/{primeiro}.log"')
        if len(specs) > 1:
            print(f'Ping basico: {primeiro} ping -c 3 {specs[1].ue_mininet_ip}')
        print('Verificar flows: ovs-ofctl dump-flows s1\n')

        modo_detach = os.environ.get("FAIR5G_DETACH") == "1"

        if modo_detach:
            # Modo desacoplado: o ambiente deixa de depender de um terminal
            # interativo aberto.
            #
            # No modo padrao o processo termina abrindo a CLI do Containernet, e
            # e ESSE processo que mantem a topologia viva — sair do prompt
            # derruba switch, hosts e links. Isso inviabiliza campanha
            # experimental com repeticoes, porque cada rodada exigiria um humano
            # com o terminal aberto, e qualquer queda de sessao SSH descarta o
            # experimento em andamento.
            #
            # Aqui o processo apenas aguarda SIGTERM/SIGINT. A limpeza continua
            # no bloco `finally`, identica ao modo interativo, entao derrubar via
            # sinal produz exatamente o mesmo estado final que sair da CLI.
            import signal

            parar = threading.Event()

            def _encerrar(signum, _frame):
                print(f"\nSinal {signum} recebido — encerrando ambiente...")
                parar.set()

            signal.signal(signal.SIGTERM, _encerrar)
            signal.signal(signal.SIGINT, _encerrar)

            pid_file = os.path.join(REPO_ROOT, ".fair5g_topology.pid")
            try:
                with open(pid_file, "w") as fh:
                    fh.write(str(os.getpid()))
            except Exception as e:
                print(f"[AVISO] nao foi possivel gravar o arquivo de pid: {e}")

            print(f"Modo desacoplado ativo (pid {os.getpid()}).")
            print("O ambiente permanece no ar sem terminal interativo.")
            print(f"Para executar comandos nos UEs:  ./fair5g exec {specs[0].ues[0].name} <comando>")
            print("Para derrubar:                   ./fair5g down\n")
            parar.wait()

            try:
                os.remove(pid_file)
            except FileNotFoundError:
                pass
            except Exception:
                pass
        else:
            # Valida as pos-condicoes do ambiente ANTES de entregar o terminal.
            #
            # Aqui a saida sai em terminal normal e em ordem. Enquanto o verify era
            # disparado pelo up_v0.sh, ele escrevia em paralelo com a CLI do
            # Containernet, que ja havia posto o terminal em modo raw (cbreak): o
            # '\n' deixava de voltar a coluna 0 e as linhas saiam escalonadas e
            # intercaladas com o prompt.
            #
            # check=False de proposito: uma pos-condicao reprovada avisa, mas nao
            # derruba a topologia — quem decide se os dados servem e o operador.
            verificador = os.path.join(REPO_ROOT, "scripts", "verify_up.py")
            if os.path.isfile(verificador):
                # subprocess.run direto, nao o helper run(): aquele usa
                # capture_output=True e engoliria o relatorio do verify.
                subprocess.run(f"python3 {verificador}", shell=True)

            roteiro = os.getenv("FAIR5G_CLI_SCRIPT") or ""
            if roteiro and os.path.isfile(roteiro):
                # Modo roteirizado: alimenta a CLI do Containernet com um arquivo
                # de comandos em vez de esperar digitacao.
                #
                # E o que viabiliza campanha experimental sem depender de um
                # terminal humano: o roteiro executa a bateria de medicoes e
                # termina com `exit`, encerrando a topologia pelo mesmo caminho do
                # modo interativo — mesma limpeza, mesmo estado final.
                #
                # A CLI aceita tanto comandos em hosts (`ue1_1 iperf3 ...`) quanto
                # comandos no hospedeiro via `sh` (`sh sudo docker exec ...`), de
                # modo que uma repeticao inteira cabe em um unico arquivo.
                print(f"Executando roteiro: {roteiro}")
                # Usa o parametro `script` da CLI, que le o arquivo e retorna ao
                # final. Alimentar via stdin nao funcionaria: a CLI registra a
                # entrada padrao em um poller, que exige descritor de arquivo real.
                CLI(net, script=roteiro)
                print("Roteiro concluido; encerrando a topologia.")
            else:
                if roteiro:
                    print(f"[AVISO] roteiro nao encontrado: {roteiro}. Abrindo CLI interativa.")
                CLI(net)

    finally:
        print("Limpando ambiente...")
        try:
            if net is not None:
                net.stop()
        except Exception:
            pass
        cleanup_host_artifacts()


if __name__ == "__main__":
    if os.geteuid() != 0:
        print("Execute como ROOT (sudo).")
        sys.exit(1)
    run_topology()
