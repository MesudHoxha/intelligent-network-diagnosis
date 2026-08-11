# HANDOFF P7-R1

Date: 2026-08-11

Status: COMPLETED — ARTIFACT CATALOG AND PROJECTION LAYER VERIFIED

## 1. What was completed

P7-R1 implemented the fail-closed 15-source artifact catalog, a
Git-tracked immutable SHA-256/size binding for every projection source,
deep-frozen in-memory joins for 120 cases, and deterministic Python
projections for all six P7-R0 route purposes. Missing artifacts, byte
drift, reference drift, join drift, invalid filters, and unknown case
IDs are rejected.

Verification passed 23/23 P7-R1 tests, 33/33 combined Phase 7 tests,
185/185 targeted Phase 6 tests, and 461/461 full regression tests.

## 2. What was decided

D-087 records that the four P7-R0 roots remain the accepted scientific
identities but are insufficient by themselves to anchor every non-root
case and prediction source. A separate versioned catalog now binds all
15 allowed sources. The catalog is trusted only because it is generated
after full accepted-graph verification and committed with the P7-R1
implementation.

The estimator remains outside the catalog. Its reference is
structure-checked, but its path is never resolved or read. P7-R1 adds no
server, route, UI, inference, metric, network command, or runtime write.

## 3. Files created or changed

- `src/phase7/__init__.py` exports the Phase 7 data boundary;
- `src/phase7/catalog.py` implements catalog generation, verification,
  immutable loading, and semantic joins;
- `src/phase7/projections.py` implements deterministic immutable data
  projections;
- `schemas/p7_accepted_artifact_catalog_v1.schema.json` validates the
  catalog structure;
- `plans/phase7/P7_R1_ACCEPTED_ARTIFACT_CATALOG_V1.json` binds the real
  15-file accepted source set and is generated during closeout;
- `tests/unit/p7_r1_fixtures.py` builds a synthetic accepted boundary
  with no estimator file;
- `tests/unit/test_p7_r1_catalog.py` verifies integrity and failure
  semantics;
- `tests/unit/test_p7_r1_projections.py` verifies immutable projections,
  filters, pagination, errors, and zero source writes;
- `docs/P7_R1_ARTIFACT_CATALOG_AND_PROJECTION.md` documents the
  implementation;
- `docs/HANDOFF_P7_R1.md` records this handoff; and
- `docs/DECISIONS.md`, `docs/MASTER_CONTEXT.md`, `docs/ROADMAP.md`, and
  `docs/STATUS.md` advance the shared project state.

No P6-R6 runtime source, estimator, source test split, topology,
scenario, evidence, prediction, report value, or metric is changed.

## 4. Open issues

- implement and test the six FastAPI GET routes over the projection
  layer in P7-R2;
- normalize framework validation and 405 behavior to the frozen error
  contract;
- implement and visually verify the four static Dashboard views only
  after P7-R2 closes; and
- define the final archive/publication policy for generated runtime
  artifacts before thesis archiving.

## 5. Next step

P7-R2 is next. It may add FastAPI/Uvicorn dependencies and implement
only the six frozen GET routes, response envelopes, error mapping, local
binding, and method rejection over `ProjectionLayer`. Dashboard HTML,
CSS, and JavaScript remain blocked until P7-R3.

## 6. Impact on central documents

- `DECISIONS.md`: adds D-087 and the complete 15-source binding;
- `MASTER_CONTEXT.md`: records the verified catalog and immutable
  projection architecture;
- `STATUS.md`: marks P7-R1 complete and P7-R2 next; and
- `ROADMAP.md`: advances Phase 7 from the data boundary to the API
  implementation gate.
