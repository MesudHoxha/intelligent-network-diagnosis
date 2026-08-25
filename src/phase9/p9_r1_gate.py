from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Mapping

from jsonschema import Draft202012Validator

from src.phase9.gate import verify_gate as verify_p9_r0_gate


ROOT = Path(__file__).resolve().parents[2]
PLAN = Path("plans/phase9/P9_R1_THESIS_SKELETON_TRACEABILITY_V1.json")
SCHEMA = Path("schemas/p9_r1_thesis_skeleton_traceability_v1.schema.json")
SKELETON = Path("docs/P9_R1_THESIS_SKELETON_AND_TRACEABILITY_MATRIX.md")
EXPECTED_PARENT = "50f0624679d7b1577d88d66ba87eb1c7390e80f0"
EXPECTED_CHAPTERS = tuple(f"CH0{number}" for number in range(1, 8))
EXPECTED_CLAIMS = tuple(f"C0{number}" for number in range(1, 9))
EXPECTED_BLOCKED = tuple(f"B0{number}" for number in range(1, 9))
EXPECTED_ASSETS = {"T01": "CH03", "T02": "CH05", "T03": "CH06", "F01": "CH05", "F02": "CH05"}


class P9R1GateError(ValueError):
    pass


def _load(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise P9R1GateError(f"Cannot read {path}.") from error
    if not isinstance(value, dict):
        raise P9R1GateError(f"{path} must be a JSON object.")
    return value


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rows(path: Path) -> list[dict[str, str]]:
    try:
        with path.open(encoding="utf-8", newline="") as stream:
            return list(csv.DictReader(stream))
    except OSError as error:
        raise P9R1GateError(f"Cannot read traceability asset: {path}.") from error


def _verify_asset(root: Path, row: Mapping[str, object]) -> Path:
    relative = row.get("path")
    if not isinstance(relative, str) or not relative.startswith("docs/thesis_assets/phase9/"):
        raise P9R1GateError("P9-R1 asset path is invalid.")
    path = root / relative
    if not path.is_file() or path.is_symlink():
        raise P9R1GateError(f"P9-R1 asset is missing or unsafe: {relative}")
    if path.stat().st_size != row.get("size_bytes") or _digest(path) != row.get("sha256"):
        raise P9R1GateError(f"P9-R1 asset hash drifted: {relative}")
    return path


def verify_p9_r1_gate(repository_root: Path = ROOT) -> dict[str, object]:
    root = Path(repository_root)
    plan = _load(root / PLAN)
    schema = _load(root / SCHEMA)
    errors = list(Draft202012Validator(schema).iter_errors(plan))
    if errors:
        raise P9R1GateError(f"P9-R1 schema validation failed: {errors[0].message}")
    if plan.get("source_boundary") != {"parent_commit": EXPECTED_PARENT, "extension_policy": "APPEND_ONLY", "runtime_inherited": False}:
        raise P9R1GateError("P9-R1 source boundary drifted.")
    authorization = plan.get("authorization")
    allowed = {"chapter_skeleton", "front_matter_placeholders", "traceability_matrix"}
    if not isinstance(authorization, Mapping) or {key for key, value in authorization.items() if value is True} != allowed or any(value is not False for key, value in authorization.items() if key not in allowed):
        raise P9R1GateError("P9-R1 authorization drifted.")
    bindings = plan.get("source_bindings")
    if not isinstance(bindings, list) or len(bindings) != 9:
        raise P9R1GateError("P9-R1 requires exactly nine source bindings.")
    seen = set()
    for binding in bindings:
        if not isinstance(binding, Mapping):
            raise P9R1GateError("P9-R1 source binding is invalid.")
        path_text = binding.get("path")
        if not isinstance(path_text, str) or path_text in seen:
            raise P9R1GateError("P9-R1 source binding is duplicate or invalid.")
        seen.add(path_text)
        path = root / path_text
        if not path.is_file() or path.is_symlink() or _digest(path) != binding.get("sha256"):
            raise P9R1GateError(f"P9-R1 source binding drifted: {path_text}")
    parent = verify_p9_r0_gate(root)
    if parent.get("next_milestone") != "P9-R1_THESIS_SKELETON_AND_TRACEABILITY_MATRIX":
        raise P9R1GateError("P9-R0 does not authorize this thesis skeleton.")
    if plan.get("phase8_boundary") != {"supported_claim_ids": list(EXPECTED_CLAIMS), "blocked_claim_ids": list(EXPECTED_BLOCKED), "hybrid_interpretation": "OPERATIONALLY_DISTINCT_NUMERICALLY_EQUAL_TO_ML", "masked_inputs": "TRANSFORMATIONS_NOT_INDEPENDENT_EXPERIMENTS"}:
        raise P9R1GateError("P9-R1 Phase 8 claim boundary drifted.")
    assets = plan.get("traceability_assets")
    if not isinstance(assets, list) or len(assets) != 4:
        raise P9R1GateError("P9-R1 requires four traceability assets.")
    asset_paths = {str(row.get("asset_id")): _verify_asset(root, row) for row in assets if isinstance(row, Mapping)}
    if set(asset_paths) != {"P9R1T01", "P9R1T02", "P9R1T03", "P9R1T04"}:
        raise P9R1GateError("P9-R1 traceability asset identities drifted.")
    source_rows = _rows(asset_paths["P9R1T01"])
    source_ids = {source["source_id"] for source in parent["source_gate"]["sources"]}
    if len(source_rows) != 16 or {row.get("source_id") for row in source_rows} != source_ids or any(not row.get("section_id", "").startswith(("CH", "FRONT.")) for row in source_rows):
        raise P9R1GateError("P9-R1 source-to-section matrix drifted.")
    claim_rows = _rows(asset_paths["P9R1T02"])
    expected_limits = {claim["claim_id"]: claim["limit"] for claim in parent["claim_boundary"]["supported_claims"]}
    if len(claim_rows) != 8 or {row.get("claim_id") for row in claim_rows} != set(EXPECTED_CLAIMS) or {row.get("claim_id"): row.get("required_limit") for row in claim_rows} != expected_limits:
        raise P9R1GateError("P9-R1 claim-to-paragraph plan drifted.")
    blocked_rows = _rows(asset_paths["P9R1T03"])
    if len(blocked_rows) != 8 or {row.get("claim_id") for row in blocked_rows} != set(EXPECTED_BLOCKED) or any(row.get("guard") != "PROHIBITED_NOT_DRAFTABLE" for row in blocked_rows):
        raise P9R1GateError("P9-R1 blocked-claim guard drifted.")
    placement_rows = _rows(asset_paths["P9R1T04"])
    if len(placement_rows) != 5 or {row.get("asset_id"): row.get("chapter_id") for row in placement_rows} != EXPECTED_ASSETS:
        raise P9R1GateError("P9-R1 Phase 8 asset placement drifted.")
    skeleton = root / SKELETON
    if not skeleton.is_file() or skeleton.is_symlink():
        raise P9R1GateError("P9-R1 thesis skeleton is missing or unsafe.")
    text = skeleton.read_text(encoding="utf-8")
    if "## Front matter" not in text or any(f"## {chapter}" not in text for chapter in EXPECTED_CHAPTERS) or any(claim not in text for claim in EXPECTED_BLOCKED):
        raise P9R1GateError("P9-R1 thesis skeleton coverage drifted.")
    return plan


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify the P9-R1 thesis skeleton boundary.")
    parser.add_argument("--repository-root", type=Path, default=Path("."))
    args = parser.parse_args()
    plan = verify_p9_r1_gate(args.repository_root)
    print("p9_r1_gate=VERIFIED")
    print("traceability_assets=" + str(len(plan["traceability_assets"])) + "/4_PASS")
    print("next_milestone=" + str(plan["track"]["next_milestone"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
