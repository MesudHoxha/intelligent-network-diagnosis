from __future__ import annotations

from collections.abc import Callable
from typing import Any

from src.fault_injection.acl_block import inject_acl_block, restore_acl_block
from src.fault_injection.interface_down import (
    inject_interface_down,
    restore_interface_down,
)
from src.fault_injection.phase6_common import Phase6FaultInjectionError
from src.fault_injection.phase6_route_faults import (
    inject_missing_static_route,
    inject_wrong_next_hop_v3,
    restore_missing_static_route,
    restore_wrong_next_hop_v3,
)
from src.fault_injection.wrong_default_gateway import (
    inject_wrong_default_gateway,
    restore_wrong_default_gateway,
)


Phase6Mutation = Callable[..., object]

PHASE6_INJECTORS: dict[str, Phase6Mutation] = {
    "missing_static_route": inject_missing_static_route,
    "wrong_next_hop": inject_wrong_next_hop_v3,
    "wrong_default_gateway": inject_wrong_default_gateway,
    "interface_down": inject_interface_down,
    "acl_block": inject_acl_block,
}

PHASE6_RESTORERS: dict[str, Phase6Mutation] = {
    "missing_static_route": restore_missing_static_route,
    "wrong_next_hop": restore_wrong_next_hop_v3,
    "wrong_default_gateway": restore_wrong_default_gateway,
    "interface_down": restore_interface_down,
    "acl_block": restore_acl_block,
}


def inject_phase6_fault(
    fault_type: str,
    *args: Any,
    **kwargs: Any,
) -> object:
    try:
        injector = PHASE6_INJECTORS[fault_type]
    except KeyError as error:
        raise Phase6FaultInjectionError(
            f"Unsupported Phase 6 fault type: {fault_type!r}."
        ) from error
    return injector(*args, **kwargs)


def restore_phase6_fault(
    fault_type: str,
    *args: Any,
    **kwargs: Any,
) -> object:
    try:
        restorer = PHASE6_RESTORERS[fault_type]
    except KeyError as error:
        raise Phase6FaultInjectionError(
            f"Unsupported Phase 6 restoration type: {fault_type!r}."
        ) from error
    return restorer(*args, **kwargs)
