#!/usr/bin/env bash
set -euo pipefail
healthy() {
  for node in r1 r2 r3; do docker exec "clab-x5r1-${node}" vtysh -c 'show ip ospf neighbor json' | grep -q 'Full'; done
  docker exec clab-x5r1-r1 vtysh -c 'show ip route 10.51.3.0/24 json' | grep -qi ospf
  docker exec clab-x5r1-hosta ping -c 1 -W 2 10.51.3.2 >/dev/null
  docker exec clab-x5r1-r2 ip link show eth2 | grep -q 'UP'
  ! docker exec clab-x5r1-r1 vtysh -c 'show running-config' | grep -q 'ip route 10.51.3.0/24'
  ! docker exec clab-x5r1-r1 iptables -S | grep -q 'X5-R1-BLOCK'
}
for attempt in $(seq 1 20); do
  if healthy; then exit 0; fi
  sleep 2
done
echo 'X5-R1 healthy OSPF baseline did not converge within 40 seconds.' >&2
exit 1
