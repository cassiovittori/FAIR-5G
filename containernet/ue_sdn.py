#!/usr/bin/python3
from mininet.net import Containernet
from mininet.node import RemoteController, OVSKernelSwitch
from mininet.cli import CLI
from mininet.link import Intf
from mininet.log import info, setLogLevel

def topology():
    setLogLevel('info')

    # Inicializa a rede
    net = Containernet(controller=RemoteController)

    info('*** Adicionando Controlador ONOS\n')
    # Aponta para o ONOS rodando no Docker (localhost)
    net.addController('c0', controller=RemoteController, ip='127.0.0.1', port=6653)

    info('*** Adicionando Switch SDN\n')
    s1 = net.addSwitch('s1', cls=OVSKernelSwitch, protocols='OpenFlow13')

    info('*** Adicionando UE via ContainerNet\n')
    
    # --- IMPORTANTE: AJUSTE ESTE CAMINHO ---
    # Coloque o caminho COMPLETO da pasta onde está o seu ue1.yaml
    # Exemplo: /home/usuario/meu-projeto/configs/network-slicing
    config_path = "/home/ubuntu/open5gs-mininet/configs/network-slicing" 
    
    # Criamos o UE com um IP fixo na MESMA FAIXA da sua rede Open5GS (10.33.33.x)
    # Escolhi .200 para não dar conflito com os outros containers
    ue1 = net.addDocker('ue1', 
                        ip='10.33.33.200/24', 
                        dimage="ghcr.io/borjis131/ue:v3.2.7",
                        privileged=True,
                        volumes=[f"{config_path}/ue1.yaml:/UERANSIM/config/ue1.yaml"],
                        dcmd="sleep infinity" # Mantém o container vivo
                        )
    info('*** Adicionando UE2\n')
    ue2 = net.addDocker('ue2', 
                        ip='10.33.33.201/24',  # IP diferente na rede SDN (201)
                        dimage="ghcr.io/borjis131/ue:v3.2.7",
                        privileged=True,
                        volumes=[f"{config_path}/ue2.yaml:/UERANSIM/config/ue2.yaml"],
                        dcmd="sleep infinity")

    info('*** Conectando UE ao Switch\n')
    net.addLink(ue1, s1)
    net.addLink(ue2, s1)

    info('*** Conectando Switch à Rede do Open5GS (Bridge)\n')
    # Aqui conectamos o Switch s1 na interface que o Docker criou para o Open5GS
    # ID da rede: 24f45ab50160... -> Interface: br-24f45ab50160
    Intf('veth-sdn', node=s1)

    info('*** Iniciando a Rede\n')
    net.start()
    
    ue1.cmd('ip link set ue1-eth0 up')
    ue2.cmd('ip link set ue2-eth0 up')

    info('*** Ambiente Pronto. O terminal do Mininet abrira abaixo.\n')
    CLI(net)

    info('*** Parando a Rede\n')
    net.stop()

if __name__ == '__main__':
    topology()
