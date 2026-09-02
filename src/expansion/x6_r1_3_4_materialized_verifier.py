"""Independent R1.3.4 verifier that derives controls from bound raw records."""
from __future__ import annotations

import hashlib
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Mapping

from src.collection.x6_performance_collector import derive_window
from src.collection.x6_r0_3_pre_runtime_validation import NUMERIC_FEATURES, build_threshold_manifest, validate_threshold_manifest
from src.orchestration.x6_r1_3_3_baseline_only_runner import WINDOW_IDS, safe_relative
from src.orchestration.x6_r1_3_4_baseline_execution import COMMANDS, RELEASE_ID


class X6R134VerificationError(ValueError):
    pass


def _fail(message: str) -> None:
    raise X6R134VerificationError("X6-R1.3.4: " + message)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read(root: Path, reference: Mapping[str, object]) -> Mapping[str, object]:
    if set(reference) != {"path", "sha256"} or not isinstance(reference.get("path"), str) or not isinstance(reference.get("sha256"), str):
        _fail("raw artifact reference malformed")
    path = root / safe_relative(str(reference["path"]))
    if not path.is_file() or path.is_symlink() or _sha(path.read_bytes()) != reference["sha256"]:
        _fail("raw artifact missing, unsafe, or hash-mismatched")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise X6R134VerificationError("X6-R1.3.4: raw artifact is not JSON") from error
    if not isinstance(value, Mapping):
        _fail("raw artifact object required")
    return value


def _command_record(root: Path, reference: Mapping[str, object], command_name: str) -> Mapping[str, object]:
    value = _read(root, reference)
    required = {"command", "shell", "timeout_seconds", "return_code", "stdout", "stderr", "source_test_only"}
    if set(value) != required or value["command"] != COMMANDS[command_name] or value["shell"] is not False or value["timeout_seconds"] != 30:
        _fail(command_name + " raw command binding drift")
    if not isinstance(value["return_code"], int) or isinstance(value["return_code"], bool) or not isinstance(value["stdout"], str) or not isinstance(value["stderr"], str):
        _fail(command_name + " raw command result malformed")
    return value


def _noqueue(record: Mapping[str, object]) -> bool:
    try:
        rows = json.loads(str(record["stdout"]))
    except json.JSONDecodeError:
        return False
    return isinstance(rows, list) and len(rows) == 1 and isinstance(rows[0], dict) and rows[0].get("kind") == "noqueue" and rows[0].get("handle") == "0:"


def _empty_filter(record: Mapping[str, object]) -> bool:
    try:
        return json.loads(str(record["stdout"])) == []
    except json.JSONDecodeError:
        return False


def _speed(record: Mapping[str, object]) -> int | None:
    try:
        value = int(str(record["stdout"]).strip())
    except ValueError:
        return None
    return value if value > 0 else None


