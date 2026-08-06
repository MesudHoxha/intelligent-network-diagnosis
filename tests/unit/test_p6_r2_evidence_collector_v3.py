import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest

from src.collection.evidence_collector_v3 import (
    EvidenceCollectorV3Error,
    collect_evidence_v3,
    parse_interface_oper_state,
    parse_matching_block_rule,
    parse_observer_route,
    parse_source_default_gateway,
)
from src.contracts.evidence_v3 import (
    EVIDENCE_V3_FEATURE_NAMES,
    validate_evidence_v3,
)
from src.contracts.observation_profile_v2 import ObservationProfileV2


TIMESTAMP = "2026-08-06T10:00:00+00:00"


def profile() -> ObservationProfileV2:
    return ObservationProfileV2(
        schema_version=2,
        topology_id="TOP_01",
        direction="hosta_to_hostb",
        source_node="hosta",
        source_container="clab-top01-hosta",
        source_address="10.10.1.10",
        source_prefix="10.10.1.0/24",
        source_gateway_address="10.10.1.1",
        destination_address="10.10.2.10",
        destination_prefix="10.10.2.0/24",
        route_observer_node="r1",
        route_observer_container="clab-top01-r1",
        expected_next_hop="10.10.12.2",
        observer_egress_interface="eth2",
        transit_node="r2",
        transit_container="clab-top01-r2",
        flow_protocol="icmp",
        flow_source_port=None,
        flow_destination_port=None,
        policy_backend="iptables",
        policy_table="filter",
        policy_chain="FORWARD",
        policy_rule_tag_prefix="IND-P6",
    )


def command_result(
    container: str,
    command: tuple[str, ...] | list[str],
    *,
    return_code: int = 0,
    stdout: str = "",
    stderr: str = "",
) -> dict[str, object]:
    return {
        "command": ["docker", "exec", container, *command],
        "return_code": return_code,
        "stdout": stdout,
        "stderr": stderr,
        "timestamp_utc": TIMESTAMP,
    }


class FakeExecutor:
    def __init__(
        self,
        responses: dict[
            tuple[str, ...],
            tuple[int, str, str],
        ],
    ) -> None:
        self.responses = responses
        self.calls: list[tuple[str, ...]] = []

    def __call__(
        self,
        container: str,
        command: tuple[str, ...] | list[str],
    ) -> dict[str, object]:
        key = (container, *command)
        self.calls.append(key)
        return_code, stdout, stderr = self.responses[key]
        return command_result(
            container,
            command,
            return_code=return_code,
            stdout=stdout,
            stderr=stderr,
        )


def healthy_responses(
    observation: ObservationProfileV2,
) -> dict[tuple[str, ...], tuple[int, str, str]]:
    source = observation.source_container
    observer = observation.route_observer_container
    transit = observation.transit_container
    return {
        (
            source,
            "ping",
            "-c",
            "2",
            "-W",
            "1",
            observation.source_gateway_address,
        ): (0, "gateway reachable", ""),
        (
            source,
            "ip",
            "-j",
            "route",
            "show",
            "default",
        ): (
            0,
            json.dumps(
                [
                    {
                        "dst": "default",
                        "gateway": observation.source_gateway_address,
                        "dev": "eth0",
                    }
                ]
            ),
            "",
        ),
        (
            source,
            "ping",
            "-c",
            "2",
            "-W",
            "1",
            observation.destination_address,
        ): (0, "destination reachable", ""),
        (
            observer,
            "ip",
            "-j",
            "route",
            "show",
            "exact",
            observation.destination_prefix,
        ): (
            0,
            json.dumps(
                [
                    {
                        "dst": observation.destination_prefix,
                        "gateway": observation.expected_next_hop,
                        "dev": observation.observer_egress_interface,
                    }
                ]
            ),
            "",
        ),
        (
            observer,
            "ping",
            "-c",
            "2",
            "-W",
            "1",
            observation.expected_next_hop,
        ): (0, "next hop reachable", ""),
        (
            observer,
            "ip",
            "-j",
            "link",
            "show",
            "dev",
            observation.observer_egress_interface,
        ): (
            0,
            json.dumps(
                [
                    {
                        "ifname": observation.observer_egress_interface,
                        "operstate": "UP",
                    }
                ]
            ),
            "",
        ),
        (
            transit,
            "ping",
            "-c",
            "2",
            "-W",
            "1",
            observation.destination_address,
        ): (0, "destination reachable", ""),
        (
            observer,
            "iptables",
            "-w",
            "2",
            "-t",
            observation.policy_table,
            "-S",
            observation.policy_chain,
        ): (0, "-P FORWARD ACCEPT\n", ""),
    }


