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

echo "TOP-02 BRANCH Baseline Validation"
echo "================================="

run_check \
    "HostA has 10.30.1.10/24 on eth1" \
    docker exec clab-top02branch-hosta \
        sh -c 'ip -4 addr show dev eth1 | grep -q "10.30.1.10/24"'

run_check \
    "R1 has 10.30.1.1/24 on eth1" \
    docker exec clab-top02branch-r1 \
        sh -c 'ip -4 addr show dev eth1 | grep -q "10.30.1.1/24"'

run_check \
    "R1 has 10.30.12.1/29 on eth2" \
    docker exec clab-top02branch-r1 \
        sh -c 'ip -4 addr show dev eth2 | grep -q "10.30.12.1/29"'

run_check \
    "R2 has 10.30.12.2/29 on eth1" \
    docker exec clab-top02branch-r2 \
        sh -c 'ip -4 addr show dev eth1 | grep -q "10.30.12.2/29"'

run_check \
    "R2 has 10.30.23.1/29 on eth2" \
    docker exec clab-top02branch-r2 \
        sh -c 'ip -4 addr show dev eth2 | grep -q "10.30.23.1/29"'

run_check \
    "R2 has 10.30.24.1/29 on eth3" \
    docker exec clab-top02branch-r2 \
        sh -c 'ip -4 addr show dev eth3 | grep -q "10.30.24.1/29"'

run_check \
    "R3 has 10.30.23.2/29 on eth1" \
    docker exec clab-top02branch-r3 \
        sh -c 'ip -4 addr show dev eth1 | grep -q "10.30.23.2/29"'

run_check \
    "R3 has 10.30.3.1/24 on eth2" \
    docker exec clab-top02branch-r3 \
        sh -c 'ip -4 addr show dev eth2 | grep -q "10.30.3.1/24"'

run_check \
    "HostB has 10.30.3.10/24 on eth1" \
    docker exec clab-top02branch-hostb \
        sh -c 'ip -4 addr show dev eth1 | grep -q "10.30.3.10/24"'

run_check \
    "R4 has 10.30.24.2/29 on eth1" \
    docker exec clab-top02branch-r4 \
        sh -c 'ip -4 addr show dev eth1 | grep -q "10.30.24.2/29"'

run_check \
    "R4 has 10.30.4.1/24 on eth2" \
    docker exec clab-top02branch-r4 \
        sh -c 'ip -4 addr show dev eth2 | grep -q "10.30.4.1/24"'

run_check \
    "HostC has 10.30.4.10/24 on eth1" \
    docker exec clab-top02branch-hostc \
        sh -c 'ip -4 addr show dev eth1 | grep -q "10.30.4.10/24"'

run_check \
    "IPv4 forwarding is enabled on R1" \
    docker exec clab-top02branch-r1 \
        sh -c 'test "$(cat /proc/sys/net/ipv4/ip_forward)" = "1"'

run_check \
    "IPv4 forwarding is enabled on R2" \
    docker exec clab-top02branch-r2 \
        sh -c 'test "$(cat /proc/sys/net/ipv4/ip_forward)" = "1"'

run_check \
    "IPv4 forwarding is enabled on R3" \
    docker exec clab-top02branch-r3 \
        sh -c 'test "$(cat /proc/sys/net/ipv4/ip_forward)" = "1"'

run_check \
    "IPv4 forwarding is enabled on R4" \
    docker exec clab-top02branch-r4 \
        sh -c 'test "$(cat /proc/sys/net/ipv4/ip_forward)" = "1"'

run_check \
    "HostA route uses R1 toward HostB arm" \
    docker exec clab-top02branch-hosta \
        sh -c 'ip route show 10.30.3.0/24 | grep -Eq "^10\.30\.3\.0/24 via 10\.30\.1\.1([[:space:]]|$)"'

run_check \
    "HostA default route uses R1 toward HostC arm" \
    docker exec clab-top02branch-hosta \
        sh -c 'ip route show default | grep -Eq "^default via 10\.30\.1\.1([[:space:]]|$)"'

run_check \
    "R1 route uses R2 toward HostB arm" \
    docker exec clab-top02branch-r1 \
        sh -c 'ip route show 10.30.3.0/24 | grep -Eq "^10\.30\.3\.0/24 via 10\.30\.12\.2([[:space:]]|$)"'

run_check \
    "R1 route uses R2 toward HostC arm" \
    docker exec clab-top02branch-r1 \
        sh -c 'ip route show 10.30.4.0/24 | grep -Eq "^10\.30\.4\.0/24 via 10\.30\.12\.2([[:space:]]|$)"'

run_check \
    "R2 return route uses R1 toward HostA" \
    docker exec clab-top02branch-r2 \
        sh -c 'ip route show 10.30.1.0/24 | grep -Eq "^10\.30\.1\.0/24 via 10\.30\.12\.1([[:space:]]|$)"'

