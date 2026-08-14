# HANDOFF X0 — Scope and Compatibility Freeze

Date: 2026-08-14

Status: COMPLETE — X1 IS NEXT; RUNTIME REMAINS UNAUTHORIZED

## Accepted outcome

X0 converts the original ambitious project vision into a machine-readable,
testable, append-only expansion track while preserving Phase 6 through Phase 8
as the accepted frozen six-class baseline.

The canonical scope contains 24 detailed fault types across addressing,
Layer 2/VLAN, routing, services, security, and performance, plus the frozen
`no_fault` healthy class. Five fault types are frozen implemented, one has a
partial reusable mechanism, and eighteen remain missing.

The document's 23/24 inconsistency is resolved by retaining `vlan_missing`,
which is described in the detailed taxonomy but omitted from the later
prioritization list.

## Created artifacts

- `plans/expansion/X0_SCOPE_COMPATIBILITY_FREEZE_V1.json`;
- `schemas/x0_scope_compatibility_freeze_v1.schema.json`;
- `src/expansion/scope_gate.py`;
- `tests/unit/test_x0_scope_compatibility_gate.py`;
- `docs/X0_SCOPE_AND_COMPATIBILITY_FREEZE.md`; and
- this HANDOFF.

Central DECISIONS, MASTER_CONTEXT, STATUS, and ROADMAP documents record the
same boundary.

## Frozen compatibility boundary

- the exact six-class P6 order is unchanged;
- Evidence v3, Dataset Row v3, Phase 6 method schemas, P6 taxonomy, and P6-R6
  method protocol remain protected;
- accepted runtime/model/report artifacts and hashes remain unchanged;
- consumed E02/E06 report-only results cannot guide the expansion design;
- Phase 7 `/api/v1` remains the read-only baseline projection;
- D-085, D-091, and D-097 remain historical decisions rather than being
  rewritten; and
- P9-R1 remains paused by explicit user request.

## Runtime boundary

X0 authorizes no Containerlab execution, network mutation, evidence
collection, dataset generation, model fit or selection, estimator
deserialization, prediction, metric calculation, report-only test access, or
multiple-fault runtime.

The X0 implementation imports no project runtime, fault, model, or orchestration
module. It verifies design artifacts and protected tracked contract presence
only.

## Verification

- X0 scope and compatibility tests: 18/18 passed;
- targeted Phase 6 regression: 185/185 passed;
- H1 runtime-safety tests: 6/6 passed;
- clean-checkout full regression: 625 passed, 3 skipped; and
- machine-readable X0 gate: `VERIFIED`, 24 canonical fault types, X1 next.

The skips are explicit and expected: one opt-in Docker/Containerlab E2E and two
accepted-runtime checks whose ignored private artifacts are not materialized in
the clean verification tree. The real infrastructure lifecycle was already
verified separately after H1 and is not rerun or promoted to new evidence by
X0.

## Next milestone

X1 — Extended Contracts and Modular Collection.

X1 must define the versioned Topology Context, Evidence, Feature Catalog,
Feature Vector, Dataset Row, Diagnosis Result, and Evidence Mask contracts. It
must keep single-fault and future multiple-fault truth boundaries separate.
No new fault injection is authorized merely by this handoff.
