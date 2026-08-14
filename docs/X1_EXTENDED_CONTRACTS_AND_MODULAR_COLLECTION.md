# X1 — Extended Contracts and Modular Collection

Date: 2026-08-14

Status: COMPLETE — X2 IS NEXT; NEW FAULT RUNTIME REMAINS UNAUTHORIZED

## 1. Objective

X1 introduces the append-only contract family required by the ambitious
technical expansion before any new fault data is collected. It does not alter
the accepted Phase 6/7/8 baseline, resume P9-R1, or authorize a new empirical
claim.

The release separates topology context, modular collector provenance,
versioned feature semantics, and single-fault dataset/diagnosis truth.

## 2. Versioned contract family

| Contract | Purpose | Boundary |
| --- | --- | --- |
| Topology Context v1 | Nodes, links, roles, variants, and capabilities | Context only |
| Collector Run v1 | Per-module status, features, raw hashes, and errors | No executor |
| Evidence v4 | Modular observations and collector-run provenance | Single-fault compatible |
| Feature Catalog v1 | Stable feature IDs, types, domains, and lifecycle | 39 entries |
| Feature Vector v2 | Typed values, availability, mask, and source hashes | No model input yet |
| Dataset Row v4 | Grouped single-fault row and quality/provenance | Single fault only |
| Diagnosis Result v2 | Ranked Rule/ML/Hybrid v2 result or abstention | Single fault only |
| Evidence Mask Plan v2 | Validation/report-only robustness masks | Mask ID is not a predictor |

All eight schemas are new files. Evidence v3, Dataset Row v3, and the Phase 6
method schemas are unchanged and remain protected by exact SHA-256 values.

## 3. Feature Catalog v1

The catalog contains 39 typed features:

- 10 exact frozen Evidence v3 feature IDs;
- 29 planned extension features;
- 2 connectivity, 7 addressing, 6 Layer 2/VLAN, 8 routing, 8 services,
  2 security, and 6 performance features.

Planned entries define stable semantics for X2 through X6 without claiming
that a probe, injector, topology, dataset row, or diagnosis already exists.
Changing the meaning of a catalog entry requires a new catalog version.

## 4. Modular collection boundary

`src.collection.modular_registry` contains metadata only. Seven collector
specifications provide exactly one owner for every catalog feature:

- the read-only Evidence v3 compatibility adapter;
- addressing state;
- Layer 2/VLAN state;
- DHCP/DNS/service state;
- service-policy state;
- OSPF state; and
- performance state.

The registry has no command executor, Docker import, subprocess call, network
mutation, or persistence API. Its planner returns deterministic collector keys
and capability gaps. Every plan explicitly records
`runtime_authorized=false`.

Concrete collector implementations require the corresponding X2–X6 design
and runtime gate.

## 5. Read-only Evidence v3 compatibility

The adapter validates accepted Evidence v3, requires the exact source-artifact
SHA-256 from the caller, and creates a new in-memory Evidence v4 projection.
It preserves all ten baseline feature IDs, values, availability states, raw
paths, and raw hashes. It does not overwrite, normalize in place, or persist
the source artifact.

The separate Feature Vector v2 projector remains in memory and binds its
output to Evidence and Feature Catalog hashes.

## 6. Availability and mask semantics

Evidence v4 distinguishes `observed`, `structurally_unavailable`,
`collection_unavailable`, and `not_requested`. Feature Vector v2 additionally
permits `masked_missing`; a mask ID is required if and only if a value is
masked.

Evidence Mask Plan v2 preserves the four frozen Phase 6 masks and adds
domain-level plans for addressing, duplicate-IP temporal evidence, VLAN
access/trunk state, DHCP, DNS, service policy, OSPF, and performance. Masks are
allowed only for validation and report-only robustness evaluation. Their
identity is never a predictor.

## 7. Truth boundary

Dataset Row v4 and Diagnosis Result v2 are explicitly single-fault contracts.
They cannot encode an array of labels or a multiple-fault truth model.

Selected multiple faults remain deferred to Dataset Row v5 and Diagnosis
Result v3, where injected, effective, and diagnosable fault sets will be
separate. X1 therefore does not force later multi-label semantics into the
single-fault expansion dataset.

## 8. Compatibility and runtime boundary

X1 preserves:

- the six-class Phase 6 order;
- the exact protected v3 and Phase 6 method files;
- accepted runtime/model/report artifacts and hashes;
- consumed E02/E06 report-only isolation;
- Phase 7 `/api/v1` as the frozen read-only baseline; and
- P9-R1 as paused by explicit user request.

Any future extended interface belongs under `/api/v2`.

All ten X1 runtime authorization flags are false. X1 performs no Containerlab
deployment, network mutation, new evidence collection, dataset generation,
model fit, estimator deserialization, prediction, metric calculation,
report-only access, or multiple-fault execution.

## 9. Acceptance gate

X1 acceptance requires:

- all eight schemas to validate as Draft 2020-12;
- semantic contract and fail-closed mutation tests;
- read-only Evidence v3 to v4 adapter tests;
- modular registry composition tests;
- exact protected-file hashes;
- the permanent Phase 6 regression;
- the complete clean-checkout regression; and
- the existing opt-in real Containerlab lifecycle E2E.

The infrastructure test is a regression of the already accepted Phase 6
lifecycle. It does not create X1 evidence or authorize a new fault.

## 10. Next milestone

After X1 is accepted, X2 may design and implement addressing vertical slices:
wrong IP address, wrong subnet mask, missing default route, and duplicate IP.
Each slice still requires its own injector, collector behavior, rule signature,
real evidence, restoration test, and explicit runtime gate.

The release gate passed 29/29 X1 tests, 18/18 X0 tests, 185/185 targeted
Phase 6 tests, 6/6 H1 tests, 175/175 Phase 7-through-9 tests, 656 passed with
one explicit infrastructure skip in the materialized suite, and 654 passed
with three explicit skips in a clean clone. The existing real Containerlab
lifecycle regression passed separately 1/1 before commit.
