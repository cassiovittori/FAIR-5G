# syntax=docker/dockerfile:1
ARG UERANSIM_VERSION="v3.2.7"

# Imagem derivada da oficial do UERANSIM, acrescentando as ferramentas de geracao
# e medicao de trafego usadas nos experimentos. Sem isso seria necessario instalar
# iperf3 em cada container a cada execucao — passo manual, dependente de rede, que
# se perde na recriacao e e facil de esquecer no meio de uma campanha.
FROM ghcr.io/borjis131/ue:${UERANSIM_VERSION}

RUN apt-get update \
 && apt-get install -y --no-install-recommends iperf3 iproute2 iputils-ping \
 && rm -rf /var/lib/apt/lists/*
