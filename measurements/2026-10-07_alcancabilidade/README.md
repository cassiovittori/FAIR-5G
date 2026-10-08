fair5g@fair5g-virtual-machine:~/dev/fair5g-dev$ ./fair5g down && ./fair5g up --slices 2 --ues-per-slice 3,1
[cmd] ./scripts/down_v0.sh
[v0] Limpando Containernet/Mininet + resíduos Docker...
[sudo] password for fair5g: 
cleanup OK
[v0] Derrubando Open5GS (docker compose)...
WARN[0000] The "OPEN5GS_VERSION" variable is not set. Defaulting to a blank string. 
WARN[0000] The "OPEN5GS_VERSION" variable is not set. Defaulting to a blank string. 
WARN[0000] The "OPEN5GS_VERSION" variable is not set. Defaulting to a blank string. 
WARN[0000] The "OPEN5GS_VERSION" variable is not set. Defaulting to a blank string. 
WARN[0000] The "OPEN5GS_VERSION" variable is not set. Defaulting to a blank string. 
WARN[0000] The "NODE_VERSION" variable is not set. Defaulting to a blank string. 
WARN[0000] The "MONGODB_VERSION" variable is not set. Defaulting to a blank string. 
WARN[0000] The "OPEN5GS_VERSION" variable is not set. Defaulting to a blank string. 
WARN[0000] The "OPEN5GS_VERSION" variable is not set. Defaulting to a blank string. 
WARN[0000] The "OPEN5GS_VERSION" variable is not set. Defaulting to a blank string. 
WARN[0000] The "OPEN5GS_VERSION" variable is not set. Defaulting to a blank string. 
WARN[0000] The "OPEN5GS_VERSION" variable is not set. Defaulting to a blank string. 
WARN[0000] The "OPEN5GS_VERSION" variable is not set. Defaulting to a blank string. 
WARN[0000] The "OPEN5GS_VERSION" variable is not set. Defaulting to a blank string. 
WARN[0000] The "OPEN5GS_VERSION" variable is not set. Defaulting to a blank string. 
WARN[0000] The "OPEN5GS_VERSION" variable is not set. Defaulting to a blank string. 
WARN[0000] The "OPEN5GS_VERSION" variable is not set. Defaulting to a blank string. 
WARN[0000] The "OPEN5GS_VERSION" variable is not set. Defaulting to a blank string. 
[+] down 21/21
 ✔ Container smf1          Removed                                                 1.0s
 ✔ Container grafana       Removed                                                 2.0s
 ✔ Container nssf          Removed                                                 2.0s
 ✔ Container statsexporter Removed                                                10.6s
 ✔ Container smf2          Removed                                                 2.2s
 ✔ Container ausf          Removed                                                 2.2s
 ✔ Container blackbox      Removed                                                 2.6s
 ✔ Container udm           Removed                                                 1.9s
 ✔ Container webui         Removed                                                 2.7s
 ✔ Container gnb           Removed                                                 2.3s
 ✔ Container bsf           Removed                                                 1.6s
 ✔ Container upf1          Removed                                                10.4s
 ✔ Container prometheus    Removed                                                 1.1s
 ✔ Container upf2          Removed                                                10.5s
 ✔ Container udr           Removed                                                 0.8s
 ✔ Container pcf           Removed                                                 0.4s
 ✔ Container amf           Removed                                                10.4s
 ✔ Container db            Removed                                                 0.7s
 ✔ Container nrf           Removed                                                 0.4s
 ✔ Network open5gs         Removed                                                 0.2s
 ✔ Network fair5g-access   Removed                                                 0.4s
[v0] Removendo ONOS (onos-controller)...
onos-controller
[v0] Down concluído.
[cmd] sudo -v
[cmd] script -q -e -f /home/fair5g/dev/fair5g-dev/runs/2026-10-07_192343/up.log -c './scripts/up_v0.sh'
[sudo] password for fair5g: 
[v0] Repo: /home/fair5g/dev/fair5g-dev
[v0] Quantidade de fatias: 2
[v0] Pre-clean: removendo resíduos do Containernet (mn.*), veth e iptables...
[v0] Renderizando configs das 2 fatia(s)...
[render-slices] 2 fatia(s) renderizada(s):
  slice 1: sd=000001 subnet=10.45.0.0/16 ambr=100Mbps(agregado) ues=[ue1_1(10.34.0.200), ue1_2(10.34.0.201), ue1_3(10.34.0.202)]
  slice 2: sd=000002 subnet=10.46.0.0/16 ambr=10Mbps(agregado) ues=[ue2(10.34.0.203)]