def set_response(
    responses: dict[tuple[str, ...], tuple[int, str, str]],
    *,
    contains: tuple[str, ...],
    value: tuple[int, str, str],
) -> None:
    keys = [
        key
        for key in responses
        if all(part in key for part in contains)
    ]
    assert len(keys) == 1
    responses[keys[0]] = value


def assert_raw_hashes(
    output_directory: Path,
    evidence: dict[str, object],
) -> None:
    probes = evidence["probes"]
    assert isinstance(probes, dict)
    for probe in probes.values():
        assert isinstance(probe, dict)
        relative_path = probe["raw_artifact"]
        digest = probe["raw_artifact_sha256"]
        if relative_path is None:
            assert digest is None
            continue
        artifact_path = output_directory / str(relative_path)
        assert artifact_path.is_file()
        assert hashlib.sha256(artifact_path.read_bytes()).hexdigest() == digest


def test_healthy_collection_produces_complete_evidence_v3(
    tmp_path: Path,
) -> None:
    observation = profile()
    executor = FakeExecutor(healthy_responses(observation))

    evidence = collect_evidence_v3(
        tmp_path,
        observation,
        executor=executor,
    )

    validate_evidence_v3(evidence)
    assert tuple(evidence["features"]) == EVIDENCE_V3_FEATURE_NAMES
    assert evidence["features"] == {
        "source_expected_gateway_reachable": True,
        "source_default_gateway_matches_expected": True,
        "destination_reachable": True,
        "route_to_destination_exists_on_observer": True,
        "route_next_hop_matches_expected": True,
        "route_next_hop_reachable_from_observer": True,
        "expected_next_hop_reachable_from_observer": True,
        "observer_egress_interface_oper_up": True,
        "destination_reachable_from_transit": True,
        "flow_blocked_by_policy": False,
    }
    assert set(evidence["availability"].values()) == {"observed"}
    assert len(executor.calls) == 9
    assert evidence["source_default_gateway_on_source"] == "10.10.1.1"
    assert evidence["route_next_hop_on_observer"] == "10.10.12.2"
    assert evidence["observer_egress_oper_state"] == "up"
    assert "fault_type" not in evidence
    assert "scenario_id" not in evidence
    assert_raw_hashes(tmp_path, evidence)

    assert json.loads(
        (tmp_path / "parsed/evidence.json").read_text(encoding="utf-8")
    ) == evidence
    status = json.loads(
        (tmp_path / "collector_status.json").read_text(encoding="utf-8")
    )
    assert status["collector"] == "RoleNeutralEvidenceCollectorV3"
    assert status["status"] == "COLLECTION_COMPLETED"
    assert status["probe_artifact_count"] == 9
    assert status["observed_feature_count"] == 10


def test_missing_route_uses_structural_unavailability(
    tmp_path: Path,
) -> None:
    observation = profile()
    responses = healthy_responses(observation)
    set_response(
        responses,
        contains=("route", "exact"),
        value=(0, "[]", ""),
    )
    set_response(
        responses,
        contains=(observation.destination_address, observation.source_container),
        value=(1, "", "unreachable"),
    )
    executor = FakeExecutor(responses)

    evidence = collect_evidence_v3(
        tmp_path,
        observation,
        executor=executor,
    )

    assert evidence["features"][
        "route_to_destination_exists_on_observer"
    ] is False
    for feature_name in (
        "route_next_hop_matches_expected",
        "route_next_hop_reachable_from_observer",
    ):
        assert evidence["features"][feature_name] is None
        assert evidence["availability"][feature_name] == (
            "structurally_unavailable"
        )
        assert evidence["probes"][feature_name]["raw_artifact"] is None
    assert evidence["route_next_hop_on_observer"] is None
    assert len(executor.calls) == 8
    validate_evidence_v3(evidence)


