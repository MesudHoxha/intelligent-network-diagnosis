"""Source and materialized-runtime gates for the single X6-R1 F1 pilot."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from src.contracts.expansion import validate_evidence_v4, validate_feature_vector_v2
from src.expansion.x6_r0_6_gate import verify_x6_r0_6
from src.expansion.x6_r1_runtime_context import load_x6_r1_runtime_context


ROOT = Path(__file__).resolve().parents[2]
PLAN = Path("plans/expansion/X6_R1_PACKET_LOSS_V1.json")
CORRECTED_TOPOLOGY_SHA256 = "9decd096606a7af5d6aa5a7de6c5d406c286e12094825cbc88b3fb59a2e37b14"


class X6R1GateError(ValueError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise X6R1GateError(message)


def _load(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), "JSON object required: " + str(path))
    return value


def verify_x6_r1_source(repository_root: Path = ROOT) -> dict[str, object]:
    root = Path(repository_root)
    # X6-R0.6 transitively verifies X6-R0.2 through X6-R0.5.  Invoking all
    # three entry points here repeats the schema-heavy predecessor chain.
    verify_x6_r0_6(root)
    context = load_x6_r1_runtime_context(root)
    plan = _load(root / PLAN)
    require(
        plan.get("release_id") == "X6_R1_PACKET_LOSS"
        and plan.get("source_boundary") == "430333f4cc78ebad5aa3bdc1a1e7a24b1d991c11"
        and plan.get("x6_r0_7_prerequisite") == "VERIFY_ONLY_HOST_SCH_NETEM_LOADED_BEFORE_DEPLOYMENT_NEVER_PRIVILEGED_MODULE_LOAD",
        "X6-R1 published source boundary drifted",
    )
    require(
        plan.get("corrected_topology") == {
            "path": "labs/topologies/x6_r1_packet_loss_r0_5/topology.clab.yml",
            "sha256": CORRECTED_TOPOLOGY_SHA256,
        }
        and context["topology"]["file"] == plan["corrected_topology"]["path"]
        and context["topology"]["sha256"] == CORRECTED_TOPOLOGY_SHA256,
        "X6-R1 must consume only the corrected X6-R0.5 topology",
    )
    require(
        plan.get("threshold_input_contract")
        == "raw baseline observations remain preserved; threshold derivation canonicalizes only its bound numeric inputs to frozen six-decimal ROUND_HALF_EVEN values before semantic validation and freeze"
        and plan.get("historical_pre_mutation_diagnostic_trees")
        == "PRESERVED_NON_AUTHORITATIVE; no mutation journal, qdisc change, fault window, Evidence v4, or diagnosis was produced",
        "X6-R1 threshold-input or diagnostic-tree boundary drifted",
    )
    routes = {row["node"]: row for row in context["topology"]["routes"] if row["node"] in {"hosta", "hostb"}}
    require(
        routes == {
            "hosta": {"node": "hosta", "destination": "10.61.3.2/32", "via": "10.61.1.1", "dev": "eth1", "src": "10.61.1.2"},
            "hostb": {"node": "hostb", "destination": "10.61.1.2/32", "via": "10.61.3.1", "dev": "eth1", "src": "10.61.3.2"},
        },
        "X6-R1 endpoint route overlay drifted",
    )
    require(
        context["topology"]["mutation_owner"] == {"node": "r2", "container": "clab-x6r1-r2", "interface": "eth2", "peer": "r3:eth1", "direction": "hosta_to_hostb"}
        and context["qdisc"]["loss_percent"] == "10.000000"
        and context["qdisc"]["netem"]["limit_packets"] == 1000
        and context["qdisc"]["pfifo"]["limit_packets"] == 1000
        and (context["windows"]["baseline"]["count"], context["windows"]["fault"]["count"], context["windows"]["restoration"]["count"]) == (10, 3, 3)
        and context["windows"]["allowed_start_skew_seconds"] == "0.250"
        and context["effectiveness"]["acceptance_drop_count_inclusive"] == [6, 25]
        and context["rule"]["rule_id"] == "R_X6_PERFORMANCE_001",
        "X6-R1 inherited frozen F1 values drifted",
    )
    bindings = plan.get("source_bindings")
    require(isinstance(bindings, list) and len(bindings) == 12, "X6-R1 requires twelve source bindings")
    for row in bindings:
        require(isinstance(row, dict) and isinstance(row.get("path"), str) and isinstance(row.get("sha256"), str), "X6-R1 source binding malformed")
        path = root / row["path"]
        require(path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == row["sha256"], "X6-R1 source binding drifted: " + row["path"])
    return plan


def verify_x6_r1_runtime(experiment_root: Path, repository_root: Path = ROOT) -> dict[str, object]:
    verify_x6_r1_source(repository_root)
    root = Path(experiment_root)
    manifest = _load(root / "manifest.json")
    effect = _load(root / "mutation/mutation_effectiveness.json")
    diagnosis = _load(root / "diagnosis/diagnosis_result_v2.json")
    predicates = _load(root / "diagnosis/conditional_predicates.json")
    restoration = _load(root / "mutation/restoration_record.json")
    replay = _load(root / "mutation/standalone_replay.json")
    hashes = _load(root / "validation/raw_hashes.json")
    evidence = _load(root / "parsed/evidence_v4.json")
    vector = _load(root / "parsed/feature_vector_v2.json")
    catalog = _load(repository_root / "plans/expansion/X1_FEATURE_CATALOG_V1.json")
    validate_evidence_v4(evidence, catalog, repository_root=repository_root)
    validate_feature_vector_v2(vector, catalog, repository_root=repository_root)
    require(manifest.get("status") == "AUTHORITATIVE" and effect.get("status") == "MUTATION_EFFECTIVE" and 6 <= effect.get("lost_packet_count", -1) <= 25 and effect.get("pfifo_drop_delta") == 0, "X6-R1 effectiveness invalid")
    require(diagnosis.get("status") == "diagnosed" and diagnosis.get("explanation_refs") == ["rule:R_X6_PERFORMANCE_001"] and all(predicates.get("predicates", {}).values()), "X6-R1 diagnosis/signature invalid")
    require(restoration.get("status") == "RESTORATION_CONFIRMED" and replay.get("status") == "STANDALONE_REPLAY_CONFIRMED", "X6-R1 restoration invalid")
    artifacts = hashes.get("artifacts", {})
    require(isinstance(artifacts, dict) and len(artifacts) == 17, "X6-R1 requires sixteen raw windows plus aggregate provenance")
    for name, digest in artifacts.items():
        require(hashlib.sha256((root / name).read_bytes()).hexdigest() == digest, "X6-R1 raw hash drifted: " + name)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, default=ROOT)
    parser.add_argument("--experiment-root", type=Path)
    args = parser.parse_args()
    plan = verify_x6_r1_source(args.repository_root)
    print("x6_r1_source=VERIFIED")
    print("source_bindings=" + str(len(plan["source_bindings"])) + "/12_HASH_BOUND_PASS")
    if args.experiment_root:
        verify_x6_r1_runtime(args.experiment_root, args.repository_root)
        print("x6_r1_runtime=AUTHORITATIVE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
