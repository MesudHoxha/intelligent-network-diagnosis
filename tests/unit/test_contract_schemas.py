import json
from pathlib import Path

import pytest

from src.dataset.contract import (
    FEATURE_NAMES_V1,
    FEATURE_NAMES_V2,
)


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
                "schemas/"
                "dataset_row_v2.schema.json"
            ),
            2,
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

    if "dataset_row" in path.name:
        feature_contract = schema[
            "properties"
        ]["features"]
        expected_features = (
            FEATURE_NAMES_V1
            if expected_version == 1
            else FEATURE_NAMES_V2
        )

        assert set(feature_contract["required"]) == set(
            expected_features
        )
        assert set(
            feature_contract["properties"]
        ) == set(expected_features)