[render-slices] 14 arquivo(s) escrito(s).
[v0] Subindo Open5GS via compose file...
[+] Building 20.6s (34/34) FINISHED                                                    
 => [internal] load local bake definitions                                        0.0s
 => => reading from stdin 2.16kB                                                  0.0s
 => [statsexporter internal] load build definition from Dockerfile                0.0s
 => => transferring dockerfile: 209B                                              0.0s
 => [upf2 internal] load build definition from Dockerfile                         0.0s
 => => transferring dockerfile: 836B                                              0.0s
 => [webui internal] load build definition from Dockerfile                        0.0s
 => => transferring dockerfile: 903B                                              0.0s
 => [statsexporter internal] load metadata for docker.io/library/python:3.11-sli  3.3s
 => [webui] resolve image config for docker-image://docker.io/docker/dockerfile:  3.2s
 => [webui] docker-image://docker.io/docker/dockerfile:1@sha256:4edf897a3ffa55b8  2.7s
 => => resolve docker.io/docker/dockerfile:1@sha256:4edf897a3ffa55b89f906fc8cc78  0.1s
 => => sha256:9d2b4f57f9e20f33279375ce25c6ff14f30f64270ed5c7b6 14.28MB / 14.28MB  1.9s
 => => extracting sha256:9d2b4f57f9e20f33279375ce25c6ff14f30f64270ed5c7b613b2b30  0.6s
 => [statsexporter internal] load .dockerignore                                   0.0s
 => => transferring context: 2B                                                   0.0s
 => [statsexporter 1/3] FROM docker.io/library/python:3.11-slim@sha256:0dd364ba7  8.3s
 => => resolve docker.io/library/python:3.11-slim@sha256:0dd364ba7e10242f0775544  0.1s
 => => sha256:496c1a902b3a93cea3e54b90b79dbcaa0e58ad90c3fe9dd0a43c95 250B / 250B  0.3s
 => => sha256:759a7f30c31818dda4c97b407b24d93da479c306568d185c 14.46MB / 14.46MB  5.1s
 => => sha256:0f752a1982d6f819fc2c9e78ac1514c63f2f2e1dec7885ffd4 1.29MB / 1.29MB  1.7s
 => => sha256:ecc510c1e359bdc007b39802570bb7e4dec7d6ebccf357c3 29.84MB / 29.84MB  2.8s
 => => extracting sha256:ecc510c1e359bdc007b39802570bb7e4dec7d6ebccf357c3201a742  3.2s
 => => extracting sha256:0f752a1982d6f819fc2c9e78ac1514c63f2f2e1dec7885ffd4cb680  0.2s
 => => extracting sha256:759a7f30c31818dda4c97b407b24d93da479c306568d185ced927e1  1.4s
 => => extracting sha256:496c1a902b3a93cea3e54b90b79dbcaa0e58ad90c3fe9dd0a43c955  0.0s
 => [statsexporter internal] load build context                                   0.1s
 => => transferring context: 6.79kB                                               0.0s
 => [upf2 internal] load metadata for ghcr.io/borjis131/upf:v2.7.5                1.3s
 => [webui internal] load metadata for docker.io/library/node:20-bookworm-slim    1.2s
 => [webui internal] load metadata for docker.io/library/node:20-bookworm         1.2s
 => [upf2 internal] load .dockerignore                                            0.1s
 => => transferring context: 2B                                                   0.0s
 => [webui internal] load .dockerignore                                           0.0s
 => => transferring context: 2B                                                   0.0s
 => [webui builder 1/4] FROM docker.io/library/node:20-bookworm@sha256:8f693eaa7  0.2s
 => => resolve docker.io/library/node:20-bookworm@sha256:8f693eaa7e0a8e71560c9a8  0.1s
 => [webui stage-1 1/3] FROM docker.io/library/node:20-bookworm-slim@sha256:2cf0  0.1s
 => => resolve docker.io/library/node:20-bookworm-slim@sha256:2cf067cfed83d5ea95  0.1s
 => [upf1 1/2] FROM ghcr.io/borjis131/upf:v2.7.5@sha256:76272f5068412e0f2f62c0fa  0.1s
 => => resolve ghcr.io/borjis131/upf:v2.7.5@sha256:76272f5068412e0f2f62c0fab72b2  0.1s
 => CACHED [webui builder 2/4] RUN apt-get update && apt-get install git -y       0.0s
 => CACHED [webui builder 3/4] RUN git clone --depth 1 --branch=v2.7.5 https://g  0.0s
 => CACHED [webui builder 4/4] RUN cd open5gs/webui && npm ci && npm run build    0.0s
 => CACHED [webui stage-1 2/3] COPY --from=builder /open5gs/webui/ /usr/local/sr  0.0s
 => CACHED [webui stage-1 3/3] WORKDIR /usr/local/src/webui                       0.0s
 => [webui] exporting to image                                                    0.3s
 => => exporting layers                                                           0.0s
 => => exporting manifest sha256:cd2f3f123205332682c61e650f1d9db0dafe4e5629fbe59  0.0s
 => => exporting config sha256:aee8e884ddaae61cc94b8de5c6558307a34c57c9c652c5e6b  0.0s
 => => exporting attestation manifest sha256:16587216d4339a67fe6f51403609688e49a  0.0s
 => => exporting manifest list sha256:321a56635223220031361345b23d7c70414cf6c237  0.0s
 => => naming to docker.io/library/webui:v2.7.5                                   0.0s
 => => unpacking to docker.io/library/webui:v2.7.5                                0.0s
 => CACHED [upf1 2/2] RUN apt-get update  && apt-get install -y --no-install-rec  0.0s
 => [upf1] exporting to image                                                     0.7s
 => => exporting layers                                                           0.1s
 => => exporting manifest sha256:c7c07aebcd20e07fe31a2b62970cc5917250d115786a21f  0.0s
 => => exporting config sha256:a5689ac1ae8a3cf52df123f0504f28ecb85e659cc1debcfd0  0.0s
 => => exporting attestation manifest sha256:5f9feb66c9587de1ba61f1c06334e54931c  0.1s
 => => exporting manifest list sha256:c90a0b82547e30952d54467c207d499866923560d0  0.1s
 => => naming to docker.io/library/fair5g-upf:v2.7.5                              0.0s
 => => unpacking to docker.io/library/fair5g-upf:v2.7.5                           0.1s
 => [upf2] exporting to image                                                     0.5s
 => => exporting layers                                                           0.1s
 => => exporting manifest sha256:e07f516dac1ca714e5a69e3ae916da9a6d3da6210c70211  0.0s
 => => exporting config sha256:6d017341b64c5d7e3321bdc3eb46253d6a1852cbbaec9eecb  0.0s
 => => exporting attestation manifest sha256:f9c99951c5901d2a1565fd08c44a99e193d  0.1s
 => => exporting manifest list sha256:c03daf2c70fab06dffad4cb260933db0790fc26c7f  0.1s
 => => naming to docker.io/library/fair5g-upf:v2.7.5                              0.0s
 => => unpacking to docker.io/library/fair5g-upf:v2.7.5                           0.1s
 => [webui] resolving provenance for metadata file                                0.0s
 => [upf2] resolving provenance for metadata file                                 0.0s
 => [upf1] resolving provenance for metadata file                                 0.0s
 => [statsexporter 2/3] RUN pip install --no-cache-dir requests requests-unixsoc  6.5s
 => [statsexporter 3/3] COPY exporter.py /app/exporter.py                         0.1s
 => [statsexporter] exporting to image                                            1.7s
 => => exporting layers                                                           0.9s
 => => exporting manifest sha256:1c29ec9f23ea2d6eb832024056cb5d5b40c424d07a3c2cb  0.0s
 => => exporting config sha256:c69b155722f5e1be2dc1458ae15b9cacdabb4402643d30c16  0.0s
 => => exporting attestation manifest sha256:357d83ffa1dfc19601d3e90d0a0b89b019e  0.0s
 => => exporting manifest list sha256:9cf33dfff20c64dd40fc3f4f2d3743ea5aaea23096  0.0s
 => => naming to docker.io/library/fair5g-statsexporter:1.0                       0.0s
 => => unpacking to docker.io/library/fair5g-statsexporter:1.0                    0.6s
 => [statsexporter] resolving provenance for metadata file                        0.0s
