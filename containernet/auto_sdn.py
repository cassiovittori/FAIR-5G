#!/usr/bin/python3
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

CONFIG_PATH = "/home/ubuntu/open5gs-mininet/configs/network-slicing"

def run_cmd(cmd, ignore_error=False, shell=True):
    try:
        subprocess.check_call(cmd, shell=shell)
    except subprocess.CalledProcessError:
        if not ignore_error:
            print(f"Erro ao executar: {cmd}")

def get_docker_bridge_name(network_name="open5gs"):
    try:
        print(f"Buscando ponte para rede: {network_name}")
        output = subprocess.check_output(f"docker network inspect {network_name}", shell=True)
        data = json.loads(output)
        
        bridge_name = data[0]['Options'].get('com.docker.network.bridge.name')
        
        if not bridge_name:
            net_id = data[0]['Id'][:12]
            bridge_name = f"br-{net_id}"
            
        print(f"Ponte encontrada: {bridge_name}")
        return bridge_name
    except Exception as e:
        print(f"Erro ao detectar ponte: {e}")
        print("Certifique-se de que o Open5GS esta rodando.")
        sys.exit(1)

def activate_app_rest(app_name):
    print(f"Ativando App via API: {app_name}")
    # Usa curl com autenticacao padrao do ONOS (karaf:karaf ou onos:rocks)
    # Tenta user onos:rocks (padrao docker)
    cmd = f"curl --fail -s -u onos:rocks -X POST http://localhost:8181/onos/v1/applications/{app_name}/active"
    try:
        subprocess.check_call(cmd, shell=True)
        return True
    except:
        return False

def wait_for_onos(port=8181, max_retries=60):
    print("Aguardando API do ONOS iniciar...")
    for i in range(max_retries):
        # Verifica a porta WEB (8181) em vez da SSH (8101)
        res = subprocess.call(f"nc -z localhost {port}", shell=True)
        if res == 0:
            # Tenta ativar o OpenFlow para ver se a API responde 200 OK
            if activate_app_rest("org.onosproject.openflow"):
                print("ONOS API pronta e Apps ativados.")
                activate_app_rest("org.onosproject.fwd")
                return True
        time.sleep(2)
        print(f"Tentativa {i+1}/{max_retries}")
    print("ERRO: ONOS nao respondeu via API.")
    return False

def setup_environment():
    print("Configurando Controlador ONOS...")
    check_onos = subprocess.call("docker ps | grep onos-controller", shell=True)
    if check_onos != 0:
        print("Iniciando container ONOS...")
        # Adicionei -p 8181:8181 explicitamente
        run_cmd("docker run -d --name onos-controller -p 8181:8181 -p 8101:8101 -p 6653:6653 -p 6633:6633 onosproject/onos:2.7.0")
    
    # A funcao wait_for_onos agora ja faz a ativacao via REST
    wait_for_onos()

    print("Configurando Cabos Virtuais...")
    bridge_name = get_docker_bridge_name()
    
    run_cmd("ip link delete veth-sdn 2>/dev/null", ignore_error=True)
    run_cmd("iptables -D DOCKER-USER -j ACCEPT 2>/dev/null", ignore_error=True)

    run_cmd("ip link add veth-sdn type veth peer name veth-docker")
    run_cmd(f"ip link set veth-docker master {bridge_name}")
    run_cmd("ip link set veth-sdn up")
    run_cmd("ip link set veth-docker up")
    run_cmd("iptables -I DOCKER-USER -j ACCEPT")
    
    return bridge_name

def configure_ue_inside_container(host, config_file):
    print(f"Configurando {host.name}...")
    host.cmd('mkdir -p /dev/net')
    host.cmd('mknod /dev/net/tun c 10 200')
    host.cmd('chmod 666 /dev/net/tun')
    host.cmd(f'ip link set {host.name}-eth0 up')
    
    log_file = f"/tmp/{host.name}.log"
    host.cmd(f"/UERANSIM/nr-ue -c /UERANSIM/config/{config_file} > {log_file} 2>&1 &")
    print(f"{host.name} iniciado. Log: {log_file}")

def run_topology():
    setLogLevel('info')
    
    setup_environment()
    
    print("Iniciando Topologia Mininet...")
    net = Containernet(controller=RemoteController)

    info('*** Adicionando Controlador\n')
    net.addController('c0', controller=RemoteController, ip='127.0.0.1', port=6653)

    info('*** Adicionando Switch\n')
    s1 = net.addSwitch('s1', cls=OVSKernelSwitch, protocols='OpenFlow13')

    info('*** Adicionando UE1\n')
    ue1 = net.addDocker('ue1', 
                        ip='10.33.33.200/24', 
                        dimage="ghcr.io/borjis131/ue:v3.2.7",
                        privileged=True,
                        volumes=[f"{CONFIG_PATH}/ue1.yaml:/UERANSIM/config/ue1.yaml"],
                        dcmd="sleep infinity")

    info('*** Adicionando UE2\n')
    ue2 = net.addDocker('ue2', ip='10.33.33.201/24', dimage="ghcr.io/borjis131/ue:v3.2.7", privileged=True, volumes=[f"{CONFIG_PATH}/ue2.yaml:/UERANSIM/config/ue2.yaml"], dcmd="sleep infinity")

    info('*** Conectando Componentes\n')
    net.addLink(ue1, s1)
    net.addLink(ue2, s1) 
    
    Intf('veth-sdn', node=s1)

    info('*** Iniciando a Rede\n')
    net.start()

    print("Iniciando Conexao 5G (UERANSIM)...")
    configure_ue_inside_container(ue1, "ue1.yaml")
    configure_ue_inside_container(ue2, "ue2.yaml") 

    print("\nAmbiente Pronto (Mininet)")
    print("Logs do UE: tail -f /tmp/ue1.log\n")
    
    CLI(net)
    
    print("Limpando ambiente...")
    net.stop()
    run_cmd("ip link delete veth-sdn 2>/dev/null", ignore_error=True)
    run_cmd("iptables -D DOCKER-USER -j ACCEPT 2>/dev/null", ignore_error=True)

if __name__ == '__main__':
    if os.geteuid() != 0:
        print("Execute como ROOT (sudo).")
        sys.exit(1)
    run_topology()
