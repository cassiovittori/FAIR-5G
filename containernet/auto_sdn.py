#!/usr/bin/env python3
import os
import time
import subprocess
import json
import sys
import base64
import urllib.request
import urllib.error

from mininet.net import Containernet
from mininet.node import RemoteController, OVSKernelSwitch
from mininet.cli import CLI
from mininet.link import Intf
from mininet.log import info, setLogLevel

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))

_UPF1_SUBNET = "10.45.0.0/16"
_UPF2_SUBNET = "10.46.0.0/16"


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


def detect_config_dir():
    env = os.getenv("FAIR5G_CONFIG_DIR")
    candidates = []
    if env:
        candidates.append(env)

    candidates += [
        os.path.join(REPO_ROOT, "configs", "runtime"),
        os.path.join(REPO_ROOT, "configs", "network-slicing"),
    ]

    for d in candidates:
        if os.path.isfile(os.path.join(d, "ue1.yaml")) and os.path.isfile(os.path.join(d, "ue2.yaml")):
            print(f"Usando CONFIG_DIR: {d}")
            return d

    print("\n[ERRO] Não achei ue1.yaml/ue2.yaml em nenhum candidato.")
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


def install_slice_flows(user: str, password: str, dpid: str,
                        port_ue1: str, port_ue2: str, port_core: str) -> bool:
    ue1_ip = "10.33.33.200"
    ue2_ip = "10.33.33.201"

    flows = [
        {
            "priority": 200, "isPermanent": True,
            "selector": {"criteria": [
                {"type": "ETH_TYPE", "ethType": "0x0800"},
                {"type": "IPV4_SRC", "ip": f"{ue1_ip}/32"},
                {"type": "IPV4_DST", "ip": _UPF2_SUBNET},
            ]},
            "treatment": {"instructions": [{"type": "NOACTION"}]},
        },
        {
            "priority": 200, "isPermanent": True,
            "selector": {"criteria": [
                {"type": "ETH_TYPE", "ethType": "0x0800"},
                {"type": "IPV4_SRC", "ip": f"{ue2_ip}/32"},
                {"type": "IPV4_DST", "ip": _UPF1_SUBNET},
            ]},
            "treatment": {"instructions": [{"type": "NOACTION"}]},
        },
        {
            "priority": 100, "isPermanent": True,
            "selector": {"criteria": [
                {"type": "ETH_TYPE", "ethType": "0x0800"},
                {"type": "IPV4_SRC", "ip": f"{ue1_ip}/32"},
            ]},
            "treatment": {"instructions": [{"type": "OUTPUT", "port": str(port_core)}]},
        },
        {
            "priority": 100, "isPermanent": True,
            "selector": {"criteria": [
                {"type": "ETH_TYPE", "ethType": "0x0800"},
                {"type": "IPV4_SRC", "ip": f"{ue2_ip}/32"},
            ]},
            "treatment": {"instructions": [{"type": "OUTPUT", "port": str(port_core)}]},
        },
        {
            "priority": 100, "isPermanent": True,
            "selector": {"criteria": [
                {"type": "ETH_TYPE", "ethType": "0x0800"},
                {"type": "IPV4_DST", "ip": f"{ue1_ip}/32"},
            ]},
            "treatment": {"instructions": [{"type": "OUTPUT", "port": str(port_ue1)}]},
        },
        {
            "priority": 100, "isPermanent": True,
            "selector": {"criteria": [
                {"type": "ETH_TYPE", "ethType": "0x0800"},
                {"type": "IPV4_DST", "ip": f"{ue2_ip}/32"},
            ]},
            "treatment": {"instructions": [{"type": "OUTPUT", "port": str(port_ue2)}]},
        },
    ]

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


def get_container_bridge_ip(container_name: str) -> str:
    result = run(
        f"docker inspect -f '{{{{.NetworkSettings.Networks.bridge.IPAddress}}}}' {container_name}",
        check=False,
    )
    return result.stdout.strip()


def install_mgmt_isolation_rules(ue1_bridge_ip: str, ue2_bridge_ip: str):
    pairs = [(ue1_bridge_ip, _UPF2_SUBNET), (ue2_bridge_ip, _UPF1_SUBNET)]
    for src, dst in pairs:
        if not src:
            print(f"[AVISO] IP Docker não encontrado para container, pulando regra → {dst}")
            continue
        run(
            f"while iptables-legacy -D FORWARD -s {src} -d {dst} "
            "-m comment --comment FAIR5G-SLICE-ISO-MGMT 2>/dev/null; do :; done",
            check=False,
        )
        run(
            f"iptables-legacy -I FORWARD 1 -s {src} -d {dst} "
            "-m comment --comment FAIR5G-SLICE-ISO-MGMT -j DROP"
        )
    print(f"Isolamento mgmt plane: mn.ue1={ue1_bridge_ip}, mn.ue2={ue2_bridge_ip}")


