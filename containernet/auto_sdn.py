#!/usr/bin/env python3
import os
import time
import subprocess
import json
import sys

from mininet.net import Containernet
from mininet.node import RemoteController, OVSKernelSwitch
from mininet.cli import CLI
from mininet.link import Intf
from mininet.log import info, setLogLevel

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))


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


def activate_app_rest(app_name: str, user: str, password: str):
    print(f"Ativando App via API: {app_name}")
    cmd = (
        f"curl --fail -s -o /dev/null "
        f"-u {user}:{password} "
        f"-X POST http://localhost:8181/onos/v1/applications/{app_name}/active"
    )
    return run(cmd, check=False).returncode == 0


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
    # veth
    run("ip link delete veth-sdn 2>/dev/null || true", check=False)
    run("ip link add veth-sdn type veth peer name veth-docker")
    run(f"ip link set veth-docker master {bridge_name}")
    run("ip link set veth-sdn up")
    run("ip link set veth-docker up")

    # iptables: remove SOMENTE regra FAIR5G
    run(
        "while iptables -D DOCKER-USER -m comment --comment FAIR5G -j ACCEPT 2>/dev/null; do :; done",
        check=False,
    )
    run("iptables -I DOCKER-USER 1 -m comment --comment FAIR5G -j ACCEPT", check=False)


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

        print("Iniciando Conexao 5G (UERANSIM)...")
        configure_ue("ue1", "ue1.yaml")
        configure_ue("ue2", "ue2.yaml")

        print("\nAmbiente Pronto (Mininet)")
        print('Logs: ue1 sh -c "tail -f /tmp/ue1.log"')
        print('Ping básico: ue1 ping -c 3 10.33.33.201\n')

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

