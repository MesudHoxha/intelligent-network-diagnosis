from __future__ import annotations

import csv
import json
from pathlib import Path

from src.phase9.gate import verify_gate as verify_p9_r0_gate
from src.phase9.p9_r1_gate import verify_p9_r1_gate


ROOT = Path(__file__).resolve().parents[2]
PLAN = ROOT / "plans/phase9/P9_R1_THESIS_SKELETON_TRACEABILITY_V1.json"


def test_p9_r1_hash_binds_the_published_x4_r6_source_boundary() -> None:
    plan = verify_p9_r1_gate(ROOT)

    assert plan["source_boundary"]["parent_commit"] == "50f0624679d7b1577d88d66ba87eb1c7390e80f0"
    assert plan["track"]["current_release"] == "P9_R1_THESIS_SKELETON_AND_TRACEABILITY_MATRIX"
    assert plan["track"]["next_milestone"] == "P9_R2_CONTROLLED_CHAPTER_DRAFTING"
    assert len(plan["source_bindings"]) == 9


def test_p9_r1_retains_all_phase8_claim_limits_and_guards() -> None:
    parent = verify_p9_r0_gate(ROOT)
    plan = verify_p9_r1_gate(ROOT)
    assets = {item["asset_id"]: ROOT / item["path"] for item in plan["traceability_assets"]}

    with assets["P9R1T02"].open(encoding="utf-8", newline="") as stream:
        claims = {row["claim_id"]: row["required_limit"] for row in csv.DictReader(stream)}
    with assets["P9R1T03"].open(encoding="utf-8", newline="") as stream:
        blocked = list(csv.DictReader(stream))

    assert claims == {claim["claim_id"]: claim["limit"] for claim in parent["claim_boundary"]["supported_claims"]}
    assert [row["claim_id"] for row in blocked] == [f"B0{number}" for number in range(1, 9)]
    assert {row["guard"] for row in blocked} == {"PROHIBITED_NOT_DRAFTABLE"}


def test_p9_r1_skeleton_covers_front_matter_chapters_and_phase8_locations() -> None:
    plan = verify_p9_r1_gate(ROOT)
    skeleton = (ROOT / plan["thesis_skeleton"]["path"]).read_text(encoding="utf-8")
    placement = next(item for item in plan["traceability_assets"] if item["asset_id"] == "P9R1T04")

    with (ROOT / placement["path"]).open(encoding="utf-8", newline="") as stream:
        locations = {row["asset_id"]: row["chapter_id"] for row in csv.DictReader(stream)}

    assert "## Front matter" in skeleton
    assert all(f"## CH0{number}" in skeleton for number in range(1, 8))
    assert locations == {"T01": "CH03", "T02": "CH05", "T03": "CH06", "F01": "CH05", "F02": "CH05"}
    assert "100.00%" not in skeleton and "79.17%" not in skeleton


def test_p9_r1_authorizes_structure_only() -> None:
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    enabled = {name for name, value in plan["authorization"].items() if value is True}

    assert enabled == {"chapter_skeleton", "front_matter_placeholders", "traceability_matrix"}
    assert all(value is False for name, value in plan["authorization"].items() if name not in enabled)
