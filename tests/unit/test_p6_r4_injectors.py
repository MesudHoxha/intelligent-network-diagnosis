import json
from pathlib import Path
from typing import Sequence

import pytest

from src.fault_injection.acl_block import (
    inject_acl_block,
    restore_acl_block,
)
from src.fault_injection.interface_down import (
    inject_interface_down,
    restore_interface_down,
)
from src.fault_injection.phase6_common import (
    Phase6FaultInjectionError,
)
from src.fault_injection.registry import (
    FAULT_INJECTORS,
    FAULT_RESTORERS,
)
from src.fault_injection.wrong_default_gateway import (
    inject_wrong_default_gateway,
    restore_wrong_default_gateway,
)


TIMESTAMP = "2026-08-10T08:00:00+00:00"
SCENARIOS = {
    "wrong_default_gateway": Path(
        "scenarios/routing/C3_WRONG_DEFAULT_GATEWAY_P6_TOP01.yml"
    ),
    "interface_down": Path(
        "scenarios/routing/C4_INTERFACE_DOWN_P6_TOP01.yml"
    ),
    "acl_block": Path(
        "scenarios/routing/C5_ACL_BLOCK_P6_TOP01.yml"
    ),
}


class FakePhase6Lab:
    def __init__(self) -> None:
        self.default_gateway = "10.10.1.1"
        self.interface_up = True
        self.routes = {
            "10.10.2.0/24": ("10.10.12.2", "eth2"),
            "10.10.22.0/24": ("10.10.12.2", "eth2"),
        }
        self.rule_tag: str | None = None
        self.force_route_get_gateway: str | None = None
        self.preserve_routes_on_link_down = False
        self.mutations: list[list[str]] = []

    def _destination_reachable(self) -> bool:
        return (
            self.default_gateway == "10.10.1.1"
            and self.interface_up
            and "10.10.2.0/24" in self.routes
            and self.rule_tag is None
        )

    def __call__(
        self,
        container: str,
        command: Sequence[str],
    ) -> dict[str, object]:
        arguments = list(command)
        return_code = 0
        stdout = ""
        stderr = ""
        if arguments == ["ip", "-j", "route", "show", "default"]:
            stdout = json.dumps([{
                "dst": "default",
                "gateway": self.default_gateway,
                "dev": "eth1",
            }])
        elif arguments[:4] == ["ip", "-j", "route", "get"]:
            stdout = json.dumps([{
                "dst": arguments[4],
                "gateway": (
                    self.force_route_get_gateway
                    or self.default_gateway
                ),
                "dev": "eth1",
            }])
        elif arguments[:5] == [
            "ip", "-j", "route", "show", "exact"
        ]:
            prefix = arguments[5]
            route = self.routes.get(prefix)
            stdout = json.dumps(
                []
                if route is None
                else [{
                    "dst": prefix,
                    "gateway": route[0],
                    "dev": route[1],
                }]
            )
        elif arguments[:4] == ["ip", "-j", "link", "show"]:
            stdout = json.dumps([{
                "ifname": "eth2",
                "operstate": "UP" if self.interface_up else "DOWN",
            }])
        elif arguments[0] == "ping":
            destination = arguments[-1]
            if container == "clab-top01-hosta":
                if destination == "10.10.1.1":
                    reachable = True
                elif destination == "10.10.1.254":
                    reachable = False
                else:
                    reachable = self._destination_reachable()
            elif container == "clab-top01-r1":
                reachable = self.interface_up
            else:
                reachable = True
            return_code = 0 if reachable else 1
            stdout = "reachable" if reachable else ""
        elif arguments[:4] == ["ip", "route", "replace", "default"]:
            self.default_gateway = arguments[5]
            self.mutations.append(arguments)
        elif arguments[:5] == ["ip", "link", "set", "dev", "eth2"]:
            self.interface_up = arguments[5] == "up"
            if (
                not self.interface_up
                and not self.preserve_routes_on_link_down
            ):
                self.routes.clear()
            self.mutations.append(arguments)
        elif arguments[:3] == ["ip", "route", "replace"]:
            prefix = arguments[3]
            gateway = arguments[5]
            interface = arguments[7]
            if not self.interface_up:
                return_code = 2
                stderr = "Error: Nexthop device is not up."
            else:
                self.routes[prefix] = (gateway, interface)
            self.mutations.append(arguments)
        elif arguments[0] == "iptables" and "-S" in arguments:
            stdout = "-P FORWARD ACCEPT\n"
            if self.rule_tag is not None:
                stdout += (
                    "-A FORWARD -s 10.10.1.10/32 "
                    "-d 10.10.2.10/32 -p icmp -m comment "
                    f"--comment {self.rule_tag} -j DROP\n"
                )
        elif arguments[0] == "iptables" and "-I" in arguments:
            tag_index = arguments.index("--comment") + 1
            self.rule_tag = arguments[tag_index]
            self.mutations.append(arguments)
        elif arguments[0] == "iptables" and "-D" in arguments:
            tag_index = arguments.index("--comment") + 1
            if self.rule_tag != arguments[tag_index]:
                return_code = 1
            else:
                self.rule_tag = None
            self.mutations.append(arguments)
        else:
            raise AssertionError(f"Unexpected command: {arguments}")
        return {
            "command": ["docker", "exec", container, *arguments],
            "return_code": return_code,
            "stdout": stdout,
            "stderr": stderr,
            "timestamp_utc": TIMESTAMP,
        }


