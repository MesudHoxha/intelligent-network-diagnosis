#!/usr/bin/env bash

set -u

PASS_COUNT=0
FAIL_COUNT=0

run_check() {
    local description="$1"
    shift

    printf '%-76s' "$description"

    if "$@" >/dev/null 2>&1; then
        echo "[PASS]"
        PASS_COUNT=$((PASS_COUNT + 1))
    else
        echo "[FAIL]"
        FAIL_COUNT=$((FAIL_COUNT + 1))
    fi
}

echo "TOP-03 ASYMMETRIC-RETURN Baseline Validation"
echo "============================================"

run_check \
    "HostA has 10.50.1.10/24 on eth1" \
    docker exec clab-top03asym-hosta \
        sh -c 'ip -4 addr show dev eth1 | grep -q "10.50.1.10/24"'

run_check \
    "R1 has 10.50.1.1/24 on eth1" \
    docker exec clab-top03asym-r1 \
        sh -c 'ip -4 addr show dev eth1 | grep -q "10.50.1.1/24"'

run_check \
    "R1 has 10.50.12.1/29 on eth2" \
    docker exec clab-top03asym-r1 \
        sh -c 'ip -4 addr show dev eth2 | grep -q "10.50.12.1/29"'

run_check \
    "R1 has 10.50.14.1/29 on eth3" \
    docker exec clab-top03asym-r1 \
        sh -c 'ip -4 addr show dev eth3 | grep -q "10.50.14.1/29"'

run_check \
    "R2 has 10.50.12.2/29 on eth1" \
    docker exec clab-top03asym-r2 \
        sh -c 'ip -4 addr show dev eth1 | grep -q "10.50.12.2/29"'

run_check \
    "R2 has 10.50.23.1/29 on eth2" \
    docker exec clab-top03asym-r2 \
        sh -c 'ip -4 addr show dev eth2 | grep -q "10.50.23.1/29"'

run_check \
    "R3 has 10.50.23.2/29 on eth1" \
    docker exec clab-top03asym-r3 \
        sh -c 'ip -4 addr show dev eth1 | grep -q "10.50.23.2/29"'

run_check \
    "R3 has 10.50.3.1/24 on eth2" \
    docker exec clab-top03asym-r3 \
        sh -c 'ip -4 addr show dev eth2 | grep -q "10.50.3.1/24"'

run_check \
    "R3 has 10.50.34.1/29 on eth3" \
    docker exec clab-top03asym-r3 \
        sh -c 'ip -4 addr show dev eth3 | grep -q "10.50.34.1/29"'

run_check \
    "HostB has 10.50.3.10/24 on eth1" \
    docker exec clab-top03asym-hostb \
        sh -c 'ip -4 addr show dev eth1 | grep -q "10.50.3.10/24"'

run_check \
    "R4 has 10.50.34.2/29 on eth1" \
    docker exec clab-top03asym-r4 \
        sh -c 'ip -4 addr show dev eth1 | grep -q "10.50.34.2/29"'

run_check \
    "R4 has 10.50.14.2/29 on eth2" \
    docker exec clab-top03asym-r4 \
        sh -c 'ip -4 addr show dev eth2 | grep -q "10.50.14.2/29"'

run_check \
    "IPv4 forwarding is enabled on R1" \
    docker exec clab-top03asym-r1 \
        sh -c 'test "$(cat /proc/sys/net/ipv4/ip_forward)" = "1"'

run_check \
    "IPv4 forwarding is enabled on R2" \
    docker exec clab-top03asym-r2 \
        sh -c 'test "$(cat /proc/sys/net/ipv4/ip_forward)" = "1"'

run_check \
    "IPv4 forwarding is enabled on R3" \
    docker exec clab-top03asym-r3 \
        sh -c 'test "$(cat /proc/sys/net/ipv4/ip_forward)" = "1"'

run_check \
    "IPv4 forwarding is enabled on R4" \
    docker exec clab-top03asym-r4 \
        sh -c 'test "$(cat /proc/sys/net/ipv4/ip_forward)" = "1"'

run_check \
    "R1 all-interface reverse-path filtering is disabled" \
    docker exec clab-top03asym-r1 \
        sh -c 'test "$(cat /proc/sys/net/ipv4/conf/all/rp_filter)" = "0"'

