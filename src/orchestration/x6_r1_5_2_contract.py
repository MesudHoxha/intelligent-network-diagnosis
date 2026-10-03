"""Frozen source contract for the exploratory N0/F1 campaign successor."""
from __future__ import annotations

import json
import re
from pathlib import Path

from src.orchestration.x6_r1_5_1_contract import canonical, canonical_location, digest, require

RELEASE = "X6_R1_5_2_EXPLORATORY_F1_CAMPAIGN_SOURCE_ONLY"
PREDECESSOR = "babde86fd863d105b30262d205ced09995251515"
CAMPAIGN_ID = "X6_F1_EXPLORATORY_BINARY_V1"
INVENTORY_SHA256 = "c1ff4d276705936111b12c918cad7a387d44369859b828ca13c7e28a5dba2c2c"
CONTRACT_PROPOSAL_SHA256 = "2e6ea92cb329088c981f03fdebb4a206def53eb8a19321458e531b9641e0e9a3"
FEATURES = ("packet_loss_ratio", "round_trip_latency_ms_p95", "throughput_mbps", "interface_utilization_ratio")
METHOD_OUTPUTS = ("F1_PRESENT", "F1_ABSENT", "ABSTAIN", "UNAVAILABLE_EVIDENCE")
ASSIGNMENTS = ("N0", "F1")
ACTIONS = {
    "freeze-development": "X6_R1_5_2_DEVELOPMENT_FREEZE_MODEL_FIT_AUTHORIZATION_V1",
    "evaluate": "X6_R1_5_2_FINAL_EVALUATION_ANALYSIS_AUTHORIZATION_V1",
    "record-not-run": "X6_R1_5_2_NOT_RUN_ACCOUNTING_AUTHORIZATION_V1",
}
NOT_RUN_REASONS = (
    "NOT_RUN_OPERATIONAL_FAILURE", "NOT_RUN_ENVIRONMENT_DRIFT",
    "NOT_RUN_DEVELOPMENT_INCONCLUSIVE", "NOT_RUN_UNUSABLE_MODEL",
)
SLOT_FINAL = {
    "TERMINAL", "REJECTED_SPENT", "NOT_RUN_OPERATIONAL_FAILURE",
    "NOT_RUN_ENVIRONMENT_DRIFT", "NOT_RUN_DEVELOPMENT_INCONCLUSIVE",
    "NOT_RUN_UNUSABLE_MODEL",
}
SLOT_TRANSITIONS = {
    "SCHEDULED": {"RESERVED_UNDECIDED", "NOT_RUN_OPERATIONAL_FAILURE", "NOT_RUN_ENVIRONMENT_DRIFT", "NOT_RUN_DEVELOPMENT_INCONCLUSIVE", "NOT_RUN_UNUSABLE_MODEL"},
    "RESERVED_UNDECIDED": {"REJECTED_SPENT", "ADMITTED"},
    "ADMITTED": {"CONSUMED", "TERMINAL"},
    "CONSUMED": {"RUNNING", "TERMINAL"},
    "RUNNING": {"TERMINAL"},
    **{name: set() for name in SLOT_FINAL},
}
ACTION_FINAL = {"PUBLISHED", "REJECTED_SPENT", "FAILED_SPENT", "INTERRUPTED_SPENT", "INTEGRITY_UNRESOLVED"}
ACTION_TRANSITIONS = {
    "AUTHORIZED_UNRESERVED": {"RESERVED_UNDECIDED"},
    "RESERVED_UNDECIDED": {"REJECTED_SPENT", "ADMITTED"},
    "ADMITTED": {"CONSUMED", "INTERRUPTED_SPENT", "INTEGRITY_UNRESOLVED"},
    "CONSUMED": {"MATERIALIZING", "FAILED_SPENT", "INTERRUPTED_SPENT", "INTEGRITY_UNRESOLVED"},
    "MATERIALIZING": {"PUBLISHED", "FAILED_SPENT", "INTERRUPTED_SPENT", "INTEGRITY_UNRESOLVED"},
    **{name: set() for name in ACTION_FINAL},
}


def accepted_inventory():
    """Load the accepted schedule from its reviewed bytes and derive all slots."""
    proposal = Path(__file__).resolve().parents[2] / "plans/expansion/X6_PROSPECTIVE_F1_SUCCESSOR_STUDY_DESIGN_PROPOSAL_V1.json"
    value = json.loads(proposal.read_text())
    inventory = value["partition_and_independence"]["scheduled_inventory"]
    require(digest(canonical(inventory)) == INVENTORY_SHA256, "accepted inventory bytes")
    slots = []
    for block in inventory["blocks"]:
        for offset, assignment in enumerate(block["within_block_order"], 1):
            position = f"S{offset:02d}"
            prefix = "DEV" if block["stage"] == "DEVELOPMENT" else "EVAL"
            slot_id = f"X6_F1_EXP_V1_{prefix}_B{block['block_id'][-2:]}_{position}_{assignment}"
            slots.append({"slot_id": slot_id, "block_id": block["block_id"], "stage": block["stage"],
                          "position": position, "assignment": assignment,
                          "run_id": slot_id.lower().replace("_", "-")})
    require(len(slots) == 100 and len({row["slot_id"] for row in slots}) == 100, "accepted slot inventory")
    return {"schedule": inventory, "sha256": INVENTORY_SHA256, "slots": slots}


