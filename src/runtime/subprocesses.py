from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Sequence


TIMEOUT_RETURN_CODE = 124


def _text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def run_capture(
    command: Sequence[str],
    *,
    timeout_seconds: float,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run one bounded command and normalize timeout as return code 124."""

    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be greater than zero.")
    arguments = list(command)
    try:
        return subprocess.run(
            arguments,
            cwd=cwd,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as error:
        stdout = _text(error.stdout)
        stderr = _text(error.stderr)
        message = f"Command timed out after {timeout_seconds:g} seconds."
        if stderr and not stderr.endswith("\n"):
            stderr += "\n"
        stderr += message
        return subprocess.CompletedProcess(
            args=arguments,
            returncode=TIMEOUT_RETURN_CODE,
            stdout=stdout,
            stderr=stderr,
        )
