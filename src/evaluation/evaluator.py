from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Required file does not exist: {path}")

    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, dict):
        raise ValueError(f"Expected a JSON object in: {path}")

    return data


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    path.write_text(
        json.dumps(data, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def evaluate_prediction(
    ground_truth: dict[str, Any],
    prediction_document: dict[str, Any],
) -> dict[str, Any]:
    expected_fault_type = ground_truth.get("fault_type")
    expected_no_fault = expected_fault_type in {
        "no_fault",
        "normal",
        "no_fault_detected",
    }

    expected_status = (
        "NO_FAULT_DETECTED"
        if expected_no_fault
        else "DIAGNOSIS_PRODUCED"
    )

    predicted_status = prediction_document.get("status")
    predicted_diagnosis = prediction_document.get("diagnosis")

    if not isinstance(predicted_diagnosis, dict):
        predicted_diagnosis = {}

    status_correct = predicted_status == expected_status

    if expected_no_fault:
        category_correct = predicted_diagnosis == {}
        fault_type_correct = predicted_diagnosis == {}
        location_correct = predicted_diagnosis == {}
        affected_prefix_correct = True
    else:
        category_correct = (
            predicted_diagnosis.get("category")
            == ground_truth.get("fault_category")
        )

        fault_type_correct = (
            predicted_diagnosis.get("fault_type")
            == ground_truth.get("fault_type")
        )

        location_correct = (
            predicted_diagnosis.get("location")
            == ground_truth.get("fault_location")
        )

        expected_prefix = ground_truth.get("affected_prefix")
        predicted_prefix = predicted_diagnosis.get("affected_prefix")

        affected_prefix_correct = (
            expected_prefix is None
            or predicted_prefix == expected_prefix
        )

    exact_match = all(
        [
            status_correct,
            category_correct,
            fault_type_correct,
            location_correct,
            affected_prefix_correct,
        ]
    )

    return {
        "schema_version": 1,
        "evaluated_at_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "method": prediction_document.get("method"),
        "expected": {
            "status": expected_status,
            "category": ground_truth.get("fault_category"),
            "fault_type": ground_truth.get("fault_type"),
            "location": ground_truth.get("fault_location"),
            "affected_prefix": ground_truth.get("affected_prefix"),
        },
        "predicted": {
            "status": predicted_status,
            "category": predicted_diagnosis.get("category"),
            "fault_type": predicted_diagnosis.get("fault_type"),
            "location": predicted_diagnosis.get("location"),
            "affected_prefix": predicted_diagnosis.get(
                "affected_prefix"
            ),
        },
        "metrics": {
            "status_correct": status_correct,
            "category_correct": category_correct,
            "fault_type_correct": fault_type_correct,
            "location_correct": location_correct,
            "affected_prefix_correct": affected_prefix_correct,
            "exact_match": exact_match,
        },
    }


def evaluate_experiment(
    experiment_directory: Path,
    method: str,
) -> dict[str, Any]:
    ground_truth_path = (
        experiment_directory / "ground_truth.json"
    )

    prediction_path = (
        experiment_directory
        / "diagnosis"
        / f"{method}.json"
    )

    output_path = (
        experiment_directory
        / "evaluation"
        / f"{method}.json"
    )

    ground_truth = read_json(ground_truth_path)
    prediction = read_json(prediction_path)

    result = evaluate_prediction(
        ground_truth=ground_truth,
        prediction_document=prediction,
    )

    result["experiment_directory"] = str(
        experiment_directory
    )

    write_json(output_path, result)

    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Compare a diagnostic prediction with experiment "
            "ground truth."
        )
    )

    parser.add_argument(
        "--experiment-dir",
        type=Path,
        required=True,
        help="Directory containing ground truth and diagnosis files.",
    )

    parser.add_argument(
        "--method",
        choices=[
            "rule_based",
            "ml",
            "hybrid",
        ],
        default="rule_based",
        help="Diagnostic method to evaluate.",
    )

    return parser


def main() -> int:
    arguments = build_parser().parse_args()

    try:
        result = evaluate_experiment(
            experiment_directory=arguments.experiment_dir,
            method=arguments.method,
        )
    except (
        FileNotFoundError,
        ValueError,
        json.JSONDecodeError,
    ) as error:
        print(f"[ERROR] {error}")
        return 1

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
