from pathlib import Path

import pytest

from src.fault_injection.common import FaultInjectionError
from src.fault_injection.missing_route import inject_missing_route
from src.fault_injection.registry import (
    FAULT_INJECTORS,
    inject_fault,
)


def test_missing_route_injector_is_registered() -> None:
    assert (
        FAULT_INJECTORS["missing_static_route"]
        is inject_missing_route
    )


def test_inject_fault_dispatches_by_fault_type(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    received: dict[str, object] = {}

    def fake_injector(
        scenario_path: Path,
        output_directory: Path,
    ) -> dict[str, object]:
        received["scenario_path"] = scenario_path
        received["output_directory"] = output_directory
        return {"status": "injected"}

    monkeypatch.setitem(
        FAULT_INJECTORS,
        "test_fault",
        fake_injector,
    )

    result = inject_fault(
        "test_fault",
        Path("scenario.yml"),
        Path("output"),
    )

    assert result == {"status": "injected"}
    assert received["scenario_path"] == Path("scenario.yml")
    assert received["output_directory"] == Path("output")
