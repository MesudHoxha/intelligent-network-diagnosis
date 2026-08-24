#!/usr/bin/env bash
set -u
pass=0; fail=0
check() { printf '%-68s' "$1"; shift; if "$@" >/dev/null 2>&1; then echo '[PASS]'; pass=$((pass+1)); else echo '[FAIL]'; fail=$((fail+1)); fi; }
echo 'X4-R1 DHCP Server Unavailable Baseline Validation'
check 'X4 DHCP image has dnsmasq and dhclient' docker exec clab-x4r1-client sh -c 'command -v dnsmasq && command -v dhclient && command -v dig && command -v nc'
check 'DHCP server wrapper reports running' docker exec clab-x4r1-dhcp_server x4-dhcp-service status
check 'DHCP server uses its reviewed interface configuration' docker exec clab-x4r1-dhcp_server sh -c 'grep -qx interface=eth1 /etc/x4-dhcp/dnsmasq.conf && grep -qx dhcp-range=10.40.0.100,10.40.0.150,255.255.255.0,1h /etc/x4-dhcp/dnsmasq.conf'
check 'Real DHCP exchange gives client expected-scope lease' docker exec clab-x4r1-client sh -c 'dhclient -r eth1 >/dev/null 2>&1 || true; rm -f /tmp/x4-dhclient.leases /tmp/x4-dhclient.pid; dhclient -4 -1 -v -cf /etc/x4-dhcp/dhclient.conf -pf /tmp/x4-dhclient.pid -lf /tmp/x4-dhclient.leases eth1 >/tmp/x4-dhclient.out 2>&1 && ip -4 -o addr show dev eth1 | grep -q 10.40.0.'
check 'Observer reaches DNS service control endpoint' docker exec clab-x4r1-observer ping -c 1 -W 1 10.40.0.3
check 'Observer obtains expected real DNS answer' docker exec clab-x4r1-observer sh -c 'dig +time=2 +tries=1 @10.40.0.3 app.x4.test A +short | grep -qx 10.40.0.4'
check 'Application process is running' docker exec clab-x4r1-app_server sh -c "pgrep -f 'http.server 8080'"
check 'Observer reaches application TCP endpoint' docker exec clab-x4r1-observer nc -z -w 2 10.40.0.4 8080
check 'No controlled service policy block exists' docker exec clab-x4r1-observer sh -c '! iptables -S | grep -q X4-R1-SERVICE-BLOCK'
echo "Passed: $pass"; echo "Failed: $fail"
if [ "$fail" -ne 0 ]; then echo 'Baseline status: INVALID'; exit 1; fi
echo 'Baseline status: VALID'
