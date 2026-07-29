import json
from copy import deepcopy
from pathlib import Path

import pytest
import yaml
from jsonschema import (
    Draft202012Validator,
    ValidationError,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def load_contracts() -> tuple[
    dict[str, object],
    dict[str, object],
]:
    schema = json.loads(
        (
            REPOSITORY_ROOT
            / "schemas"
            / "batch_plan_v1.schema.json"
        ).read_text(encoding="utf-8")
    )
    plan = yaml.safe_load(
        (
            REPOSITORY_ROOT
            / "plans"
            / "batches"
            / "B0_SMOKE_CANONICAL.yml"
        ).read_text(encoding="utf-8")
    )
    return schema, plan


def test_schema_accepts_canonical_smoke_plan(
) -> None:
    schema, plan = load_contracts()

    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(plan)


def test_schema_rejects_zero_repetitions(
) -> None:
    schema, plan = load_contracts()
    invalid_plan = deepcopy(plan)
    invalid_plan["batch"]["entries"][0][
        "repetitions"
    ] = 0

    with pytest.raises(ValidationError):
        Draft202012Validator(schema).validate(
            invalid_plan
        )


def test_schema_rejects_unknown_entry_property(
) -> None:
    schema, plan = load_contracts()
    invalid_plan = deepcopy(plan)
    invalid_plan["batch"]["entries"][0][
        "unexpected"
    ] = True

    with pytest.raises(ValidationError):
        Draft202012Validator(schema).validate(
            invalid_plan
        )


def test_schema_rejects_more_than_1000_entries(
) -> None:
    schema, plan = load_contracts()
    invalid_plan = deepcopy(plan)
    template = invalid_plan["batch"]["entries"][0]

    invalid_plan["batch"]["entries"] = [
        deepcopy(template)
        for _ in range(1001)
    ]

    with pytest.raises(ValidationError):
        Draft202012Validator(schema).validate(
            invalid_plan
        )