[+] up 24/24
 ✔ Image webui:v2.7.5             Built                                           21.1s
 ✔ Image fair5g-statsexporter:1.0 Built                                           21.2s
 ✔ Image fair5g-upf:v2.7.5        Built                                           20.9s
 ✔ Network fair5g-access          Created                                          0.1s
 ✔ Network open5gs                Created                                          0.3s
 ✔ Container blackbox             Started                                          7.2s
 ✔ Container upf2                 Started                                          7.2s
 ✔ Container db                   Started                                          7.4s
 ✔ Container nrf                  Started                                          4.9s
 ✔ Container upf1                 Started                                          5.3s
 ✔ Container statsexporter        Started                                          5.4s
 ✔ Container bsf                  Started                                         11.0s
 ✔ Container nssf                 Started                                         10.9s
 ✔ Container ausf                 Started                                         12.5s
 ✔ Container udm                  Started                                         12.6s
 ✔ Container amf                  Started                                         13.5s
 ✔ Container smf2                 Started                                         15.3s
 ✔ Container webui                Started                                         15.6s
 ✔ Container pcf                  Started                                         15.6s
 ✔ Container udr                  Started                                         15.6s
 ✔ Container smf1                 Started                                         13.5s
 ... 3 more                                                                            
[v0] Seed subscribers (idempotente)...
[seed] Waiting for Mongo to respond...
[seed] Mongo is ready.
[seed] Copying seed file into container...
Successfully copied 4.5kB (transferred 6.14kB) to db:/tmp/subscribers.js
[seed] Applying subscribers seed...
[seed] subscribers processed=4 upserts=2
[seed] Done.
[v0] Renderizando configs runtime do UE (gnbSearchList)...
[render] gnb ip: 10.34.0.3
[render] atualizado: /home/fair5g/dev/fair5g-dev/configs/runtime/ue1_1.yaml
[render] atualizado: /home/fair5g/dev/fair5g-dev/configs/runtime/ue1_2.yaml
[render] atualizado: /home/fair5g/dev/fair5g-dev/configs/runtime/ue1_3.yaml
[render] atualizado: /home/fair5g/dev/fair5g-dev/configs/runtime/ue2.yaml
[v0] Subindo SDN + UEs (Containernet + ONOS)...
Provisionando 2 fatia(s): [1, 2]
Usando CONFIG_DIR: /home/fair5g/dev/fair5g-dev/configs/runtime
Configurando Controlador ONOS...
Iniciando container ONOS (novo)...
Aguardando API do ONOS iniciar...
Ativando App via API: org.onosproject.openflow
Tentativa 1/60
Ativando App via API: org.onosproject.openflow
Tentativa 2/60
Ativando App via API: org.onosproject.openflow
Tentativa 3/60
Ativando App via API: org.onosproject.openflow
Tentativa 4/60
Ativando App via API: org.onosproject.openflow
Tentativa 5/60
Ativando App via API: org.onosproject.openflow
Tentativa 6/60
Ativando App via API: org.onosproject.openflow
Tentativa 7/60
Ativando App via API: org.onosproject.openflow
Tentativa 8/60
Ativando App via API: org.onosproject.openflow
Tentativa 9/60
Ativando App via API: org.onosproject.openflow
Tentativa 10/60
Ativando App via API: org.onosproject.openflow
Tentativa 11/60
Ativando App via API: org.onosproject.openflow
Tentativa 12/60
Ativando App via API: org.onosproject.openflow
Tentativa 13/60
Ativando App via API: org.onosproject.openflow
ONOS API pronta e Apps ativados.
Ativando App via API: org.onosproject.fwd
Configurando Cabos Virtuais...
Buscando ponte para rede: fair5g-access
Ponte encontrada: br-access
Isolamento cross-slice aplicado entre 2 fatia(s): 10.45.0.0/16, 10.46.0.0/16
Iniciando Topologia Mininet...
*** Adicionando Controlador
*** Adicionando Switch
*** Adicionando UE1_1 (fatia 1)
ue1_1: kwargs {'ip': '10.34.0.200/24', 'privileged': True, 'volumes': ['/home/fair5g/dev/fair5g-dev/configs/runtime:/UERANSIM/config:ro']}
ue1_1: update resources {}
*** Adicionando UE1_2 (fatia 1)
ue1_2: kwargs {'ip': '10.34.0.201/24', 'privileged': True, 'volumes': ['/home/fair5g/dev/fair5g-dev/configs/runtime:/UERANSIM/config:ro']}
ue1_2: update resources {}
*** Adicionando UE1_3 (fatia 1)
ue1_3: kwargs {'ip': '10.34.0.202/24', 'privileged': True, 'volumes': ['/home/fair5g/dev/fair5g-dev/configs/runtime:/UERANSIM/config:ro']}
ue1_3: update resources {}
*** Adicionando UE2 (fatia 2)
ue2: kwargs {'ip': '10.34.0.203/24', 'privileged': True, 'volumes': ['/home/fair5g/dev/fair5g-dev/configs/runtime:/UERANSIM/config:ro']}
ue2: update resources {}
*** Conectando Componentes
*** Iniciando a Rede
*** Configuring hosts
ue1_1 ue1_2 ue1_3 ue2 
*** Starting controller
c0 
*** Starting 1 switches
s1 ...
Configurando flows de fatiamento no SDN...
Aguardando switch conectar ao ONOS...
  aguardando switch (1/30)...
Switch disponível no ONOS: of:0000000000000001
gNB na rede de acesso: 10.34.0.3
Probe (blackbox) na rede de acesso: 10.34.0.2
Instalando 2 meters no switch of:0000000000000001...
Meter fatia 1: id=1 rate=100000 kbps
Meter fatia 2: id=2 rate=10000 kbps
Meters confirmed on the switch: [10000, 100000] kbps
Instalando 20 flows proativos no switch of:0000000000000001...
  flow 1/20 instalado.
  flow 2/20 instalado.
  flow 3/20 instalado.
  flow 4/20 instalado.
  flow 5/20 instalado.
  flow 6/20 instalado.
  flow 7/20 instalado.
  flow 8/20 instalado.
  flow 9/20 instalado.
  flow 10/20 instalado.
  flow 11/20 instalado.
  flow 12/20 instalado.
  flow 13/20 instalado.
  flow 14/20 instalado.
  flow 15/20 instalado.
  flow 16/20 instalado.
  flow 17/20 instalado.
  flow 18/20 instalado.
  flow 19/20 instalado.
  flow 20/20 instalado.
Flows de fatiamento instalados.
Configurando isolamento mgmt plane...
Isolamento mgmt plane: {'ue1_1': '172.17.0.3', 'ue1_2': '172.17.0.4', 'ue1_3': '172.17.0.5', 'ue2': '172.17.0.6'}
Configurando isolamento do plano de dados nas UPFs...
Isolamento aplicado dentro das UPFs (antes do masquerade) em 2 fatia(s).
Iniciando Conexao 5G (UERANSIM)...
ue1_1 iniciado. Log: /tmp/ue1_1.log
ue1_2 iniciado. Log: /tmp/ue1_2.log
ue1_3 iniciado. Log: /tmp/ue1_3.log
ue2 iniciado. Log: /tmp/ue2.log

