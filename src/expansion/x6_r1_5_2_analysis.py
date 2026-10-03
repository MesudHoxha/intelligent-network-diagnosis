"""Deterministic full-denominator exploratory analysis."""
from __future__ import annotations

import numpy as np

from src.orchestration.x6_r1_5_1_contract import require
from src.orchestration.x6_r1_5_2_contract import METHOD_OUTPUTS


def metrics(slots, method):
    require(len(slots) == 40, "exact evaluation inventory")
    f1 = [row for row in slots if row["assignment"] == "F1"]; n0 = [row for row in slots if row["assignment"] == "N0"]
    require(len(f1) == len(n0) == 20, "evaluation class balance")
    def output(row):
        value = row.get("predictions", {}).get(method)
        require(value is None or value in METHOD_OUTPUTS, "method output")
        return value
    correct = lambda row: row.get("lifecycle_verified") is True and row.get("eligible",True) is True and output(row) == ("F1_PRESENT" if row["assignment"] == "F1" else "F1_ABSENT")
    sensitivity = sum(correct(row) for row in f1) / 20
    specificity = sum(correct(row) for row in n0) / 20
    result = {
        "assignment_accuracy": sum(correct(row) for row in slots) / 40,
        "assignment_sensitivity": sensitivity, "assignment_specificity": specificity,
        "balanced_accuracy": (sensitivity + specificity) / 2,
        "decisive_coverage": sum(output(row) in {"F1_PRESENT", "F1_ABSENT"} for row in slots) / 40,
        "abstention_rate": sum(output(row) == "ABSTAIN" for row in slots) / 40,
        "unavailable_rate": sum(output(row) == "UNAVAILABLE_EVIDENCE" or row.get("accounting_status") == "NO_PREDICTION_OPERATIONAL" for row in slots) / 40,
        "effectiveness_rate": sum(row.get("effectiveness") == "EFFECTIVE" for row in f1) / 20,
        "operational_yield": sum(row.get("target_verified") is True for row in slots) / 40,
    }
    effective = [row for row in f1 if row.get("effectiveness") == "EFFECTIVE"]
    clean = [row for row in n0 if row.get("clean_control") is True]
    result["secondary_effectiveness_qualified_sensitivity"] = "NOT_ESTIMABLE" if not effective else sum(output(row) == "F1_PRESENT" for row in effective) / len(effective)
    result["secondary_clean_control_specificity"] = "NOT_ESTIMABLE" if not clean else sum(output(row) == "F1_ABSENT" for row in clean) / len(clean)
    entered = [row for row in f1 if row.get("entered_mutation")]
    result["restoration_rate"] = "NOT_ESTIMABLE" if not entered else sum(row.get("restoration_confirmed") is True for row in entered) / len(entered)
    result["end_to_end_success"] = sum(correct(row) and row.get("intervention_valid") is True and row.get("lifecycle_verified") is True and row.get("restoration_confirmed") is True for row in slots) / 40
    return result


def evaluation_status(slots):
    """Accepted sufficiency gate; never changes fixed outcome denominators."""
    by_block = {}
    for row in slots:
        by_block.setdefault(row["block_id"], []).append(row)
    complete = sum(len(rows) == 2 and all(row.get("target_verified") is True for row in rows)
                   for rows in by_block.values())
    counts = {label: sum(row["assignment"] == label and row.get("eligible") is True
                         for row in slots) for label in ("N0", "F1")}
    return "EXPLORATORY_COMPLETE" if complete >= 18 and min(counts.values()) >= 18 else "INCONCLUSIVE_INCOMPLETE_EVALUATION"


