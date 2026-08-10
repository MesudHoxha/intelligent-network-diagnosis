#!/usr/bin/env bash

set -euo pipefail

SOURCE_CONTAINER="clab-top01-hosta"
OBSERVER_CONTAINER="clab-top01-r1"
EXPECTED_GATEWAY="10.10.1.1"
WRONG_GATEWAY="10.10.1.254"
SOURCE_INTERFACE="eth1"
DESTINATION_ADDRESS="10.10.2.10"
DESTINATION_PREFIX="10.10.2.0/24"
ALTERNATE_PREFIX="10.10.22.0/24"

docker inspect "$SOURCE_CONTAINER" >/dev/null
docker inspect "$OBSERVER_CONTAINER" >/dev/null

docker exec "$SOURCE_CONTAINER" \
    ip route replace default \
    via "$EXPECTED_GATEWAY" \
    dev "$SOURCE_INTERFACE"

docker exec "$SOURCE_CONTAINER" \
    ip route del "$DESTINATION_PREFIX" \
    via "$EXPECTED_GATEWAY"

if docker exec "$SOURCE_CONTAINER" \
    ip route show exact "$DESTINATION_PREFIX" | grep -q .
then
    printf '[STOP] The selected source-specific route still exists.\n'
    exit 1
fi

if ! docker exec "$SOURCE_CONTAINER" \
    ip route show exact "$ALTERNATE_PREFIX" | grep -q .
then
    printf '[STOP] The unrelated alternate route was not preserved.\n'
    exit 1
fi

DEFAULT_ROUTE_JSON="$(
    docker exec "$SOURCE_CONTAINER" \
        ip -j route show default
)"
FLOW_ROUTE_JSON="$(
    docker exec "$SOURCE_CONTAINER" \
        ip -j route get "$DESTINATION_ADDRESS"
)"

python3 - "$DEFAULT_ROUTE_JSON" "$FLOW_ROUTE_JSON" <<'PY'
import json
import sys

default_routes = json.loads(sys.argv[1])
flow_routes = json.loads(sys.argv[2])

for name, routes in (
    ("default", default_routes),
    ("selected flow", flow_routes),
):
    if not isinstance(routes, list) or len(routes) != 1:
        raise SystemExit(
            f"[STOP] HostA must have one {name} route result."
        )
    route = routes[0]
    if route.get("gateway") != "10.10.1.1":
        raise SystemExit(
            f"[STOP] HostA {name} route does not use 10.10.1.1."
        )
    if route.get("dev") != "eth1":
        raise SystemExit(
            f"[STOP] HostA {name} route does not use eth1."
        )

print("phase6_selected_flow_uses_default=PASS")
PY

if docker exec "$SOURCE_CONTAINER" \
    ping -c 2 -W 1 "$WRONG_GATEWAY" >/dev/null 2>&1
then
    printf '[STOP] Controlled wrong gateway unexpectedly responds.\n'
    exit 1
fi

if docker exec "$OBSERVER_CONTAINER" \
    iptables -w 2 -t filter -S FORWARD | \
    grep -F -- '--comment IND-P6' >/dev/null
then
    printf '[STOP] A conflicting IND-P6 policy rule already exists.\n'
    exit 1
fi

printf 'phase6_wrong_gateway_unreachable=PASS\n'
printf 'phase6_policy_prefix_clean=PASS\n'
printf 'p6_r4_profile_preparation=PASS\n'