Ambiente Pronto (Mininet)
Logs: ue1_1 sh -c "tail -f /tmp/ue1_1.log"
Ping basico: ue1_1 ping -c 3 10.34.0.203
Verificar flows: ovs-ofctl dump-flows s1


================================================================
  ENVIRONMENT POST-CONDITION CHECKS
================================================================

[verify] Checking environment post-conditions...
  [OK  ] containers: 21 expected containers running
  [OK  ] PDU sessions: 4 UE(s) with an active PDU session
  [OK  ] switch in ONOS: 1 switch(es) available in ONOS
  [OK  ] meters per slice: 2 distinct meter(s) installed
  [OK  ] Prometheus: 11 Prometheus target(s) up
[verify] environment validated.

================================================================

*** Starting CLI:
containernet> ue1_1 ping -c 3 10.34.0.203
PING 10.34.0.203 (10.34.0.203) 56(84) bytes of data.
^C
--- 10.34.0.203 ping statistics ---
3 packets transmitted, 0 received, 100% packet loss, time 2058ms

containernet> ue1_1 ping -c 3 ue1_2
ping: ue1_2: Name or service not known
containernet> ue1_1 ifconfig
bash: ifconfig: command not found
containernet> ue1_1 ping -c 3 10.33.0.204
PING 10.33.0.204 (10.33.0.204) 56(84) bytes of data.
^C
--- 10.33.0.204 ping statistics ---
2 packets transmitted, 0 received, 100% packet loss, time 1015ms

containernet> ue1_1 ping -c 3 10.33.0.203
PING 10.33.0.203 (10.33.0.203) 56(84) bytes of data.
^C
--- 10.33.0.203 ping statistics ---
2 packets transmitted, 0 received, 100% packet loss, time 1049ms

containernet> ue1_1 ping -c 3 10.33.0.202
PING 10.33.0.202 (10.33.0.202) 56(84) bytes of data.
^C
--- 10.33.0.202 ping statistics ---
3 packets transmitted, 0 received, 100% packet loss, time 2027ms

containernet> ue1_1 ping -c 3 10.34.0.202
PING 10.34.0.202 (10.34.0.202) 56(84) bytes of data.
^C
--- 10.34.0.202 ping statistics ---
3 packets transmitted, 0 received, 100% packet loss, time 2061ms

containernet> ue1_1 ping -c 3 10.34.0.201
PING 10.34.0.201 (10.34.0.201) 56(84) bytes of data.
^C
--- 10.34.0.201 ping statistics ---
3 packets transmitted, 0 received, 100% packet loss, time 2072ms

containernet> ue1_2 ip -br addr show uesimtun0
uesimtun0        UNKNOWN        10.45.0.3/16 fe80::ba82:1fe7:3aa3:d15d/64 
containernet> ue1_3 ip -br addr show uesimtun0
uesimtun0        UNKNOWN        10.45.0.4/16 fe80::a865:ff7e:5642:8c4a/64 
containernet> ue2 ip -br addr show uesimtun0
uesimtun0        UNKNOWN        10.46.0.2/16 fe80::5dd3:e5e2:f497:7996/64 
containernet> ue1_1 ping -c 3 10.34.0.3
PING 10.34.0.3 (10.34.0.3) 56(84) bytes of data.
64 bytes from 10.34.0.3: icmp_seq=1 ttl=64 time=0.248 ms
64 bytes from 10.34.0.3: icmp_seq=2 ttl=64 time=0.104 ms
64 bytes from 10.34.0.3: icmp_seq=3 ttl=64 time=0.101 ms

--- 10.34.0.3 ping statistics ---
3 packets transmitted, 3 received, 0% packet loss, time 2041ms
rtt min/avg/max/mdev = 0.101/0.151/0.248/0.068 ms
containernet> ue1_1 ping -c 3 -I uesimtun0 10.45.0.1
PING 10.45.0.1 (10.45.0.1) from 10.45.0.2 uesimtun0: 56(84) bytes of data.
64 bytes from 10.45.0.1: icmp_seq=1 ttl=64 time=5.98 ms
64 bytes from 10.45.0.1: icmp_seq=2 ttl=64 time=2.89 ms
64 bytes from 10.45.0.1: icmp_seq=3 ttl=64 time=2.95 ms

--- 10.45.0.1 ping statistics ---
3 packets transmitted, 3 received, 0% packet loss, time 2003ms
rtt min/avg/max/mdev = 2.892/3.940/5.978/1.441 ms
containernet> ue2   ping -c 3 -I uesimtun0 10.46.0.1
PING 10.46.0.1 (10.46.0.1) from 10.46.0.2 uesimtun0: 56(84) bytes of data.
64 bytes from 10.46.0.1: icmp_seq=1 ttl=64 time=5.14 ms
64 bytes from 10.46.0.1: icmp_seq=2 ttl=64 time=2.94 ms
64 bytes from 10.46.0.1: icmp_seq=3 ttl=64 time=3.27 ms

--- 10.46.0.1 ping statistics ---
3 packets transmitted, 3 received, 0% packet loss, time 2003ms
rtt min/avg/max/mdev = 2.944/3.786/5.140/0.966 ms
containernet> ue1_1 ping -c 3 -I uesimtun0 10.46.0.1
PING 10.46.0.1 (10.46.0.1) from 10.45.0.2 uesimtun0: 56(84) bytes of data.
^C
--- 10.46.0.1 ping statistics ---
3 packets transmitted, 0 received, 100% packet loss, time 2037ms

containernet> ue1_1 ping -c 3 10.34.0.203
PING 10.34.0.203 (10.34.0.203) 56(84) bytes of data.

--- 10.34.0.203 ping statistics ---
3 packets transmitted, 0 received, 100% packet loss, time 2085ms

containernet> ue1_1 ping -c 3 -I uesimtun0 10.45.0.3
PING 10.45.0.3 (10.45.0.3) from 10.45.0.2 uesimtun0: 56(84) bytes of data.
64 bytes from 10.45.0.3: icmp_seq=1 ttl=63 time=6.76 ms
From 10.45.0.1 icmp_seq=2 Redirect Host(New nexthop: 10.45.0.3)
64 bytes from 10.45.0.3: icmp_seq=2 ttl=63 time=7.47 ms

--- 10.45.0.3 ping statistics ---
2 packets transmitted, 2 received, +1 errors, 0% packet loss, time 1002ms
rtt min/avg/max/mdev = 6.763/7.115/7.467/0.352 ms
containernet> exit
Limpando ambiente...
*** Stopping 1 controllers
c0 
*** Stopping 4 links
....
*** Stopping 1 switches
s1 
*** Stopping 4 hosts
ue1_1 ue1_2 ue1_3 ue2 
*** Done
*** Removing NAT rules of 0 SAPs