@pytest.mark.parametrize(
    ("fault_type", "injector", "restorer"),
    [
        (
            "wrong_default_gateway",
            inject_wrong_default_gateway,
            restore_wrong_default_gateway,
        ),
        (
            "interface_down",
            inject_interface_down,
            restore_interface_down,
        ),
        ("acl_block", inject_acl_block, restore_acl_block),
    ],
)
def test_new_injector_and_exact_restoration(
    tmp_path: Path,
    fault_type: str,
    injector,
    restorer,
) -> None:
    lab = FakePhase6Lab()
    output = tmp_path / fault_type
    injection = injector(
        SCENARIOS[fault_type],
        output,
        executor=lab,
    )

    assert injection["status"] == "FAULT_CONFIRMED"
    assert injection["preconditions_passed"] is True
    assert injection["postconditions_passed"] is True
    assert injection["mutation_applied"] is True

    restoration = restorer(
        SCENARIOS[fault_type],
        output,
        executor=lab,
    )

    assert restoration["status"] == "RESTORATION_CONFIRMED"
    assert lab.default_gateway == "10.10.1.1"
    assert lab.interface_up is True
    assert lab.rule_tag is None
    assert (output / "preconditions.json").is_file()
    assert (output / "injection_record.json").is_file()
    assert (output / "restoration_record.json").is_file()
    assert (output / "ground_truth.json").is_file()


def test_new_fault_registry_bindings_are_exact() -> None:
    assert FAULT_INJECTORS["wrong_default_gateway"] is (
        inject_wrong_default_gateway
    )
    assert FAULT_INJECTORS["interface_down"] is inject_interface_down
    assert FAULT_INJECTORS["acl_block"] is inject_acl_block
    assert FAULT_RESTORERS["wrong_default_gateway"] is (
        restore_wrong_default_gateway
    )
    assert FAULT_RESTORERS["interface_down"] is restore_interface_down
    assert FAULT_RESTORERS["acl_block"] is restore_acl_block


