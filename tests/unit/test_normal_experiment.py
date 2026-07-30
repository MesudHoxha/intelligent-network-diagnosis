import json
from pathlib import Path

from src.contracts.observation_profile import (
    ObservationProfile,
)
from src.dataset.contract import build_dataset_row
from src.orchestration import experiment_runner


def test_normal_experiment_uses_no_fault_path(
    tmp_path: Path,
    monkeypatch,
) -> None:
    scenario_path = tmp_path / "normal.yml"
    scenario_path.write_text(
        """
schema_version: 1
scenario:
  id: N0_NORMAL_OPERATION
  name: Normal operation
  kind: normal
  variant_id: canonical
  topology:
    id: TOP_01
    file: topology.yml
  observation:
    schema_version: 1
    direction: hosta_to_hostb
    source_container: clab-top01-hosta
    source_gateway_address: 10.10.1.1
    destination_address: 10.10.2.10
    destination_prefix: 10.10.2.0/24
    route_observer_node: r1
    route_observer_container: clab-top01-r1
    expected_next_hop: 10.10.12.2
    transit_node: r2
    transit_container: clab-top01-r2
  ground_truth:
    fault_category: null
    fault_type: no_fault
    fault_location: null
    affected_prefix: null
""".lstrip(),
        encoding="utf-8",
    )

    def fake_baseline(
        _: Path,
    ) -> dict[str, object]:
        return {
            "return_code": 0,
            "stdout": "baseline valid",
            "stderr": "",
            "timestamp_utc": (
                "2026-07-28T12:00:00+00:00"
            ),
        }

    def fake_collect(
        experiment_directory: Path,
        profile: ObservationProfile,
    ) -> dict[str, object]:
        assert profile.destination_address == "10.10.2.10"
        assert profile.destination_prefix == "10.10.2.0/24"

        evidence = {
            "schema_version": 2,
            "topology_id": "TOP_01",
            "collected_at_utc": (
                "2026-07-28T12:00:10+00:00"
            ),
            "direction": "hosta_to_hostb",
            "route_observer_node": "r1",
            "transit_node": "r2",
            "destination_address": "10.10.2.10",
            "destination_prefix": "10.10.2.0/24",
            "source_gateway_reachable": True,
            "destination_reachable": True,
            (
                "route_to_destination_exists_on_observer"
            ): True,
            "route_next_hop_on_observer": "10.10.12.2",
            (
                "route_next_hop_reachable_from_observer"
            ): True,
            (
                "expected_next_hop_reachable_from_observer"
            ): True,
            (
                "destination_reachable_from_transit"
            ): True,
        }

        experiment_runner.write_json(
            experiment_directory
            / "parsed"
            / "evidence.json",
            evidence,
        )
        experiment_runner.write_json(
            experiment_directory
            / "collector_status.json",
            {
                "status": "COLLECTION_COMPLETED",
            },
        )

        return evidence

    def forbidden_operation(*args, **kwargs):
        raise AssertionError(
            "Normal runs must not inject or restore a fault."
        )

    monkeypatch.setattr(
        experiment_runner,
        "validate_baseline",
        fake_baseline,
    )
    monkeypatch.setattr(
        experiment_runner,
        "collect_evidence",
        fake_collect,
    )
    monkeypatch.setattr(
        experiment_runner,
        "inject_fault",
        forbidden_operation,
    )
    monkeypatch.setattr(
        experiment_runner,
        "restore_fault",
        forbidden_operation,
    )

    result = experiment_runner.run_experiment(
        scenario_path=scenario_path,
        output_root=tmp_path / "raw",
        baseline_validator=tmp_path / "validator.sh",
    )

    experiment_directory = Path(
        result["experiment_directory"]
    )
    manifest = json.loads(
        (
            experiment_directory / "manifest.json"
        ).read_text(encoding="utf-8")
    )
    diagnosis = json.loads(
        (
            experiment_directory
            / "diagnosis"
            / "rule_based.json"
        ).read_text(encoding="utf-8")
    )

    assert result["scenario_kind"] == "normal"
    assert result["exact_match"] is True
    assert result["baseline_restored"] is False
    assert result["baseline_valid_after"] is True

    assert manifest["schema_version"] == 2
    assert manifest["current_state"] == "COMPLETED"

    states = [
        entry["state"]
        for entry in manifest["state_history"]
    ]

    assert "NORMAL_CONFIRMED" in states
    assert "POST_RUN_VALIDATED" in states
    assert "FAULT_CONFIRMED" not in states
    assert "FAULT_RESTORED" not in states

    assert diagnosis["status"] == "NO_FAULT_DETECTED"
    assert diagnosis["diagnosis"] is None

    row = build_dataset_row(experiment_directory)

    assert row["schema_version"] == 2
    assert row["labels"]["fault_type"] == "no_fault"
    assert set(row["features"].values()) == {"true"}
    assert (
        row["quality"]["unavailable_feature_count"]
        == 0
    )