[ok] run_id=2026-10-07_192343 logs=/home/fair5g/dev/fair5g-dev/runs/2026-10-07_192343/up.log
fair5g@fair5g-virtual-machine:~/dev/fair5g-dev$ ./fair5g
    _________    ________        ____________
   / ____/   |  /  _/ __ \      / ____/ ____/
  / /_  / /| |  / // /_/ /_____/___ \/ / __  
 / __/ / ___ |_/ // _, _/_____/___/ / /_/ /  
/_/   /_/  |_/___/_/ |_|     /_____/\____/   
                                             

FAIR5G: Open5GS + Slicing + SDN + Metrics

? Selecione uma opção: up (subir ambiente)
? Config dir (ENTER para padrão):
? Quantidade de fatias [1-8] (ENTER para 2): 2
? Quantos UEs por fatia? (padrão: 1 por fatia) Definir fatia a fatia
?   Fatia 1 — quantidade de UEs [1-4]: 1
?   Fatia 2 — quantidade de UEs [1-4]: 3
  → fatia 1: 1 UE(s), fatia 2: 3 UE(s)
[cmd] sudo -v
[sudo] password for fair5g: 
[cmd] script -q -e -f /home/fair5g/dev/fair5g-dev/runs/2026-10-07_194730/up.log -c './scripts/up_v0.sh'
[sudo] password for fair5g: 
[v0] Repo: /home/fair5g/dev/fair5g-dev
[v0] Quantidade de fatias: 2
[v0] Pre-clean: removendo resíduos do Containernet (mn.*), veth e iptables...
[v0] Renderizando configs das 2 fatia(s)...
[render-slices] 2 fatia(s) renderizada(s):
  slice 1: sd=000001 subnet=10.45.0.0/16 ambr=100Mbps(agregado) ues=[ue1(10.34.0.200)]
  slice 2: sd=000002 subnet=10.46.0.0/16 ambr=10Mbps(agregado) ues=[ue2_1(10.34.0.201), ue2_2(10.34.0.202), ue2_3(10.34.0.203)]
[render-slices] 14 arquivo(s) escrito(s).
[v0] Subindo Open5GS via compose file...
[+] Building 5.6s (34/34) FINISHED                                                     
 => [internal] load local bake definitions                                        0.0s
 => => reading from stdin 2.16kB                                                  0.0s
 => [upf1 internal] load build definition from Dockerfile                         0.0s
 => => transferring dockerfile: 836B                                              0.0s
 => [statsexporter internal] load build definition from Dockerfile                0.0s
 => => transferring dockerfile: 209B                                              0.0s
 => [webui internal] load build definition from Dockerfile                        0.0s
 => => transferring dockerfile: 903B                                              0.0s
 => [statsexporter internal] load metadata for docker.io/library/python:3.11-sli  2.0s
 => [upf1] resolve image config for docker-image://docker.io/docker/dockerfile:1  2.0s
 => [statsexporter internal] load .dockerignore                                   0.0s
 => => transferring context: 2B                                                   0.0s
 => CACHED [upf1] docker-image://docker.io/docker/dockerfile:1@sha256:4edf897a3f  0.1s
 => => resolve docker.io/docker/dockerfile:1@sha256:4edf897a3ffa55b89f906fc8cc78  0.1s
 => [statsexporter 1/3] FROM docker.io/library/python:3.11-slim@sha256:0dd364ba7  0.1s
 => => resolve docker.io/library/python:3.11-slim@sha256:0dd364ba7e10242f0775544  0.1s
 => [statsexporter internal] load build context                                   0.0s
 => => transferring context: 33B                                                  0.0s
 => CACHED [statsexporter 2/3] RUN pip install --no-cache-dir requests requests-  0.0s
 => CACHED [statsexporter 3/3] COPY exporter.py /app/exporter.py                  0.0s
 => [statsexporter] exporting to image                                            0.4s
 => => exporting layers                                                           0.0s
 => => exporting manifest sha256:1c29ec9f23ea2d6eb832024056cb5d5b40c424d07a3c2cb  0.0s
 => => exporting config sha256:c69b155722f5e1be2dc1458ae15b9cacdabb4402643d30c16  0.0s
 => => exporting attestation manifest sha256:2089eb3529ffe3c596532d20f02873e4e54  0.0s
 => => exporting manifest list sha256:a1f7552b14ec20dc06f5f1d4ad94aa168a6a6fc2d8  0.0s
 => => naming to docker.io/library/fair5g-statsexporter:1.0                       0.0s
 => => unpacking to docker.io/library/fair5g-statsexporter:1.0                    0.1s
 => [upf2 internal] load metadata for ghcr.io/borjis131/upf:v2.7.5                1.5s
 => [webui internal] load metadata for docker.io/library/node:20-bookworm-slim    1.1s
 => [webui internal] load metadata for docker.io/library/node:20-bookworm         1.1s
 => [statsexporter] resolving provenance for metadata file                        0.0s
 => [webui internal] load .dockerignore                                           0.0s
 => => transferring context: 2B                                                   0.0s
 => [webui stage-1 1/3] FROM docker.io/library/node:20-bookworm-slim@sha256:2cf0  0.1s
 => => resolve docker.io/library/node:20-bookworm-slim@sha256:2cf067cfed83d5ea95  0.1s
 => [webui builder 1/4] FROM docker.io/library/node:20-bookworm@sha256:8f693eaa7  0.1s
 => => resolve docker.io/library/node:20-bookworm@sha256:8f693eaa7e0a8e71560c9a8  0.1s
 => CACHED [webui builder 2/4] RUN apt-get update && apt-get install git -y       0.0s
 => CACHED [webui builder 3/4] RUN git clone --depth 1 --branch=v2.7.5 https://g  0.0s
 => CACHED [webui builder 4/4] RUN cd open5gs/webui && npm ci && npm run build    0.0s
 => CACHED [webui stage-1 2/3] COPY --from=builder /open5gs/webui/ /usr/local/sr  0.0s
 => CACHED [webui stage-1 3/3] WORKDIR /usr/local/src/webui                       0.0s
 => [webui] exporting to image                                                    0.4s
 => => exporting layers                                                           0.0s
 => => exporting manifest sha256:cd2f3f123205332682c61e650f1d9db0dafe4e5629fbe59  0.0s
 => => exporting config sha256:aee8e884ddaae61cc94b8de5c6558307a34c57c9c652c5e6b  0.0s
 => => exporting attestation manifest sha256:c0cb4ddbc6954be4798462f05689c7dec40  0.1s
 => => exporting manifest list sha256:4f2c30d7932eb907cc57b96d8b4c056d2a6356e2e8  0.1s
 => => naming to docker.io/library/webui:v2.7.5                                   0.0s
 => => unpacking to docker.io/library/webui:v2.7.5                                0.1s
 => [upf1 internal] load .dockerignore                                            0.0s
 => => transferring context: 2B                                                   0.0s
 => [upf2 1/2] FROM ghcr.io/borjis131/upf:v2.7.5@sha256:76272f5068412e0f2f62c0fa  0.1s
 => => resolve ghcr.io/borjis131/upf:v2.7.5@sha256:76272f5068412e0f2f62c0fab72b2  0.1s
 => CACHED [upf1 2/2] RUN apt-get update  && apt-get install -y --no-install-rec  0.0s
 => [upf1] exporting to image                                                     0.3s
 => => exporting layers                                                           0.1s
 => => exporting manifest sha256:c7c07aebcd20e07fe31a2b62970cc5917250d115786a21f  0.0s
 => => exporting config sha256:a5689ac1ae8a3cf52df123f0504f28ecb85e659cc1debcfd0  0.0s
 => => exporting attestation manifest sha256:2edab5448b5120c08d4d2d1001a19ab2b51  0.0s
 => => exporting manifest list sha256:dfdd6062710eebce12eabacce57bb8198e31eab946  0.0s
 => => naming to docker.io/library/fair5g-upf:v2.7.5                              0.0s
 => => unpacking to docker.io/library/fair5g-upf:v2.7.5                           0.1s
 => [upf2] exporting to image                                                     0.4s
 => => exporting layers                                                           0.1s
 => => exporting manifest sha256:e07f516dac1ca714e5a69e3ae916da9a6d3da6210c70211  0.0s
 => => exporting config sha256:6d017341b64c5d7e3321bdc3eb46253d6a1852cbbaec9eecb  0.0s
 => => exporting attestation manifest sha256:406bfae2b964cfecffaa93a92af70ad0c45  0.0s
 => => exporting manifest list sha256:956cbe7e90e37bdf7dd24da3722c23a26bc455b802  0.0s
 => => naming to docker.io/library/fair5g-upf:v2.7.5                              0.0s
 => => unpacking to docker.io/library/fair5g-upf:v2.7.5                           0.1s
 => [webui] resolving provenance for metadata file                                0.0s
 => [upf1] resolving provenance for metadata file                                 0.0s
 => [upf2] resolving provenance for metadata file                                 0.0s