run_check \
    "R1 eth1 reverse-path filtering is disabled" \
    docker exec clab-top03asym-r1 \
        sh -c 'test "$(cat /proc/sys/net/ipv4/conf/eth1/rp_filter)" = "0"'

run_check \
    "R1 eth2 reverse-path filtering is disabled" \
    docker exec clab-top03asym-r1 \
        sh -c 'test "$(cat /proc/sys/net/ipv4/conf/eth2/rp_filter)" = "0"'

run_check \
    "R1 eth3 reverse-path filtering is disabled" \
    docker exec clab-top03asym-r1 \
        sh -c 'test "$(cat /proc/sys/net/ipv4/conf/eth3/rp_filter)" = "0"'

run_check \
    "R2 all-interface reverse-path filtering is disabled" \
    docker exec clab-top03asym-r2 \
        sh -c 'test "$(cat /proc/sys/net/ipv4/conf/all/rp_filter)" = "0"'

run_check \
    "R2 eth1 reverse-path filtering is disabled" \
    docker exec clab-top03asym-r2 \
        sh -c 'test "$(cat /proc/sys/net/ipv4/conf/eth1/rp_filter)" = "0"'

run_check \
    "R2 eth2 reverse-path filtering is disabled" \
    docker exec clab-top03asym-r2 \
        sh -c 'test "$(cat /proc/sys/net/ipv4/conf/eth2/rp_filter)" = "0"'

run_check \
    "R3 all-interface reverse-path filtering is disabled" \
    docker exec clab-top03asym-r3 \
        sh -c 'test "$(cat /proc/sys/net/ipv4/conf/all/rp_filter)" = "0"'

run_check \
    "R3 eth1 reverse-path filtering is disabled" \
    docker exec clab-top03asym-r3 \
        sh -c 'test "$(cat /proc/sys/net/ipv4/conf/eth1/rp_filter)" = "0"'

run_check \
    "R3 eth2 reverse-path filtering is disabled" \
    docker exec clab-top03asym-r3 \
        sh -c 'test "$(cat /proc/sys/net/ipv4/conf/eth2/rp_filter)" = "0"'

run_check \
    "R3 eth3 reverse-path filtering is disabled" \
    docker exec clab-top03asym-r3 \
        sh -c 'test "$(cat /proc/sys/net/ipv4/conf/eth3/rp_filter)" = "0"'

run_check \
    "R4 all-interface reverse-path filtering is disabled" \
    docker exec clab-top03asym-r4 \
        sh -c 'test "$(cat /proc/sys/net/ipv4/conf/all/rp_filter)" = "0"'

run_check \
    "R4 eth1 reverse-path filtering is disabled" \
    docker exec clab-top03asym-r4 \
        sh -c 'test "$(cat /proc/sys/net/ipv4/conf/eth1/rp_filter)" = "0"'

run_check \
    "R4 eth2 reverse-path filtering is disabled" \
    docker exec clab-top03asym-r4 \
        sh -c 'test "$(cat /proc/sys/net/ipv4/conf/eth2/rp_filter)" = "0"'

run_check \
    "HostA default route uses R1 toward HostB" \
    docker exec clab-top03asym-hosta \
        sh -c 'ip route show default | grep -Eq "^default via 10\.50\.1\.1([[:space:]]|$)"'

run_check \
    "R1 forward route uses R2 toward HostB" \
    docker exec clab-top03asym-r1 \
        sh -c 'ip route show 10.50.3.0/24 | grep -Eq "^10\.50\.3\.0/24 via 10\.50\.12\.2([[:space:]]|$)"'

run_check \
    "R2 observer route uses R3 toward HostB" \
    docker exec clab-top03asym-r2 \
        sh -c 'ip route show 10.50.3.0/24 | grep -Eq "^10\.50\.3\.0/24 via 10\.50\.23\.2([[:space:]]|$)"'

run_check \
    "HostB route uses R3 toward HostA" \
    docker exec clab-top03asym-hostb \
        sh -c 'ip route show 10.50.1.0/24 | grep -Eq "^10\.50\.1\.0/24 via 10\.50\.3\.1([[:space:]]|$)"'

run_check \
    "R3 return route uses R4 toward HostA" \
    docker exec clab-top03asym-r3 \
        sh -c 'ip route show 10.50.1.0/24 | grep -Eq "^10\.50\.1\.0/24 via 10\.50\.34\.2([[:space:]]|$)"'