def require_accepted_slot(slot):
    matches = [row for row in accepted_inventory()["slots"] if row["slot_id"] == slot.get("slot_id")]
    require(len(matches) == 1 and matches[0] == slot, "slot is not the accepted inventory member")
    return slot


def authorization_digest(value):
    unsigned = dict(value)
    claimed = unsigned.pop("authorization_sha256", None)
    require(isinstance(claimed, str), "authorization digest absent")
    require(claimed == digest(canonical(unsigned)), "authorization digest mismatch")
    return claimed


def validate_slot_authorization(value, *, campaign_root, slot, source, now_ns, boot_id):
    authorization_digest(value)
    required = {
        "schema_version", "record_kind", "authorization_id", "authorization_sha256",
        "campaign_id", "campaign_contract_sha256", "inventory_sha256", "slot",
        "run_id", "output_root", "source", "issued_ns", "expires_ns", "boot_id",
        "scope", "artifact_inventory", "source_test_only", "runtime_image", "runtime_bindings", "epoch", "development_freeze_sha256",
    }
    require(set(value) == required and type(value["source_test_only"]) is bool, "slot authorization schema")
    require(value["schema_version"] == 1 and value["record_kind"] == "X6_R1_5_2_CAMPAIGN_SLOT_AUTHORIZATION_V1", "slot authorization kind")
    require(value["campaign_id"] == CAMPAIGN_ID and value["campaign_contract_sha256"] == CONTRACT_PROPOSAL_SHA256 and value["inventory_sha256"] == INVENTORY_SHA256, "campaign authorization binding")
    require_accepted_slot(slot)
    require(value["slot"] == slot and slot["assignment"] in ASSIGNMENTS and value["run_id"]==slot["run_id"], "slot authorization binding")
    require(re.fullmatch(r"[A-Z0-9_]{8,160}", value["authorization_id"]) is not None, "authorization identity")
    expected_root = canonical_location(str(Path(campaign_root) / "slots" / value["run_id"]))
    require(canonical_location(value["output_root"]) == expected_root, "slot output binding")
    require(value["source"] == source, "slot source binding")
    from src.orchestration.x6_r1_5_1_contract import ACCEPTED_IMAGE
    require(value["runtime_image"] == ACCEPTED_IMAGE and value["runtime_bindings"] == runtime_bindings(), "slot topology/image/command/threshold binding")
    require(isinstance(value["epoch"], dict) and set(value["epoch"]) == {"path", "sha256", "epoch_id"}, "slot epoch binding")
    require(value["development_freeze_sha256"] is None if slot["stage"] == "DEVELOPMENT" else
            isinstance(value["development_freeze_sha256"], str) and len(value["development_freeze_sha256"]) == 64,
            "slot development freeze binding")
    require(value["scope"] == ("N0_CONTROL" if slot["assignment"] == "N0" else "F1_PACKET_LOSS_SINGLE_FAULT"), "slot scope")
    require(type(value["issued_ns"]) is int and type(value["expires_ns"]) is int and value["issued_ns"] <= now_ns <= value["expires_ns"], "slot authorization validity")
    require(value["boot_id"] == boot_id, "slot authorization boot")
    require(value["artifact_inventory"]==["raw","parsed","state","terminal"], "slot artifact inventory")
    return value


