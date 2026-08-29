from __future__ import annotations

import argparse
import hashlib
import json
import tomllib
from pathlib import Path

from src.expansion.x6_r0_5_gate import verify_x6_r0_5


ROOT = Path(__file__).resolve().parents[2]
PLAN = Path(
    "plans/expansion/X6_R0_6_TEST_ENVIRONMENT_REPRODUCIBILITY_CORRECTION_V1.json"
)
EXPECTED_REQUIREMENT = "pytest>=9,<10"


class X6R06GateError(ValueError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise X6R06GateError(message)


def verify_x6_r0_6(repository_root: Path = ROOT) -> dict[str, object]:
    root = Path(repository_root)
    verify_x6_r0_5(root)
    plan = json.loads((root / PLAN).read_text())
    project = tomllib.loads((root / "pyproject.toml").read_text())
    extras = project["project"]["optional-dependencies"]
    require("test" in extras, "project test extra is missing")
    requirements = extras["test"]
    require(EXPECTED_REQUIREMENT in requirements, "bounded pytest requirement drifted")
    require("httpx>=0.27,<1" in requirements, "existing httpx test dependency drifted")
    require(
        sum(item.startswith("pytest") for item in requirements) == 1,
        "pytest must be declared directly and exactly once",
    )
    require(
        plan["pytest_requirement"] == EXPECTED_REQUIREMENT
        and plan["accepted_environment_pytest_version"] == "9.1.1",
        "accepted pytest compatibility record drifted",
    )
    require(
        plan["clean_install_command"] == "python -m pip install -e '.[test]'"
        and plan["clean_install_command"] in (root / "README.md").read_text(),
        "documented clean-install workflow drifted",
    )
    authorization = plan["runtime_scientific_authorization"]
    require(len(authorization) == 10 and not any(authorization.values()), "authorization must remain 0/10")
    bindings = plan["source_bindings"]
    require(len(bindings) == 4, "X6-R0.6 requires four source bindings")
    for binding in bindings:
        path = root / binding["path"]
        require(
            path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == binding["sha256"],
            "source binding drifted: " + binding["path"],
        )
    return plan


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, default=ROOT)
    args = parser.parse_args()
    verify_x6_r0_6(args.repository_root)
    print("x6_r0_6=VERIFIED")
    print("source_bindings=4/4_HASH_BOUND_PASS")
    print("runtime_scientific_authorization=0/10_FALSE_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
