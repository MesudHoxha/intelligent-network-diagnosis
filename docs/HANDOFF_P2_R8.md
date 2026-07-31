# HANDOFF — P2-R8 G05 TOP-03 Asymmetric Context Implementation

Date: 2026-07-31
Status: COMPLETED

## 1. What was completed

- Implemented the frozen TOP_03_ASYMMETRIC_RETURN Containerlab
  topology with the r1-r2-r3-r4-r1 routed cycle.
- Implemented the selected forward path
  hosta-r1-r2-r3-hostb and the distinct return path
  hostb-r3-r4-r1-hosta.
- Configured and verified IPv4 forwarding and disabled reverse-path
  filtering on the asymmetric routed interfaces.
- Added the 52-check G05 baseline validator.
- Added N0, C1, and C2 scenario bindings sharing
  CTX_G05_TOP03_ASYMMETRIC_RETURN.
- Added the P2_G05_SMOKE fail-stop plan.
- Added static contract, topology, reverse-path-filter, and
  cross-context distinction tests.
- Passed 7/7 targeted G05 tests and the complete 155/155 regression
  suite.
- Verified the initial and final G05 baselines as 52/52 VALID.
- Verified the baseline forward/return distinction, C1 asymmetric
  isolation, C2 same-segment wrong-next-hop behavior, restoration,
  and runtime distinction.
- Completed the real three-scenario batch and audited Evidence v2,
  Dataset Row v2, role binding, feature semantics, and exact match.
- Destroyed the laboratory successfully after verification.
- Bound the normalized G05 artifact bundle to SHA-256
  6bd4de9818ba0c3b589e5a17cf47553f523fc743d6feb12334bd525ea79ca870.

Accepted batch run:

p2_g05_smoke-20260731T083408705159Z-
4badf5fdf6da4141af74af11d4b5f1a2

## 2. What was decided

- D-064 accepts G05 as the first implemented and verified
  asymmetric-return evaluation context.
- The frozen r2 forward-only observer and r4 return-only corridor
  remain the material causal distinction.
- Fault-state return-corridor health is proven through route lookups
  and adjacent-hop reachability, not through a reverse end-to-end
  echo reply that would depend on the intentionally faulty forward
  path.
- Reverse-path-filter configuration is part of the required G05
  baseline and runtime contract.
- Observation Profile v1, Evidence v2, Dataset Row v2, and the seven
  approved model features remain unchanged.
- The real G05 smoke rows are valid experimental artifacts but are
  not by themselves an ML training dataset.
- Historical rows and split_group_id values remain unchanged.
- ML and hybrid diagnosis remain blocked until the expanded campaign
  and grouped split pass.

## 3. Files created or changed

Created implementation files:

- labs/topologies/top03_asymmetric_return/topology.clab.yml
- labs/topologies/top03_asymmetric_return/scripts/validate_baseline.sh
- plans/batches/P2_G05_SMOKE.yml
- scenarios/routing/N0_NORMAL_OPERATION_TOP03_ASYMMETRIC_RETURN.yml
- scenarios/routing/C1_MISSING_STATIC_ROUTE_TOP03_ASYMMETRIC_RETURN.yml
- scenarios/routing/C2_WRONG_NEXT_HOP_TOP03_ASYMMETRIC_RETURN.yml
- tests/unit/test_p2_r8_top03_asymmetric_return.py

Created closeout document:

- docs/HANDOFF_P2_R8.md

Changed central documents:

- docs/MASTER_CONTEXT.md
- docs/DECISIONS.md
- docs/STATUS.md
- docs/ROADMAP.md
- docs/EVALUATION_GROUP_PROTOCOL.md
- docs/TOP03_CONTEXT_DESIGN.md

Runtime experiment, evidence, batch metadata, and processed dataset
artifacts remain outside the implementation commit.

## 4. Open issues

- Create reviewed future G01 N0/C1/C2 bindings using
  CTX_G01_TOP01_LINEAR_2R without rewriting historical artifacts.
- Define and validate the consolidated five-context campaign with
  two repetitions per class and context.
- Execute the minimum 30-row Dataset Row v2 campaign.
- Produce and audit the first valid D-058 3/1/1 grouped split.
- Implement the ML baseline only after the readiness gate passes.
- Implement and compare the hybrid method only after the ML baseline.
- Add missing-evidence, unseen-context, and controlled multi-fault
  experiments only after the base campaign.
- Keep OSPF proposed until a separate reviewed extension stage.

## 5. Next step

Start P2-R9 — Expanded Campaign Binding and Plan Review.

P2-R9 must:

- preserve all historical scenarios and rows;
- create explicit future G01 bindings using
  CTX_G01_TOP01_LINEAR_2R;
- reference the frozen G02-G05 scenarios without changing their
  group identifiers;
- define the exact five-context, three-class, two-repetition
  30-experiment sequence;
- validate complete class coverage and repetition counts per group;
- keep failure_policy=stop and Dataset Row v2;
- define the post-run grouped-split audit; and
- stop before real campaign execution, ML training, or hybrid
  diagnosis.

## 6. Impact on central documents

- MASTER_CONTEXT records G05 as implemented and runtime-verified,
  including its accepted batch and artifact hash.
- DECISIONS adds D-064 without changing D-058 or weakening the ML
  readiness gate.
- STATUS records P2-R8 results and moves the next milestone to the
  expanded campaign binding and plan review.
- ROADMAP marks G05 complete and identifies the campaign as the next
  Phase 2 target.
- EVALUATION_GROUP_PROTOCOL records G05 as the fourth verified
  non-G01 complete-class smoke context.
- TOP03_CONTEXT_DESIGN records the real implementation, batch,
  tests, and artifact fingerprint while preserving the frozen design.
