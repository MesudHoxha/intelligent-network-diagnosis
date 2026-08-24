FROM ind-linux:0.1

ENV DEBIAN_FRONTEND=noninteractive

# This is a distinct X4 image.  The accepted ind-linux:0.1 tag is never
# rebuilt, retagged, or modified by this definition.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        dnsmasq \
        isc-dhcp-client \
        python3 && \
    rm -rf /var/lib/apt/lists/*

COPY x4-dhcp-service /usr/local/bin/x4-dhcp-service
COPY x4-dhclient.conf /etc/x4-dhcp/dhclient.conf
RUN chmod 0755 /usr/local/bin/x4-dhcp-service

CMD ["sleep", "infinity"]
