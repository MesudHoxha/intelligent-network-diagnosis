# HANDOFF — P2-R7 G05 TOP-03 Asymmetric Context Design Review

Date: 2026-07-31
Status: COMPLETED

## 1. What was completed

- Audited D-058, D-059, D-060, D-061, D-062, the verified G02-G04
  designs and runtime results, Observation Profile v1, Evidence v2,
  Dataset Row v2, the Collector, and the current C1/C2 injectors.
- Converted G05 from a planned asymmetric coverage label into one
  concrete static-routing design.
- Froze TOP_03_ASYMMETRIC_RETURN and
  CTX_G05_TOP03_ASYMMETRIC_RETURN.
- Froze the physical r1-r2-r3-r4-r1 router cycle.
- Froze HostA-to-HostB forwarding through r1-r2-r3 and return
  forwarding through r3-r4-r1.
- Froze hosta_to_hostb with observer r2 and transit r3.
- Froze C1/C2 on the r2 route toward 10.50.3.0/24.
- Froze 10.50.23.2 as the correct next hop and unassigned
  10.50.23.6 as the C2 wrong next hop.
- Defined the addressing, forward/return routes, evidence producers,
  baseline assertions, runtime distinction audit, and scenario
  acceptance rules.
- Recorded a semantic design fingerprint and an explicit distinction
  audit against G01-G04.

No topology, validator, scenario, test, source-code, schema,
laboratory experiment, evidence artifact, dataset row, split, or
runtime artifact hash was created in P2-R7.

## 2. What was decided

- D-063 freezes G05 as the first TOP-03 asymmetric context design.
- G05's material distinction is forward/return path divergence, not
  address variation, node renaming, or nominal direction reversal.
- R2 is traversed only on the selected forward path and produces the
  route evidence.
- R4 is traversed only on the selected return path and is validated
  outside Dataset Row v2.
- Strict reverse-path filtering must be disabled on the asymmetric
  routed path.
- Fault-state return-corridor proof uses route lookups and
  adjacent-hop reachability, because a reverse end-to-end ping still
  needs an echo reply through the intentionally faulty forward path.
- Observation Profile v1, Evidence v2, Dataset Row v2, and the seven
  approved features remain unchanged.
- Static routing and the complete no_fault, missing_static_route,
  and wrong_next_hop class set remain in force.
- No real SHA-256 is recorded until implementation artifacts exist.
- ML and hybrid diagnosis remain blocked.

## 3. Files created or changed

Created:

- docs/TOP03_CONTEXT_DESIGN.md
- docs/HANDOFF_P2_R7.md

Changed:

- docs/MASTER_CONTEXT.md
- docs/DECISIONS.md
- docs/STATUS.md
- docs/ROADMAP.md
- docs/EVALUATION_GROUP_PROTOCOL.md
- docs/TOP02_CONTEXT_DESIGN.md

No implementation, test, schema, topology, scenario, dataset, or
historical artifact was changed.

## 4. Open issues

- Implement and verify the frozen G05 laboratory in P2-R8.
- Produce the G05 baseline validator and N0/C1/C2 scenario files.
- Prove the forward/return divergence in the real laboratory.
- Compute and record the real G05 artifact SHA-256.
- Execute and semantically audit the real G05 smoke batch.
- Bind future G01 campaign scenarios to
  CTX_G01_TOP01_LINEAR_2R without rewriting historical artifacts.
- Execute two repetitions per class and context for the minimum
  30-row campaign.
- Produce and audit the first valid D-058 grouped split.
- Add missing-evidence, unseen-context, and controlled multi-fault
  experiments only after the base context campaign.
- Implement and compare ML and hybrid methods only after the
  readiness gate passes.

## 5. Next step

Start P2-R8 — G05 TOP_03_ASYMMETRIC_RETURN Implementation.

The implementation must:

- preserve the frozen graph, identifiers, addresses, routes, roles,
  and fault target;
- configure and verify reverse-path filtering for asymmetric
  forwarding;
- add a complete baseline validator;
- add N0, C1, and C2 bindings with the shared frozen group;
- add contract, topology, and cross-context distinction tests;
- preserve all TOP-01 and G02-G04 regressions;
- execute separate C1/C2 forward/return distinction audits;
- execute one real three-scenario smoke batch;
- validate Evidence v2 and Dataset Row v2;
- verify rule-based exact match separately;
- verify restoration and final baseline;
- clean up the laboratory; and
- record the real artifact fingerprint.

Do not start the expanded campaign, ML training, or hybrid diagnosis
inside the G05 implementation commit.

## 6. Impact on central documents

- MASTER_CONTEXT records the frozen G05 design while keeping it
  explicitly unimplemented.
- DECISIONS adds D-063 without changing D-058 or weakening the ML
  readiness gate.
- STATUS records the completed design review and sets P2-R8 as the
  next milestone.
- ROADMAP separates completed G05 design work from pending
  implementation.
- EVALUATION_GROUP_PROTOCOL replaces the planned G05 label with its
  frozen identifier and causal distinction.
- TOP02_CONTEXT_DESIGN cross-references the separate normative
  TOP-03 design instead of expanding TOP-02 scope.
- TOP03_CONTEXT_DESIGN becomes the normative source for P2-R8.
