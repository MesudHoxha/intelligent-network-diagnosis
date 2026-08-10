from collections.abc import Callable
from typing import Any

from src.fault_injection.acl_block import (
    inject_acl_block,
    restore_acl_block,
)
from src.fault_injection.common import FaultInjectionError
from src.fault_injection.interface_down import (
    inject_interface_down,
    restore_interface_down,
)
from src.fault_injection.missing_route import inject_missing_route
from src.fault_injection.phase6_common import (
    Phase6FaultInjectionError,
)
from src.fault_injection.wrong_next_hop import (
    inject_wrong_next_hop,
)
from src.fault_injection.wrong_default_gateway import (
    inject_wrong_default_gateway,
    restore_wrong_default_gateway,
)


FaultInjector = Callable[..., object]


FAULT_INJECTORS: dict[str, FaultInjector] = {
    "missing_static_route": inject_missing_route,
    "wrong_next_hop": inject_wrong_next_hop,
    "wrong_default_gateway": inject_wrong_default_gateway,
    "interface_down": inject_interface_down,
    "acl_block": inject_acl_block,
}

FAULT_RESTORERS: dict[str, FaultInjector] = {
    "wrong_default_gateway": restore_wrong_default_gateway,
    "interface_down": restore_interface_down,
    "acl_block": restore_acl_block,
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


def restore_fault(
    fault_type: str,
    *args: Any,
    **kwargs: Any,
) -> object:
    try:
        restorer = FAULT_RESTORERS[fault_type]
    except KeyError as error:
        supported_types = ", ".join(sorted(FAULT_RESTORERS))
        raise Phase6FaultInjectionError(
            f"Unsupported Phase 6 restoration type '{fault_type}'. "
            f"Supported types: {supported_types}"
        ) from error
    return restorer(*args, **kwargs)
