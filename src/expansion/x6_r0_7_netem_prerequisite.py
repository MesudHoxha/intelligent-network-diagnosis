"""Fail-closed X6 NetEm runtime-prerequisite validation."""
from __future__ import annotations

from collections.abc import Mapping
import re


class X6R07NetemPrerequisiteError(ValueError):
    pass


def _record(records: Mapping[str, object], name: str) -> Mapping[str, object]:
    value = records.get(name)
    if not isinstance(value, Mapping):
        raise X6R07NetemPrerequisiteError("MODULE_UNAVAILABLE: missing record " + name)
    if value.get("return_code") != 0:
        stderr = value.get("stderr")
        detail = stderr.strip() if isinstance(stderr, str) and stderr.strip() else "no stderr"
        raise X6R07NetemPrerequisiteError("COMMAND_REJECTED: " + name + ": " + detail)
    return value


def _stdout(record: Mapping[str, object], name: str) -> str:
    value = record.get("stdout")
    if not isinstance(value, str):
        raise X6R07NetemPrerequisiteError("COMMAND_REJECTED: malformed stdout for " + name)
    return value


def validate_netem_prerequisite(records: Mapping[str, object]) -> dict[str, object]:
    """Validate records captured before any future X6-R1 baseline.

    This checker never loads a host module or creates a qdisc.  It merely
    fails closed on absent module, userspace support, capability, or recovery.
    """
    kernel = _stdout(_record(records, "kernel"), "kernel").strip()
    config = _stdout(_record(records, "kernel_config"), "kernel_config")
    module = _stdout(_record(records, "module"), "module")
    loaded = _stdout(_record(records, "loaded_modules"), "loaded_modules")
    image = _stdout(_record(records, "image_identity"), "image_identity").strip()
    tc_version = _stdout(_record(records, "tc_version"), "tc_version")
    package = _stdout(_record(records, "iproute2_package"), "iproute2_package")
    capability = _stdout(_record(records, "capability"), "capability")
    active = _stdout(_record(records, "active_qdisc"), "active_qdisc")
    restored = _stdout(_record(records, "restored_qdisc"), "restored_qdisc")
    if not kernel or ("CONFIG_NET_SCH_NETEM=m" not in config and "CONFIG_NET_SCH_NETEM=y" not in config):
        raise X6R07NetemPrerequisiteError("MODULE_UNAVAILABLE: compatible CONFIG_NET_SCH_NETEM is absent")
    if "name:           sch_netem" not in module or kernel not in module or not re.search(r"(?m)^sch_netem\s", loaded):
        raise X6R07NetemPrerequisiteError("MODULE_UNAVAILABLE: sch_netem is not loaded for the running kernel")
    if not image or "tc utility, iproute2-" not in tc_version or not package.startswith("iproute2"):
        raise X6R07NetemPrerequisiteError("USERSPACE_QDISC_UNAVAILABLE: frozen image tc/iproute2 provenance is incomplete")
    if "CapEff:" not in capability:
        raise X6R07NetemPrerequisiteError("PERMISSION_FAILURE: disposable NET_ADMIN capability is not recorded")
    if '"kind":"netem"' not in active or '"handle":"10:"' not in active or '"kind":"pfifo"' not in active or '"handle":"20:"' not in active:
        raise X6R07NetemPrerequisiteError("USERSPACE_QDISC_UNAVAILABLE: exact NetEm/pfifo chain was not observed")
    if '"kind":"noqueue"' not in restored or '"handle":"0:"' not in restored:
        raise X6R07NetemPrerequisiteError("COMMAND_REJECTED: disposable qdisc restoration was not observed")
    return {"status": "NETEM_PREREQUISITE_VALIDATED", "kernel_release": kernel, "image_identity": image, "tc_version": tc_version.strip(), "iproute2_package": package.strip(), "operator_action_required_after_wsl_restart": "sudo modprobe sch_netem", "pre_baseline_policy": "VERIFY_ONLY_NEVER_LOAD_FROM_SCIENTIFIC_RUNNER"}


__all__ = ["X6R07NetemPrerequisiteError", "validate_netem_prerequisite"]