[+] up 22/22
 ✔ Image fair5g-statsexporter:1.0 Built                                            6.1s
 ✔ Image fair5g-upf:v2.7.5        Built                                            5.8s
 ✔ Image webui:v2.7.5             Built                                            6.0s
 ✔ Container db                   Running                                          0.0s
 ✔ Container smf1                 Running                                          0.0s
 ✔ Container webui                Running                                          0.0s
 ✔ Container statsexporter        Running                                          0.0s
 ✔ Container blackbox             Running                                          0.0s
 ✔ Container gnb                  Running                                          0.0s
 ✔ Container prometheus           Running                                          0.0s
 ✔ Container bsf                  Running                                          0.0s
 ✔ Container grafana              Running                                          0.0s
 ✔ Container smf2                 Running                                          0.0s
 ✔ Container nrf                  Running                                          0.0s
 ✔ Container amf                  Running                                          0.0s
 ✔ Container pcf                  Running                                          0.0s
 ✔ Container udm                  Running                                          0.0s
 ✔ Container ausf                 Running                                          0.0s
 ✔ Container udr                  Running                                          0.0s
 ✔ Container nssf                 Running                                          0.0s
 ✔ Container upf1                 Started                                         12.2s
 ✔ Container upf2                 Started                                         12.4s
[v0] Seed subscribers (idempotente)...
[seed] Waiting for Mongo to respond...
[seed] Mongo is ready.
[seed] Copying seed file into container...
Successfully copied 4.5kB (transferred 6.14kB) to db:/tmp/subscribers.js
[seed] Applying subscribers seed...
[seed] subscribers processed=4 upserts=0
[seed] Done.
[v0] Renderizando configs runtime do UE (gnbSearchList)...
[render] gnb ip: 10.34.0.3
[render] atualizado: /home/fair5g/dev/fair5g-dev/configs/runtime/ue1.yaml
[render] atualizado: /home/fair5g/dev/fair5g-dev/configs/runtime/ue2_1.yaml
[render] atualizado: /home/fair5g/dev/fair5g-dev/configs/runtime/ue2_2.yaml
[render] atualizado: /home/fair5g/dev/fair5g-dev/configs/runtime/ue2_3.yaml
[v0] Subindo SDN + UEs (Containernet + ONOS)...
Provisionando 2 fatia(s): [1, 2]
Usando CONFIG_DIR: /home/fair5g/dev/fair5g-dev/configs/runtime
Configurando Controlador ONOS...
ONOS já está rodando. OK.
Aguardando API do ONOS iniciar...
Ativando App via API: org.onosproject.openflow
ONOS API pronta e Apps ativados.
Ativando App via API: org.onosproject.fwd
Configurando Cabos Virtuais...
Buscando ponte para rede: fair5g-access
Ponte encontrada: br-access
Isolamento cross-slice aplicado entre 2 fatia(s): 10.45.0.0/16, 10.46.0.0/16
Iniciando Topologia Mininet...
*** Adicionando Controlador
*** Adicionando Switch
*** Adicionando UE1 (fatia 1)
ue1: kwargs {'ip': '10.34.0.200/24', 'privileged': True, 'volumes': ['/home/fair5g/dev/fair5g-dev/configs/runtime:/UERANSIM/config:ro']}
ue1: update resources {}
*** Adicionando UE2_1 (fatia 2)
ue2_1: kwargs {'ip': '10.34.0.201/24', 'privileged': True, 'volumes': ['/home/fair5g/dev/fair5g-dev/configs/runtime:/UERANSIM/config:ro']}
ue2_1: update resources {}
*** Adicionando UE2_2 (fatia 2)
ue2_2: kwargs {'ip': '10.34.0.202/24', 'privileged': True, 'volumes': ['/home/fair5g/dev/fair5g-dev/configs/runtime:/UERANSIM/config:ro']}
ue2_2: update resources {}
*** Adicionando UE2_3 (fatia 2)
ue2_3: kwargs {'ip': '10.34.0.203/24', 'privileged': True, 'volumes': ['/home/fair5g/dev/fair5g-dev/configs/runtime:/UERANSIM/config:ro']}
ue2_3: update resources {}
*** Conectando Componentes
*** Iniciando a Rede
*** Configuring hosts
ue1 ue2_1 ue2_2 ue2_3 
*** Starting controller
c0 
*** Starting 1 switches
s1 ...
Configurando flows de fatiamento no SDN...
Aguardando switch conectar ao ONOS...
  aguardando switch (1/30)...