def validate_action_authorization(value, *, action, campaign_root, source, input_inventory_sha256, prior_state_sha256, now_ns, boot_id):
    authorization_digest(value)
    require(action in ACTIONS and value.get("record_kind") == ACTIONS[action], "action authorization kind")
    required = {
        "schema_version", "record_kind", "authorization_id", "authorization_sha256",
        "campaign_id", "campaign_contract_sha256", "inventory_sha256", "action",
        "stage", "campaign_root", "canonical_output", "source", "input_inventory_sha256",
        "prior_state_sha256", "issued_ns", "expires_ns", "boot_id", "source_test_only",
    }
    if action == "record-not-run":
        required |= {"target_slot_ids", "expected_accounting_heads", "epoch", "reason", "supporting_evidence_sha256"}
    require(set(value) == required and value["schema_version"] == 1, "action authorization schema")
    require(type(value["source_test_only"]) is bool,"action synthetic marker type")
    require(isinstance(value["authorization_id"],str) and re.fullmatch(r"[A-Z0-9_]{8,160}",value["authorization_id"]) is not None,"action authorization identity")
    require(value["campaign_id"] == CAMPAIGN_ID and value["campaign_contract_sha256"] == CONTRACT_PROPOSAL_SHA256 and value["inventory_sha256"] == INVENTORY_SHA256, "action campaign binding")
    require(value["action"] == action and value["source"] == source, "action/source binding")
    expected_stage = "DEVELOPMENT" if action == "freeze-development" else ("EVALUATION" if action == "evaluate" else "ACCOUNTING")
    require(value["stage"] == expected_stage, "action stage binding")
    require(canonical_location(value["campaign_root"]) == canonical_location(str(campaign_root)), "action campaign root")
    expected = Path(campaign_root) / ("development-freeze-v1" if action == "freeze-development" else ("final-analysis-v1" if action == "evaluate" else f"accounting-actions/not-run/{value['authorization_id']}"))
    require(canonical_location(value["canonical_output"]) == canonical_location(str(expected)), "action output binding")
    require(value["input_inventory_sha256"] == input_inventory_sha256 and value["prior_state_sha256"] == prior_state_sha256, "action input/prior-state binding")
    require(type(value["issued_ns"]) is int and type(value["expires_ns"]) is int and value["issued_ns"] <= now_ns <= value["expires_ns"], "action authorization validity")
    require(value["boot_id"] == boot_id, "action authorization boot")
    if action == "record-not-run":
        require(value["reason"] in NOT_RUN_REASONS, "NOT_RUN reason")
        require(isinstance(value["target_slot_ids"], list) and value["target_slot_ids"] and len(value["target_slot_ids"]) <= 100, "NOT_RUN bounded targets")
        require(len(value["target_slot_ids"]) == len(set(value["target_slot_ids"])), "NOT_RUN duplicate target")
        accepted = {row["slot_id"] for row in accepted_inventory()["slots"]}
        require(set(value["target_slot_ids"]) <= accepted, "NOT_RUN target outside inventory")
        require(value["expected_accounting_heads"] == {slot_id: "SCHEDULED" for slot_id in value["target_slot_ids"]}, "NOT_RUN expected heads")
        require(isinstance(value["epoch"], dict) and value["epoch"], "NOT_RUN epoch binding")
        require(isinstance(value["supporting_evidence_sha256"], str) and len(value["supporting_evidence_sha256"]) == 64, "NOT_RUN evidence binding")
    return value


def validate_transition(current, target, *, action=False):
    table = ACTION_TRANSITIONS if action else SLOT_TRANSITIONS
    require(current in table and target in table[current], f"illegal transition {current}->{target}")
    return target


def runtime_bindings():
    """Accepted immutable runtime context, never inferred from matching tags."""
    from src.orchestration.x6_r1_5_1_contract import ROOT, TOPOLOGY, CONTEXT, BOOTSTRAP, ACCEPTED_IMAGE, SCHEDULE, MANIFEST_EMBEDDED_SHA256
    from src.orchestration.x6_r1_5_1_observations import catalog
    return {"topology": {"path": TOPOLOGY, "sha256": digest((ROOT/TOPOLOGY).read_bytes())},
            "context_sha256": digest((ROOT/CONTEXT).read_bytes()),
            "bootstrap_sha256": digest((ROOT/BOOTSTRAP).read_bytes()),
            "image": ACCEPTED_IMAGE, "schedule": SCHEDULE,
            "manifest_sha256": MANIFEST_EMBEDDED_SHA256, "command_catalog_sha256": digest(canonical(campaign_catalog()))}


