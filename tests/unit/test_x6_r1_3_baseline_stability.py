"""Synthetic source-only tests for X6-R1.3; no fixture is runtime evidence."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

import src.expansion.x6_r1_3_baseline_stability as contract
from src.expansion.x6_r1_3_baseline_stability import X6R13ContractError


ROOT = Path(__file__).resolve().parents[2]


def _write(root: Path, relative: str, value: object) -> str:
    path = root / relative; path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _field(root: Path, section: str, field_id: str, spec: tuple[str, str, str, str, bool, str], *, available: bool = True) -> dict[str, object]:
    relative = f"raw/provenance/{section}_{field_id}.json"
    digest = _write(root, relative, {"synthetic_source_test_only": True, "field_id": field_id})
    owner, source, parser, unit, required, absence = spec
    raw_value = {"counter_reset_or_wrap": False, "delta_valid": True} if field_id == "interface_counter_deltas" else {"synthetic": field_id}
    return {"field_id": field_id, "owner": owner, "source": source, "parser": parser, "unit": unit, "required": required, "absence_effect": absence, "availability": "observed" if available else "collection_unavailable", "value": raw_value if available else None, "captured_at_utc": "2026-09-01T00:00:00Z", "monotonic_ns": 100, "raw_provenance_path": relative, "raw_provenance_sha256": digest, "failure_behavior": "FAIL_CLOSED_NEVER_COERCE_TO_HEALTHY"}


def _provenance(root: Path, *, missing_dynamic: bool = False) -> dict[str, object]:
    static = [_field(root, "static", field_id, spec) for field_id, spec in contract.STATIC_FIELDS.items()]
    dynamic = [_field(root, "dynamic", field_id, spec, available=not (missing_dynamic and field_id == "host_load_average")) for field_id, spec in contract.DYNAMIC_FIELDS.items()]
    return {"schema_version": 1, "contract_id": "X6_HOST_RUNTIME_PROVENANCE_V1", "timestamp_format": "RFC3339_UTC_AND_MONOTONIC_NS", "static_environment_identity": static, "dynamic_execution_context": dynamic}


def _qualification(root: Path) -> dict[str, object]:
    windows: list[dict[str, object]] = []
    for index in range(1, 31):
        phase = "calibration" if index <= 20 else "holdout"
        relative = f"raw/windows/{index:02d}.json"; digest = _write(root, relative, {"synthetic_source_test_only": True, "window": index})
        values = {metric: index for metric in contract.METRICS}
        windows.append({"window_id": f"{phase}-{index:02d}", "phase": phase, "monotonic_start_ns": index * 1000, "wall_clock_utc": f"2026-09-01T00:00:{index:02d}Z", "startup_skew_seconds": 0.1, "mutation": "NONE", "raw_provenance_path": relative, "raw_provenance_sha256": digest, "measurements": values})
    calibration = windows[:20]; holdout = windows[20:]
    statistics: dict[str, object] = {}
    for metric in contract.METRICS:
        cal_median, cal_mad = contract._statistics([contract.Decimal(str(row["measurements"][metric])) for row in calibration])
        hold_median, hold_mad = contract._statistics([contract.Decimal(str(row["measurements"][metric])) for row in holdout])
        statistics[metric] = {"formula": "median_mad_independent_calibration_holdout_v1", "calibration_median": cal_median, "calibration_mad": cal_mad, "holdout_median": hold_median, "holdout_mad": hold_mad, "drift": contract._six(contract.Decimal(hold_median) - contract.Decimal(cal_median)), "numeric_limit": "UNRESOLVED"}
    value: dict[str, object] = {"schema_version": 1, "release_id": "X6_R1_3_BASELINE_STABILITY_AND_HOST_PROVENANCE_METHOD_GATE", "execution_kind": "BASELINE_ONLY_NO_MUTATION", "numeric_limits_status": "UNRESOLVED_NO_RUNTIME_DERIVATION", "windows": windows, "calibration_window_ids": [row["window_id"] for row in calibration], "holdout_window_ids": [row["window_id"] for row in holdout], "statistics": statistics, "decision": {"status": "INCONCLUSIVE", "mutation_authorized": False, "pilot_authorized": False}}
    value["sha256"] = contract.qualification_canonical_sha256(value)
    return value


def _tree(root: Path) -> None:
    provenance = _provenance(root); qualification = _qualification(root)
    _write(root, "provenance/host_runtime_provenance_v1.json", provenance)
    _write(root, "qualification/baseline_qualification_v1.json", qualification)
    artifacts: dict[str, str] = {}
    for row in provenance["static_environment_identity"] + provenance["dynamic_execution_context"]:
        artifacts[row["raw_provenance_path"]] = row["raw_provenance_sha256"]
    for row in qualification["windows"]:
        artifacts[row["raw_provenance_path"]] = row["raw_provenance_sha256"]
    _write(root, "validation/raw_hashes.json", {"artifacts": artifacts})
    _write(root, "validation/cleanup_provenance.json", {"status": "CLEANUP_CONFIRMED_NO_CONTAINERS_NAMESPACES_OR_IPERF", "lingering_iperf_processes": []})


def test_provenance_schema_catalog_and_fail_closed_admission(tmp_path: Path) -> None:
    provenance = _provenance(tmp_path)
    contract.validate_host_runtime_provenance(provenance, repository_root=ROOT)
    assert contract.provenance_admission(provenance) == "ELIGIBLE_FOR_BASELINE_QUALIFICATION_ONLY"
    unavailable = _provenance(tmp_path / "unavailable", missing_dynamic=True)
    contract.validate_host_runtime_provenance(unavailable, repository_root=ROOT)
    assert contract.provenance_admission(unavailable) == "COLLECTION_UNAVAILABLE"
    provenance["dynamic_execution_context"][0]["unit"] = "wrong_unit"
    with pytest.raises(X6R13ContractError, match="field contract drift"):
        contract.validate_host_runtime_provenance(provenance, repository_root=ROOT)


def test_provenance_rejects_malformed_dynamic_and_counter_reset(tmp_path: Path) -> None:
    malformed = _provenance(tmp_path / "malformed")
    malformed["dynamic_execution_context"][0]["value"] = "unparsed /proc output"
    with pytest.raises(X6R13ContractError, match="structured raw-derived"):
        contract.validate_host_runtime_provenance(malformed, repository_root=ROOT)
    reset = _provenance(tmp_path / "reset")
    counter = next(row for row in reset["dynamic_execution_context"] if row["field_id"] == "interface_counter_deltas")
    counter["value"] = {"counter_reset_or_wrap": True, "delta_valid": False}
    with pytest.raises(X6R13ContractError, match="counter reset"):
        contract.validate_host_runtime_provenance(reset, repository_root=ROOT)


@pytest.mark.parametrize("mutation", ["duplicate", "leakage", "reordered", "post_hoc", "skew", "false_rehashed"])
def test_qualification_contract_rejects_adversarial_structure(tmp_path: Path, mutation: str) -> None:
    qualification = _qualification(tmp_path)
    if mutation == "duplicate": qualification["windows"][1]["window_id"] = qualification["windows"][0]["window_id"]
    elif mutation == "leakage": qualification["holdout_window_ids"][0] = qualification["calibration_window_ids"][0]
    elif mutation == "reordered": qualification["windows"][4]["monotonic_start_ns"] = 1
    elif mutation == "post_hoc": qualification["statistics"]["packet_loss_ratio"]["numeric_limit"] = "0.100000"
    elif mutation == "skew": qualification["windows"][0]["startup_skew_seconds"] = 0.251
    else: qualification["decision"]["status"] = "QUALIFIED"; qualification["sha256"] = contract.qualification_canonical_sha256(qualification)
    with pytest.raises(X6R13ContractError):
        contract.validate_baseline_qualification(qualification)


def test_independent_future_qualification_verifier_rejects_provenance_hash_cleanup_and_missing_window(tmp_path: Path) -> None:
    _tree(tmp_path)
    assert contract.verify_future_baseline_qualification(tmp_path, ROOT)["status"] == "INCONCLUSIVE"
    hashes = json.loads((tmp_path / "validation/raw_hashes.json").read_text()); hashes["artifacts"]["raw/windows/01.json"] = "0" * 64
    (tmp_path / "validation/raw_hashes.json").write_text(json.dumps(hashes))
    with pytest.raises(X6R13ContractError, match="hash"):
        contract.verify_future_baseline_qualification(tmp_path, ROOT)
    _tree(tmp_path / "cleanup")
    (tmp_path / "cleanup/validation/cleanup_provenance.json").write_text(json.dumps({"status": "CLEANUP_CONFIRMED_NO_CONTAINERS_NAMESPACES_OR_IPERF", "lingering_iperf_processes": ["iperf3"]}))
    with pytest.raises(X6R13ContractError, match="cleanup"):
        contract.verify_future_baseline_qualification(tmp_path / "cleanup", ROOT)
