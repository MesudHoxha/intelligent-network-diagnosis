from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from src.expansion.x6_r0_4_runtime_parameter_freeze import (
    CONTEXT,
    EXPECTED_FEATURES,
    ROOT,
    X6R04ParameterFreezeError,
    _strings,
    _validate_commands_and_qdisc,
    _validate_rule_and_policy,
    _validate_topology,
    _validate_windows_features_and_effectiveness,
    validate_x6_r0_4_runtime_context,
)


def _context() -> dict[str, object]:
    return json.loads((ROOT / CONTEXT).read_text(encoding="utf-8"))


def test_runtime_context_schema_and_semantics_pass() -> None:
    context = validate_x6_r0_4_runtime_context(ROOT)
    assert context["release_id"] == "X6_R0_4_F1_RUNTIME_PARAMETER_FREEZE"


def test_topology_hash_nodes_links_interfaces_addresses_and_routes_are_frozen() -> None:
    context = _context()
    _validate_topology(context, ROOT)
    topology_path = ROOT / context["topology"]["file"]
    assert hashlib.sha256(topology_path.read_bytes()).hexdigest() == context["topology"]["sha256"]
    assert context["topology"]["mutation_owner"]["container"] == "clab-x6r1-r2"
    assert context["topology"]["mutation_owner"]["interface"] == "eth2"


def test_duplicate_or_unmaterialized_address_is_rejected() -> None:
    context = _context()
    context["topology"]["links"][1]["addresses"]["r2:eth1"] = "10.61.12.1/30"
    with pytest.raises(X6R04ParameterFreezeError):
        _validate_topology(context, ROOT)


def test_complete_ping_iperf_and_qdisc_commands_have_no_runtime_placeholders() -> None:
    context = _context()
    _validate_commands_and_qdisc(context)
    assert not any("TBD" in text or "PENDING" in text or "<hostb" in text or "<r2" in text for text in _strings(context))
    assert context["traffic"]["ping_command"][-1] == "10.61.3.2"
    assert context["traffic"]["client_command"][-1] == "-J"


def test_exact_loss_model_and_limits_are_frozen_before_runtime() -> None:
    qdisc = _context()["qdisc"]
    assert qdisc["loss_percent"] == "10.000000"
    assert qdisc["correlation_percent"] == "0.000000"
    assert qdisc["seed"] is None
    assert qdisc["netem"] == {"kind": "netem", "handle": "10:", "parent": "root", "limit_packets": 1000}
    assert qdisc["pfifo"]["handle"] == "20:" and qdisc["pfifo"]["parent"] == "10:1" and qdisc["pfifo"]["limit_packets"] == 1000


def test_only_exact_noqueue_prestate_and_declared_partial_states_are_supported() -> None:
    context = _context()
    _validate_commands_and_qdisc(context)
    assert context["qdisc"]["pre_state"]["kind"] == "noqueue"
    assert [row["name"] for row in context["qdisc"]["partial_states"]] == ["root_only", "root_and_child"]
    changed = copy.deepcopy(context)
    changed["qdisc"]["pre_state"]["kind"] = "fq_codel"
    with pytest.raises(X6R04ParameterFreezeError):
        _validate_commands_and_qdisc(changed)


def test_composite_timeline_and_window_counts_are_fixed() -> None:
    context = _context()
    _validate_windows_features_and_effectiveness(context, ROOT)
    assert context["windows"]["warm_up"]["count"] == 1
    assert [context["windows"][name]["count"] for name in ("baseline", "fault", "restoration")] == [10, 3, 3]
    assert context["windows"]["allowed_start_skew_seconds"] == "0.250"


def test_all_six_x1_features_keep_types_and_raw_provenance_separate() -> None:
    context = _context()
    assert tuple(row["feature_id"] for row in context["features"]) == EXPECTED_FEATURES
    assert [row["value_type"] for row in context["features"]] == ["number", "number", "number", "number", "integer", "boolean"]
    assert all("predicate" not in row for row in context["features"])


def test_utilization_uses_direct_equal_speed_measurements_not_nominal_capacity() -> None:
    utilization = next(row for row in _context()["features"] if row["feature_id"] == "interface_utilization_ratio")
    assert "measured_speed_mbps" in utilization["per_window"]
    assert "require equal positive integer Mbps" in utilization["denominator"]
    assert "never use nominal topology capacity" in utilization["denominator"]


def test_binomial_loss_selection_and_effectiveness_bounds_are_recomputed() -> None:
    context = _context()
    _validate_windows_features_and_effectiveness(context, ROOT)
    effectiveness = context["effectiveness"]
    assert effectiveness["acceptance_drop_count_inclusive"] == [6, 25]
    assert effectiveness["central_coverage"] == "0.9941638589199969"
    assert effectiveness["single_window_detection_probability"] == "0.9948462247926799"


def test_changed_effectiveness_bound_fails_semantic_validation() -> None:
    context = _context()
    context["effectiveness"]["acceptance_drop_count_inclusive"] = [1, 40]
    with pytest.raises(X6R04ParameterFreezeError):
        _validate_windows_features_and_effectiveness(context, ROOT)


def test_rule_identity_diagnosis_mapping_and_fail_closed_states_are_frozen() -> None:
    context = _context()
    _validate_rule_and_policy(context)
    assert context["rule"]["rule_id"] == "R_X6_PERFORMANCE_001"
    assert context["rule"]["insufficient_evidence"]["status"] == "insufficient_evidence"
    assert context["rule"]["no_rule_match"]["status"] == "abstained"
    assert context["rule"]["diagnosed"]["explanation_ref"] == "rule:R_X6_PERFORMANCE_001"


def test_one_official_pilot_and_no_post_hoc_rerun_policy_are_frozen() -> None:
    policy = _context()["rerun_policy"]
    assert policy["official_pilot_count"] == 1
    assert "no opportunistic rerun" in policy["post_mutation"]
    assert {"loss_percent", "thresholds", "traffic", "window_counts", "sample_selection", "qdisc_limits"} == set(policy["immutable_after_result"])


def test_current_authorization_is_zero_and_only_x6_r1_source_pilot_are_next() -> None:
    authorization = _context()["authorization"]
    assert len(authorization["current_release"]) == 10 and not any(authorization["current_release"].values())
    assert authorization["next_release"]["x6_r1_source_implementation"] is True
    assert authorization["next_release"]["x6_r1_controlled_runtime_pilot"] is True
    assert not any(value for key, value in authorization["next_release"].items() if key not in {"x6_r1_source_implementation", "x6_r1_controlled_runtime_pilot"})
