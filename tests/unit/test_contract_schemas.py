import json
from pathlib import Path

import pytest

from src.dataset.contract import FEATURE_NAMES


@pytest.mark.parametrize(
    ("path", "expected_version"),
    [
        (
            Path(
                "schemas/"
                "experiment_manifest_v2.schema.json"
            ),
            2,
        ),
        (
            Path(
                "schemas/"
                "dataset_row_v1.schema.json"
            ),
            1,
        ),
        (
            Path(
                "schemas/evidence_v2.schema.json"
            ),
            2,
        ),
    ],
)
def test_formal_contract_schema(
    path: Path,
    expected_version: int,
) -> None:
    schema = json.loads(
        path.read_text(encoding="utf-8")
    )

    assert (
        schema["$schema"]
        == "https://json-schema.org/draft/2020-12/schema"
    )
    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False
    assert (
        schema["properties"]["schema_version"]["const"]
        == expected_version
    )

    if expected_version == 1:
        feature_contract = schema[
            "properties"
        ]["features"]

        assert set(feature_contract["required"]) == set(
            FEATURE_NAMES
        )
        assert set(
            feature_contract["properties"]
        ) == set(FEATURE_NAMES)
