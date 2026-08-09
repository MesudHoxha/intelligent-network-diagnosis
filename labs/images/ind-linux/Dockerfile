FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        iproute2 \
        iptables \
        iputils-ping \
        traceroute \
        tcpdump \
        curl \
        jq \
        net-tools \
        procps \
        ethtool \
        iperf3 \
        dnsutils \
        netcat-openbsd && \
    rm -rf /var/lib/apt/lists/*

CMD ["sleep", "infinity"]