def validate_epoch(path, campaign_root, *, allow_observed_drift=False):
    """Reconstruct epoch fields from bound readiness commands, not status flags."""
    from src.orchestration.x6_r1_5_1_contract import load, canonical_location, ACCEPTED_IMAGE
    from src.orchestration.x6_r1_5_1_durable import records
    from src.orchestration.x6_r1_5_1_observations import catalog, host_state, success
    value=load(path)
    required={"schema_version","campaign_id","campaign_root","epoch_id","stage","source","boot_id",
              "runtime_bindings","host_identity","readiness_root","kernel_and_module","tools","readiness_observation_hashes"}
    require(set(value)==required and value["schema_version"]==1 and value["campaign_id"]==CAMPAIGN_ID,"canonical epoch schema")
    require(value["campaign_root"]==str(canonical_location(str(Path(campaign_root).resolve()))),"epoch campaign binding")
    unsigned=dict(value); epoch_id=unsigned.pop("epoch_id")
    require(epoch_id==digest(canonical(unsigned)),"canonical epoch identity")
    from src.expansion.x6_r1_5_2_materialized_verifier import _verify_source_snapshot
    _verify_source_snapshot(value["source"])
    accepted_bindings=runtime_bindings()
    observed_bindings=dict(value["runtime_bindings"])
    require(set(observed_bindings)==set(accepted_bindings),"epoch runtime binding schema")
    if allow_observed_drift:observed_bindings["image"]=accepted_bindings["image"]
    require(observed_bindings==accepted_bindings,"epoch runtime binding")
    evidence_root=canonical_location(value["readiness_root"])
    raw=records(evidence_root,campaign_catalog())
    require(raw and all(row["started"]["boot_id"]==value["boot_id"] for row in raw),"epoch raw boot binding")
    names=("kernel","kernel_config","module","module_provenance","python","ip","tc","ethtool","docker","containerlab","git","image")
    observed={}
    for name in names:
        selected=[row for row in raw if row["name"]==name]
        require(len(selected)==1,"epoch provenance cardinality")
        success(selected[0]); observed[name]=selected[0]
    require(observed["git"]["stdout"].splitlines()==[value["source"]["git_commit"],value["source"]["git_tree"]],"epoch observed source")
    require(allow_observed_drift or "CONFIG_NET_SCH_NETEM=m" in observed["kernel_config"]["stdout"] and
            "sch_netem" in observed["module"]["stdout"] and
            observed["kernel"]["stdout"].strip() in observed["module_provenance"]["stdout"],"epoch module provenance")
    image=json.loads(observed["image"]["stdout"])
    require(len(image)==1 and {k:image[0][k] for k in ACCEPTED_IMAGE}==value["runtime_bindings"]["image"],"epoch observed image identity")
    if not allow_observed_drift: require(value["runtime_bindings"]["image"]==ACCEPTED_IMAGE,"epoch accepted image identity")
    require(value["kernel_and_module"]=={n:observed[n]["stdout"] for n in names[:4]},"epoch kernel fields")
    require(value["tools"]=={n:observed[n]["stdout"] for n in names[4:10]},"epoch tool fields")
    require(value["readiness_observation_hashes"]==[digest(canonical(row)) for row in raw],"epoch raw inventory")
    before=[row for row in raw if row["phase"]=="host_before"]
    host=host_state(before)
    require(allow_observed_drift or not host["containers"] and not host["namespaces"],"epoch conflicting experiment resources")
    identity_rows=[row for row in raw if row["name"]=="host_identity"]
    require(len(identity_rows)==1,"epoch host identity observation")
    success(identity_rows[0])
    require(value["host_identity"]==identity_rows[0]["stdout"].strip() and value["host_identity"],"epoch host identity contradiction")
    return value


def campaign_catalog():
    from src.orchestration.x6_r1_5_1_observations import catalog
    return {**catalog(), "host_identity": (["cat", "/etc/machine-id"], 5)}


def observe_epoch(campaign_root,stage,source,readiness_root,*,simulation=False):
    """Read-only readiness observations; no deployment, reservation or slot root."""
    from src.orchestration.x6_r1_5_1_contract import load,ACCEPTED_IMAGE,current_boot_id
    from src.orchestration.x6_r1_5_1_durable import Recorder,records,save
    from src.orchestration.x6_r1_5_1_production_path import preflight
    readiness_root=Path(readiness_root)
    require(not readiness_root.exists(),"readiness observation root already exists")
    save(readiness_root/"state/authorization.json",{"runtime_image":ACCEPTED_IMAGE},exclusive=True)
    recorder=Recorder(readiness_root,campaign_catalog(),simulation=simulation)
    preflight(recorder,source)
    recorder.capture("host_identity","provenance")
    raw=records(readiness_root,campaign_catalog())
    by_name={row["name"]:row for row in raw}
    value={"schema_version":1,"campaign_id":CAMPAIGN_ID,"campaign_root":str(Path(campaign_root).resolve()),
           "stage":stage,"source":source,"boot_id":current_boot_id(),"runtime_bindings":runtime_bindings(),
           "host_identity":by_name["host_identity"]["stdout"].strip(),"readiness_root":str(readiness_root.resolve()),
           "kernel_and_module":{n:by_name[n]["stdout"] for n in ("kernel","kernel_config","module","module_provenance")},
           "tools":{n:by_name[n]["stdout"] for n in ("python","ip","tc","ethtool","docker","containerlab")},
           "readiness_observation_hashes":[digest(canonical(row)) for row in raw]}
    value["epoch_id"]=digest(canonical(value))
    path=readiness_root/"epoch.json";save(path,value,exclusive=True)
    validate_epoch(path,campaign_root)
    return path,value


def epoch_context(value):
    return {name:value[name] for name in ("stage","source","boot_id","runtime_bindings","host_identity","kernel_and_module","tools")}
