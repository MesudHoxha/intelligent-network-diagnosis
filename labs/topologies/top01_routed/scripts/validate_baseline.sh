#!/usr/bin/env bash

set -u

PASS_COUNT=0
FAIL_COUNT=0

run_check() {
    local description="$1"
    shift

    printf '%-50s' "$description"

    if "$@" >/dev/null 2>&1; then
        echo "[PASS]"
        PASS_COUNT=$((PASS_COUNT + 1))
    else
        echo "[FAIL]"
        FAIL_COUNT=$((FAIL_COUNT + 1))
    fi
}

echo "TOP-01 Baseline Validation"
echo "=========================="

run_check \
    "HostA reaches local router R1" \
    docker exec clab-top01-hosta ping -c 2 -W 1 10.10.1.1

run_check \
    "R1 reaches transit neighbor R2" \
    docker exec clab-top01-r1 ping -c 2 -W 1 10.10.12.2

run_check \
    "R2 reaches HostB" \
    docker exec clab-top01-r2 ping -c 2 -W 1 10.10.2.10

run_check \
    "HostA reaches HostB end-to-end" \
    docker exec clab-top01-hosta ping -c 2 -W 1 10.10.2.10

run_check \
    "HostA reaches alternate HostB address" \
    docker exec clab-top01-hosta ping -c 2 -W 1 10.10.22.10

run_check \
    "HostB reaches HostA end-to-end" \
    docker exec clab-top01-hostb ping -c 2 -W 1 10.10.1.10

run_check \
    "R1 contains route to HostB network" \
    docker exec clab-top01-r1 \
        sh -c 'test -n "$(ip route show 10.10.2.0/24)"'

run_check \
    "R1 contains route to alternate HostB network" \
    docker exec clab-top01-r1 \
        sh -c 'test -n "$(ip route show 10.10.22.0/24)"'

run_check \
    "R2 contains route to HostA network" \
    docker exec clab-top01-r2 \
        sh -c 'test -n "$(ip route show 10.10.1.0/24)"'

run_check \
    "R2 contains alternate gateway address" \
    docker exec clab-top01-r2 \
        sh -c 'ip -4 addr show dev eth2 | grep -q "10.10.22.1/24"'

run_check \
    "HostB contains alternate destination address" \
    docker exec clab-top01-hostb \
        sh -c 'ip -4 addr show dev eth1 | grep -q "10.10.22.10/24"'

run_check \
    "IPv4 forwarding is enabled on R1" \
    docker exec clab-top01-r1 \
        sh -c 'test "$(cat /proc/sys/net/ipv4/ip_forward)" = "1"'

run_check \
    "IPv4 forwarding is enabled on R2" \
    docker exec clab-top01-r2 \
        sh -c 'test "$(cat /proc/sys/net/ipv4/ip_forward)" = "1"'

echo
echo "Passed: $PASS_COUNT"
echo "Failed: $FAIL_COUNT"

if [ "$FAIL_COUNT" -ne 0 ]; then
    echo "Baseline status: INVALID"
    exit 1
fi

echo "Baseline status: VALID"
