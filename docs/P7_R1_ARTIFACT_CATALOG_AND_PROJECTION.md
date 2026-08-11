# P7-R1 Artifact Catalog and Immutable Projection Layer

Date: 2026-08-11

Status: IMPLEMENTED AND TEST-VERIFIED

## 1. Purpose and boundary

P7-R1 implements the data boundary authorized by D-086 before any HTTP
or Dashboard code is allowed. It reads only the 15 JSON/JSONL sources in
the P7-R0 allowlist, verifies their accepted identities and transitive
references, joins the 120 report-only cases, and exposes deterministic
deep-immutable Python projections.

It does not start FastAPI or Uvicorn, render a UI, deserialize the
estimator, execute Rule/ML/Hybrid methods, read the source test split,
run Containerlab, calculate a new empirical metric, or write a runtime
artifact.

## 2. Integrity amendment

P7-R1 identified a concrete integrity gap in the P7-R0 design. The four
accepted root hashes bind the development freeze, independent receipt,
report-only run manifest, and descriptive comparison, but they do not
cryptographically anchor the gate file or every case, target,
prediction, and method-report source. Transitive-reference validation
alone could therefore accept coordinated drift of a non-root source and
its unanchored reference.

D-087 closes that gap with
`plans/phase7/P7_R1_ACCEPTED_ARTIFACT_CATALOG_V1.json`. The catalog is a
Git-tracked, deterministic binding of the artifact ID, canonical path,
role, SHA-256, and byte size of all 15 P7-R0 projection sources. The four
D-086 roots remain unchanged and are repeated as catalog root IDs. The
catalog is generated once only after the accepted roots, P6-R6 gate,
selection identities, report-only limits, 120-case contracts, joins,
method reports, and descriptive comparison all verify.

The catalog is metadata about the accepted runtime; it is not a 16th
projection source and contains no evidence, label, prediction, model,
or metric value.

## 3. Artifact catalog behavior

`src/phase7/catalog.py` implements a fail-closed loader with stable
`ARTIFACT_SET_UNAVAILABLE` and `ARTIFACT_INTEGRITY_FAILED` categories.
It:

- resolves only canonical fixed paths beneath the repository root;
- rejects symlinked, missing, non-UTF-8, invalid JSON, and blank-record
  JSONL sources;
- verifies the four accepted P7-R0 root SHA-256 values;
- verifies all 15 catalog SHA-256 and byte-size bindings;
- verifies gate-to-report, receipt-to-freeze/selection,
  run-to-freeze/selection, and report-to-input/target/prediction
  references;
- validates 120 Method Input v1 rows, 120 targets, and 120 predictions
  for each of the three fixed methods;
- verifies unique and order-aligned IDs, 24 clean plus 96 masked cases,
  all four masks per clean case, six-class balance, accepted method
  coverage boundaries, and report/comparison consistency; and
- records the estimator reference but never resolves, reads, imports,
  or deserializes the `.joblib` file.

After verification, every parsed mapping is a `MappingProxyType` and
every array is a tuple. The loader retains no writable alias to a parsed
artifact.

## 4. Projection behavior

`src/phase7/projections.py` implements data projections corresponding to
the six frozen route purposes without creating HTTP responses:

- health: readiness plus 4/4 root and 15/15 source counts;
- overview: accepted classes, methods, counts, selections, comparison
  type, and claim limitations;
- comparison: unchanged raw accepted values for `clean`,
  `masked_overall`, or `overall` in the frozen method order;
- case list: deterministic `input_id:asc` ordering, frozen filters, and
  page sizes from 1 to 100;
- case detail: normalized evidence, provenance, expected diagnosis, and
  the three already accepted predictions; and
- provenance: verified roots, selections, source count, and claim
  limitations.

The projection layer resolves a case ID only against the verified
in-memory index. Unknown and traversal-like strings never become file
paths. A prediction-status filter is rejected unless a method is also
specified.

## 5. Verification

P7-R1 tests prove:

- the 15-entry catalog schema and exact allowlist order;
- successful loading without an estimator file being present;
- deep immutability of inputs, targets, predictions, and documents;
- fail-closed behavior for missing, byte-drifted, path-rebound,
  reference-drifted, and join-drifted artifacts;
- exact readiness, selection, comparison, pagination, filtering, case
  detail, provenance, and limitation projections;
- rejection of invalid queries and traversal-like case IDs; and
- unchanged SHA-256 values for all 15 sources before and after catalog
  and projection operations.

The implementation adds no FastAPI dependency and starts no server.

The verified test totals are 23/23 P7-R1 tests, 33/33 combined Phase 7
tests, 185/185 targeted Phase 6 regression tests, and 461/461 tests in
the full suite. The full-suite warnings in the isolated verification
environment are historical scikit-learn deprecation warnings and do not
originate from the Phase 7 loader or projections.

## 6. Next milestone

P7-R2 may implement the six FastAPI `GET` routes and the frozen success,
error, validation, and method-not-allowed envelopes over this projection
layer. It must not bypass the catalog, add a route, serve arbitrary
files, deserialize the model, execute diagnosis, or write artifacts.