run_check \
    "R2 selects R3 for the independent HostB arm" \
    docker exec clab-top02branch-r2 \
        sh -c 'ip route show 10.30.3.0/24 | grep -Eq "^10\.30\.3\.0/24 via 10\.30\.23\.2([[:space:]]|$)"'

run_check \
    "R2 selects R4 for the observed HostC arm" \
    docker exec clab-top02branch-r2 \
        sh -c 'ip route show 10.30.4.0/24 | grep -Eq "^10\.30\.4\.0/24 via 10\.30\.24\.2([[:space:]]|$)"'

run_check \
    "R3 return route uses R2 toward HostA" \
    docker exec clab-top02branch-r3 \
        sh -c 'ip route show 10.30.1.0/24 | grep -Eq "^10\.30\.1\.0/24 via 10\.30\.23\.1([[:space:]]|$)"'

run_check \
    "HostB return route uses R3 toward HostA" \
    docker exec clab-top02branch-hostb \
        sh -c 'ip route show 10.30.1.0/24 | grep -Eq "^10\.30\.1\.0/24 via 10\.30\.3\.1([[:space:]]|$)"'

run_check \
    "R4 return route uses R2 toward HostA" \
    docker exec clab-top02branch-r4 \
        sh -c 'ip route show 10.30.1.0/24 | grep -Eq "^10\.30\.1\.0/24 via 10\.30\.24\.1([[:space:]]|$)"'

run_check \
    "HostC return route uses R4 toward HostA" \
    docker exec clab-top02branch-hostc \
        sh -c 'ip route show 10.30.1.0/24 | grep -Eq "^10\.30\.1\.0/24 via 10\.30\.4\.1([[:space:]]|$)"'

run_check \
    "HostA reaches local gateway R1" \
    docker exec clab-top02branch-hosta \
        ping -c 2 -W 1 10.30.1.1

run_check \
    "R1 reaches interior branch observer R2" \
    docker exec clab-top02branch-r1 \
        ping -c 2 -W 1 10.30.12.2

run_check \
    "R2 reaches independent-arm router R3" \
    docker exec clab-top02branch-r2 \
        ping -c 2 -W 1 10.30.23.2

run_check \
    "R3 reaches independent destination HostB" \
    docker exec clab-top02branch-r3 \
        ping -c 2 -W 1 10.30.3.10

run_check \
    "R2 reaches observed transit R4" \
    docker exec clab-top02branch-r2 \
        ping -c 2 -W 1 10.30.24.2

run_check \
    "R4 reaches observed destination HostC" \
    docker exec clab-top02branch-r4 \
        ping -c 2 -W 1 10.30.4.10

run_check \
    "HostA reaches HostB through the independent branch" \
    docker exec clab-top02branch-hosta \
        ping -c 2 -W 1 10.30.3.10

run_check \
    "HostB reaches HostA through the independent branch" \
    docker exec clab-top02branch-hostb \
        ping -c 2 -W 1 10.30.1.10

run_check \
    "HostA reaches HostC through the observed branch" \
    docker exec clab-top02branch-hosta \
        ping -c 2 -W 1 10.30.4.10

run_check \
    "HostC reaches HostA through the observed branch" \
    docker exec clab-top02branch-hostc \
        ping -c 2 -W 1 10.30.1.10

run_check \
    "Wrong next-hop 10.30.24.6 is not locally assigned on R2" \
    docker exec clab-top02branch-r2 \
        sh -c '! ip -4 addr show | grep -q "10.30.24.6/"'

run_check \
    "Wrong next-hop 10.30.24.6 is unreachable from R2" \
    docker exec clab-top02branch-r2 \
        sh -c '! ping -c 2 -W 1 10.30.24.6'

run_check \
    "R2 baseline HostC route excludes wrong next-hop 10.30.24.6" \
    docker exec clab-top02branch-r2 \
        sh -c '! ip route show 10.30.4.0/24 | grep -q "via 10.30.24.6"'

run_check \
    "HostA has no selected HostC specific route" \
    docker exec clab-top02branch-hosta \
        sh -c '! ip route show exact 10.30.4.0/24 | grep -q .'

run_check \
    "Controlled wrong source gateway is unreachable" \
    docker exec clab-top02branch-hosta \
        sh -c '! ping -c 2 -W 1 10.30.1.254'

run_check \
    "R2 has iptables and no IND-P6 tagged rule" \
    docker exec clab-top02branch-r2 \
        sh -c 'command -v iptables >/dev/null && ! iptables -w 2 -t filter -S FORWARD | grep -F -- "--comment IND-P6"'

echo
echo "Passed: $PASS_COUNT"
echo "Failed: $FAIL_COUNT"

if [ "$FAIL_COUNT" -ne 0 ]; then
    echo "Baseline status: INVALID"
    exit 1
fi

echo "Baseline status: VALID"
