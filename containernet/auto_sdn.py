#!/usr/bin/env python3
import os
import sys
import time
import json
import subprocess
from pathlib import Path
from base64 import b64encode
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

from mininet.net import Containernet
from mininet.node import RemoteController, OVSKernelSwitch
from mininet.cli import CLI
from mininet.link import Intf
from mininet.log import setLogLevel, info


# -----------------------------
# Config (V0)
# -----------------------------
NETWORK_NAME = os.environ.get("FAIR5G_DOCKER_NETWORK", "open5gs")
GNB_CONTAINER = os.environ.get("FAIR5G_GNB_CONTAINER", "gnb")

ONOS_CONTAINER = os.environ.get("FAIR5G_ONOS_CONTAINER", "onos-controller")
ONOS_IMAGE = os.environ.get("FAIR5G_ONOS_IMAGE", "onosproject/onos:2.7.0")
ONOS_REST = os.environ.get("FAIR5G_ONOS_REST", "http://localhost:8181/onos/v1")
ONOS_USER = os.environ.get("FAIR5G_ONOS_USER", "onos")
ONOS_PASS = os.environ.get("FAIR5G_ONOS_PASS", "rocks")
ONOS_OF_PORT = int(os.environ.get("FAIR5G_ONOS_OF_PORT", "6653"))

UE_IMAGE = os.environ.get("FAIR5G_UE_IMAGE", "ghcr.io/borjis131/ue:v3.2.7")

VETH_HOST = os.environ.get("FAIR5G_VETH_HOST", "veth-sdn")
VETH_DOCKER = os.environ.get("FAIR5G_VETH_DOCKER", "veth-docker")


def run_cmd(cmd, check=True, capture=False, text=True):
    """Run command. cmd can be list or str (shell)."""
    if isinstance(cmd, list):
        res = subprocess.run(cmd, check=check, capture_output=capture, text=text)
    else:
        res = subprocess.run(cmd, shell=True, check=check, capture_output=capture, text=text)
    return res


def docker_ps_has(name: str) -> bool:
    try:
        out = run_cmd(["docker", "ps", "--format", "{{.Names}}"], capture=True).stdout
        return any(line.strip() == name for line in out.splitlines())
    except Exception:
        return False


def docker_container_ip(container_name: str, network_name: str) -> str:
    # prefer IP from the specified network
    try:
        out = run_cmd(["docker", "inspect", container_name], capture=True).stdout
        data = json.loads(out)[0]
        nets = data.get("NetworkSettings", {}).get("Networks", {})
        if network_name in nets and "IPAddress" in nets[network_name]:
            ip = nets[network_name]["IPAddress"]
            if ip:
                return ip
        # fallback: first network IP
        for _, v in nets.items():
            ip = v.get("IPAddress")
            if ip:
                return ip
    except subprocess.CalledProcessError:
        raise RuntimeError(f"Container '{container_name}' não encontrado (docker inspect falhou).")
    except Exception as e:
        raise RuntimeError(f"Falha ao obter IP do container '{container_name}': {e}")
    raise RuntimeError(f"Não consegui obter IP do container '{container_name}'.")


def get_docker_bridge_name(network_name: str) -> str:
    try:
        info(f"Buscando ponte para rede: {network_name}\n")
        out = run_cmd(["docker", "network", "inspect", network_name], capture=True).stdout
        data = json.loads(out)
        bridge_name = (data[0].get("Options") or {}).get("com.docker.network.bridge.name")

        if not bridge_name:
            net_id = data[0]["Id"][:12]
            bridge_name = f"br-{net_id}"

        info(f"Ponte encontrada: {bridge_name}\n")
        return bridge_name
    except subprocess.CalledProcessError:
        raise RuntimeError(f"Rede docker '{network_name}' não existe. Suba o compose antes.")
    except Exception as e:
        raise RuntimeError(f"Erro ao detectar ponte da rede '{network_name}': {e}")


