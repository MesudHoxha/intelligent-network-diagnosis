#!/usr/bin/env bash

set -u

PASS_COUNT=0
FAIL_COUNT=0

run_check() {
    local description="$1"
    shift

    printf '%-70s' "$description"

    if "$@" >/dev/null 2>&1; then
        echo "[PASS]"
        PASS_COUNT=$((PASS_COUNT + 1))
    else
        echo "[FAIL]"
        FAIL_COUNT=$((FAIL_COUNT + 1))
    fi
}

echo "TOP-02 DUAL-TRANSIT Baseline Validation"
echo "======================================="

run_check \
    "HostA has 10.40.1.10/24 on eth1" \
    docker exec clab-top02dual-hosta \
        sh -c 'ip -4 addr show dev eth1 | grep -q "10.40.1.10/24"'

run_check \
    "R1 has 10.40.1.1/24 on eth1" \
    docker exec clab-top02dual-r1 \
        sh -c 'ip -4 addr show dev eth1 | grep -q "10.40.1.1/24"'

run_check \
    "R1 has 10.40.12.1/29 on eth2" \
    docker exec clab-top02dual-r1 \
        sh -c 'ip -4 addr show dev eth2 | grep -q "10.40.12.1/29"'

run_check \
    "R1 has 10.40.13.1/29 on eth3" \
    docker exec clab-top02dual-r1 \
        sh -c 'ip -4 addr show dev eth3 | grep -q "10.40.13.1/29"'

run_check \
    "R2 has 10.40.12.2/29 on eth1" \
    docker exec clab-top02dual-r2 \
        sh -c 'ip -4 addr show dev eth1 | grep -q "10.40.12.2/29"'

run_check \
    "R2 has 10.40.2.1/24 on eth2" \
    docker exec clab-top02dual-r2 \
        sh -c 'ip -4 addr show dev eth2 | grep -q "10.40.2.1/24"'

run_check \
    "HostB has 10.40.2.10/24 on eth1" \
    docker exec clab-top02dual-hostb \
        sh -c 'ip -4 addr show dev eth1 | grep -q "10.40.2.10/24"'

run_check \
    "R3 has 10.40.13.2/29 on eth1" \
    docker exec clab-top02dual-r3 \
        sh -c 'ip -4 addr show dev eth1 | grep -q "10.40.13.2/29"'

run_check \
    "R3 has 10.40.3.1/24 on eth2" \
    docker exec clab-top02dual-r3 \
        sh -c 'ip -4 addr show dev eth2 | grep -q "10.40.3.1/24"'

run_check \
    "HostC has 10.40.3.10/24 on eth1" \
    docker exec clab-top02dual-hostc \
        sh -c 'ip -4 addr show dev eth1 | grep -q "10.40.3.10/24"'

run_check \
    "IPv4 forwarding is enabled on R1" \
    docker exec clab-top02dual-r1 \
        sh -c 'test "$(cat /proc/sys/net/ipv4/ip_forward)" = "1"'

run_check \
    "IPv4 forwarding is enabled on R2" \
    docker exec clab-top02dual-r2 \
        sh -c 'test "$(cat /proc/sys/net/ipv4/ip_forward)" = "1"'

run_check \
    "IPv4 forwarding is enabled on R3" \
    docker exec clab-top02dual-r3 \
        sh -c 'test "$(cat /proc/sys/net/ipv4/ip_forward)" = "1"'

run_check \
    "HostA route uses R1 toward HostB arm" \
    docker exec clab-top02dual-hosta \
        sh -c 'ip route show 10.40.2.0/24 | grep -Eq "^10\.40\.2\.0/24 via 10\.40\.1\.1([[:space:]]|$)"'

run_check \
    "HostA route uses R1 toward HostC arm" \
    docker exec clab-top02dual-hosta \
        sh -c 'ip route show 10.40.3.0/24 | grep -Eq "^10\.40\.3\.0/24 via 10\.40\.1\.1([[:space:]]|$)"'