def test_wrong_next_hop_signature_is_observation_derived(
    tmp_path: Path,
) -> None:
    observation = profile()
    responses = healthy_responses(observation)
    wrong_next_hop = "10.10.12.254"
    set_response(
        responses,
        contains=("route", "exact"),
        value=(
            0,
            json.dumps(
                [
                    {
                        "dst": observation.destination_prefix,
                        "gateway": wrong_next_hop,
                        "dev": observation.observer_egress_interface,
                    }
                ]
            ),
            "",
        ),
    )
    responses[
        (
            observation.route_observer_container,
            "ping",
            "-c",
            "2",
            "-W",
            "1",
            wrong_next_hop,
        )
    ] = (1, "", "unreachable")
    set_response(
        responses,
        contains=(observation.destination_address, observation.source_container),
        value=(1, "", "unreachable"),
    )

    evidence = collect_evidence_v3(
        tmp_path,
        observation,
        executor=FakeExecutor(responses),
    )

    assert evidence["route_next_hop_on_observer"] == wrong_next_hop
    assert evidence["features"]["route_next_hop_matches_expected"] is False
    assert evidence["features"][
        "route_next_hop_reachable_from_observer"
    ] is False
    assert evidence["features"][
        "expected_next_hop_reachable_from_observer"
    ] is True
    validate_evidence_v3(evidence)


def test_wrong_default_gateway_signature_keeps_gateway_probe_separate(
    tmp_path: Path,
) -> None:
    observation = profile()
    responses = healthy_responses(observation)
    set_response(
        responses,
        contains=("route", "default"),
        value=(
            0,
            json.dumps(
                [
                    {
                        "dst": "default",
                        "gateway": "10.10.1.254",
                        "dev": "eth0",
                    }
                ]
            ),
            "",
        ),
    )
    set_response(
        responses,
        contains=(observation.destination_address, observation.source_container),
        value=(1, "", "unreachable"),
    )

    evidence = collect_evidence_v3(
        tmp_path,
        observation,
        executor=FakeExecutor(responses),
    )

    assert evidence["source_default_gateway_on_source"] == "10.10.1.254"
    assert evidence["features"][
        "source_expected_gateway_reachable"
    ] is True
    assert evidence["features"][
        "source_default_gateway_matches_expected"
    ] is False
    assert evidence["features"]["destination_reachable"] is False
    validate_evidence_v3(evidence)


def test_interface_down_signature_uses_link_and_reachability_probes(
    tmp_path: Path,
) -> None:
    observation = profile()
    responses = healthy_responses(observation)
    set_response(
        responses,
        contains=("link", observation.observer_egress_interface),
        value=(
            0,
            json.dumps(
                [
                    {
                        "ifname": observation.observer_egress_interface,
                        "operstate": "DOWN",
                    }
                ]
            ),
            "",
        ),
    )
    set_response(
        responses,
        contains=(observation.destination_address, observation.source_container),
        value=(1, "", "unreachable"),
    )
    set_response(
        responses,
        contains=(observation.expected_next_hop, observation.route_observer_container),
        value=(1, "", "unreachable"),
    )

    evidence = collect_evidence_v3(
        tmp_path,
        observation,
        executor=FakeExecutor(responses),
    )

    assert evidence["observer_egress_oper_state"] == "down"
    assert evidence["features"][
        "observer_egress_interface_oper_up"
    ] is False
    assert evidence["features"][
        "route_next_hop_reachable_from_observer"
    ] is False
    assert evidence["features"][
        "expected_next_hop_reachable_from_observer"
    ] is False
    validate_evidence_v3(evidence)


