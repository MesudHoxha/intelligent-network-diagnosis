# P7-R0 Dashboard/API Scope and Read-Only Contract

Date: 2026-08-11

Status: FROZEN FOR IMPLEMENTATION

## 1. Purpose and decision boundary

P7-R0 freezes the presentation boundary for the accepted P6-R6 result.
The Dashboard and API are a local read-only projection layer, not a new
diagnostic method or experimental runtime. They may present accepted
evidence states, ground truth, method predictions, descriptive metrics,
provenance, and limitations without altering their source artifacts.

P7-R0 creates no server, UI, prediction, metric, dataset row, model, or
network evidence. It does not reopen the consumed E02/E06 report-only
authorization. Implementation begins only in P7-R1.

## 2. Frozen local architecture

The API will use FastAPI served by Uvicorn and bind by default only to
`127.0.0.1`. The Dashboard will use static HTML, CSS, and JavaScript
served from the same local application. It will not require React,
Node.js, a database, a cloud deployment, an external CDN, telemetry, or
a paid service.

All visual assets must be stored in the repository. The browser may use
only same-origin `GET` requests. Network access outside the local server
is not part of the accepted application path.

## 3. Accepted artifact boundary

The application must verify these accepted root bindings before it can
report `READY`:

| Root | Path | Accepted SHA-256 |
| --- | --- | --- |
| Development freeze | `models/p6_r6_six_class_v1/freeze_manifest.json` | `fa98a17e2ffae42f6dd009a13af65ad32174035eca8352bf26f321531a4fe0f5` |
| Independent receipt | `models/p6_r6_six_class_v1/freeze_receipt.json` | `5c6c6537cb233efdeb52c6872f7a6ef7fb32eb3ac7b2474e2514b2908cd29bcc` |
| Report-only run | `reports/experiments/p6_r6_six_class_v1/run_manifest.json` | `44c505b451c6211b4515564f4b889633b6d74ed0c618f19cc0ab3b9bdfe72b1d` |
| Descriptive comparison | `reports/experiments/p6_r6_six_class_v1/cross_method_comparison.json` | `ca1c15d04828c0ae61cacaf80a5ee6f49f64a9cf3ac151a4b4ccd2386987e570` |

The exact 15-file projection allowlist is machine-readable in
`plans/phase7/P7_R0_READ_ONLY_INTERFACE_V1.json`. It contains the gate,
four safe freeze/selection JSON files, and the ten report-only JSON/JSONL
files. Every transitive artifact reference must match its declared
SHA-256 before any projection is served.

The selected estimator is not deserialized or served. Development
train/validation inputs, the source split test file, arbitrary paths,
and raw file downloads are outside the runtime allowlist. A case ID is
resolved only against a verified in-memory index and never converted
into a filesystem path.

## 4. Frozen API surface

The data API has exactly six versioned `GET` routes:

| Route | Purpose |
| --- | --- |
| `/api/v1/health` | Report readiness after complete artifact verification. |
| `/api/v1/overview` | Present the accepted class/method identities, counts, selections, and limitations. |
| `/api/v1/comparison` | Present unchanged accepted metrics for `clean`, `masked_overall`, or `overall`. |
| `/api/v1/cases` | List and filter the 120 accepted report-only inputs with deterministic pagination. |
| `/api/v1/cases/{input_id}` | Present one input's normalized evidence, target, and three accepted predictions. |
| `/api/v1/provenance` | Present verified root hashes, selection identities, and claim limits. |

`POST`, `PUT`, `PATCH`, and `DELETE` are not defined. There is no generic
artifact route, file path parameter, model-download route, inference
route, experiment route, remediation route, or command route. The exact
request/response structures are frozen in
`contracts/api/p7_readonly_api_v1.openapi.yml`.

All successful JSON responses carry schema version 1 and metadata that
identifies `p7_readonly_dashboard_api_v1`, the read-only mode, and the
accepted P6-R6 report-only source role. The implementation must preserve
the raw accepted numeric values. Display rounding may occur only in the
Dashboard and must not replace the API values.

Case listing sorts by `input_id` ascending. Pagination defaults to page
1 and 25 items and allows at most 100 items. The frozen filters are
context, expected fault type, mask, method, and prediction status. A
prediction-status filter without a method is invalid because status is
method-specific.

## 5. Dashboard views

The Dashboard contains four bounded views:

1. **Overview** — accepted dataset/test counts, six classes, three
   methods, selected ML/Hybrid identities, and the descriptive-only
   result boundary.
2. **Method comparison** — the accepted clean, masked, and overall
   metrics for Rule-based, ML, and Hybrid, including coverage and
   insufficient-evidence rate.
3. **Case explorer** — filterable report-only cases with evidence
   availability, expected diagnosis, three method outputs, confidence
   where defined, and explanation text already present in predictions.
4. **Provenance and limitations** — verified root hashes, report-only
   role, absence of statistical superiority testing, equality of ML and
   Hybrid aggregate results, and the non-generalization warning.

No chart or interface text may imply that masked copies are independent
experiments, that Hybrid outperformed ML, or that the controlled results
establish real-world accuracy.

## 6. Failure and integrity semantics

The application fails closed. Missing accepted files return
`ARTIFACT_SET_UNAVAILABLE`; a hash or transitive-reference mismatch
returns `ARTIFACT_INTEGRITY_FAILED`. Neither condition may fall back to
unverified data. Invalid filters return `INVALID_QUERY`, and an unknown
input ID returns `CASE_NOT_FOUND`.

Unexpected failures return `INTERNAL_ERROR` without exposing absolute
paths, tracebacks, environment values, or artifact content. Framework
validation must be normalized to the frozen error envelope rather than
leaking FastAPI's default response shape. Unsupported mutating methods
must return `METHOD_NOT_ALLOWED` or the equivalent HTTP 405 response
without executing application logic.

## 7. Prohibited behavior

The interface layer must not:

- write to project artifacts or create a cache inside accepted paths;
- import or invoke fault injection, orchestration, collection, Docker,
  Containerlab, shell, or subprocess control;
- deserialize the selected estimator or run Rule, ML, or Hybrid
  prediction functions;
- fit, refit, select, tune, or change a threshold or policy;
- calculate a new empirical performance or superiority statistic;
- expose arbitrary repository files or accept filesystem paths; or
- provide production execution or automatic remediation.

Derived presentation operations such as filtering, pagination, and
sorting are permitted because they do not create an empirical claim.

## 8. Acceptance criteria for implementation

Later implementation gates must prove at least:

- contract and OpenAPI validation;
- exact 4/4 root and 15/15 projection-source integrity checks;
- refusal on a missing or byte-drifted artifact;
- deterministic joins across 120 inputs, 120 targets, and 120
  predictions for each method;
- exact route and error-envelope conformance;
- rejection of unsupported methods, invalid filters, traversal-like
  IDs, and arbitrary paths;
- zero writes and unchanged source-artifact hashes before and after API
  and Dashboard tests;
- local same-origin operation with no external asset dependency; and
- accurate display of the accepted P6-R6 metrics and limitations.

## 9. Next milestone

P7-R1 is the artifact-catalog and projection milestone. It may implement
only a fail-closed loader, integrity verifier, immutable in-memory view,
and deterministic projections under this contract. FastAPI routes and
Dashboard rendering remain blocked until that data boundary passes its
own tests.