def test_interface_down_models_and_exactly_restores_kernel_routes(
    tmp_path: Path,
) -> None:
    lab = FakePhase6Lab()
    output = tmp_path / "interface_kernel_routes"

    injection = inject_interface_down(
        SCENARIOS["interface_down"],
        output,
        executor=lab,
    )

    assert injection["status"] == "FAULT_CONFIRMED"
    assert lab.interface_up is False
    assert lab.routes == {}
    assert injection["kernel_route_side_effect"] == {
        "expected": "baseline_routes_absent_while_interface_down",
        "baseline_route_count": 2,
    }
    assert "route_preservation_commands" not in injection

    restoration = restore_interface_down(
        SCENARIOS["interface_down"],
        output,
        executor=lab,
    )

    assert restoration["status"] == "RESTORATION_CONFIRMED"
    assert lab.interface_up is True
    assert lab.routes == {
        "10.10.2.0/24": ("10.10.12.2", "eth2"),
        "10.10.22.0/24": ("10.10.12.2", "eth2"),
    }
    assert len(restoration["route_restoration_commands"]) == 2
    assert all(
        command["return_code"] == 0
        for command in restoration["route_restoration_commands"]
    )


def test_interface_down_unexpected_route_state_restores_safe_baseline(
    tmp_path: Path,
) -> None:
    lab = FakePhase6Lab()
    lab.preserve_routes_on_link_down = True
    output = tmp_path / "unexpected_kernel_route_state"

    with pytest.raises(
        Phase6FaultInjectionError,
        match="was restored",
    ):
        inject_interface_down(
            SCENARIOS["interface_down"],
            output,
            executor=lab,
        )

    injection = json.loads(
        (output / "injection_record.json").read_text(
            encoding="utf-8"
        )
    )
    restoration = json.loads(
        (output / "restoration_record.json").read_text(
            encoding="utf-8"
        )
    )
    assert injection["status"] == "FAULT_NOT_CONFIRMED"
    assert restoration["status"] == "RESTORATION_CONFIRMED"
    assert lab.interface_up is True
    assert lab.routes == {
        "10.10.2.0/24": ("10.10.12.2", "eth2"),
        "10.10.22.0/24": ("10.10.12.2", "eth2"),
    }


def test_invalid_baseline_stops_before_mutation(tmp_path: Path) -> None:
    lab = FakePhase6Lab()
    lab.default_gateway = "10.10.1.254"
    output = tmp_path / "invalid"

    with pytest.raises(
        Phase6FaultInjectionError,
        match="preconditions failed",
    ):
        inject_wrong_default_gateway(
            SCENARIOS["wrong_default_gateway"],
            output,
            executor=lab,
        )

    record = json.loads(
        (output / "injection_record.json").read_text(encoding="utf-8")
    )
    assert record["status"] == "INVALID_BASELINE"
    assert record["mutation_applied"] is False
    assert lab.mutations == []


def test_failed_postcondition_triggers_exact_restoration(
    tmp_path: Path,
) -> None:
    lab = FakePhase6Lab()
    lab.force_route_get_gateway = "10.10.1.1"
    output = tmp_path / "emergency_restore"

    with pytest.raises(
        Phase6FaultInjectionError,
        match="was restored",
    ):
        inject_wrong_default_gateway(
            SCENARIOS["wrong_default_gateway"],
            output,
            executor=lab,
        )

    restoration = json.loads(
        (output / "restoration_record.json").read_text(
            encoding="utf-8"
        )
    )
    assert restoration["status"] == "RESTORATION_CONFIRMED"
    assert lab.default_gateway == "10.10.1.1"


def test_restoration_refuses_scenario_hash_drift(tmp_path: Path) -> None:
    lab = FakePhase6Lab()
    output = tmp_path / "drift"
    scenario_copy = tmp_path / "scenario.yml"
    scenario_copy.write_bytes(
        SCENARIOS["interface_down"].read_bytes()
    )
    inject_interface_down(scenario_copy, output, executor=lab)
    scenario_copy.write_text(
        scenario_copy.read_text(encoding="utf-8") + "\n",
        encoding="utf-8",
    )

    with pytest.raises(
        Phase6FaultInjectionError,
        match="does not match",
    ):
        restore_interface_down(scenario_copy, output, executor=lab)
