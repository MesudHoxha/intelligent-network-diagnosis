# HANDOFF — P6-R3 Healthy Evidence v3 Runtime and Toolchain Gate

Date: 2026-08-06

Status: COMPLETED

## 1. What was completed

P6-R3 completed the first real fault-free Evidence v3 runtime gate.

The milestone:

- added open-source iptables to the Ubuntu 24.04 ind-linux image;
- preserved the previous image under ind-linux:p6-r2-preflight;
- reviewed a TOP-01 Observation Profile v2 binding for HostA, R1, R2,
  and HostB;
- added an isolated post-deploy source-default-route setup without
  changing the historical topology or G01 fingerprint;
- collected real Evidence v3 for experiment
  p6_r3_healthy_top01-20260806T090542Z;
- verified all 10 healthy feature values as observed;
- verified 9/9 raw JSON artifacts and their SHA-256 bindings;
- preserved the 13/13 baseline before and after collection;
- passed 31/31 targeted and 343/343 full regression tests; and
- destroyed the lab with zero TOP-01 containers remaining.

## 2. What was decided

D-080 is approved and implemented.

The healthy TOP-01 runtime path, toolchain, profile binding, verifier,
and raw-provenance boundary are accepted as the prerequisite for
P6-R4. The real Evidence v3 SHA-256 is
654cb717aa823091b6832d586b22503eb26f37aad81dc3e2f40f7d1f64c75ac2
and collector-status SHA-256 is
d68b14f65b80f72ab7f0b8c7f3709b37b2f0a18165167ec3dd3593c914aed88d.

Dataset Row v2 remains the runtime default. Generated data/raw runtime
artifacts remain intentionally excluded from Git. No fault signature,
restoration result, Dataset Row v3, campaign result, model, prediction,
or metric is accepted by this milestone.

## 3. Files created or changed

P6-R3 files are:

- docs/DECISIONS.md;
- docs/HANDOFF_P6_R3.md;
- docs/MASTER_CONTEXT.md;
- docs/P6_R3_HEALTHY_EVIDENCE_GATE.md;
- docs/ROADMAP.md;
- docs/STATUS.md;
- labs/images/ind-linux/Dockerfile;
- labs/topologies/top01_routed/scripts/prepare_p6_r3_profile.sh;
- scenarios/routing/N0_NORMAL_OPERATION_P6_TOP01.yml;
- src/verification/__init__.py;
- src/verification/healthy_evidence_v3.py; and
- tests/unit/test_p6_r3_healthy_evidence_v3.py.

The historical TOP-01 topology, G01 fingerprint, Evidence v2 and v3
contracts, collector v2, Experiment Runner, Dataset Row runtime default,
accepted datasets, P3-P5 artifacts, model, and hybrid policy were not
changed.

## 4. Open issues

- Implement fail-stop wrong_default_gateway injection on the source
  role and exact restoration.
- Implement fail-stop interface_down injection on the observer egress
  interface and exact restoration.
- Implement one uniquely tagged acl_block FORWARD rule and exact
  deletion/restoration.
- Implement rule signatures for the three new classes without using
  ground truth or expected signatures as rule inputs.
- Smoke each new class in one reviewed context and verify the frozen
  Evidence v3 signatures and final healthy baseline.
- Keep E01-E06, the 72-row campaign, Dataset Row v3 aggregation, model
  fitting, prediction, and metrics outside P6-R4.
- Preserve accepted P2-P5 artifacts and Dataset Row v2 default until
  the complete Phase 6 runtime path is separately accepted.

## 5. Next step

Start P6-R4 — Fail-stop Injectors, Rule Signatures, and New-Class Smoke
Gate.

P6-R4 must implement the three new deterministic injectors, verify
preconditions and exact restoration, add evidence-only rule signatures,
and smoke wrong_default_gateway, interface_down, and acl_block in one
reviewed context each. Every execution must finish with the accepted
healthy baseline. It must not execute E01-E06 or the 72-row campaign and
must not fit or evaluate a model.

## 6. Impact on central documents

- DECISIONS adds D-080 and accepts the bounded healthy runtime gate.
- MASTER_CONTEXT records the real toolchain, profile, experiment, and
  preservation result without extending the empirical claim.
- P6_R3_HEALTHY_EVIDENCE_GATE records the normative runtime boundary,
  exact feature signature, hashes, tests, and limitations.
- ROADMAP closes P6-R3 and names P6-R4.
- STATUS records the 31/31 and 343/343 tests, 13/13 baseline checks,
  10/10 features, 9/9 raw probes, cleanup, and absent downstream work.
