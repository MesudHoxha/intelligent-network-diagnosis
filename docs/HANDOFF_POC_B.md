# HANDOFF — PoC-B

## 1. What was completed

- Implemented C2_WRONG_NEXT_HOP.
- Registered C2 in the fault-injection registry.
- Extended the Evidence Collector to parse the configured
  next-hop and test its reachability.
- Added rule R_ROUTING_002 for wrong_next_hop.
- Preserved C1 behavior under rule R_ROUTING_001.
- Verified both scenarios through the complete experiment runner.
- Verified automatic restoration to the TOP-01 9/9 baseline.
- Completed the full test suite with 18 passing tests.
- Confirmed that Collector and Rule Engine do not read
  ground_truth.

Verified runtime experiments:

- data/raw/c1_missing_static_route-20260728T120013Z
- data/raw/c2_wrong_next_hop-20260728T120038Z

## 2. What was decided

- PoC-B is accepted as implemented and tested.
- Static-route evidence includes route presence, configured
  next-hop, and active next-hop reachability.
- `ip neigh` is not mandatory for the current scenarios.
- Ground truth remains isolated from evidence collection and
  diagnosis.
- These two scenarios do not represent general diagnostic
  performance.
- ML and hybrid implementation will begin only after the dataset
  contract and generation process are validated.

## 3. Files created or changed

Changed implementation and tests:

- src/collection/evidence_collector.py
- src/fault_injection/registry.py
- src/rules/rule_engine.py
- tests/unit/test_fault_registry.py

Created implementation and tests:

- scenarios/routing/C2_WRONG_NEXT_HOP.yml
- src/fault_injection/wrong_next_hop.py
- tests/integration/test_wrong_next_hop_scenario.py
- tests/unit/test_evidence_collector.py
- tests/unit/test_rule_engine.py
- tests/unit/test_wrong_next_hop_helpers.py

Updated central documents:

- docs/MASTER_CONTEXT.md
- docs/DECISIONS.md
- docs/STATUS.md

Created handoff:

- docs/HANDOFF_POC_B.md

## 4. Open issues

- Detailed experiment-manifest and dataset schemas
- Parameterized normal, C1, and C2 variants
- Missing-evidence and unseen-variant experiments
- Final pilot fault-class set
- Controlled multiple-fault subset
- Group-aware dataset splitting
- ML and hybrid diagnostic approaches
- Later OSPF and FRRouting extensions

## 5. Next step

Review and commit the complete PoC-B checkpoint. Then define the
experiment manifest, dataset row, feature contract, and the first
reproducible dataset-generation batch.

## 6. Impact on central documents

- MASTER_CONTEXT now records the tested C1/C2 baseline and the
  current native Docker environment.
- DECISIONS records PoC-B completion, the static-routing evidence
  contract, and ground-truth isolation.
- STATUS replaces obsolete setup tasks with the verified PoC-B
  state and dataset-preparation milestone.