def paired_bootstrap(slots, methods, *, replicates=10000):
    require(replicates == 10000, "accepted bootstrap replicate count")
    blocks = sorted({row["block_id"] for row in slots}); require(len(blocks) == 20, "twenty evaluation blocks")
    by_block = {block: [row for row in slots if row["block_id"] == block] for block in blocks}
    require(all(len(rows) == 2 and {r["assignment"] for r in rows} == {"N0", "F1"}
                for rows in by_block.values()), "paired block inventory")
    rng = np.random.Generator(np.random.PCG64(3705850974925186758))
    conditional_names = ("secondary_effectiveness_qualified_sensitivity", "secondary_clean_control_specificity", "restoration_rate")
    point={method:metrics(slots,method) for method in methods}
    names=tuple(point[methods[0]])
    samples={method:{name:[] for name in names} for method in methods}
    pairs=[(left,right) for i,left in enumerate(methods) for right in methods[i+1:]]
    differences={left+"-"+right:{name:[] for name in names} for left,right in pairs}
    for _ in range(replicates):
        chosen = rng.integers(0,20,size=20)
        rows=[row for index in chosen for row in by_block[blocks[int(index)]]]
        results={method:metrics(rows,method) for method in methods}
        for method in methods:
            for name,value in results[method].items():
                if value!="NOT_ESTIMABLE":samples[method][name].append(value)
        for left,right in pairs:
            for name in names:
                a,b=results[left][name],results[right][name]
                if a!="NOT_ESTIMABLE" and b!="NOT_ESTIMABLE":differences[left+"-"+right][name].append(a-b)
    def summary(values):
        return {"estimable_replicates":len(values),"not_estimable_replicates":replicates-len(values),
                "interval":[float(v) for v in np.quantile(values,[.025,.975],method="linear")] if len(values)>=9500 else "NOT_ESTIMABLE"}
    all_intervals={method:{name:summary(values) for name,values in data.items()} for method,data in samples.items()}
    all_differences={pair:{name:summary(values) for name,values in data.items()} for pair,data in differences.items()}
    return {"replicates":replicates,"seed_uint64":3705850974925186758,
            "method_intervals":{method:all_intervals[method]["assignment_accuracy"]["interval"] for method in methods},
            "difference_intervals":{pair:data["assignment_accuracy"]["interval"] for pair,data in all_differences.items()},
            "conditional_intervals":{method:{name:data[name] for name in conditional_names} for method,data in all_intervals.items()},
            "method_metric_intervals":all_intervals,"paired_metric_difference_intervals":all_differences}


def outcome_accounting(slots,methods):
    """Class/reason breakdowns use scheduled slots; metadata never reaches predictors."""
    output={}
    for method in methods:
        classes={}
        for label in ("N0","F1"):
            selected=[row for row in slots if row["assignment"]==label]
            reasons={}
            for row in selected:
                prediction=row.get("predictions",{}).get(method)
                if prediction=="UNAVAILABLE_EVIDENCE" or row.get("accounting_status")=="NO_PREDICTION_OPERATIONAL" or row.get("eligible") is False:
                    reason=row.get("terminal_status") or row.get("accounting_state") or "COMMON_CONTROL_OR_EVIDENCE_GATE"
                    reasons[reason]=reasons.get(reason,0)+1
            classes[label]={"denominator":len(selected),"abstention_count":sum(row.get("predictions",{}).get(method)=="ABSTAIN" for row in selected),
                            "unavailable_count":sum(reasons.values()),"unavailable_by_reason":reasons}
        entered=[row for row in slots if row["assignment"]=="F1" and row.get("entered_mutation") is True]
        classes["restoration"]={"denominator_entered_mutation":len(entered),"confirmed":sum(row.get("restoration_confirmed") is True for row in entered),
                                "unconfirmed_by_terminal":{reason:sum(row.get("restoration_confirmed") is not True and (row.get("terminal_status") or row.get("accounting_state") or "UNAVAILABLE")==reason for row in entered)
                                    for reason in sorted({row.get("terminal_status") or row.get("accounting_state") or "UNAVAILABLE" for row in entered if row.get("restoration_confirmed") is not True})},
                                "not_reached":20-len(entered)}
        output[method]=classes
    return output


def progression(slots,methods):
    result={}
    for method in methods:
        counts={label:sum(row.get("lifecycle_verified") is True and row.get("eligible",True) is True and row.get("predictions",{}).get(method)==("F1_PRESENT" if label=="F1" else "F1_ABSENT") for row in slots if row["assignment"]==label) for label in ("N0","F1")}
        decisive=sum(row.get("predictions",{}).get(method) in {"F1_PRESENT","F1_ABSENT"} for row in slots)
        result[method]={"F1_correct":counts["F1"],"N0_correct":counts["N0"],"decisive":decisive,
                        "eligible_for_separately_reviewed_confirmatory_proposal":counts["F1"]>=18 and counts["N0"]>=18 and decisive>=36,
                        "scientific_acceptance":False}
    return result


def analysis_document(slots):
    methods=["rule","ml","hybrid"]
    return {"metrics":{method:metrics(slots,method) for method in methods},"bootstrap":paired_bootstrap(slots,methods),
            "outcome_accounting":outcome_accounting(slots,methods),"progression":progression(slots,methods),
            "scientific_acceptance":False,"status":evaluation_status(slots)}