run_check \
    "R1 selects R2 for the alternate HostB arm" \
    docker exec clab-top02dual-r1 \
        sh -c 'ip route show 10.40.2.0/24 | grep -Eq "^10\.40\.2\.0/24 via 10\.40\.12\.2([[:space:]]|$)"'

run_check \
    "R1 selects R3 for the observed HostC arm" \
    docker exec clab-top02dual-r1 \
        sh -c 'ip route show 10.40.3.0/24 | grep -Eq "^10\.40\.3\.0/24 via 10\.40\.13\.2([[:space:]]|$)"'

run_check \
    "R2 return route uses R1 toward HostA" \
    docker exec clab-top02dual-r2 \
        sh -c 'ip route show 10.40.1.0/24 | grep -Eq "^10\.40\.1\.0/24 via 10\.40\.12\.1([[:space:]]|$)"'

run_check \
    "HostB return route uses R2 toward HostA" \
    docker exec clab-top02dual-hostb \
        sh -c 'ip route show 10.40.1.0/24 | grep -Eq "^10\.40\.1\.0/24 via 10\.40\.2\.1([[:space:]]|$)"'

run_check \
    "R3 return route uses R1 toward HostA" \
    docker exec clab-top02dual-r3 \
        sh -c 'ip route show 10.40.1.0/24 | grep -Eq "^10\.40\.1\.0/24 via 10\.40\.13\.1([[:space:]]|$)"'

run_check \
    "HostC return route uses R3 toward HostA" \
    docker exec clab-top02dual-hostc \
        sh -c 'ip route show 10.40.1.0/24 | grep -Eq "^10\.40\.1\.0/24 via 10.40.3.1([[:space:]]|$)"'

run_check \
    "HostA reaches local gateway R1" \
    docker exec clab-top02dual-hosta \
        ping -c 2 -W 1 10.40.1.1

run_check \
    "R1 reaches alternate transit R2" \
    docker exec clab-top02dual-r1 \
        ping -c 2 -W 1 10.40.12.2

run_check \
    "R2 reaches alternate destination HostB" \
    docker exec clab-top02dual-r2 \
        ping -c 2 -W 1 10.40.2.10

run_check \
    "R1 reaches observed transit R3" \
    docker exec clab-top02dual-r1 \
        ping -c 2 -W 1 10.40.13.2

run_check \
    "R3 reaches observed destination HostC" \
    docker exec clab-top02dual-r3 \
        ping -c 2 -W 1 10.40.3.10

run_check \
    "HostA reaches HostB through the alternate transit arm" \
    docker exec clab-top02dual-hosta \
        ping -c 2 -W 1 10.40.2.10

run_check \
    "HostB reaches HostA through the alternate transit arm" \
    docker exec clab-top02dual-hostb \
        ping -c 2 -W 1 10.40.1.10

run_check \
    "HostA reaches HostC through the observed transit arm" \
    docker exec clab-top02dual-hosta \
        ping -c 2 -W 1 10.40.3.10

run_check \
    "HostC reaches HostA through the observed transit arm" \
    docker exec clab-top02dual-hostc \
        ping -c 2 -W 1 10.40.1.10

run_check \
    "Wrong next-hop 10.40.12.6 is not locally assigned on R1" \
    docker exec clab-top02dual-r1 \
        sh -c '! ip -4 addr show | grep -q "10.40.12.6/"'

run_check \
    "Wrong next-hop 10.40.12.6 is unreachable from R1" \
    docker exec clab-top02dual-r1 \
        sh -c '! ping -c 2 -W 1 10.40.12.6'

run_check \
    "R1 baseline HostC route excludes wrong next-hop 10.40.12.6" \
    docker exec clab-top02dual-r1 \
        sh -c '! ip route show 10.40.3.0/24 | grep -q "via 10.40.12.6"'

echo
echo "Passed: $PASS_COUNT"
echo "Failed: $FAIL_COUNT"

if [ "$FAIL_COUNT" -ne 0 ]; then
    echo "Baseline status: INVALID"
    exit 1
fi

echo "Baseline status: VALID"