def onos_request(method: str, path: str) -> bool:
    url = f"{ONOS_REST.rstrip('/')}/{path.lstrip('/')}"
    auth = b64encode(f"{ONOS_USER}:{ONOS_PASS}".encode()).decode()
    req = Request(url, method=method)
    req.add_header("Authorization", f"Basic {auth}")
    try:
        with urlopen(req, timeout=3) as r:
            _ = r.read()
        return True
    except HTTPError:
        return False
    except URLError:
        return False
    except Exception:
        return False


def activate_onos_app(app_name: str) -> bool:
    info(f"Ativando App via API: {app_name}\n")
    return onos_request("POST", f"applications/{app_name}/active")


def wait_for_onos(max_retries=60, sleep_s=2) -> bool:
    info("Aguardando API do ONOS iniciar...\n")
    for i in range(max_retries):
        # tenta ativar OpenFlow para validar API
        if activate_onos_app("org.onosproject.openflow"):
            info("ONOS API pronta e Apps ativados.\n")
            activate_onos_app("org.onosproject.fwd")
            return True
        time.sleep(sleep_s)
        info(f"Tentativa {i+1}/{max_retries}\n")
    return False


def ensure_onos():
    info("Configurando Controlador ONOS...\n")
    if not docker_ps_has(ONOS_CONTAINER):
        info("Iniciando container ONOS...\n")
        run_cmd([
            "docker", "run", "-d", "--name", ONOS_CONTAINER,
            "-p", "8181:8181",
            "-p", "8101:8101",
            "-p", f"{ONOS_OF_PORT}:{ONOS_OF_PORT}",
            "-p", "6633:6633",
            ONOS_IMAGE
        ], check=True)

    if not wait_for_onos():
        raise RuntimeError("ERRO: ONOS não respondeu via API (8181).")


def iptables_rule_exists() -> bool:
    # checa se a regra já existe (iptables -C)
    try:
        run_cmd(["iptables", "-C", "DOCKER-USER", "-j", "ACCEPT"], check=True)
        return True
    except subprocess.CalledProcessError:
        return False


def iptables_insert_accept():
    try:
        if not iptables_rule_exists():
            run_cmd(["iptables", "-I", "DOCKER-USER", "-j", "ACCEPT"], check=True)
    except Exception:
        # V0: se falhar, segue (muitas vezes não é necessário)
        pass


def iptables_remove_accept():
    try:
        if iptables_rule_exists():
            run_cmd(["iptables", "-D", "DOCKER-USER", "-j", "ACCEPT"], check=False)
    except Exception:
        pass


def setup_veth_to_docker_bridge(bridge_name: str):
    info("Configurando Cabos Virtuais...\n")

    # remove veth anterior
    run_cmd(f"ip link delete {VETH_HOST} 2>/dev/null", check=False)

    # cria veth pair e conecta no bridge do docker
    run_cmd(["ip", "link", "add", VETH_HOST, "type", "veth", "peer", "name", VETH_DOCKER], check=True)
    run_cmd(["ip", "link", "set", VETH_DOCKER, "master", bridge_name], check=True)
    run_cmd(["ip", "link", "set", VETH_HOST, "up"], check=True)
    run_cmd(["ip", "link", "set", VETH_DOCKER, "up"], check=True)

    # regra (V0)
    iptables_insert_accept()


def render_runtime_ue_config(src: Path, dst: Path, gnb_ip: str):
    """
    Substitui bloco gnbSearchList por:
      gnbSearchList:
        - <gnb_ip>
    sem depender de PyYAML.
    """
    lines = src.read_text(encoding="utf-8").splitlines(True)
    out = []
    in_list = False
    for line in lines:
        if line.strip() == "gnbSearchList:":
            out.append("gnbSearchList:\n")
            out.append(f"  - {gnb_ip}\n")
            in_list = True
            continue

        if in_list:
            # pula itens do bloco anterior (linhas começando com "-" com indentação)
            stripped = line.lstrip()
            if stripped.startswith("- "):
                continue
            # terminou a lista
            in_list = False

        out.append(line)

    dst.write_text("".join(out), encoding="utf-8")