def test_acl_block_signature_requires_exact_tagged_drop_rule(
    tmp_path: Path,
) -> None:
    observation = profile()
    responses = healthy_responses(observation)
    rule = (
        "-A FORWARD -s 10.10.1.10/32 -d 10.10.2.10/32 "
        "-p icmp -m comment --comment IND-P6-ACL-001 -j DROP"
    )
    set_response(
        responses,
        contains=("iptables",),
        value=(0, rule, ""),
    )
    set_response(
        responses,
        contains=(observation.destination_address, observation.source_container),
        value=(1, "", "unreachable"),
    )

    evidence = collect_evidence_v3(
        tmp_path,
        observation,
        executor=FakeExecutor(responses),
    )

    assert evidence["features"]["flow_blocked_by_policy"] is True
    assert evidence["matching_block_rule_id"] == "IND-P6-ACL-001"
    assert evidence["features"]["destination_reachable"] is False
    validate_evidence_v3(evidence)


def test_failed_policy_command_is_collection_unavailable_with_raw_hash(
    tmp_path: Path,
) -> None:
    observation = profile()
    responses = healthy_responses(observation)
    set_response(
        responses,
        contains=("iptables",),
        value=(127, "", "iptables: not found"),
    )

    evidence = collect_evidence_v3(
        tmp_path,
        observation,
        executor=FakeExecutor(responses),
    )

    feature_name = "flow_blocked_by_policy"
    assert evidence["features"][feature_name] is None
    assert evidence["availability"][feature_name] == (
        "collection_unavailable"
    )
    assert evidence["matching_block_rule_id"] is None
    assert_raw_hashes(tmp_path, evidence)
    validate_evidence_v3(evidence)


def test_malformed_route_output_does_not_become_missing_route(
    tmp_path: Path,
) -> None:
    observation = profile()
    responses = healthy_responses(observation)
    set_response(
        responses,
        contains=("route", "exact"),
        value=(0, "not-json", ""),
    )

    evidence = collect_evidence_v3(
        tmp_path,
        observation,
        executor=FakeExecutor(responses),
    )

    for feature_name in (
        "route_to_destination_exists_on_observer",
        "route_next_hop_matches_expected",
        "route_next_hop_reachable_from_observer",
    ):
        assert evidence["features"][feature_name] is None
        assert evidence["availability"][feature_name] == (
            "collection_unavailable"
        )
        assert evidence["probes"][feature_name]["raw_artifact"] == (
            "raw/v3/observer_destination_route_v3.json"
        )
    validate_evidence_v3(evidence)


def test_executor_contract_failure_is_persisted_as_probe_failure(
    tmp_path: Path,
) -> None:
    observation = profile()
    delegate = FakeExecutor(healthy_responses(observation))

    def malformed_executor(
        container: str,
        command: tuple[str, ...] | list[str],
    ) -> dict[str, object]:
        if "iptables" in command:
            return {"return_code": "zero"}
        return delegate(container, command)

    evidence = collect_evidence_v3(
        tmp_path,
        observation,
        executor=malformed_executor,
    )

    assert evidence["availability"]["flow_blocked_by_policy"] == (
        "collection_unavailable"
    )
    raw_path = tmp_path / evidence["probes"]["flow_blocked_by_policy"][
        "raw_artifact"
    ]
    artifact = json.loads(raw_path.read_text(encoding="utf-8"))
    assert artifact["return_code"] == 125
    assert "collector_executor_failure" in artifact["stderr"]


def test_existing_output_stops_before_any_probe(tmp_path: Path) -> None:
    (tmp_path / "parsed").mkdir()
    (tmp_path / "parsed/evidence.json").write_text(
        "{}\n",
        encoding="utf-8",
    )
    executor = FakeExecutor(healthy_responses(profile()))

    with pytest.raises(
        EvidenceCollectorV3Error,
        match="output already exists",
    ):
        collect_evidence_v3(
            tmp_path,
            profile(),
            executor=executor,
        )

    assert executor.calls == []


def test_rejects_observation_profile_v1_object(tmp_path: Path) -> None:
    with pytest.raises(
        EvidenceCollectorV3Error,
        match="requires Observation Profile v2",
    ):
        collect_evidence_v3(
            tmp_path,
            object(),  # type: ignore[arg-type]
            executor=FakeExecutor({}),
        )


