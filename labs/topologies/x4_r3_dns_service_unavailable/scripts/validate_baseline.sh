#!/usr/bin/env bash
set -u
pass=0; fail=0
check() { printf '%-68s' "$1"; shift; if "$@" >/dev/null 2>&1; then echo '[PASS]'; pass=$((pass+1)); else echo '[FAIL]'; fail=$((fail+1)); fi; }
echo 'X4-R3 DNS Service Down Baseline Validation'
check 'X4 DNS image has dnsmasq dig and dhclient' docker exec clab-x4r3-client sh -c 'command -v dnsmasq && command -v dig && command -v dhclient && command -v nc'
check 'DNS server process and UDP 53 listener are present' docker exec clab-x4r3-dns_server sh -c 'test -s /run/x4-dns.pid && kill -0 "$(cat /run/x4-dns.pid)" && ss -lun | grep -q :53'
check 'DHCP server wrapper reports running' docker exec clab-x4r3-dhcp_server x4-dhcp-service status
check 'Real DHCP exchange gives client expected-scope lease' docker exec clab-x4r3-client sh -c 'dhclient -r eth1 >/dev/null 2>&1 || true; rm -f /tmp/x4-dhclient.leases /tmp/x4-dhclient.pid; dhclient -4 -1 -v -cf /etc/x4-dhcp/dhclient.conf -pf /tmp/x4-dhclient.pid -lf /tmp/x4-dhclient.leases eth1 >/tmp/x4-dhclient.out 2>&1 && ip -4 -o addr show dev eth1 | grep -q 10.40.0.'
check 'Client reaches DNS host control endpoint' docker exec clab-x4r3-client ping -c 1 -W 1 10.40.0.3
check 'Client obtains expected real DNS answer' docker exec clab-x4r3-client sh -c 'dig +time=2 +tries=1 @10.40.0.3 app.x4.test A +short | grep -qx 10.40.0.4'
check 'Application process is running' docker exec clab-x4r3-app_server sh -c "pgrep -f 'http.server 8080'"
check 'Observer reaches application TCP endpoint' docker exec clab-x4r3-observer nc -z -w 2 10.40.0.4 8080
check 'No controlled service policy block exists' docker exec clab-x4r3-observer sh -c '! iptables -S | grep -q X4-R1-SERVICE-BLOCK'
echo "Passed: $pass"; echo "Failed: $fail"
if [ "$fail" -ne 0 ]; then echo 'Baseline status: INVALID'; exit 1; fi
echo 'Baseline status: VALID'
