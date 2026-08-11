#!/usr/bin/env bash

set -u

PASS_COUNT=0
FAIL_COUNT=0

run_check() {
    local description="$1"
    shift

    printf '%-62s' "$description"

    if "$@" >/dev/null 2>&1; then
        echo "[PASS]"
        PASS_COUNT=$((PASS_COUNT + 1))
    else
        echo "[FAIL]"
        FAIL_COUNT=$((FAIL_COUNT + 1))
    fi
}

echo "TOP-02 CHAIN Baseline Validation"
echo "================================"

run_check \
    "HostA has 10.20.1.10/24 on eth1" \
    docker exec clab-top02chain-hosta \
        sh -c 'ip -4 addr show dev eth1 | grep -q "10.20.1.10/24"'

run_check \
    "R1 has 10.20.1.1/24 on eth1" \
    docker exec clab-top02chain-r1 \
        sh -c 'ip -4 addr show dev eth1 | grep -q "10.20.1.1/24"'

run_check \
    "R1 has 10.20.12.1/29 on eth2" \
    docker exec clab-top02chain-r1 \
        sh -c 'ip -4 addr show dev eth2 | grep -q "10.20.12.1/29"'

run_check \
    "R2 has 10.20.12.2/29 on eth1" \
    docker exec clab-top02chain-r2 \
        sh -c 'ip -4 addr show dev eth1 | grep -q "10.20.12.2/29"'

run_check \
    "R2 has 10.20.23.1/29 on eth2" \
    docker exec clab-top02chain-r2 \
        sh -c 'ip -4 addr show dev eth2 | grep -q "10.20.23.1/29"'

run_check \
    "R3 has 10.20.23.2/29 on eth1" \
    docker exec clab-top02chain-r3 \
        sh -c 'ip -4 addr show dev eth1 | grep -q "10.20.23.2/29"'

run_check \
    "R3 has 10.20.3.1/24 on eth2" \
    docker exec clab-top02chain-r3 \
        sh -c 'ip -4 addr show dev eth2 | grep -q "10.20.3.1/24"'

run_check \
    "HostB has 10.20.3.10/24 on eth1" \
    docker exec clab-top02chain-hostb \
        sh -c 'ip -4 addr show dev eth1 | grep -q "10.20.3.10/24"'

run_check \
    "IPv4 forwarding is enabled on R1" \
    docker exec clab-top02chain-r1 \
        sh -c 'test "$(cat /proc/sys/net/ipv4/ip_forward)" = "1"'

run_check \
    "IPv4 forwarding is enabled on R2" \
    docker exec clab-top02chain-r2 \
        sh -c 'test "$(cat /proc/sys/net/ipv4/ip_forward)" = "1"'

run_check \
    "IPv4 forwarding is enabled on R3" \
    docker exec clab-top02chain-r3 \
        sh -c 'test "$(cat /proc/sys/net/ipv4/ip_forward)" = "1"'

run_check \
    "HostA default route uses R1" \
    docker exec clab-top02chain-hosta \
        sh -c 'ip route show default | grep -Eq "^default via 10\.20\.1\.1([[:space:]]|$)"'

run_check \
    "R1 route uses R2 toward 10.20.3.0/24" \
    docker exec clab-top02chain-r1 \
        sh -c 'ip route show 10.20.3.0/24 | grep -Eq "^10\.20\.3\.0/24 via 10\.20\.12\.2([[:space:]]|$)"'

run_check \
    "R2 route uses R3 toward 10.20.3.0/24" \
    docker exec clab-top02chain-r2 \
        sh -c 'ip route show 10.20.3.0/24 | grep -Eq "^10\.20\.3\.0/24 via 10\.20\.23\.2([[:space:]]|$)"'

run_check \
    "HostB route uses R3 toward 10.20.1.0/24" \
    docker exec clab-top02chain-hostb \
        sh -c 'ip route show 10.20.1.0/24 | grep -Eq "^10\.20\.1\.0/24 via 10\.20\.3\.1([[:space:]]|$)"'

run_check \
    "HostB route returns R2 transit traffic through R3" \
    docker exec clab-top02chain-hostb \
        sh -c 'ip route show 10.20.23.0/29 | grep -Eq "^10\.20\.23\.0/29 via 10\.20\.3\.1([[:space:]]|$)"'

run_check \
    "R3 route uses R2 toward 10.20.1.0/24" \
    docker exec clab-top02chain-r3 \
        sh -c 'ip route show 10.20.1.0/24 | grep -Eq "^10\.20\.1\.0/24 via 10\.20\.23\.1([[:space:]]|$)"'

run_check \
    "R2 route uses R1 toward 10.20.1.0/24" \
    docker exec clab-top02chain-r2 \
        sh -c 'ip route show 10.20.1.0/24 | grep -Eq "^10\.20\.1\.0/24 via 10\.20\.12\.1([[:space:]]|$)"'

run_check \
    "HostA reaches local gateway R1" \
    docker exec clab-top02chain-hosta \
        ping -c 2 -W 1 10.20.1.1

run_check \
    "R1 reaches expected transit R2" \
    docker exec clab-top02chain-r1 \
        ping -c 2 -W 1 10.20.12.2

run_check \
    "R2 reaches downstream router R3" \
    docker exec clab-top02chain-r2 \
        ping -c 2 -W 1 10.20.23.2

run_check \
    "R3 reaches destination HostB" \
    docker exec clab-top02chain-r3 \
        ping -c 2 -W 1 10.20.3.10

run_check \
    "HostA reaches HostB end-to-end" \
    docker exec clab-top02chain-hosta \
        ping -c 2 -W 1 10.20.3.10

run_check \
    "HostB reaches HostA end-to-end" \
    docker exec clab-top02chain-hostb \
        ping -c 2 -W 1 10.20.1.10

run_check \
    "Transit R2 reaches HostB through R3" \
    docker exec clab-top02chain-r2 \
        ping -c 2 -W 1 10.20.3.10

run_check \
    "Wrong next-hop 10.20.12.6 is not locally assigned on R1" \
    docker exec clab-top02chain-r1 \
        sh -c '! ip -4 addr show | grep -q "10.20.12.6/"'

run_check \
    "Wrong next-hop 10.20.12.6 is unreachable from R1" \
    docker exec clab-top02chain-r1 \
        sh -c '! ping -c 2 -W 1 10.20.12.6'

run_check \
    "R1 baseline route excludes wrong next-hop 10.20.12.6" \
    docker exec clab-top02chain-r1 \
        sh -c '! ip route show 10.20.3.0/24 | grep -q "via 10.20.12.6"'

run_check \
    "HostA has no selected-flow specific route" \
    docker exec clab-top02chain-hosta \
        sh -c '! ip route show exact 10.20.3.0/24 | grep -q .'

run_check \
    "Controlled wrong source gateway is unreachable" \
    docker exec clab-top02chain-hosta \
        sh -c '! ping -c 2 -W 1 10.20.1.254'

run_check \
    "R1 has iptables and no IND-P6 tagged rule" \
    docker exec clab-top02chain-r1 \
        sh -c 'command -v iptables >/dev/null && ! iptables -w 2 -t filter -S FORWARD | grep -F -- "--comment IND-P6"'

echo
echo "Passed: $PASS_COUNT"
echo "Failed: $FAIL_COUNT"

if [ "$FAIL_COUNT" -ne 0 ]; then
    echo "Baseline status: INVALID"
    exit 1
fi

echo "Baseline status: VALID"
