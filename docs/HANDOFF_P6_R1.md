# HANDOFF — P6-R1 Versioned Phase 6 Contracts

Date: 2026-08-06

Status: COMPLETED

## 1. What was completed

P6-R1 implemented and contract-tested the data boundary required by
the frozen D-077 six-class evaluation plan.

The milestone completed:

- Observation Profile v2 and its strict JSON Schema;
- explicit Observation Profile v1/v2 dispatch;
- source, gateway, egress-interface, flow-selector, and policy-role
  validation;
- Evidence v3 with the exact ten D-077 features;
- feature-level availability and SHA-256-bound raw-probe provenance;
- raw/derived consistency gates for gateway, next-hop, interface, and
  policy features;
- explicit Evidence v2/v3 dispatch;
- Dataset Row v3, strict predictor whitelist, and JSON Schema;
- source Evidence v3 SHA-256 binding;
- structural, collection, and masked missingness semantics;
- four deterministic non-destructive missing-evidence transforms;
- generic Dataset Row v1/v2/v3 dispatch and mixed-version rejection;
- explicit Dataset Row v3 export for future Evidence v3 experiments;
  and
- 57 targeted contract tests.

The complete regression suite passed 316/316 tests in the isolated
verification environment. P6-R1 did not execute Containerlab or
produce a real Phase 6 runtime artifact.

## 2. What was decided

D-078 is approved and implemented.

Dataset Row v2 remains the runtime default until the real Evidence v3
collector is implemented and accepted. This prevents the existing v2
collector from being treated as a Phase 6 data source.

Evidence v3 records one availability reason and one probe provenance
record for every predictor. Observed and failed probes require a
normalized raw-artifact path and SHA-256. Structural non-applicability
must not claim a raw artifact.

Dataset Row v3 preserves separate structural_unavailable,
collection_unavailable, and masked_missing reasons while exposing only
the tri-state predictor value. Masking is non-destructive, does not
alter the source Evidence v3 hash, does not overwrite structural
reasons, and does not impute values.

The first policy backend remains iptables/filter/FORWARD as frozen by
the P6-R0 design. P6-R1 validates that contract but does not establish
tool availability or probe feasibility.

## 3. Files created or changed

P6-R1 files are:

- docs/DECISIONS.md;
- docs/HANDOFF_P6_R1.md;
- docs/MASTER_CONTEXT.md;
- docs/P6_R1_CONTRACTS.md;
- docs/ROADMAP.md;
- docs/STATUS.md;
- schemas/dataset_row_v3.schema.json;
- schemas/evidence_v3.schema.json;
- schemas/observation_profile_v2.schema.json;
- src/contracts/evidence_v3.py;
- src/contracts/observation_profile_v2.py;
- src/dataset/contract.py;
- src/dataset/contract_v3.py;
- tests/unit/test_p6_r1_dataset_row_v3.py;
- tests/unit/test_p6_r1_evidence_v3.py; and
- tests/unit/test_p6_r1_observation_profile_v2.py.

Evidence v2 and Dataset Row v2 schemas, the accepted P2 dataset, the
P3/P4/P5 method artifacts, model, and hybrid policy were not changed.

## 4. Open issues

- Implement Evidence v3 raw commands, parsing, and atomic artifact
  persistence.
- Preserve the existing Evidence v2 collector and runtime path.
- Verify iptables availability in the local image before ACL work.
- Implement fail-stop wrong_default_gateway, interface_down, and
  acl_block injectors and exact restoration in later milestones.
- Implement/review E01-E06 scenario bundles and the new TOP-04 only
  after collector and injector gates pass.
- Execute and audit the 72-row campaign only after all prior gates.
- Keep masked validation/test generation separate from clean fitting
  rows and preserve source hashes.
- Implement new six-class Rule-based, ML, and Hybrid versions without
  altering the accepted P3-P5 baselines.
- Define a multi-label contract before considering multiple faults.
- Keep OSPF proposed until separately reviewed.

## 5. Next step

Start P6-R2 — Evidence v3 Collector and Raw-Probe Implementation.

P6-R2 must:

- implement the source expected-gateway reachability probe;
- parse and persist the installed source default gateway;
- preserve the destination-reachability probe;
- parse observer route existence and installed next-hop;
- calculate next-hop agreement without scenario-label access;
- probe installed and expected next-hop reachability separately;
- parse the observer egress operational state;
- preserve transit-to-destination reachability;
- inspect the exact iptables/filter/FORWARD flow policy;
- persist raw success/failure outputs and SHA-256 bindings;
- preserve and regression-test the v2 collector path;
- use synthetic command outputs and isolated tests first;
- stop before any new fault injector or Containerlab execution; and
- produce no Phase 6 dataset, model, prediction, or metric.

## 6. Impact on central documents

- DECISIONS adds D-078 and the version/default boundary.
- MASTER_CONTEXT records the implemented contract and unavailable
  semantics without claiming experimental results.
- P6_R1_CONTRACTS is the normative contract implementation document.
- ROADMAP closes P6-R1 and names P6-R2.
- STATUS records 57/57 targeted and 316/316 regression verification,
  keeps Phase 6 in progress, and distinguishes synthetic contract
  verification from absent network execution.
