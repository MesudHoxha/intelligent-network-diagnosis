"""Leakage-safe reconstruction of one attempt-level target row."""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_EVEN

from src.orchestration.x6_r1_5_1_contract import require
from src.orchestration.x6_r1_5_3_contract import FEATURES
from src.collection.x6_performance_collector import exact_fault_hierarchy,qdisc_dropped

Q = Decimal("0.000001")


def finite(value, name):
    try: result = Decimal(str(value))
    except Exception as error: raise ValueError(name + " is not decimal") from error
    require(result.is_finite(), name + " is non-finite")
    return result


def six(value, name):
    return finite(value, name).quantize(Q, rounding=ROUND_HALF_EVEN)


def nearest_rank_p95(values):
    rows = sorted(finite(value, "individual RTT reply") for value in values)
    require(rows, "individual RTT replies absent")
    rank = (95 * len(rows) + 99) // 100
    return rows[rank - 1]


def aggregate_target(windows, replies):
    require(len(windows) == 3, "exactly three target windows required")
    for row in windows:
        require(set(FEATURES).issubset(row), "target feature absent")
    loss = sum((six(row["packet_loss_ratio"], "packet loss window") for row in windows), Decimal(0)) / Decimal(3)
    throughput = sorted(six(row["throughput_mbps"], "throughput window") for row in windows)[1]
    utilization = sorted(six(row["interface_utilization_ratio"], "utilization window") for row in windows)[1]
    values = {
        "packet_loss_ratio": loss.quantize(Q, rounding=ROUND_HALF_EVEN),
        "round_trip_latency_ms_p95": nearest_rank_p95(replies).quantize(Q, rounding=ROUND_HALF_EVEN),
        "throughput_mbps": throughput.quantize(Q, rounding=ROUND_HALF_EVEN),
        "interface_utilization_ratio": utilization.quantize(Q, rounding=ROUND_HALF_EVEN),
    }
    return {name: format(values[name], ".6f") for name in FEATURES}


def reconstruct_effectiveness(slot,windows,raw_rows):
    require(len(windows)==3,"effectiveness target cardinality")
    if slot["assignment"]=="N0":
        require(not any(row.get("phase") in {"mutation","restoration"} or row.get("name","").startswith("mutation_") for row in raw_rows),"N0 mutation evidence")
        return "CLEAN_CONTROL"
    qdisc=[row for row in raw_rows if row.get("window") in {"F01","F02","F03"} and row.get("name")=="qdisc"]
    require(len(qdisc)==6 and all(exact_fault_hierarchy(row) for row in qdisc),"F1 hierarchy evidence")
    deltas=[]
    for index in range(0,6,2):
        before=qdisc_dropped(qdisc[index],kind="netem",handle="10:"); after=qdisc_dropped(qdisc[index+1],kind="netem",handle="10:")
        require(before is not None and after is not None and after>=before,"F1 netem counter continuity"); deltas.append(after-before)
    loss=sum((six(row["measurements"]["packet_loss_ratio"],"packet loss window") for row in windows),Decimal(0))/Decimal(3)
    lost=int((loss*Decimal(150)).quantize(Decimal("1"),rounding=ROUND_HALF_EVEN))
    pfifo=sum(int(row["measurements"]["queue_drop_count"]) for row in windows)
    return "EFFECTIVE" if 6<=lost<=25 and sum(deltas)>=0 and pfifo==0 else "INEFFECTIVE"


def build_row(*, slot, predictors, controls, effectiveness, provenance):
    require(tuple(predictors) == FEATURES, "predictor order")
    require(controls == {"queue_drop_count": 0, "rate_limit_detected": False}, "common eligibility controls")
    require(slot["assignment"] in {"N0", "F1"}, "assignment")
    for key in predictors: six(predictors[key], key)
    return {
        "schema_version": 1,
        "slot_identity": {k: slot[k] for k in ("slot_id", "block_id", "stage", "position")},
        "predictors": {k: predictors[k] for k in FEATURES},
        "controls": controls,
        "effectiveness": effectiveness,
        "provenance": provenance,
        "ground_truth": {"assignment": slot["assignment"]},
        "assignment": slot["assignment"],
        "block_id": slot["block_id"],
        "target_verified": True,
        "entered_mutation": slot["assignment"] == "F1",
        "clean_control": slot["assignment"] == "N0" and effectiveness == "CLEAN_CONTROL",
        "intervention_valid": effectiveness in {"EFFECTIVE", "CLEAN_CONTROL"},
        "restoration_confirmed": True,
        "lifecycle_verified": True,
        "eligible": True,
    }


def model_matrix(rows):
    matrix, labels = [], []
    for row in rows:
        require(row["slot_identity"]["stage"] == "DEVELOPMENT" and row["slot_identity"]["block_id"].startswith("DEV_"), "evaluation row in development fitting")
        require(row["controls"] == {"queue_drop_count": 0, "rate_limit_detected": False}, "ineligible row")
        require(set(row["predictors"]) == set(FEATURES), "predictor boundary")
        matrix.append([float(six(row["predictors"][name], name)) for name in FEATURES])
        labels.append(1 if row["ground_truth"]["assignment"] == "F1" else 0)
    return matrix, labels


def historical_rule(predictors, common_controls, manifest):
    """Unchanged historical six-predicate comparator on reconstructed inputs."""
    bounds = {row["feature_id"]: row for row in manifest["features"]}
    values = {name: Decimal(predictors[name]) for name in FEATURES}
    require(all(value.is_finite() for value in values.values()), "non-finite rule input")
    require(type(common_controls["queue_drop_count"]) is int and
            type(common_controls["rate_limit_detected"]) is bool, "rule control types")
    predicates = (
        values["packet_loss_ratio"] > Decimal(bounds["packet_loss_ratio"]["upper_threshold"]),
        values["round_trip_latency_ms_p95"] <= Decimal(bounds["round_trip_latency_ms_p95"]["upper_threshold"]),
        values["throughput_mbps"] >= Decimal(bounds["throughput_mbps"]["lower_threshold"]),
        values["interface_utilization_ratio"] <= Decimal(bounds["interface_utilization_ratio"]["upper_threshold"]),
        common_controls["queue_drop_count"] == 0,
        common_controls["rate_limit_detected"] is False,
    )
    return {"output": "F1_PRESENT" if all(predicates) else "ABSTAIN", "predicates": list(predicates)}


def accounting_row(slot,events,verified):
    """Metadata from verified accounting, never a predictor or routing input."""
    import copy
    value=copy.deepcopy(verified.get("row",verified.get("accounting_row")))
    if value is None:
        value={"block_id":slot["block_id"],"assignment":slot["assignment"],"accounting_status":"NO_PREDICTION_OPERATIONAL","predictions":{}}
        outcomes=verified.get("outcomes",{})
        require(set(outcomes)<= {"target_verified","entered_mutation","restoration_confirmed","lifecycle_verified","eligible"} and all(type(v) is bool for v in outcomes.values()),"partial accounting outcome types")
        value.update(outcomes)
    value["accounting_state"]=events[-1]["state"]
    value["terminal_status"]=verified.get("terminal","SLOT_COMPLETE" if "row" in verified else None)
    value["completed_windows"]=verified.get("completed_windows",[*(f"B{i:02d}" for i in range(1,11)),*(f"F{i:02d}" for i in range(1,4)),*(f"R{i:02d}" for i in range(1,4))] if "row" in verified else [])
    return value
