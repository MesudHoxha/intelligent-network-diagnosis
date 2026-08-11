import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from src.phase6.contracts import apply_method_input_mask
from src.phase6.methods import rule_prediction
from tests.unit.p6_r6_fixtures import method_input


SCHEMAS = (
    "phase6_method_input_v1.schema.json",
    "phase6_method_prediction_v1.schema.json",
    "phase6_method_freeze_v1.schema.json",
    "phase6_method_report_v1.schema.json",
)


@pytest.mark.parametrize("schema_name", SCHEMAS)
def test_phase6_r6_schema_is_valid(schema_name: str) -> None:
    schema = json.loads((Path("schemas") / schema_name).read_text())
    Draft202012Validator.check_schema(schema)


def test_input_and_prediction_match_json_schemas() -> None:
    method_schema = json.loads(
        Path("schemas/phase6_method_input_v1.schema.json").read_text()
    )
    prediction_schema = json.loads(
        Path("schemas/phase6_method_prediction_v1.schema.json").read_text()
    )
    value = apply_method_input_mask(method_input("acl_block"), "mask_policy_state")
    prediction = rule_prediction(value)

    Draft202012Validator(method_schema).validate(value)
    Draft202012Validator(prediction_schema).validate(prediction)
