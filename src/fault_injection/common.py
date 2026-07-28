from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


class FaultInjectionError(RuntimeError):
    """Raised when a fault cannot be injected or validated safely."""


@dataclass(frozen=True)
class CommandResult:
    command: list[str]
    return_code: int
    stdout: str
    stderr: str


def run_command(
    command: Sequence[str],
    *,
    check: bool = False,
) -> CommandResult:
    process = subprocess.run(
        list(command),
        capture_output=True,
        text=True,
        check=False,
    )

    result = CommandResult(
        command=list(command),
        return_code=process.returncode,
        stdout=process.stdout.strip(),
        stderr=process.stderr.strip(),
    )

    if check and result.return_code != 0:
        raise FaultInjectionError(
            f"Command failed: {' '.join(result.command)}\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )

    return result


def docker_exec(
    container: str,
    command: Sequence[str],
    *,
    check: bool = False,
) -> CommandResult:
    return run_command(
        ["docker", "exec", container, *command],
        check=check,
    )


def route_exists(container: str, prefix: str) -> bool:
    result = docker_exec(
        container,
        ["ip", "route", "show", prefix],
    )
    return result.return_code == 0 and bool(result.stdout.strip())


def ping_succeeds(container: str, destination: str) -> bool:
    result = docker_exec(
        container,
        ["ping", "-c", "2", "-W", "1", destination],
    )
    return result.return_code == 0


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