run_check \
    "R4 return route uses R1 toward HostA" \
    docker exec clab-top03asym-r4 \
        sh -c 'ip route show 10.50.1.0/24 | grep -Eq "^10\.50\.1\.0/24 via 10\.50\.14\.1([[:space:]]|$)"'

run_check \
    "R2 support route uses R1 toward HostA" \
    docker exec clab-top03asym-r2 \
        sh -c 'ip route show 10.50.1.0/24 | grep -Eq "^10\.50\.1\.0/24 via 10\.50\.12\.1([[:space:]]|$)"'

run_check \
    "R4 support route uses R3 toward HostB" \
    docker exec clab-top03asym-r4 \
        sh -c 'ip route show 10.50.3.0/24 | grep -Eq "^10\.50\.3\.0/24 via 10\.50\.34\.1([[:space:]]|$)"'

run_check \
    "R3 return lookup excludes forward-only R2" \
    docker exec clab-top03asym-r3 \
        sh -c '! ip route get 10.50.1.10 | grep -q "via 10.50.23.1"'

run_check \
    "R1 forward lookup resolves HostB through R2" \
    docker exec clab-top03asym-r1 \
        sh -c 'ip route get 10.50.3.10 | grep -Eq "via 10\.50\.12\.2([[:space:]]|$)"'

run_check \
    "R2 forward lookup resolves HostB through R3" \
    docker exec clab-top03asym-r2 \
        sh -c 'ip route get 10.50.3.10 | grep -Eq "via 10\.50\.23\.2([[:space:]]|$)"'

run_check \
    "HostA reaches local gateway R1" \
    docker exec clab-top03asym-hosta \
        ping -c 2 -W 1 10.50.1.1

run_check \
    "R1 reaches forward-only observer R2" \
    docker exec clab-top03asym-r1 \
        ping -c 2 -W 1 10.50.12.2

run_check \
    "Observer R2 reaches selected transit R3" \
    docker exec clab-top03asym-r2 \
        ping -c 2 -W 1 10.50.23.2

run_check \
    "Transit R3 reaches destination HostB" \
    docker exec clab-top03asym-r3 \
        ping -c 2 -W 1 10.50.3.10

run_check \
    "R3 reaches return-only router R4" \
    docker exec clab-top03asym-r3 \
        ping -c 2 -W 1 10.50.34.2

run_check \
    "R4 reaches final return router R1" \
    docker exec clab-top03asym-r4 \
        ping -c 2 -W 1 10.50.14.1

run_check \
    "HostA reaches HostB over the selected forward path" \
    docker exec clab-top03asym-hosta \
        ping -c 2 -W 1 10.50.3.10

run_check \
    "HostB reaches HostA over the distinct return path" \
    docker exec clab-top03asym-hostb \
        ping -c 2 -W 1 10.50.1.10

run_check \
    "Wrong next-hop 10.50.23.6 is not locally assigned on R2" \
    docker exec clab-top03asym-r2 \
        sh -c '! ip -4 addr show | grep -q "10.50.23.6/"'

run_check \
    "Wrong next-hop 10.50.23.6 is unreachable from R2" \
    docker exec clab-top03asym-r2 \
        sh -c '! ping -c 2 -W 1 10.50.23.6'

run_check \
    "R2 baseline HostB route excludes wrong next-hop 10.50.23.6" \
    docker exec clab-top03asym-r2 \
        sh -c '! ip route show 10.50.3.0/24 | grep -q "via 10.50.23.6"'

run_check \
    "HostA has no selected-flow specific route" \
    docker exec clab-top03asym-hosta \
        sh -c '! ip route show exact 10.50.3.0/24 | grep -q .'

run_check \
    "Controlled wrong source gateway is unreachable" \
    docker exec clab-top03asym-hosta \
        sh -c '! ping -c 2 -W 1 10.50.1.254'

run_check \
    "R2 has iptables and no IND-P6 tagged rule" \
    docker exec clab-top03asym-r2 \
        sh -c 'command -v iptables >/dev/null && ! iptables -w 2 -t filter -S FORWARD | grep -F -- "--comment IND-P6"'

echo
echo "Passed: $PASS_COUNT"
echo "Failed: $FAIL_COUNT"

if [ "$FAIL_COUNT" -ne 0 ]; then
    echo "Baseline status: INVALID"
    exit 1
fi

echo "Baseline status: VALID"