def prepare_runtime_configs(repo_root: Path) -> Path:
    template_dir = repo_root / "configs" / "network-slicing"
    runtime_dir = repo_root / "configs" / "runtime"
    runtime_dir.mkdir(parents=True, exist_ok=True)

    ue1_src = template_dir / "ue1.yaml"
    ue2_src = template_dir / "ue2.yaml"

    if not ue1_src.exists() or not ue2_src.exists():
        raise FileNotFoundError(f"Não achei ue1/ue2 em: {template_dir}")

    # IP real do gNB dentro da rede docker
    gnb_ip = docker_container_ip(GNB_CONTAINER, NETWORK_NAME)
    info(f"[runtime] gNB IP detectado: {gnb_ip}\n")

    render_runtime_ue_config(ue1_src, runtime_dir / "ue1.yaml", gnb_ip)
    render_runtime_ue_config(ue2_src, runtime_dir / "ue2.yaml", gnb_ip)

    return runtime_dir


def configure_ue_inside_container(host, config_file: str):
    info(f"Configurando {host.name}...\n")
    host.cmd("mkdir -p /dev/net")
    host.cmd("mknod /dev/net/tun c 10 200 || true")
    host.cmd("chmod 666 /dev/net/tun || true")
    host.cmd(f"ip link set {host.name}-eth0 up || true")

    log_file = f"/tmp/{host.name}.log"
    host.cmd(f"/UERANSIM/nr-ue -c /UERANSIM/config/{config_file} > {log_file} 2>&1 &")
    info(f"{host.name} iniciado. Log: {log_file}\n")


def run_topology():
    setLogLevel("info")

    if os.geteuid() != 0:
        print("Execute como ROOT (sudo).")
        sys.exit(1)

    # repo root = ../ (auto_sdn.py está em containernet/)
    repo_root = Path(__file__).resolve().parents[1]

    # garante ONOS e runtime configs
    ensure_onos()
    runtime_dir = prepare_runtime_configs(repo_root)

    # ponte do docker (br-ogs / br-<id>)
    bridge_name = get_docker_bridge_name(NETWORK_NAME)
    setup_veth_to_docker_bridge(bridge_name)

    net = None
    try:
        info("Iniciando Topologia Mininet...\n")
        net = Containernet(controller=RemoteController)

        info("*** Adicionando Controlador\n")
        net.addController("c0", controller=RemoteController, ip="127.0.0.1", port=ONOS_OF_PORT)

        info("*** Adicionando Switch\n")
        s1 = net.addSwitch("s1", cls=OVSKernelSwitch, protocols="OpenFlow13")

        info("*** Adicionando UE1\n")
        ue1 = net.addDocker(
            "ue1",
            ip="10.33.33.200/24",
            dimage=UE_IMAGE,
            privileged=True,
            volumes=[f"{(runtime_dir / 'ue1.yaml').as_posix()}:/UERANSIM/config/ue1.yaml:ro"],
            dcmd="sleep infinity",
        )

        info("*** Adicionando UE2\n")
        ue2 = net.addDocker(
            "ue2",
            ip="10.33.33.201/24",
            dimage=UE_IMAGE,
            privileged=True,
            volumes=[f"{(runtime_dir / 'ue2.yaml').as_posix()}:/UERANSIM/config/ue2.yaml:ro"],
            dcmd="sleep infinity",
        )

        info("*** Conectando Componentes\n")
        net.addLink(ue1, s1)
        net.addLink(ue2, s1)

        # conecta o switch ao veth que entra no bridge do docker
        Intf(VETH_HOST, node=s1)

        info("*** Iniciando a Rede\n")
        net.start()

        info("Iniciando Conexao 5G (UERANSIM)...\n")
        configure_ue_inside_container(ue1, "ue1.yaml")
        configure_ue_inside_container(ue2, "ue2.yaml")

        print("\nAmbiente Pronto (Containernet)")
        print("Logs do UE: tail -f /tmp/ue1.log\n")

        CLI(net)

    finally:
        print("Limpando ambiente...")
        try:
            if net is not None:
                net.stop()
        except Exception:
            pass

        run_cmd(f"ip link delete {VETH_HOST} 2>/dev/null", check=False)
        iptables_remove_accept()


if __name__ == "__main__":
    run_topology()
