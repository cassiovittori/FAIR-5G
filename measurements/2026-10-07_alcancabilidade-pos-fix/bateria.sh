#!/usr/bin/env bash
# Reachability battery after the docker0 isolation fix. Run with the environment UP
# and --ues-per-slice 2,1 (ue1_1, ue1_2, ue2).
ip_of()  { sudo docker inspect -f "{{with index .NetworkSettings.Networks \"$2\"}}{{.IPAddress}}{{end}}" "$1" 2>/dev/null; }
tun_ip() { sudo docker exec "$1" ip -4 -o addr show uesimtun0 | awk '{print $4}' | cut -d/ -f1; }
probe()  { echo -n "  tcp $2:$3 -> "; sudo docker exec "$1" timeout 3 bash -c "echo > /dev/tcp/$2/$3" 2>/dev/null && echo ABERTO || echo FECHADO; }
pingt()  { echo -n "  ping $2${3:+ -I $3} -> "; sudo docker exec "$1" ping ${3:+-I $3} -c 2 -W 2 "$2" >/dev/null 2>&1 && echo RESPONDE || echo SEM_RESPOSTA; }

date -Iseconds; sudo docker version -f 'Docker {{.Server.Version}}'
echo "== host"
sudo ss -ltnp | grep -E ':8181|:6653'
sudo iptables -S DOCKER-USER 2>/dev/null
sudo ovs-vsctl show | grep is_connected
echo "  ONOS via localhost: $(curl -u onos:rocks -s -o /dev/null -w '%{http_code}' http://localhost:8181/onos/v1/devices)"

ONOS=$(ip_of onos-controller fair5g-ctrl)
DB=$(ip_of db open5gs); DB=${DB:-10.33.33.6}
NRF=$(ip_of nrf open5gs); AMF=$(ip_of amf open5gs)
T11=$(tun_ip mn.ue1_1); T12=$(tun_ip mn.ue1_2); T2=$(tun_ip mn.ue2)
echo "ONOS=$ONOS DB=$DB NRF=$NRF AMF=$AMF | tunnel: ue1_1=$T11 ue1_2=$T12 ue2=$T2"

for UE in mn.ue1_1 mn.ue1_2 mn.ue2; do
  case $UE in
    mn.ue2) OTHER_UE=$T11; OTHER_GW=10.45.0.1; PEER=10.34.0.200 ;;
    *)      OTHER_UE=$T2;  OTHER_GW=10.46.0.1; PEER=10.34.0.202 ;;
  esac
  echo "== $UE"
  sudo docker exec $UE ip -br addr; sudo docker exec $UE ip route
  echo " [normal state]"
  pingt $UE 10.34.0.3                      # gNB: RESPONDE
  pingt $UE 8.8.8.8 uesimtun0              # via core: RESPONDE
  pingt $UE 8.8.8.8                        # no route: SEM_RESPOSTA
  pingt $UE $PEER                          # UE->UE on access net (M1): SEM_RESPOSTA
  for ip in 172.17.0.2 $ONOS 10.33.33.1; do probe $UE $ip 8181; done   # FECHADO
  echo " [default route forced through the tunnel]"
  sudo docker exec $UE ip route add default dev uesimtun0
  probe $UE 8.8.8.8 53                     # control: ABERTO
  for ip in 172.17.0.2 $ONOS 10.33.33.1; do probe $UE $ip 8181; done   # controller: FECHADO
  probe $UE $DB 27017; probe $UE $NRF 7777; probe $UE $AMF 7777          # core: FECHADO
  pingt $UE $OTHER_UE; pingt $UE $OTHER_GW                               # cross-slice: SEM_RESPOSTA
  sudo docker exec $UE ip route del default dev uesimtun0
done
echo "== intra-slice ue1_1 -> ue1_2 via tunnel (allowed on 2026-10-07; policy pending)"
pingt mn.ue1_1 $T12 uesimtun0
