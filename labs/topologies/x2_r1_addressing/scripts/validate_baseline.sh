#!/usr/bin/env bash

set -u

PASS_COUNT=0
FAIL_COUNT=0

run_check() {
    local description="$1"
    shift
    printf '%-58s' "$description"
    if "$@" >/dev/null 2>&1; then
        echo "[PASS]"
        PASS_COUNT=$((PASS_COUNT + 1))
    else
        echo "[FAIL]"
        FAIL_COUNT=$((FAIL_COUNT + 1))
    fi
}

echo "X2-R1 Addressing Baseline Validation"
echo "===================================="

run_check "HostA has the exact expected address" \
    docker exec clab-x2r1-hosta sh -c \
    'ip -o -4 addr show dev eth1 | grep -Eq "[[:space:]]10\.20\.1\.10/24([[:space:]]|$)"'

run_check "HostA does not retain the controlled wrong address" \
    docker exec clab-x2r1-hosta sh -c \
    '! ip -o -4 addr show dev eth1 | grep -Eq "[[:space:]]10\.20\.1\.11/24([[:space:]]|$)"'

run_check "HostA default route uses the expected gateway" \
    docker exec clab-x2r1-hosta sh -c \
    'ip route show default | grep -Eq "^default via 10\.20\.1\.1 dev eth1([[:space:]]|$)"'

run_check "HostA reaches its expected gateway" \
    docker exec clab-x2r1-hosta ping -c 2 -W 1 10.20.1.1

run_check "HostA reaches HostB" \
    docker exec clab-x2r1-hosta ping -c 2 -W 1 10.20.2.10

run_check "HostB reaches HostA's expected address" \
    docker exec clab-x2r1-hostb ping -c 2 -W 1 10.20.1.10

run_check "Controlled wrong address is unused in baseline" \
    docker exec clab-x2r1-r1 sh -c '! ping -c 2 -W 1 10.20.1.11'

echo
echo "Passed: $PASS_COUNT"
echo "Failed: $FAIL_COUNT"

if [ "$FAIL_COUNT" -ne 0 ]; then
    echo "Baseline status: INVALID"
    exit 1
fi

echo "Baseline status: VALID"
