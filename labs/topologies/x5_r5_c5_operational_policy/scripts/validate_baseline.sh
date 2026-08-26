#!/usr/bin/env bash
set -euo pipefail

healthy() {
  for node in r1 r2 r3; do docker exec "clab-x5r5c5-${node}" vtysh -c 'show ip ospf neighbor json' | grep -q 'Full'; done
  docker exec clab-x5r5c5-r1 vtysh -c 'show ip route 10.51.3.0/24 json' | grep -qi ospf
  docker exec clab-x5r5c5-hosta ping -c 1 -W 2 10.51.3.2 >/dev/null
  docker exec clab-x5r5c5-r3 vtysh -c 'show running-config' | grep -q 'redistribute connected route-map X5-R5-C5-EXPORT'
  docker exec clab-x5r5c5-r3 vtysh -c 'show running-config' | grep -q 'ip prefix-list X5-R5-C5-TARGET seq 5 permit 10.51.3.0/24'
  ! docker exec clab-x5r5c5-r3 vtysh -c 'show running-config' | grep -q 'network 10.51.3.0/24 area 0'
}
for attempt in {1..20}; do
  if healthy; then exit 0; fi
  sleep 2
done
echo 'X5-R6 healthy operational-policy OSPF baseline did not converge within 40 seconds.' >&2
exit 1
