"""Build the X6-R1 context by overlaying only published X6-R0.5 topology data."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from src.expansion.x6_r0_4_runtime_parameter_freeze import (
    validate_x6_r0_4_runtime_context,
)


ROOT = Path(__file__).resolve().parents[2]
BOOTSTRAP = Path("labs/topologies/x6_r1_packet_loss_r0_5/bootstrap_context_v1.json")


class X6R1RuntimeContextError(ValueError):
    pass


def _require(value: bool, message: str) -> None:
    if not value:
        raise X6R1RuntimeContextError(message)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_x6_r1_runtime_context(repository_root: Path = ROOT) -> dict[str, Any]:
    """Return frozen R0.4 values with only the R0.5 route-bootstrap overlay."""

    root = Path(repository_root)
    base = validate_x6_r0_4_runtime_context(root)
    bootstrap_path = root / BOOTSTRAP
    bootstrap = json.loads(bootstrap_path.read_text(encoding="utf-8"))
    historical = bootstrap["historical_topology"]
    corrected = bootstrap["topology"]
    _require(
        historical == {
            "path": base["topology"]["file"],
            "sha256": base["topology"]["sha256"],
        },
        "X6-R0.5 historical topology binding drifted",
    )
    topology_path = root / corrected["path"]
    _require(topology_path.is_file() and _sha256(topology_path) == corrected["sha256"], "X6-R0.5 corrected topology hash drifted")
    routes = bootstrap["endpoint_routes"]
    _require(
        routes == {
            "hosta": {"destination": "10.61.3.2/32", "via": "10.61.1.1", "dev": "eth1", "src": "10.61.1.2"},
            "hostb": {"destination": "10.61.1.2/32", "via": "10.61.3.1", "dev": "eth1", "src": "10.61.3.2"},
        },
        "X6-R0.5 endpoint route contract drifted",
    )
    _require(
        bootstrap["management_defaults"] == {"preserved": True, "interface": "eth0", "forbidden_for_experiment_traffic": True},
        "X6-R0.5 management-default contract drifted",
    )
    context = copy.deepcopy(base)
    context["topology"]["file"] = corrected["path"]
    context["topology"]["sha256"] = corrected["sha256"]
    context["topology"]["routes"] = [
        row
        for row in base["topology"]["routes"]
        if row["node"] not in {"hosta", "hostb"}
    ] + [
        {"node": node, **route}
        for node, route in routes.items()
    ]
    return context


def x6_r1_context_identity(repository_root: Path = ROOT) -> dict[str, str]:
    root = Path(repository_root)
    base_path = root / "labs/topologies/x6_r1_packet_loss/runtime_context_v1.json"
    bootstrap_path = root / BOOTSTRAP
    context = load_x6_r1_runtime_context(root)
    return {
        "historical_r0_4_runtime_context_sha256": _sha256(base_path),
        "x6_r0_5_bootstrap_context_sha256": _sha256(bootstrap_path),
        "authoritative_topology_sha256": context["topology"]["sha256"],
    }
