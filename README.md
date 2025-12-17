# open5gs-mininet

## Dependencies
docker

make

Ubuntu 22.04 - jammy

## Step by step

1. Clone o repositorio
2. cd para o diretorio
3. `make`
4. `docker compose -f compose-files/network-slicing/docker-compose.yaml --env-file=.env up -d`
5. Para desligar os containers: `docker compose -f compose-files/network-slicing/docker-compose.yaml --env-file=.env down`

6. Depois voce precisa adicionar os UEs como subscribers, segue o addsub_ue.txt executando:
   `docker exec -it db mongosh`
   `use open5gs`
   E dentro do open5gs voce copia individualmente cada UE (cada UE termina em:
   `"schema_version": 1,
  "__v": 0
  })`

7. Para subir a topologia SDN linkada ao nosso Simulador 5G basta apenas ir para o diretório do containernet e rodar o script com: `sudo python3 auto_sdn.py`


## TODO

1. Add choices for user when using container net
2. Add Grafana access here
3. Automate add subscribers step
