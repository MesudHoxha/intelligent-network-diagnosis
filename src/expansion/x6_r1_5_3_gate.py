"""Append-only source inventory gate; never grants execution authority."""
from pathlib import Path
from src.orchestration.x6_r1_5_1_contract import load,digest,require
PLAN="plans/expansion/X6_R1_5_3_EPOCH_NORMALIZATION_SOURCE_ONLY_V1.json"
def verify_source(root,inventory):
    root=Path(root);plan=load(root/PLAN)
    require([row["path"] for row in inventory]==plan["implementation_inventory"],"successor inventory")
    for row in inventory:
        path=root/row["path"]
        require(path.is_file() and not path.is_symlink() and digest(path.read_bytes())==row["sha256"],"successor bytes")
        expected="100755" if row["path"].endswith("external_stub.py") else "100644"
        require(row["mode"]==expected and path.stat().st_mode & 0o777==(0o755 if expected=="100755" else 0o644),"successor modes")
    return True