def cleanup_mgmt_isolation_rules():
    for cname, deny_subnet in [("mn.ue1", _UPF2_SUBNET), ("mn.ue2", _UPF1_SUBNET)]:
        ip = get_container_bridge_ip(cname)
        if ip:
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

    run(
        f"while iptables-legacy -D FORWARD -s {_UPF1_SUBNET} -d {_UPF2_SUBNET} "
        "-m comment --comment FAIR5G-SLICE-ISO 2>/dev/null; do :; done",
        check=False,
    )
    run(
        f"while iptables-legacy -D FORWARD -s {_UPF2_SUBNET} -d {_UPF1_SUBNET} "
        "-m comment --comment FAIR5G-SLICE-ISO 2>/dev/null; do :; done",
        check=False,
    )
    run(
        f"iptables-legacy -I FORWARD 1 -s {_UPF1_SUBNET} -d {_UPF2_SUBNET} "
        "-m comment --comment FAIR5G-SLICE-ISO -j DROP"
    )
    run(
        f"iptables-legacy -I FORWARD 1 -s {_UPF2_SUBNET} -d {_UPF1_SUBNET} "
        "-m comment --comment FAIR5G-SLICE-ISO -j DROP"
    )
    print(f"Isolamento cross-slice aplicado: {_UPF1_SUBNET} ↔ {_UPF2_SUBNET}")


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
    run(
        f"while iptables-legacy -D FORWARD -s {_UPF1_SUBNET} -d {_UPF2_SUBNET} "
        "-m comment --comment FAIR5G-SLICE-ISO 2>/dev/null; do :; done",
        check=False,
    )
    run(
        f"while iptables-legacy -D FORWARD -s {_UPF2_SUBNET} -d {_UPF1_SUBNET} "
        "-m comment --comment FAIR5G-SLICE-ISO 2>/dev/null; do :; done",
        check=False,
    )
    cleanup_mgmt_isolation_rules()
    preclean_mn_containers()


def run_topology():
    setLogLevel("info")

    config_dir = detect_config_dir()
    preclean_mn_containers()

    print("Configurando Controlador ONOS...")
    ensure_onos()

    print("Configurando Cabos Virtuais...")
    bridge_name = get_docker_bridge_name("open5gs")
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

        info("*** Adicionando UE1\n")
        ue1 = net.addDocker(
            "ue1",
            ip="10.33.33.200/24",
            dimage="ghcr.io/borjis131/ue:v3.2.7",
            privileged=True,
            volumes=[f"{config_dir}:/UERANSIM/config:ro"],
            dcmd="sleep infinity",
        )

        info("*** Adicionando UE2\n")
        ue2 = net.addDocker(
            "ue2",
            ip="10.33.33.201/24",
            dimage="ghcr.io/borjis131/ue:v3.2.7",
            privileged=True,
            volumes=[f"{config_dir}:/UERANSIM/config:ro"],
            dcmd="sleep infinity",
        )

        info("*** Conectando Componentes\n")
        net.addLink(ue1, s1)
        net.addLink(ue2, s1)

        Intf("veth-sdn", node=s1)

        info("*** Iniciando a Rede\n")
        net.start()

        print("Configurando flows de fatiamento no SDN...")
        dpid = wait_for_switch(user, password)

        port_ue1 = get_port_by_name(user, password, dpid, "s1-eth1")
        port_ue2 = get_port_by_name(user, password, dpid, "s1-eth2")
        port_core = get_port_by_name(user, password, dpid, "veth-sdn")

        if not all([port_ue1, port_ue2, port_core]):
            raise RuntimeError(
                f"Portas não encontradas no ONOS — ue1={port_ue1}, ue2={port_ue2}, core={port_core}"
            )

        install_slice_flows(user, password, dpid, port_ue1, port_ue2, port_core)
        deactivate_app_rest("org.onosproject.fwd", user, password)

        print("Configurando isolamento mgmt plane...")
        ue1_bridge_ip = get_container_bridge_ip("mn.ue1")
        ue2_bridge_ip = get_container_bridge_ip("mn.ue2")
        install_mgmt_isolation_rules(ue1_bridge_ip, ue2_bridge_ip)

        print("Iniciando Conexao 5G (UERANSIM)...")
        configure_ue("ue1", "ue1.yaml")
        configure_ue("ue2", "ue2.yaml")

        print("\nAmbiente Pronto (Mininet)")
        print('Logs: ue1 sh -c "tail -f /tmp/ue1.log"')
        print('Ping básico: ue1 ping -c 3 10.33.33.201')
        print('Verificar flows: ovs-ofctl dump-flows s1\n')

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
