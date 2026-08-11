#!/usr/bin/env bash

set -u

PASS_COUNT=0
FAIL_COUNT=0

run_check() {
    local description="$1"
    shift

    printf '%-72s' "$description"
    if "$@" >/dev/null 2>&1; then
        echo "[PASS]"
        PASS_COUNT=$((PASS_COUNT + 1))
    else
        echo "[FAIL]"
        FAIL_COUNT=$((FAIL_COUNT + 1))
    fi
}

echo "P6 E06 TOP-04 FILTER-BOUNDARY Baseline Validation"
echo "=================================================="

run_check "HostA has its reviewed source address" \
    docker exec clab-p6top04filter-hosta \
        sh -c 'ip -4 addr show dev eth1 | grep -q "10.60.1.10/24"'
run_check "HostA default route uses R1" \
    docker exec clab-p6top04filter-hosta \
        sh -c 'ip route show default | grep -Eq "^default via 10\.60\.1\.1 dev eth1([[:space:]]|$)"'
run_check "HostA has no destination-specific route" \
    docker exec clab-p6top04filter-hosta \
        sh -c '! ip route show exact 10.60.3.0/24 | grep -q .'
run_check "R1 routes the destination toward FW1" \
    docker exec clab-p6top04filter-r1 \
        sh -c 'ip route show 10.60.3.0/24 | grep -Eq "^10\.60\.3\.0/24 via 10\.60\.12\.2 dev eth2([[:space:]]|$)"'
run_check "FW1 routes the destination toward R2" \
    docker exec clab-p6top04filter-fw1 \
        sh -c 'ip route show 10.60.3.0/24 | grep -Eq "^10\.60\.3\.0/24 via 10\.60\.23\.2 dev eth2([[:space:]]|$)"'
run_check "R2 routes the source toward FW1" \
    docker exec clab-p6top04filter-r2 \
        sh -c 'ip route show 10.60.1.0/24 | grep -Eq "^10\.60\.1\.0/24 via 10\.60\.23\.1 dev eth1([[:space:]]|$)"'
run_check "HostB routes the source toward R2" \
    docker exec clab-p6top04filter-hostb \
        sh -c 'ip route show 10.60.1.0/24 | grep -Eq "^10\.60\.1\.0/24 via 10\.60\.3\.1 dev eth1([[:space:]]|$)"'
run_check "R1 forwarding is enabled" \
    docker exec clab-p6top04filter-r1 \
        sh -c 'test "$(cat /proc/sys/net/ipv4/ip_forward)" = "1"'
run_check "FW1 forwarding is enabled" \
    docker exec clab-p6top04filter-fw1 \
        sh -c 'test "$(cat /proc/sys/net/ipv4/ip_forward)" = "1"'
run_check "R2 forwarding is enabled" \
    docker exec clab-p6top04filter-r2 \
        sh -c 'test "$(cat /proc/sys/net/ipv4/ip_forward)" = "1"'
run_check "HostA reaches its expected gateway" \
    docker exec clab-p6top04filter-hosta ping -c 2 -W 1 10.60.1.1
run_check "FW1 reaches its expected next hop" \
    docker exec clab-p6top04filter-fw1 ping -c 2 -W 1 10.60.23.2
run_check "R2 reaches HostB downstream" \
    docker exec clab-p6top04filter-r2 ping -c 2 -W 1 10.60.3.10
run_check "HostA reaches HostB end-to-end" \
    docker exec clab-p6top04filter-hosta ping -c 2 -W 1 10.60.3.10
run_check "HostB reaches HostA end-to-end" \
    docker exec clab-p6top04filter-hostb ping -c 2 -W 1 10.60.1.10
run_check "Controlled wrong source gateway is unreachable" \
    docker exec clab-p6top04filter-hosta \
        sh -c '! ping -c 2 -W 1 10.60.1.254'
run_check "Controlled wrong next hop is unreachable" \
    docker exec clab-p6top04filter-fw1 \
        sh -c '! ping -c 2 -W 1 10.60.23.6'
run_check "FW1 forwarding policy is explicitly ACCEPT" \
    docker exec clab-p6top04filter-fw1 \
        sh -c 'iptables -w 2 -t filter -S FORWARD | grep -qx -- "-P FORWARD ACCEPT"'
run_check "FW1 has no IND-P6 tagged policy rule" \
    docker exec clab-p6top04filter-fw1 \
        sh -c '! iptables -w 2 -t filter -S FORWARD | grep -F -- "--comment IND-P6"'

echo
echo "Passed: $PASS_COUNT"
echo "Failed: $FAIL_COUNT"

if [ "$FAIL_COUNT" -ne 0 ]; then
    echo "Baseline status: INVALID"
    exit 1
fi

echo "Baseline status: VALID"