Switch disponível no ONOS: of:0000000000000001
gNB na rede de acesso: 10.34.0.3
Probe (blackbox) na rede de acesso: 10.34.0.2
Instalando 2 meters no switch of:0000000000000001...
Meter fatia 1: id=1 rate=100000 kbps
Meter fatia 2: id=2 rate=10000 kbps
Meters confirmed on the switch: [10000, 100000] kbps
Instalando 20 flows proativos no switch of:0000000000000001...
  flow 1/20 instalado.
  flow 2/20 instalado.
  flow 3/20 instalado.
  flow 4/20 instalado.
  flow 5/20 instalado.
  flow 6/20 instalado.
  flow 7/20 instalado.
  flow 8/20 instalado.
  flow 9/20 instalado.
  flow 10/20 instalado.
  flow 11/20 instalado.
  flow 12/20 instalado.
  flow 13/20 instalado.
  flow 14/20 instalado.
  flow 15/20 instalado.
  flow 16/20 instalado.
  flow 17/20 instalado.
  flow 18/20 instalado.
  flow 19/20 instalado.
  flow 20/20 instalado.
Flows de fatiamento instalados.
Configurando isolamento mgmt plane...
Isolamento mgmt plane: {'ue1': '172.17.0.3', 'ue2_1': '172.17.0.4', 'ue2_2': '172.17.0.5', 'ue2_3': '172.17.0.6'}
Configurando isolamento do plano de dados nas UPFs...
Isolamento aplicado dentro das UPFs (antes do masquerade) em 2 fatia(s).
Iniciando Conexao 5G (UERANSIM)...
ue1 iniciado. Log: /tmp/ue1.log
ue2_1 iniciado. Log: /tmp/ue2_1.log
ue2_2 iniciado. Log: /tmp/ue2_2.log
ue2_3 iniciado. Log: /tmp/ue2_3.log

Ambiente Pronto (Mininet)
Logs: ue1 sh -c "tail -f /tmp/ue1.log"
Ping basico: ue1 ping -c 3 10.34.0.201
Verificar flows: ovs-ofctl dump-flows s1


================================================================
  ENVIRONMENT POST-CONDITION CHECKS
================================================================

[verify] Checking environment post-conditions...
  [OK  ] containers: 21 expected containers running
  [OK  ] PDU sessions: 4 UE(s) with an active PDU session
  [OK  ] switch in ONOS: 1 switch(es) available in ONOS
  [OK  ] meters per slice: 2 distinct meter(s) installed
  [OK  ] Prometheus: 11 Prometheus target(s) up
[verify] environment validated.

================================================================

*** Starting CLI:
containernet> ue2_1 ip -br addr show uesimtun0
uesimtun0        UNKNOWN        10.46.0.3/16 fe80::5ca9:dedb:f412:746/64 
containernet> ue2_2 ip -br addr show uesimtun0
uesimtun0        UNKNOWN        10.46.0.4/16 fe80::82f8:c99d:2fdb:b5b1/64 
containernet> ue2_3 ip -br addr show uesimtun0
uesimtun0        UNKNOWN        10.46.0.5/16 fe80::778d:b833:f24b:bfeb/64 
containernet> ue1 ip -br addr show uesimtun0
uesimtun0        UNKNOWN        10.45.0.5/16 fe80::614c:f3aa:944f:c71/64 
containernet> ue1_1 ip -br addr show uesimtun0
*** Unknown command: ue1_1 ip -br addr show uesimtun0
containernet> ue2_1 ping -c 3 10.45.0.5
PING 10.45.0.5 (10.45.0.5) 56(84) bytes of data.
^C
--- 10.45.0.5 ping statistics ---
3 packets transmitted, 0 received, 100% packet loss, time 2059ms

containernet> ue2_1 ping -c 3 10.46.0.3
PING 10.46.0.3 (10.46.0.3) 56(84) bytes of data.
64 bytes from 10.46.0.3: icmp_seq=1 ttl=64 time=0.112 ms
64 bytes from 10.46.0.3: icmp_seq=2 ttl=64 time=0.052 ms
64 bytes from 10.46.0.3: icmp_seq=3 ttl=64 time=0.049 ms

--- 10.46.0.3 ping statistics ---
3 packets transmitted, 3 received, 0% packet loss, time 2044ms
rtt min/avg/max/mdev = 0.049/0.071/0.112/0.029 ms
containernet> ue2_1 ping -c 3 10.46.0.4
PING 10.46.0.4 (10.46.0.4) 56(84) bytes of data.
64 bytes from 10.46.0.4: icmp_seq=1 ttl=63 time=9.48 ms
From 10.46.0.1 icmp_seq=2 Redirect Host(New nexthop: 10.46.0.4)
64 bytes from 10.46.0.4: icmp_seq=2 ttl=63 time=7.42 ms

--- 10.46.0.4 ping statistics ---
2 packets transmitted, 2 received, +1 errors, 0% packet loss, time 1002ms
rtt min/avg/max/mdev = 7.419/8.448/9.477/1.029 ms
containernet> ue2_1 ping -c 3 10.46.0.5
PING 10.46.0.5 (10.46.0.5) 56(84) bytes of data.
64 bytes from 10.46.0.5: icmp_seq=1 ttl=63 time=7.88 ms
From 10.46.0.1 icmp_seq=2 Redirect Host(New nexthop: 10.46.0.5)
64 bytes from 10.46.0.5: icmp_seq=2 ttl=63 time=10.4 ms

--- 10.46.0.5 ping statistics ---
2 packets transmitted, 2 received, +1 errors, 0% packet loss, time 1002ms
rtt min/avg/max/mdev = 7.875/9.113/10.351/1.238 ms
containernet> ue2_1 ip route
default via 172.17.0.1 dev eth0 
10.34.0.0/24 dev ue2_1-eth0 proto kernel scope link src 10.34.0.201 
10.46.0.0/16 dev uesimtun0 proto kernel scope link src 10.46.0.3 
172.17.0.0/16 dev eth0 proto kernel scope link src 172.17.0.4 
containernet> ue2_1 ping -c 3 8.8.8.8
PING 8.8.8.8 (8.8.8.8) 56(84) bytes of data.
64 bytes from 8.8.8.8: icmp_seq=1 ttl=127 time=39.7 ms
64 bytes from 8.8.8.8: icmp_seq=2 ttl=127 time=37.3 ms
64 bytes from 8.8.8.8: icmp_seq=3 ttl=127 time=38.6 ms

