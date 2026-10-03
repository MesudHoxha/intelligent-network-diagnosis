"""Source gate for the prospective campaign successor."""
from pathlib import Path
from src.orchestration.x6_r1_5_1_contract import digest,require

FILES=('src/orchestration/x6_r1_5_2_campaign.py', 'src/orchestration/x6_r1_5_2_contract.py', 'src/orchestration/x6_r1_5_2_durable.py', 'src/orchestration/x6_r1_5_2_not_run.py', 'src/orchestration/x6_r1_5_2_slot.py', 'src/orchestration/x6_r1_5_2_recovery.py', 'src/expansion/x6_r1_5_2_dataset.py', 'src/expansion/x6_r1_5_2_model.py', 'src/expansion/x6_r1_5_2_analysis.py', 'src/expansion/x6_r1_5_2_materialized_verifier.py', 'src/expansion/x6_r1_5_2_gate.py', 'tests/fixtures/x6_r1_5_2_external_stub.py', 'tests/unit/test_x6_r1_5_2_campaign.py', 'plans/expansion/X6_R1_5_2_EXPLORATORY_F1_CAMPAIGN_SOURCE_ONLY_V1.json', 'plans/expansion/X6_R1_5_2_NOT_RUN_ACCOUNTING_AUTHORITY_DECISION_V1.json', 'docs/DECISION_X6_R1_5_2.md', 'docs/STATUS_X6_R1_5_2.md', 'docs/HANDOFF_X6_R1_5_2.md', 'src/orchestration/x6_r1_5_2_source_test.py', 'tests/fixtures/x6_r1_5_2_test_support.py', 'tests/fixtures/x6_r1_5_2_synthetic.py', 'tests/unit/test_x6_r1_5_2_contract_corrections.py', 'tests/unit/test_x6_r1_5_2_production_integration.py', 'src/orchestration/x6_r1_5_2_launcher.py', 'tests/unit/test_x6_r1_5_2_launcher.py')

def verify_source(root,inventory):
    root=Path(root); require([x["path"] for x in inventory]==list(FILES),"successor inventory")
    for row in inventory:
        path=root/row["path"]; require(path.is_file() and digest(path.read_bytes())==row["sha256"],"successor source binding: "+row["path"])
        require(row["mode"]==("100755" if row["path"].endswith("external_stub.py") else "100644") and (path.stat().st_mode & 0o777)==(0o755 if row["mode"]=="100755" else 0o644),"successor actual mode")
    return True