@pytest.mark.parametrize(
    ("stdout", "expected"),
    [
        ("[]", (True, None)),
        (
            '[{"dst":"default","gateway":"10.10.1.1"}]',
            (True, "10.10.1.1"),
        ),
        ("not-json", (False, None)),
        (
            '[{"dst":"default","gateway":"10.10.1.1"},'
            '{"dst":"default","gateway":"10.10.1.2"}]',
            (False, None),
        ),
    ],
)
def test_default_gateway_parser_is_fail_safe(
    stdout: str,
    expected: tuple[bool, str | None],
) -> None:
    result = command_result(
        "host",
        ["ip", "-j", "route", "show", "default"],
        stdout=stdout,
    )
    assert parse_source_default_gateway(result) == expected


def test_route_parser_distinguishes_absent_from_failed() -> None:
    absent = command_result(
        "router",
        ["ip", "-j", "route", "show", "exact", "10.10.2.0/24"],
        stdout="[]",
    )
    failed = deepcopy(absent)
    failed["return_code"] = 2

    assert parse_observer_route(absent, "10.10.2.0/24").exists is False
    failed_state = parse_observer_route(failed, "10.10.2.0/24")
    assert failed_state.available is False
    assert failed_state.exists is None


@pytest.mark.parametrize(
    ("operstate", "expected"),
    [
        ("UP", (True, "up")),
        ("DOWN", (True, "down")),
        ("UNKNOWN", (False, None)),
    ],
)
def test_interface_parser_accepts_only_frozen_oper_states(
    operstate: str,
    expected: tuple[bool, str | None],
) -> None:
    result = command_result(
        "router",
        ["ip", "-j", "link", "show", "dev", "eth2"],
        stdout=json.dumps([{"ifname": "eth2", "operstate": operstate}]),
    )
    assert parse_interface_oper_state(result, "eth2") == expected


def test_policy_parser_ignores_non_exact_tagged_rule() -> None:
    observation = profile()
    result = command_result(
        observation.route_observer_container,
        ["iptables", "-t", "filter", "-S", "FORWARD"],
        stdout=(
            "-A FORWARD -s 10.10.1.99/32 -d 10.10.2.10/32 "
            "-p icmp -m comment --comment IND-P6-OTHER -j DROP"
        ),
    )
    assert parse_matching_block_rule(result, observation) == (True, None)

    unsupported = deepcopy(result)
    unsupported["stdout"] = (
        "-A FORWARD -s 10.10.1.10/32 -d 10.10.2.10/32 "
        "-p icmp -m conntrack --ctstate ESTABLISHED "
        "-m comment --comment IND-P6-ACL-001 -j DROP"
    )
    assert parse_matching_block_rule(unsupported, observation) == (
        False,
        None,
    )


def test_policy_parser_rejects_ambiguous_exact_rules() -> None:
    observation = profile()
    rule = (
        "-A FORWARD -s 10.10.1.10/32 -d 10.10.2.10/32 "
        "-p icmp -m comment --comment IND-P6-ACL-001 -j DROP"
    )
    second = rule.replace("001", "002")
    result = command_result(
        observation.route_observer_container,
        ["iptables", "-t", "filter", "-S", "FORWARD"],
        stdout=f"{rule}\n{second}\n",
    )
    assert parse_matching_block_rule(result, observation) == (False, None)


def test_policy_parser_matches_tcp_ports_exactly() -> None:
    observation = profile()
    tcp_profile = ObservationProfileV2(
        **{
            **observation.__dict__,
            "flow_protocol": "tcp",
            "flow_source_port": 12345,
            "flow_destination_port": 443,
        }
    )
    result = command_result(
        tcp_profile.route_observer_container,
        ["iptables", "-t", "filter", "-S", "FORWARD"],
        stdout=(
            "-A FORWARD -s 10.10.1.10/32 -d 10.10.2.10/32 "
            "-p tcp --sport 12345 --dport 443 -m comment "
            "--comment IND-P6-TCP-001 -j DROP"
        ),
    )
    assert parse_matching_block_rule(result, tcp_profile) == (
        True,
        "IND-P6-TCP-001",
    )
