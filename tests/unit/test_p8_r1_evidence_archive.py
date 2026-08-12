from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from src.phase7.catalog import (
    DEFAULT_CATALOG_MANIFEST_PATH,
    DEFAULT_INTERFACE_PLAN_PATH,
    FREEZE_ROOT,
    REPORT_ROOT,
    ROOT_IDS,
    build_catalog_manifest,
)
from src.phase8.archive import (
    ARCHIVE_DIRECTORY_NAME,
    ARCHIVE_FILE_NAME,
    CONTEXT_FILE_NAMES,
    DEFAULT_REGISTRY_PATH,
    DEFAULT_RECEIPT_PATH,
    MODEL_FILE_NAMES,
    MODEL_ROOT,
    P7_CATALOG_PATH,
    P8_SCOPE_PATH,
    PUBLIC_EVIDENCE_PATHS,
    REPORT_FILE_NAMES,
    REPORT_ROOT as ARCHIVE_REPORT_ROOT,
    ArchiveContract,
    EvidenceArchiveError,
    build_receipt,
    build_registry,
    create_archive,
    sha256_file,
    verify_archive,
    write_receipt,
    write_registry,
)
from tests.unit.p7_r1_fixtures import build_p7_fixture_repository


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, values: list[object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(value, sort_keys=True) + "\n" for value in values),
        encoding="utf-8",
    )


def _reference(root: Path, relative: str) -> dict[str, object]:
    path = root / relative
    return {
        "path": relative,
        "sha256": sha256_file(path),
        "size_bytes": path.stat().st_size,
    }


