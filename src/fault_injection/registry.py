from collections.abc import Callable
from typing import Any

from src.fault_injection.common import FaultInjectionError
from src.fault_injection.missing_route import inject_missing_route


FaultInjector = Callable[..., object]


FAULT_INJECTORS: dict[str, FaultInjector] = {
    "missing_static_route": inject_missing_route,
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