def verify_materialized_run(run_root: Path, *, repository_root: Path) -> dict[str, object]:
    """Verify a completed runner tree without trusting asserted terminal booleans."""
    root = Path(run_root)
    controls_path = root / "state" / "control_artifacts.json"
    if not controls_path.is_file():
        _fail("control artifact inventory missing")
    controls = json.loads(controls_path.read_text(encoding="utf-8"))
    required_controls = {"deploy", "readiness", "qdisc", "filters_root", "filters_ingress", "r2_tx", "r3_rx", "r2_speed", "r3_speed", "processes", "namespaces", "qdisc_after", "filters_root_after", "filters_ingress_after", "cleanup"}
    if not isinstance(controls, Mapping) or set(controls) != required_controls:
        _fail("complete control inventory required")
    parsed = {name: _command_record(root, value, "qdisc" if name == "qdisc_after" else "filters_root" if name == "filters_root_after" else "filters_ingress" if name == "filters_ingress_after" else name) for name, value in controls.items()}
    if any(row["return_code"] != 0 for row in parsed.values()):
        _fail("raw command return code is nonzero")
    if not _noqueue(parsed["qdisc"]) or not _noqueue(parsed["qdisc_after"]):
        _fail("qdisc raw evidence is not exact noqueue")
    if not all(_empty_filter(parsed[name]) for name in ("filters_root", "filters_ingress", "filters_root_after", "filters_ingress_after")):
        _fail("filter raw evidence is not empty")
    left, right = _speed(parsed["r2_speed"]), _speed(parsed["r3_speed"])
    if left is None or left != right:
        _fail("speed raw evidence is unavailable or unequal")
    windows: list[Mapping[str, object]] = []
    previous_end: int | float | None = None
    for window_id in WINDOW_IDS:
        raw_path = root / "raw" / "windows" / (window_id + ".json")
        if not raw_path.is_file():
            _fail("missing required window: " + window_id)
        row = json.loads(raw_path.read_text(encoding="utf-8"))
        if set(row) != {"window_id", "canonical_features", "collector_raw", "timing", "source_test_only"} or row["window_id"] != window_id:
            _fail("window raw schema or order drift: " + window_id)
        features = row["canonical_features"]
        if not isinstance(features, Mapping) or set(features) != set(NUMERIC_FEATURES):
            _fail("window feature catalog drift: " + window_id)
        timing = row["timing"]
        if not isinstance(timing, Mapping) or set(timing) != {"actual_start_ns", "actual_end_ns", "startup_skew_seconds"}:
            _fail("window timing schema drift: " + window_id)
        start, end, skew = timing["actual_start_ns"], timing["actual_end_ns"], timing["startup_skew_seconds"]
        if any(isinstance(item, bool) or not isinstance(item, (int, float)) for item in (start, end, skew)) or start < 0 or end - start < 20_000_000_000 or skew < 0 or skew > 0.250 or previous_end is not None and start < previous_end + 5_000_000_000:
            _fail("window timing or spacing drift: " + window_id)
        previous_end = end
        # Production raw payloads are re-derived. Synthetic source-only records
        # may exercise lifecycle mechanics but are never qualifying evidence.
        if row["source_test_only"] is False:
            source = row["collector_raw"]
            if not isinstance(source, Mapping):
                _fail("collector raw payload missing")
            derived = derive_window(source, phase="baseline", speed_mbps=left)
            expected = {feature: derived[feature].get("value") for feature in NUMERIC_FEATURES}
            if any(derived[feature].get("availability") != "observed" for feature in NUMERIC_FEATURES) or dict(features) != expected:
                _fail("window values do not derive from bound raw commands")
        windows.append(features)
    threshold_path = root / "state" / "threshold_manifest.json"
    freeze_path = root / "state" / "threshold_freeze.json"
    if not threshold_path.is_file() or not freeze_path.is_file():
        _fail("threshold finalization evidence missing")
    manifest = json.loads(threshold_path.read_text(encoding="utf-8"))
    expected = build_threshold_manifest({feature: [row[feature] for row in windows[:10]] for feature in NUMERIC_FEATURES}, topology_context_id="X6_TOP_01_CONTROLLED_PERFORMANCE_PATH", traffic_context_id="X6_R1_BASELINE_ONLY_QUALIFICATION")
    if manifest != expected:
        _fail("threshold manifest is not exactly C01-C10 canonical output")
    validate_threshold_manifest(manifest, repository_root=repository_root)
    thresholds = {row["feature_id"]: row for row in manifest["features"]}
    comparisons: dict[str, dict[str, bool]] = {}
    for window_id, row in zip(WINDOW_IDS[10:], windows[10:], strict=True):
        comparisons[window_id] = {}
        for feature in NUMERIC_FEATURES:
            try:
                measured = Decimal(str(row[feature])); lower = Decimal(str(thresholds[feature]["lower_threshold"])); upper = Decimal(str(thresholds[feature]["upper_threshold"]))
            except (InvalidOperation, KeyError) as error:
                raise X6R134VerificationError("X6-R1.3.4: later-cohort numeric comparison malformed") from error
            comparisons[window_id][feature] = lower <= measured <= upper
    if not all(all(values.values()) for values in comparisons.values()):
        _fail("calibration or holdout value is outside the frozen manifest")
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    if freeze.get("after_window_id") != "C10" or freeze.get("before_window_id") != "C11" or freeze.get("manifest_sha256") != manifest["sha256"] or freeze.get("byte_sha256") != _sha(threshold_path.read_bytes()):
        _fail("threshold-freeze binding drift")
    terminal = root / "terminal" / "terminal.json"
    if not terminal.is_file() or json.loads(terminal.read_text(encoding="utf-8")).get("status") not in {"INCONCLUSIVE", "COLLECTION_UNAVAILABLE", "QUALIFIED"}:
        _fail("terminalization is missing or invalid")
    lifecycle_terminal = root / "state" / "r1_3_4_terminal.json"
    if not lifecycle_terminal.is_file():
        _fail("R1.3.4 lifecycle terminalization is missing")
    lifecycle = json.loads(lifecycle_terminal.read_text(encoding="utf-8"))
    if lifecycle.get("release_id") != RELEASE_ID or lifecycle.get("qualification") != "INDEPENDENT_MATERIALIZED_VERIFIER_REQUIRED":
        _fail("R1.3.4 lifecycle terminalization drift")
    return {"release_id": RELEASE_ID, "all_windows_complete": True, "threshold_frozen_before_c11": True, "qdisc_filter_state_valid": True, "speed_control_valid": True, "calibration_validation": comparisons, "source_test_only": all(bool(json.loads((root / "raw" / "windows" / (window_id + ".json")).read_text())["source_test_only"]) for window_id in WINDOW_IDS), "qualified": False}
