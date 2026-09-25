# syntax=docker/dockerfile:1
ARG OPEN5GS_VERSION="v2.7.5"

# Derived UPF image, adding the traffic measurement tools used by the
# experiments.
#
# The UPF runs from the published image (ghcr.io/borjis131/upf), not from a
# locally built one, so editing images/upf/Dockerfile has no effect on what
# actually runs. This thin layer is what puts iperf3 inside the UPF.
#
# Why it belongs in the image and not in a per-run install step: installing it
# at runtime requires network access and is lost when the container is
# recreated, which makes it unusable for measurement campaigns — a DNS outage
# mid-campaign would take down the round.
FROM ghcr.io/borjis131/upf:${OPEN5GS_VERSION}

RUN apt-get update \
 && apt-get install -y --no-install-recommends iperf3 \
 && rm -rf /var/lib/apt/lists/*
