# HANDOFF — P2-R3 TOP-02 Context Design Review

Date: 2026-07-30
Status: COMPLETED

## 1. What was completed

- Audited the current TOP-01 topology, baseline validator, N0/C1/C2
  scenario bindings, Observation Profile v1, Evidence v2 collector,
  fault injectors, Experiment Runner, and Dataset Row v2 boundary.
- Converted G02, G03, and G04 from coverage labels into concrete
  static-routing designs.
- Froze one topology_id and one shared split_group_id for every
  planned TOP-02 context.
- Froze the future G01 shared multi-class split_group_id without
  rewriting historical artifacts.
- Recorded each graph, addressing plan, forwarding intent, directed
  path, observation roles, fault target, evidence producers, and
  design fingerprint.
- Performed a distinction audit against G01 and across G02-G04.
- Defined required baseline assertions and per-context scenario
  acceptance rules.
- Selected G02 as the first implementation target for P2-R4.

No topology, validator, scenario, source-code, schema, laboratory
experiment, dataset row, or split artifact was created in this stage.

## 2. What was decided

- D-059 freezes the TOP-02 context designs.
- G01 future campaign rows use CTX_G01_TOP01_LINEAR_2R.
- G02 uses TOP_02_CHAIN and CTX_G02_TOP02_CHAIN_3R.
- G03 uses TOP_02_BRANCH and CTX_G03_TOP02_BRANCH_MID.
- G04 uses TOP_02_DUAL_TRANSIT and
  CTX_G04_TOP02_DUAL_TRANSIT.
- Every N0, C1, and C2 scenario inside one context must use the same
  group identifier.
- G02 is a three-router chain with r1 as observer and r2 as transit.
- G03 uses an interior observer at a real two-arm branch.
- G04 uses two live transit arms and a cross-segment C2 wrong next
  hop.
- All three contexts retain static routing and the current approved
  class semantics.
- Observation Profile v1, Evidence v2, and Dataset Row v2 remain
  unchanged.
- Design descriptors are frozen now; real SHA-256 artifact
  fingerprints are computed only after files exist.
- OSPF remains proposed and is not part of the first TOP-02
  implementation.
- ML training remains blocked.

## 3. Files created or changed

Created:

- docs/TOP02_CONTEXT_DESIGN.md
- docs/HANDOFF_P2_R3.md

Changed:

- docs/MASTER_CONTEXT.md
- docs/DECISIONS.md
- docs/STATUS.md
- docs/EVALUATION_GROUP_PROTOCOL.md

No implementation, test, schema, topology, scenario, dataset, or
historical artifact was changed.

## 4. Open issues

- Implement and test the G02 TOP_02_CHAIN laboratory.
- Produce the G02 baseline validator and N0/C1/C2 scenario files.
- Add the frozen G01 group binding to future TOP-01 campaign
  scenarios without rewriting historical data.
- Compute and record the G02 artifact SHA-256 fingerprint.
- Execute and semantically audit the real G02 smoke batch.
- Implement and test the design-frozen G03 and G04 contexts after
  G02.
- Design and implement the G05 TOP-03 asymmetric context.
- Execute the complete minimum 30-row campaign.
- Produce and audit the first valid D-058 split.
- Implement and evaluate the ML and hybrid methods.

## 5. Next step

Start P2-R4 — G02 TOP_02_CHAIN Implementation.

The implementation must:

- preserve the frozen G02 graph, roles, fault location, addresses,
  and split_group_id;
- add a complete baseline validator;
- add N0, C1, and C2 scenario bindings;
- verify the scenario and observation contracts before laboratory
  execution;
- preserve all TOP-01 regressions;
- execute one real three-scenario G02 smoke batch;
- verify Evidence v2 and Dataset Row v2 artifacts;
- verify rule-based exact-match results separately;
- verify complete restoration; and
- record the real artifact fingerprint.

Do not implement G03, G04, ML, or hybrid diagnosis in P2-R4.

## 6. Impact on central documents

- MASTER_CONTEXT records the frozen G01-G04 identifiers, the three
  reviewed TOP-02 designs, and the P2-R4 implementation order.
- DECISIONS adds D-059 without changing D-058.
- STATUS distinguishes completed design review from unimplemented
  laboratories and sets G02 implementation as the next milestone.
- EVALUATION_GROUP_PROTOCOL updates the matrix from planned labels to
  design-frozen contexts while retaining the five-context ML gate.
- TOP02_CONTEXT_DESIGN becomes the normative P2-R4 design source.
