#!/usr/bin/env bash

set -euo pipefail

SOURCE_CONTAINER="clab-top01-hosta"
EXPECTED_GATEWAY="10.10.1.1"
SOURCE_INTERFACE="eth1"

docker inspect "$SOURCE_CONTAINER" >/dev/null
docker exec "$SOURCE_CONTAINER" \
    ip route replace default \
    via "$EXPECTED_GATEWAY" \
    dev "$SOURCE_INTERFACE"

DEFAULT_ROUTE_JSON="$(
    docker exec "$SOURCE_CONTAINER" \
        ip -j route show default
)"

python3 - "$DEFAULT_ROUTE_JSON" <<'PY'
import json
import sys

routes = json.loads(sys.argv[1])
expected = [{
    "dst": "default",
    "gateway": "10.10.1.1",
    "dev": "eth1",
}]

if not isinstance(routes, list) or len(routes) != 1:
    raise SystemExit(
        "[STOP] HostA must contain exactly one default route."
    )

route = routes[0]
for name, value in expected[0].items():
    if route.get(name) != value:
        raise SystemExit(
            f"[STOP] HostA default route has unexpected {name}."
        )

print("phase6_source_default_route=PASS")
PY
