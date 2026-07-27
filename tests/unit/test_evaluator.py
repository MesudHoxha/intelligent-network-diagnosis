from src.evaluation.evaluator import evaluate_prediction


def test_correct_missing_route_prediction() -> None:
    ground_truth = {
        "fault_category": "routing",
        "fault_type": "missing_static_route",
        "fault_location": "r1",
        "affected_prefix": "10.10.2.0/24",
    }

    prediction = {
        "method": "rule_based",
        "status": "DIAGNOSIS_PRODUCED",
        "diagnosis": {
            "category": "routing",
            "fault_type": "missing_static_route",
            "location": "r1",
            "affected_prefix": "10.10.2.0/24",
        },
    }

    result = evaluate_prediction(
        ground_truth,
        prediction,
    )

    assert result["metrics"]["status_correct"] is True
    assert result["metrics"]["category_correct"] is True
    assert result["metrics"]["fault_type_correct"] is True
    assert result["metrics"]["location_correct"] is True
    assert result["metrics"]["exact_match"] is True


def test_wrong_fault_location_is_not_exact_match() -> None:
    ground_truth = {
        "fault_category": "routing",
        "fault_type": "missing_static_route",
        "fault_location": "r1",
        "affected_prefix": "10.10.2.0/24",
    }

    prediction = {
        "method": "rule_based",
        "status": "DIAGNOSIS_PRODUCED",
        "diagnosis": {
            "category": "routing",
            "fault_type": "missing_static_route",
            "location": "r2",
            "affected_prefix": "10.10.2.0/24",
        },
    }

    result = evaluate_prediction(
        ground_truth,
        prediction,
    )

    assert result["metrics"]["fault_type_correct"] is True
    assert result["metrics"]["location_correct"] is False
    assert result["metrics"]["exact_match"] is False