--- 8.8.8.8 ping statistics ---
3 packets transmitted, 3 received, 0% packet loss, time 2004ms
rtt min/avg/max/mdev = 37.296/38.513/39.664/0.967 ms
containernet> ue2_1 ping -c 3 -I uesimtun0 8.8.8.8
PING 8.8.8.8 (8.8.8.8) from 10.46.0.3 uesimtun0: 56(84) bytes of data.
64 bytes from 8.8.8.8: icmp_seq=1 ttl=126 time=44.4 ms
64 bytes from 8.8.8.8: icmp_seq=2 ttl=126 time=47.6 ms
64 bytes from 8.8.8.8: icmp_seq=3 ttl=126 time=42.9 ms

--- 8.8.8.8 ping statistics ---
3 packets transmitted, 3 received, 0% packet loss, time 2004ms
rtt min/avg/max/mdev = 42.941/44.983/47.639/1.966 ms
containernet> sh sudo docker inspect -f '{{.Name}} {{range .NetworkSettings.Networks}}{{.IPAddress}} {{end}}' amf nrf db
/amf 10.33.33.12 
/nrf 10.33.33.3 
/db 10.33.33.6 
containernet> ue2_1 ping -c 2 10.33.33.12
PING 10.33.33.12 (10.33.33.12) 56(84) bytes of data.

--- 10.33.33.12 ping statistics ---
2 packets transmitted, 0 received, 100% packet loss, time 1035ms

containernet> ue2_1 bash -c 'timeout 3 bash -c "echo > /dev/tcp/<IP do db>/27017" && echo "MONGO ALCANÇÁVEL" || echo "bloqueado"'
bash: line 1: /dev/tcp/: Is a directory
bloqueado
containernet> ue2_1 bash -c 'timeout 3 bash -c "echo > /dev/tcp/10.33.33.6/27017" && echo "MONGO ALCANÇÁVEL" || echo "bloqueado"
> ^C^C
containernet> ue2_1 bash -c 'timeout 3 bash -c "echo > /dev/tcp/8.8.8.8/53" && echo ABERTO || echo FECHADO'
ABERTO
containernet> sh bash -c 'timeout 3 bash -c "echo > /dev/tcp/10.33.33.6/27017" && echo ABERTO || echo FECHADO'
ABERTO
containernet> ue2_1 bash -c 'timeout 3 bash -c "echo > /dev/tcp/10.33.33.6/27017" && echo MONGO_ABERTO || echo MONGO_FECHADO'
MONGO_FECHADO
containernet> ue2_1 bash -c 'timeout 3 bash -c "echo > /dev/tcp/10.33.33.3/80" && echo NRF_ABERTO || echo NRF_FECHADO'
NRF_FECHADO
containernet> ue2_1 bash -c 'timeout 3 bash -c "echo > /dev/tcp/10.33.33.12/80" && echo AMF_ABERTO || echo AMF_FECHADO'
AMF_FECHADO
containernet> sh sudo docker version --format '{{.Server.Version}}'
29.7.2
containernet> sh sudo iptables -t raw -S | grep -i drop
# Warning: iptables-legacy tables present, use iptables-legacy to see them
-A PREROUTING -d 10.33.33.2/32 ! -i br-ogs -j DROP
-A PREROUTING -d 10.34.0.2/32 ! -i br-access -j DROP
-A PREROUTING -d 10.33.33.3/32 ! -i br-ogs -j DROP
-A PREROUTING -d 10.33.33.6/32 ! -i br-ogs -j DROP
-A PREROUTING -d 10.33.33.7/32 ! -i br-ogs -j DROP
-A PREROUTING -d 10.33.33.8/32 ! -i br-ogs -j DROP
-A PREROUTING -d 10.33.33.9/32 ! -i br-ogs -j DROP
-A PREROUTING -d 10.33.33.10/32 ! -i br-ogs -j DROP
-A PREROUTING -d 10.33.33.11/32 ! -i br-ogs -j DROP
-A PREROUTING -d 10.33.33.12/32 ! -i br-ogs -j DROP
-A PREROUTING -d 10.33.33.13/32 ! -i br-ogs -j DROP
-A PREROUTING -d 10.33.33.14/32 ! -i br-ogs -j DROP
-A PREROUTING -d 10.33.33.15/32 ! -i br-ogs -j DROP
-A PREROUTING -d 10.33.33.16/32 ! -i br-ogs -j DROP
-A PREROUTING -d 10.33.33.17/32 ! -i br-ogs -j DROP
-A PREROUTING -d 10.33.33.18/32 ! -i br-ogs -j DROP
-A PREROUTING -d 10.34.0.3/32 ! -i br-access -j DROP
-A PREROUTING -d 10.33.33.19/32 ! -i br-ogs -j DROP
-A PREROUTING -d 10.33.33.20/32 ! -i br-ogs -j DROP
-A PREROUTING -d 172.17.0.2/32 ! -i docker0 -j DROP
-A PREROUTING -d 10.33.33.4/32 ! -i br-ogs -j DROP
-A PREROUTING -d 10.33.33.5/32 ! -i br-ogs -j DROP
-A PREROUTING -d 172.17.0.3/32 ! -i docker0 -j DROP
-A PREROUTING -d 172.17.0.4/32 ! -i docker0 -j DROP
-A PREROUTING -d 172.17.0.5/32 ! -i docker0 -j DROP
-A PREROUTING -d 172.17.0.6/32 ! -i docker0 -j DROP
containernet> sh sudo iptables -S DOCKER-USER
# Warning: iptables-legacy tables present, use iptables-legacy to see them
-N DOCKER-USER
-A DOCKER-USER -m comment --comment FAIR5G -j ACCEPT
containernet> sh sudo docker inspect -f '{{.Name}} {{.NetworkSettings.IPAddress}}' onos-controller

template parsing error: template: :1:28: executing "" at <.NetworkSettings.IPAddress>: map has no entry for key "IPAddress"
containernet> ue2_1 bash -c 'timeout 3 bash -c "echo > /dev/tcp/172.17.0.2/8181" && echo ONOS_ABERTO || echo ONOS_FECHADO'
ONOS_ABERTO
containernet> ue2_1 bash -c 'exec 3<>/dev/tcp/172.17.0.2/8181; printf "GET /onos/v1/devices HTTP/1.0\r\nAuthorization: Basic b25vczpyb2Nrcw==\r\n\r\n" >&3; timeout 3 head -c 600 <&3'
HTTP/1.1 200 OK
Content-Type: application/json
Content-Length: 396
Server: Jetty(9.4.28.v20200408)

{"devices":[{"id":"of:0000000000000001","type":"SWITCH","available":true,"role":"MASTER","mfr":"Nicira, Inc.","hw":"Open vSwitch","sw":"2.17.12","serial":"None","driver":"ovs","chassisId":"1","lastUpdate":"1791413294478","humanReadableLastUpdate":"connected 1h0m ago","annotations":{"channelId":"172.17.0.1:34076","datapathDescription":"s1","managementAddress":"172.17.0.1","protocol":"OF_13"}}]}containernet> 
