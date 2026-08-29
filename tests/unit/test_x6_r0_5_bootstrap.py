import json
from pathlib import Path

import pytest

from src.collection.x6_r0_5_route_bootstrap import (
    X6R05RouteError,
    validate_management_default,
    validate_route_get,
)
from src.expansion.x6_r0_5_gate import verify_x6_r0_5
from src.orchestration.x6_r0_5_bootstrap_smoke import run_bootstrap_smoke

ROOT = Path(__file__).resolve().parents[2]


def test_x6_r0_5_gate_preserves_r0_4_except_bootstrap():
    plan = verify_x6_r0_5(ROOT)
    assert plan["release_id"] == "X6_R0_5_TOPOLOGY_BOOTSTRAP_CORRECTION"
    assert len(plan["source_bindings"]) == 6


def test_structured_route_rejects_management_ambiguous_and_wrong_source():
    record = {
        "return_code": 0,
        "stderr": "",
        "stdout": json.dumps(
            [{"dst": "10.61.3.2", "gateway": "10.61.1.1", "dev": "eth1", "prefsrc": "10.61.1.2"}]
        ),
    }
    assert validate_route_get(record, destination="10.61.3.2", via="10.61.1.1", dev="eth1", src="10.61.1.2")["dev"] == "eth1"
    for row in (
        [{"dst": "10.61.3.2", "gateway": "172.20.20.1", "dev": "eth0", "prefsrc": "172.20.20.5"}],
        [],
        [{"dst": "10.61.3.2", "gateway": "10.61.1.1", "dev": "eth1", "prefsrc": "wrong"}],
    ):
        with pytest.raises(X6R05RouteError):
            validate_route_get({**record, "stdout": json.dumps(row)}, destination="10.61.3.2", via="10.61.1.1", dev="eth1", src="10.61.1.2")


def test_management_default_must_remain_on_docker_eth0():
    record = {"return_code": 0, "stderr": "", "stdout": json.dumps([{"dst": "default", "gateway": "172.20.20.1", "dev": "eth0"}])}
    assert validate_management_default(record)["dev"] == "eth0"
    for row in (
        [{"dst": "default", "gateway": "10.61.1.1", "dev": "eth1"}],
        [],
        [{"dst": "default", "gateway": "172.20.20.1", "dev": "eth0"}, {"dst": "default", "gateway": "172.20.20.2", "dev": "eth0"}],
    ):
        with pytest.raises(X6R05RouteError):
            validate_management_default({**record, "stdout": json.dumps(row)})


def test_smoke_creates_non_scientific_provenance_with_complete_route_chain(tmp_path):
    routes = {
        "10.61.3.2": {
            "hosta": ("10.61.1.1", "eth1", "10.61.1.2"),
            "r1": ("10.61.12.2", "eth2", "10.61.12.1"),
            "r2": ("10.61.23.2", "eth2", "10.61.23.1"),
        },
        "10.61.1.2": {
            "hostb": ("10.61.3.1", "eth1", "10.61.3.2"),
            "r2": ("10.61.12.1", "eth1", "10.61.12.2"),
            "r3": ("10.61.23.1", "eth1", "10.61.23.2"),
        },
    }

    def executor(command):
        if command[-3:] == ["route", "show", "default"]:
            return {"command": command, "return_code": 0, "stdout": json.dumps([{"dst": "default", "gateway": "172.20.20.1", "dev": "eth0"}]), "stderr": ""}
        if command[-3:] in (["route", "get", "10.61.3.2"], ["route", "get", "10.61.1.2"]):
            node = command[2].removeprefix("clab-x6r1-")
            destination = command[-1]
            via, dev, src = routes[destination][node]
            return {"command": command, "return_code": 0, "stdout": json.dumps([{"dst": destination, "gateway": via, "dev": dev, "prefsrc": src}]), "stderr": ""}
        if "sysctl" in command:
            return {"command": command, "return_code": 0, "stdout": "1\n", "stderr": ""}
        if "ping" in command:
            return {"command": command, "return_code": 0, "stdout": "", "stderr": ""}
        if "qdisc" in command:
            return {"command": command, "return_code": 0, "stdout": json.dumps([{"kind": "noqueue", "handle": "0:"}]), "stderr": ""}
        if "filter" in command:
            return {"command": command, "return_code": 0, "stdout": "[]", "stderr": ""}
        return {"command": command, "return_code": 0, "stdout": "[]", "stderr": ""}

    result = run_bootstrap_smoke(tmp_path, executor=executor)
    assert result["status"] == "TOPOLOGY_BOOTSTRAP_VALIDATED_NON_SCIENTIFIC"
    provenance = json.loads((Path(result["directory"]) / "bootstrap_provenance.json").read_text())
    assert set(provenance["records"]["management_defaults"]) == {"hosta", "hostb"}
    assert set(provenance["records"]).issuperset({"hosta_forward", "hostb_reverse", "r1_forward", "r2_forward", "r2_reverse", "r3_reverse", "qdisc"})
