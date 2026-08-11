# P7-R3 Static Dashboard Implementation

Date: 2026-08-11

Status: IMPLEMENTED, TEST-VERIFIED, AND VISUALLY VERIFIED

## Purpose

P7-R3 adds the bounded browser presentation authorized by D-086 and
D-088. It displays the accepted P6-R6 projections; it does not execute a
diagnostic method or create an experimental result.

## Static same-origin architecture

`src/phase7/dashboard/` contains exactly:

- `index.html`, the semantic four-view document;
- `styles.css`, the local responsive and accessible presentation; and
- `app.js`, the dependency-free same-origin API client.

`src/phase7/api.py` mounts that dedicated directory after its six
versioned data routes. The data API remains exactly six `GET` operations.
The mount cannot expose files outside the Dashboard directory, and the
automatic FastAPI documentation routes remain disabled.

The application requires no React, Node build, package manager, CDN,
external font, image host, database, cloud service, telemetry system,
paid API, browser storage, or production deployment.

## Four implemented views

### Overview

The overview displays the 24 clean, 96 masked, and 120 total accepted
inputs; the six frozen classes; the Rule-based, Machine Learning, and
Hybrid method identities; and the descriptive-only boundary. It states
that masked inputs are deterministic transformations rather than new
independent experiments.

### Method comparison

The comparison switches among `clean`, `masked_overall`, and `overall`
through the existing API query. It displays the accepted metrics in both
compact bars and a semantic table. Percentages are rounded only for
display, with exact API values retained in presentation metadata. The UI
states that no statistical-superiority test was performed.

### Case explorer

The explorer uses only the frozen filters and deterministic pagination.
Each row shows the expected class and three accepted predictions. The
native detail dialog shows topology/direction fields, confidence where
defined, accepted explanation text, and the ten normalized feature and
availability values. A prediction-status filter remains disabled until
a method is selected, matching the API contract.

### Provenance and limitations

The final view presents the four verified root references, the 15-source
count, selected ML candidate, selected Hybrid policy, and every accepted
claim limitation. It does not offer raw downloads or arbitrary paths.

## Failure, safety, and accessibility behavior

Every projection has a visible loading state. API failure envelopes are
shown without paths or tracebacks and can be retried. A zero-result case
query has a distinct empty state. All browser requests use default
same-origin `GET`; no mutation method, WebSocket, external request,
upload, cookie, or browser-persistence path exists.

The document includes a skip link, semantic headings and landmarks,
table captions, accessible names, live status regions, visible keyboard
focus, reduced-motion handling, and a native detail dialog that closes
with its button, backdrop interaction, or `Escape`.

## Verification

Automated verification adds 10 P7-R3 tests covering:

- the exact three-file static asset set and local content types;
- preservation of the exact six-route data API;
- the four frozen views and unique accessible identifiers;
- same-origin GET-only behavior and absence of external dependencies;
- loading, empty, fail-closed error, and retry states;
- Dashboard availability while the API fails closed; and
- a complete static/UI/API read path with no estimator and unchanged
  hashes for all 15 fixture sources.

Browser verification checked the populated desktop view, comparison
scope switching, method/status filter dependency, empty and reset
states, case detail, corrected evidence-table layout, absence of desktop
horizontal overflow, the 390-pixel layout, and keyboard `Escape`
closing. The browser used a local contract-shaped fixture; it did not
recompute an accepted result.

Final verification:

- P7-R3 tests: 10/10;
- combined Phase 7 tests: 75/75;
- targeted Phase 6 regression: 185/185; and
- complete regression suite: 503/503.

The 48 full-suite warnings are existing NumPy/joblib deprecation
warnings. No Containerlab topology was started, estimator deserialized,
method executed, metric created, or accepted runtime source changed.

## Boundary and next step

P7-R3 does not establish production readiness, remote access security,
real-time diagnosis, statistical superiority, or generalization beyond
the controlled laboratory. P7-R4 may perform only the Phase 7 closeout
gate, local run instructions, and archive handoff without reopening the
interface or experiment.