def _run(root: Path, *arguments: str) -> None:
    subprocess.run(
        [*arguments],
        cwd=root,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def _build_complete_fixture(tmp_path: Path) -> tuple[Path, ArchiveContract]:
    root = build_p7_fixture_repository(tmp_path)
    run_id = "p6_r5_fixture_campaign"

    # Complete the 13-file model boundary around the P7 fixture sources.
    for name in sorted(MODEL_FILE_NAMES):
        path = root / MODEL_ROOT / name
        if path.exists():
            continue
        if name == "selected_estimator.joblib":
            path.write_bytes(b"opaque-estimator-bytes-not-a-pickle")
        elif name.endswith(".jsonl"):
            _write_jsonl(path, [{"artifact": name}])
        else:
            _write_json(path, {"artifact": name})

    implementation_path = root / "src/archive_fixture_source.py"
    implementation_path.parent.mkdir(parents=True, exist_ok=True)
    implementation_path.write_text("VALUE = 'tracked source'\n", encoding="utf-8")
    protocol_path = root / "plans/phase6/P6_R6_METHOD_PROTOCOL_V1.json"
    _write_json(protocol_path, {"protocol_id": "fixture"})

    development_names = MODEL_FILE_NAMES - {"freeze_manifest.json", "freeze_receipt.json"}
    freeze_manifest = {
        "schema_version": 1,
        "freeze_id": "p6_r6_six_class_method_freeze_v1",
        "protocol": _reference(root, protocol_path.relative_to(root).as_posix()),
        "implementation": {
            implementation_path.relative_to(root).as_posix(): _reference(
                root, implementation_path.relative_to(root).as_posix()
            )
        },
        "development_artifacts": {
            name: _reference(root, (MODEL_ROOT / name).as_posix())
            for name in sorted(development_names)
        },
        "selected_ml_candidate": "logreg_l2_c1",
        "selected_hybrid_policy": "rule_then_ml_fallback_v1",
        "test_inputs_read": 0,
        "test_predictions_or_metrics": "ABSENT",
    }
    _write_json(root / MODEL_ROOT / "freeze_manifest.json", freeze_manifest)
    freeze_receipt = {
        "schema_version": 1,
        "receipt_id": "p6_r6_independent_freeze_verification_v1",
        "authorization": "ONE_REPORT_ONLY_TEST_EVALUATION",
        "freeze_manifest": _reference(root, (MODEL_ROOT / "freeze_manifest.json").as_posix()),
        "selected_estimator": _reference(root, (MODEL_ROOT / "selected_estimator.joblib").as_posix()),
        "ml_selection": _reference(root, (MODEL_ROOT / "ml_selection.json").as_posix()),
        "hybrid_selection": _reference(root, (MODEL_ROOT / "hybrid_selection.json").as_posix()),
    }
    _write_json(root / MODEL_ROOT / "freeze_receipt.json", freeze_receipt)

    run_manifest = json.loads((root / REPORT_ROOT / "run_manifest.json").read_text())
    run_manifest.update(
        {
            "freeze_manifest": _reference(root, (MODEL_ROOT / "freeze_manifest.json").as_posix()),
            "freeze_receipt": _reference(root, (MODEL_ROOT / "freeze_receipt.json").as_posix()),
            "selected_estimator": _reference(root, (MODEL_ROOT / "selected_estimator.joblib").as_posix()),
            "ml_selection": _reference(root, (MODEL_ROOT / "ml_selection.json").as_posix()),
            "hybrid_selection": _reference(root, (MODEL_ROOT / "hybrid_selection.json").as_posix()),
        }
    )
    _write_json(root / REPORT_ROOT / "run_manifest.json", run_manifest)
    gate_path = root / "data/metadata/p6_r6_six_class_method_gate_v1.json"
    gate = json.loads(gate_path.read_text())
    gate["artifacts"] = {
        name: _reference(root, f"{REPORT_ROOT}/{name}")
        for name in sorted(REPORT_FILE_NAMES)
    }
    _write_json(gate_path, gate)

    plan = json.loads((root / DEFAULT_INTERFACE_PLAN_PATH).read_text())
    root_paths = {
        "freeze_manifest": f"{FREEZE_ROOT}/freeze_manifest.json",
        "freeze_receipt": f"{FREEZE_ROOT}/freeze_receipt.json",
        "run_manifest": f"{REPORT_ROOT}/run_manifest.json",
        "cross_method_comparison": f"{REPORT_ROOT}/cross_method_comparison.json",
    }
    plan["accepted_root_bindings"] = [
        {
            "artifact_id": artifact_id,
            "path": root_paths[artifact_id],
            "sha256": sha256_file(root / root_paths[artifact_id]),
        }
        for artifact_id in ROOT_IDS
    ]
    _write_json(root / DEFAULT_INTERFACE_PLAN_PATH, plan)
    _write_json(root / DEFAULT_CATALOG_MANIFEST_PATH, build_catalog_manifest(repository_root=root))

    # Six contexts with 12 experiments each mirror the accepted 72-run shape.
    contexts: list[dict[str, object]] = []
    for index, name in enumerate(sorted(CONTEXT_FILE_NAMES), start=1):
        slot = name.removesuffix(".jsonl")
        context_path = root / "data/processed" / f"{run_id}-contexts" / name
        _write_jsonl(
            context_path,
            [{"context": slot, "repetition": repetition} for repetition in range(1, 13)],
        )
        contexts.append(
            {
                "group_slot": slot,
                "dataset_sha256": sha256_file(context_path),
            }
        )
        for repetition in range(1, 13):
            raw = root / "data/raw" / run_id / slot / f"experiment-{repetition:02d}"
            _write_json(raw / "manifest.json", {"context": index, "experiment": repetition})
            _write_json(raw / "evidence.json", {"context": index, "evidence": repetition})

    merged = root / "data/processed" / f"{run_id}.dataset-row-v3.jsonl"
    _write_jsonl(merged, [{"row": index} for index in range(72)])
    split_root = root / "data/processed" / f"{run_id}-split"
    _write_json(split_root / "split_manifest.json", {"status": "fixture"})
    _write_jsonl(split_root / "train.jsonl", [{"row": 1}, {"row": 2}])
    _write_jsonl(split_root / "validation.jsonl", [{"row": 3}, {"row": 4}])
    _write_jsonl(split_root / "test.jsonl", [{"row": 5}, {"row": 6}])

    campaign = {
        "schema_version": 1,
        "campaign_run_id": run_id,
        "status": "COMPLETED",
        "completed_context_count": 6,
        "completed_experiment_count": 72,
        "dataset_row_count": 72,
        "diagnosis_count": 0,
        "prediction_count": 0,
        "metric_count": 0,
        "masked_row_count": 0,
        "test_partition_status": "SEALED_FOR_P6_R6_REPORT_ONLY",
        "merged_dataset": {
            "path": merged.relative_to(root).as_posix(),
            "sha256": sha256_file(merged),
            "row_count": 72,
        },
        "contexts": contexts,
    }
    campaign_path = root / "data/metadata" / f"{run_id}.phase6-campaign.json"
    _write_json(campaign_path, campaign)
    contract = ArchiveContract(
        campaign_run_id=run_id,
        campaign_result_sha256=sha256_file(campaign_path),
        merged_dataset_sha256=sha256_file(merged),
        split_manifest_sha256=sha256_file(split_root / "split_manifest.json"),
        partition_sha256={
            name: sha256_file(split_root / f"{name}.jsonl")
            for name in ("train", "validation", "test")
        },
        expected_experiment_count=72,
        expected_context_count=6,
    )

    # P8-R0 binds the regenerated P7 catalog.
    catalog_path = root / P7_CATALOG_PATH
    _write_json(
        root / P8_SCOPE_PATH,
        {
            "status": "FROZEN",
            "decision": "NO_NEW_EXPERIMENT_REQUIRED",
            "final_evaluation_snapshot": {
                "catalog_binding": _reference(root, P7_CATALOG_PATH.as_posix())
            },
        },
    )

    # Every public binding must exist and be tracked; private runtime remains
    # ignored exactly as in the real repository.
    for relative in PUBLIC_EVIDENCE_PATHS:
        path = root / relative
        if not path.exists():
            if path.suffix == ".json":
                _write_json(path, {"public": relative})
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(f"tracked public evidence: {relative}\n", encoding="utf-8")
    (root / ".gitignore").write_text("data/\nmodels/\nreports/\n", encoding="utf-8")
    _run(root, "git", "init", "-b", "main")
    _run(root, "git", "config", "user.name", "P8 Fixture")
    _run(root, "git", "config", "user.email", "fixture@example.invalid")
    tracked = sorted(set(PUBLIC_EVIDENCE_PATHS) | {implementation_path.relative_to(root).as_posix(), ".gitignore"})
    _run(root, "git", "add", "--", *tracked)
    _run(root, "git", "commit", "-m", "fixture checkpoint")
    return root, contract


@pytest.fixture(scope="module")
def accepted_fixture(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, ArchiveContract]:
    return _build_complete_fixture(tmp_path_factory.mktemp("p8_r1_fixture"))


def _registry(accepted_fixture: tuple[Path, ArchiveContract]) -> dict[str, object]:
    root, contract = accepted_fixture
    return build_registry(root, contract=contract)


def test_registry_covers_final_campaign_model_and_report_chain(
    accepted_fixture: tuple[Path, ArchiveContract],
) -> None:
    registry = _registry(accepted_fixture)
    roles = {item["role"] for item in registry["runtime_artifacts"]}
    assert registry["raw_experiment_count"] == 72
    assert registry["runtime_artifact_count"] == len(registry["runtime_artifacts"])
    assert {
        "campaign_result",
        "raw_experiment_artifact",
        "merged_dataset",
        "dataset_partition",
        "opaque_selected_estimator",
        "report_only_evaluation_artifact",
    } <= roles


def test_estimator_is_opaque_and_runtime_is_unauthorized(
    accepted_fixture: tuple[Path, ArchiveContract],
) -> None:
    registry = _registry(accepted_fixture)
    estimator = [
        item for item in registry["runtime_artifacts"]
        if item["role"] == "opaque_selected_estimator"
    ]
    assert len(estimator) == 1
    assert registry["integrity"]["estimator_handling"] == (
        "OPAQUE_BYTES_HASHED_AND_COPIED_NOT_DESERIALIZED"
    )
    assert set(registry["runtime_authorization"].values()) == {False}
    source = Path("src/phase8/archive.py").read_text(encoding="utf-8")
    import_lines = {line.strip() for line in source.splitlines() if line.startswith(("import ", "from "))}
    assert "import joblib" not in import_lines
    assert "import pickle" not in import_lines


def test_public_source_is_bound_but_not_copied(
    accepted_fixture: tuple[Path, ArchiveContract],
) -> None:
    registry = _registry(accepted_fixture)
    assert registry["public_source_binding_count"] == len(registry["public_source_bindings"])
    assert all(item["archive_member"] is False for item in registry["public_source_bindings"])
    assert {item["path"] for item in registry["public_source_bindings"]}.isdisjoint(
        {item["path"] for item in registry["runtime_artifacts"]}
    )


def test_registry_binds_p7_catalog_and_p8_scope(
    accepted_fixture: tuple[Path, ArchiveContract],
) -> None:
    root, _ = accepted_fixture
    registry = _registry(accepted_fixture)
    assert registry["p7_projection_catalog"]["sha256"] == sha256_file(root / P7_CATALOG_PATH)
    assert registry["p8_scope_gate"]["sha256"] == sha256_file(root / P8_SCOPE_PATH)
    assert len(registry["accepted_roots"]) == 8


def test_registry_schema_accepts_generated_contract(
    accepted_fixture: tuple[Path, ArchiveContract],
) -> None:
    schema = json.loads(Path("schemas/p8_final_evidence_registry_v1.schema.json").read_text())
    Draft202012Validator.check_schema(schema)
    errors = list(Draft202012Validator(schema).iter_errors(_registry(accepted_fixture)))
    assert errors == [], errors[0].message if errors else ""


def test_deterministic_archives_have_identical_sha256(
    accepted_fixture: tuple[Path, ArchiveContract], tmp_path: Path,
) -> None:
    root, _ = accepted_fixture
    registry_path = tmp_path / "registry.json"
    write_registry(registry_path, _registry(accepted_fixture))
    first = tmp_path / "first.tar.gz"
    second = tmp_path / "second.tar.gz"
    one = create_archive(root, registry_path, first)
    two = create_archive(root, registry_path, second)
    assert one["archive_sha256"] == two["archive_sha256"]
    assert first.read_bytes() == second.read_bytes()


def test_archive_verification_and_layout(
    accepted_fixture: tuple[Path, ArchiveContract], tmp_path: Path,
) -> None:
    root, _ = accepted_fixture
    registry_path = tmp_path / "registry.json"
    registry = _registry(accepted_fixture)
    write_registry(registry_path, registry)
    archive_path = tmp_path / ARCHIVE_FILE_NAME
    result = create_archive(root, registry_path, archive_path)
    assert result["runtime_artifact_count"] == registry["runtime_artifact_count"]
    assert result["archive_member_count"] == registry["runtime_artifact_count"] + 2
    assert verify_archive(root, registry_path, archive_path) == result


def test_receipt_schema_accepts_verified_archive(
    accepted_fixture: tuple[Path, ArchiveContract], tmp_path: Path,
) -> None:
    root, _ = accepted_fixture
    registry_path = tmp_path / DEFAULT_REGISTRY_PATH
    write_registry(registry_path, _registry(accepted_fixture))
    archive_path = tmp_path / ARCHIVE_FILE_NAME
    verification = create_archive(root, registry_path, archive_path)
    receipt = build_receipt(
        registry_path=registry_path,
        archive_path=archive_path,
        verification=verification,
    )
    schema = json.loads(Path("schemas/p8_private_archive_receipt_v1.schema.json").read_text())
    Draft202012Validator.check_schema(schema)
    errors = list(Draft202012Validator(schema).iter_errors(receipt))
    assert errors == [], errors[0].message if errors else ""
    receipt_path = tmp_path / DEFAULT_RECEIPT_PATH
    write_receipt(receipt_path, receipt)
    assert json.loads(receipt_path.read_text()) == receipt


def _copy_fixture(
    accepted_fixture: tuple[Path, ArchiveContract], tmp_path: Path
) -> tuple[Path, ArchiveContract]:
    root, contract = accepted_fixture
    copy = tmp_path / "repository"
    shutil.copytree(root, copy, symlinks=True)
    return copy, contract


def test_missing_runtime_artifact_fails_closed(
    accepted_fixture: tuple[Path, ArchiveContract], tmp_path: Path,
) -> None:
    root, contract = _copy_fixture(accepted_fixture, tmp_path)
    (root / MODEL_ROOT / "development_summary.json").unlink()
    with pytest.raises(EvidenceArchiveError, match="model file set drifted"):
        build_registry(root, contract=contract)


def test_drifted_runtime_artifact_fails_closed(
    accepted_fixture: tuple[Path, ArchiveContract], tmp_path: Path,
) -> None:
    root, contract = _copy_fixture(accepted_fixture, tmp_path)
    with (root / REPORT_ROOT / "test_inputs.jsonl").open("ab") as stream:
        stream.write(b"{}\n")
    with pytest.raises(Exception, match="drifted"):
        build_registry(root, contract=contract)


def test_extra_model_artifact_fails_closed(
    accepted_fixture: tuple[Path, ArchiveContract], tmp_path: Path,
) -> None:
    root, contract = _copy_fixture(accepted_fixture, tmp_path)
    _write_json(root / MODEL_ROOT / "unexpected.json", {"unexpected": True})
    with pytest.raises(EvidenceArchiveError, match="model file set drifted"):
        build_registry(root, contract=contract)


def test_symbolic_raw_artifact_fails_closed(
    accepted_fixture: tuple[Path, ArchiveContract], tmp_path: Path,
) -> None:
    root, contract = _copy_fixture(accepted_fixture, tmp_path)
    target = root / "data/raw" / contract.campaign_run_id / "E01/experiment-01/evidence.json"
    link = target.with_name("linked.json")
    os.symlink(target.name, link)
    with pytest.raises(EvidenceArchiveError, match="Symbolic links are forbidden"):
        build_registry(root, contract=contract)


def test_tampered_archive_fails_verification(
    accepted_fixture: tuple[Path, ArchiveContract], tmp_path: Path,
) -> None:
    root, _ = accepted_fixture
    registry_path = tmp_path / "registry.json"
    write_registry(registry_path, _registry(accepted_fixture))
    archive_path = tmp_path / ARCHIVE_FILE_NAME
    create_archive(root, registry_path, archive_path)
    payload = bytearray(archive_path.read_bytes())
    payload[len(payload) // 2] ^= 0x01
    archive_path.write_bytes(payload)
    with pytest.raises(EvidenceArchiveError):
        verify_archive(root, registry_path, archive_path)


def test_registry_and_archive_outputs_refuse_overwrite(
    accepted_fixture: tuple[Path, ArchiveContract], tmp_path: Path,
) -> None:
    root, _ = accepted_fixture
    registry_path = tmp_path / "registry.json"
    registry = _registry(accepted_fixture)
    write_registry(registry_path, registry)
    with pytest.raises(EvidenceArchiveError, match="already exists"):
        write_registry(registry_path, registry)
    archive_path = tmp_path / ARCHIVE_FILE_NAME
    create_archive(root, registry_path, archive_path)
    with pytest.raises(EvidenceArchiveError, match="already exists"):
        create_archive(root, registry_path, archive_path)


def test_archive_scope_excludes_historical_and_failed_runtime(
    accepted_fixture: tuple[Path, ArchiveContract],
) -> None:
    registry = _registry(accepted_fixture)
    categories = {item["category"] for item in registry["excluded_from_private_runtime_archive"]}
    assert {
        "FAILED_OR_DIAGNOSTIC_CAMPAIGNS",
        "P1_TO_P5_DEVELOPMENT_RUNTIME",
        "TRACKED_PUBLIC_SOURCE",
    } <= categories
    assert registry["next_milestone"] == "P8-R2"
