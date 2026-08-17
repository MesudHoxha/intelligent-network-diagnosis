#!/usr/bin/env bash

set -u

PASS_COUNT=0
FAIL_COUNT=0

run_check() {
    local description="$1"
    shift
    printf '%-66s' "$description"
    if "$@" >/dev/null 2>&1; then
        echo "[PASS]"
        PASS_COUNT=$((PASS_COUNT + 1))
    else
        echo "[FAIL]"
        FAIL_COUNT=$((FAIL_COUNT + 1))
    fi
}

echo "X3-R1 Layer 2/VLAN Baseline Validation"
echo "======================================="

run_check "SW1 HostA access port is VLAN 10 PVID untagged" \
    docker exec clab-x3r1-sw1 sh -c \
    'bridge -j vlan show dev eth1 | jq -e '\''.[0].vlans | any(.vlan == 10 and (.flags | index("PVID")) and (.flags | index("Egress Untagged")))'\'''

run_check "SW1 HostA access port does not contain wrong VLAN 20" \
    docker exec clab-x3r1-sw1 sh -c \
    '! bridge -j vlan show dev eth1 | jq -e '\''.[0].vlans | any(.vlan == 20)'\'''

run_check "SW2 HostB access port is VLAN 10 PVID untagged" \
    docker exec clab-x3r1-sw2 sh -c \
    'bridge -j vlan show dev eth1 | jq -e '\''.[0].vlans | any(.vlan == 10 and (.flags | index("PVID")) and (.flags | index("Egress Untagged")))'\'''

run_check "SW1 trunk carries tagged VLAN 10" \
    docker exec clab-x3r1-sw1 sh -c \
    'bridge -j vlan show dev eth3 | jq -e '\''.[0].vlans | any(.vlan == 10 and ((.flags // []) | index("PVID") | not))'\'''

run_check "SW2 trunk carries tagged VLAN 10" \
    docker exec clab-x3r1-sw2 sh -c \
    'bridge -j vlan show dev eth3 | jq -e '\''.[0].vlans | any(.vlan == 10 and ((.flags // []) | index("PVID") | not))'\'''

run_check "SW1 trunk uses native VLAN 99" \
    docker exec clab-x3r1-sw1 sh -c \
    'bridge -j vlan show dev eth3 | jq -e '\''.[0].vlans | any(.vlan == 99 and (.flags | index("PVID")) and (.flags | index("Egress Untagged")))'\'''

run_check "SW2 trunk uses native VLAN 99" \
    docker exec clab-x3r1-sw2 sh -c \
    'bridge -j vlan show dev eth3 | jq -e '\''.[0].vlans | any(.vlan == 99 and (.flags | index("PVID")) and (.flags | index("Egress Untagged")))'\'''

run_check "Tagged VLAN 10 flow HostA reaches HostB" \
    docker exec clab-x3r1-hosta ping -c 2 -W 1 10.30.10.20

run_check "Tagged VLAN 10 return flow HostB reaches HostA" \
    docker exec clab-x3r1-hostb ping -c 2 -W 1 10.30.10.10

run_check "Native VLAN 99 flow HostC reaches HostD" \
    docker exec clab-x3r1-hostc ping -c 2 -W 1 10.30.99.20

run_check "Native VLAN 99 return flow HostD reaches HostC" \
    docker exec clab-x3r1-hostd ping -c 2 -W 1 10.30.99.10

echo
echo "Passed: $PASS_COUNT"
echo "Failed: $FAIL_COUNT"

if [ "$FAIL_COUNT" -ne 0 ]; then
    echo "Baseline status: INVALID"
    exit 1
fi

echo "Baseline status: VALID"
