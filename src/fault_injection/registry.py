from collections.abc import Callable
from typing import Any

from src.fault_injection.common import FaultInjectionError
from src.fault_injection.missing_route import inject_missing_route
from src.fault_injection.wrong_next_hop import (
    inject_wrong_next_hop,
)


FaultInjector = Callable[..., object]


FAULT_INJECTORS: dict[str, FaultInjector] = {
    "missing_static_route": inject_missing_route,
    "wrong_next_hop": inject_wrong_next_hop,
}


def inject_fault(
    fault_type: str,
    *args: Any,
    **kwargs: Any,
) -> object:
    try:
        injector = FAULT_INJECTORS[fault_type]
    except KeyError as error:
        supported_types = ", ".join(
            sorted(FAULT_INJECTORS)
        )
        raise FaultInjectionError(
            f"Unsupported fault type '{fault_type}'. "
            f"Supported fault types: {supported_types}"
        ) from error

    return injector(*args, **kwargs)
