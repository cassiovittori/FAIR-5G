# open5gs-mininet

## Dependencies
docker
make
Ubuntu 22.04 - jammy

## Step by step

1. Clone repository
2. cd to directory
3. `make`
4. `docker compose -f compose-files/network-slicing/docker-compose.yaml --env-file=.env up -d`
5. To shut down container you run: `docker compose -f compose-files/network-slicing/docker-compose.yaml --env-file=.env down`


## TODO

1. Fix webui image
2. Add Grafana access here
