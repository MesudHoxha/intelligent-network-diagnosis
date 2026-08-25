# ROADMAP

## Phase 0 — Project foundation
Status: In progress

- Central documents
- Repository
- Local environment
- Initial architecture

## Phase 1 — End-to-end proof of concept
Status: Completed

- Deploy TOP-01
- Validate normal routing
- Inject missing-route fault
- Collect evidence
- Produce rule-based diagnosis
- Evaluate against ground truth

## Phase 2 — Pilot multiclass dataset
Status: Completed

- Dataset artifact contracts: completed and tested
- Normal: canonical, alternate-subnet, G02, G03, G04, and G05 smoke
  executions completed
- Missing route: canonical, alternate-subnet, G02, G03, G04, and G05
  smoke executions completed
- Wrong next-hop: canonical, alternate-subnet, G02, G03, G04, and G05
  smoke executions completed
- Batch Plan v1 contract and canonical smoke plan: completed
  and tested
- Reproducible batch runner and dataset aggregation: implemented,
  tested, and verified through the first real canonical smoke batch
- Canonical B0 smoke batch: completed and semantically verified;
  three-row smoke dataset generated
- Complete evaluation-context-aware splitting: implemented, tested,
  and verified through the first valid five-context split
- G02 TOP_02_CHAIN: implemented and smoke-verified
- G03 TOP_02_BRANCH: implemented and smoke-verified
- G04 TOP_02_DUAL_TRANSIT: implemented and smoke-verified
- G05 TOP_03_ASYMMETRIC_RETURN: implemented and smoke-verified
- Five-context two-repetition campaign: G01 bindings, five context
  batches, Dataset Campaign Plan v1, and deterministic split
  precommitment completed and tested
- Cross-topology campaign coordinator: implemented and tested
- Real P2_ROUTING_5CTX_V1 campaign: 30/30 experiments completed and
  independently audited
- Atomic merged Dataset Row v2 dataset: 30 rows accepted
- Rule-based campaign reference audit: 30/30 exact matches and
  affected-prefix checks
- First valid five-context split: completed with 18/6/6 rows,
  3/1/1 groups, and no cross-partition group
- Wrong gateway: deferred to Phase 6
- Interface down: deferred to Phase 6
- ACL block: deferred to Phase 6

## Phase 3 — Rule-based baseline
Status: Completed

- Existing deterministic rule engine retained as the traditional
  baseline
- Campaign reference audit completed separately from model features
- Formal Method Evaluation Protocol v1: frozen
- Method Evaluation Result v1 runtime contract and JSON Schema:
  implemented and tested
- Shared partition roles and comparable per-class/macro metrics:
  implemented and tested
- P2-R10 rule-audit adapter with hashed evidence and explanation
  provenance: implemented and tested
- Real 30-record partition-aware rule-based result: completed and
  independently verified
- Train/validation/test accuracy and macro F1: 1.0/1.0/1.0 under the
  frozen controlled campaign
- Report SHA-256 and 150/150 source-artifact bindings: recorded
- P3-R0 closeout and HANDOFF: completed

## Phase 4 — Machine Learning baseline
Status: Completed

- Leakage-safe ML experiment protocol and feature-matrix contract:
  implemented and verified against the real D-067 artifacts
- Lossless seven-tri-state to 14-binary-column transformation:
  implemented and tested
- Predictor leakage gates and immutable partition roles: implemented
  and tested
- Bounded logistic-regression and shallow-tree candidate set:
  precommitted before fitting
- Real 30-record ML Feature Matrix v1: completed and independently
  verified
- Matrix SHA-256, 30/30 source-row bindings, and ten structural
  unavailable values: recorded
- P4-R0 closeout and HANDOFF: completed
- Train-only candidate fitting and validation-only selection
  implementation: completed and covered by 10 targeted tests and
  the 205-test regression suite
- Atomic ML Pipeline Selection v1 and selected-estimator freeze:
  executed and independently hash-verified
- Independent model/selection hash gate before test access:
  executed successfully before G02 access
- Evidence-bearing ML predictions with model-specific explanation:
  completed for 30/30 rows
- Selected candidate: logreg_l2_c0_1
- Single report-only G02 evaluation: completed without refit
- Fault-type accuracy and macro-F1: 1.0/1.0/1.0 on
  train/validation/test for the frozen controlled campaign
- Exact-diagnosis rate: 1/3 per partition; affected-prefix rate: 0.0,
  exposing the independent classifier's localization boundary
- Method Evaluation Result v1 ML report, selection SHA-256, model
  SHA-256, and 150/150 source-artifact bindings: recorded
- P4-R1 closeout and HANDOFF: completed

## Phase 5 — Hybrid diagnosis
Status: Completed

- P5-R0 Hybrid Diagnosis Policy v1 design: frozen and locally
  runtime-verified
- Accepted D-069 and D-073 artifact/hash bindings: encoded without
  changing either baseline
- Prediction-time label, ground-truth, partition, evaluation, and
  test leakage boundary: encoded
- Candidate set: consensus_abstain_v1 and
  rule_guarded_fallback_v1
- Agreement, disagreement, non-final-input, localization, prefix,
  explanation, and integrity-failure behavior: precommitted
- Validation-only candidate selection and deterministic tie-break
  order: precommitted for P5-R1
- Abstention-aware future evaluation and seven-reference hybrid
  provenance contract: precommitted
- Hybrid Policy v1 JSON Schema and semantic validator: implemented
  and verified with 11/11 targeted and 216/216 regression tests
- Policy SHA-256 and five accepted baseline artifact bindings:
  independently verified without baseline mutation
- Hybrid predictions, candidate selection, hybrid metrics, and G02
  access: absent in P5-R0
- P5-R0 closeout and HANDOFF: completed
- P5-R1 candidate implementation, Hybrid Prediction/Selection
  schemas, abstention-aware evaluator, and independent verifier:
  implemented and runtime-verified
- P5-R1 validation-only run: 48 predictions, 48 evaluations, two
  manifests, and 99 runtime JSON files; no test output
- P5-R1 selected candidate: consensus_abstain_v1 by the frozen
  complexity tie-break after equal train/validation metrics
- P5-R1 selected-policy SHA-256 and independent freeze verification:
  completed
- P5-R1 tests: 14/14 targeted and 229/229 full regression passed
- P5-R1 HANDOFF and closeout: completed
- P5-R2 report coordinator, Cross-Method Comparison v1 schema, and
  independent verifier: implemented and isolated-test verified
- P5-R2 tests: 14/14 targeted and 243/243 full regression passed on
  synthetic boundary fixtures
- P5-R2 real frozen-policy G02 report-only evaluation: completed and
  independently verified
- Complete 30-row hybrid Method Evaluation Result v1 with 210/210
  source-artifact bindings: completed
- Descriptive Rule-based vs Machine Learning vs Hybrid comparison:
  completed without a statistical-superiority claim
- P5-R2 closeout and HANDOFF: completed

## Phase 6 — Extended fault taxonomy
Status: Complete

- P6-R0 bounded six-class fault taxonomy: frozen and
  contract-verified
- Canonical new labels: wrong_default_gateway, interface_down, and
  acl_block
- Planned Evidence v3 and Dataset Row v3 ten-feature boundary: frozen
- Six complete contexts, two repetitions, and 72-row clean campaign:
  precommitted
- Explicit whole-context split: 36/12/24 rows across 3/1/2 groups
- Two unseen report-only test contexts: precommitted
- Four deterministic missing-evidence masks: precommitted
- P2-P5 datasets and method artifacts: immutable references
- Multiple-fault execution: deferred pending a separate multi-label
  design gate
- P6-R0 Containerlab execution, new dataset, training, predictions,
  and metrics: absent
- P6-R1 Observation Profile v2, Evidence v3, and Dataset Row v3
  runtime validators and strict JSON Schemas: completed
- Exact ten-feature predictor whitelist and raw-probe SHA-256
  provenance: implemented and contract-tested
- Structural unavailable, collection unavailable, and masked-missing
  semantics: implemented without imputation
- Backwards-compatible Observation v1/v2, Evidence v2/v3, and Dataset
  Row v1/v2/v3 dispatch: implemented and tested
- Dataset Row v2 runtime default retained until collector v3 closeout
- P6-R1 targeted tests: 57/57 passed
- Full automated regression suite: 316/316 passed in isolated
  verification
- P6-R1 Containerlab execution and Phase 6 runtime artifacts: absent
- P6-R2 separate Evidence v3 collector and bounded raw probes:
  implemented and synthetic-test verified
- Atomic raw/v3 command artifacts and per-feature SHA-256 provenance:
  implemented
- Fail-safe route, gateway, interface-state, and exact flow-policy
  parsing: implemented
- Observed route absence separated from route-probe collection failure:
  implemented and negative-tested
- Accepted Evidence v2 collector and historical Experiment Runner path:
  unchanged
- P6-R2 targeted collector tests: 26/26 passed
- Full automated regression suite: 338/338 passed in isolated
  verification
- P6-R2 Containerlab execution and real Phase 6 artifacts: absent
- P6-R3 Ubuntu 24.04 image toolchain with ip, ping, and open-source
  iptables: real-runtime verified
- P6-R3 reviewed TOP-01 Observation Profile v2 binding and isolated
  source-default-route setup: completed without changing the historical
  topology or G01 fingerprint
- Real healthy Evidence v3 collection: 10/10 observed features and 9/9
  SHA-256-bound raw probes verified
- TOP-01 baseline before binding, before collection, and after
  collection: 13/13 valid
- P6-R3 targeted tests: 31/31 passed
- Full automated regression suite: 343/343 passed in the real local
  verification environment
- Fault injection, Dataset Row v3, Phase 6 campaign, model, prediction,
  and metric in P6-R3: absent
- P6-R4 `wrong_default_gateway` one-context smoke: verified
- D-081 runtime amendment: `interface_down` route absence and two
  structurally unavailable installed-next-hop features accepted after
  two safely restored fail-stop diagnostics
- P6-R4 amended `interface_down` re-smoke: verified
- P6-R4 exact tagged `acl_block` smoke: verified
- Three new-class injections, rule exact matches, restorations, and
  restored healthy signatures: 3/3 verified
- P6-R4 targeted tests: 46/46 passed
- Full automated regression suite: 373/373 passed
- Final TOP-01 baseline: 13/13 valid; cleanup containers: 0
- P6-R4 closeout and HANDOFF: completed
- Dataset Row v3, E01-E06, 72-row campaign, fitting, prediction, and
  metrics in P6-R4: absent
- P6-R5 E01-E06 complete six-class context bundles: implemented and
  runtime-verified
- Initial P6-R5 campaign: stopped safely after eight diagnostic-only
  rows because C4 used an obsolete route-binding key; no partial dataset
  was accepted
- D-081 C4 contract recovery: six isolated interface-down smokes,
  injections, and restorations verified without Dataset Row export
- Recovered clean campaign: 72/72 experiments and six clean context
  teardowns accepted
- Dataset Row v3: 72 clean, unmasked rows with 12 rows per class and
  12 rows per context
- Explicit split: 36/12/24 rows across 3/1/2 whole contexts with no
  group leakage
- E02 and E06 test partition: sealed for P6-R6 report-only use
- P6-R5 tests: 144/144 targeted and 387/387 full regression passed
- Model, prediction, selection, evaluation, and metric artifacts in
  P6-R5: absent
- P6-R5 closeout and HANDOFF: completed
- P6-R6 four deterministic missing-evidence masks and leakage-safe
  20-column method input: implemented and verified
- Six ML candidates fit only on 36 clean E01/E03/E05 train rows
- ML selection: `logreg_l2_c1`, chosen only with E04 validation
- Hybrid selection: `rule_then_ml_fallback_v1`, chosen only with E04
  clean/masked validation
- Independent development-freeze verification: passed before E02/E06
  access
- E02/E06 report-only evaluation: opened and completed exactly once
- Report inputs per method: 24 clean, 96 masked, 120 total
- Clean accuracy and macro-F1: 1.0 for Rule-based, ML, and Hybrid
- Masked Rule-based accuracy/macro-F1/coverage: 0.0/0.0/0.0, with
  insufficient-evidence rate 1.0
- Masked ML and Hybrid accuracy/macro-F1/coverage:
  0.791667/0.810486/1.0 for both methods
- Overall ML and Hybrid accuracy/macro-F1: 0.833333/0.846672, with no
  empirical difference between them
- Comparison: descriptive only; statistical-superiority test absent
- Post-freeze model refit, policy reselection, and test-guided revision:
  absent
- P6-R6 tests: 185/185 targeted and 428/428 full regression passed
- P6-R6 closeout and HANDOFF: completed
- P6-R7 multi-label multiple-fault academic-value and feasibility gate:
  completed as a design-only decision
- D-085: multiple-fault runtime not authorized in the current bachelor
  scope; no combined injection or new experimental artifact created
- Phase 6 closeout and HANDOFF: completed

## Phase 7 — Dashboard and API
Status: Complete

- P7-R0 Dashboard/API scope and read-only contract gate: complete
- D-086 freezes FastAPI/Uvicorn plus static same-origin HTML/CSS/JS as
  the local zero-cost architecture
- The interface is limited to six versioned `GET` routes and 15 verified
  JSON/JSONL projection sources
- Model deserialization, live inference, mutation, automatic
  remediation, retraining, arbitrary file access, and new empirical
  claims remain outside the interface layer
- P7-R1 artifact catalog and immutable projection layer: complete
- D-087 adds a Git-tracked 15/15 SHA-256 and size binding because the
  four P7-R0 roots alone did not anchor every non-root projection source
- Fail-closed path, byte, reference, contract, join, and accepted-scope
  verification: implemented
- Deep-immutable 120-case index and deterministic health, overview,
  comparison, case-list, case-detail, and provenance projections:
  implemented
- P7-R1 tests: 23/23; combined Phase 7 tests: 33/33; targeted Phase 6:
  185/185; full regression: 461/461
- Estimator deserialization, inference, server startup, Dashboard,
  subprocess, and runtime writes in P7-R1: absent
- P7-R2 read-only FastAPI implementation: complete
- D-088 accepts exactly six `GET` routes, one startup catalog load,
  OpenAPI-conformant envelopes, normalized `400/404/405/503/500`
  failures, and the `127.0.0.1:8000` Uvicorn entry point
- Automatic docs/OpenAPI routes, remote binding, CORS, authentication,
  inference, runtime writes, and Dashboard rendering in P7-R2: absent
- P7-R2 tests: 32/32; combined Phase 7 tests: 65/65; targeted Phase 6:
  185/185; full regression: 493/493
- P7-R3 static same-origin Dashboard implementation: complete
- D-089 accepts exactly four views over the unchanged six-route API,
  explicit loading/empty/fail-closed states, accessible interaction, and
  responsive desktop/390-pixel presentation
- External assets, React/Node build, browser persistence, new data route,
  inference, runtime writes, and new empirical claims in P7-R3: absent
- P7-R3 tests: 10/10; combined Phase 7 tests: 75/75; targeted Phase 6:
  185/185; full regression: 503/503
- P7-R4 Phase 7 closeout: complete
- D-090 accepts the final six-route/four-view local read-only boundary,
  reproducible start/health/stop operation, and separate tracked-source
  versus private 15-source projection archives
- Temporary live-server acceptance: passed and stopped cleanly; no
  Containerlab, estimator read, method execution, or runtime write
- P7-R4 tests: 10/10; combined Phase 7 tests: 85/85; targeted Phase 6:
  185/185; full regression: 513/513
- Phase 7 closeout and HANDOFF: completed
- P7-UX1 presentation-only maintenance amendment: complete after P9-R0
- D-096 improves terminology, information hierarchy, explanations, and
  technical-detail disclosure without reopening the six-route API,
  accepted P6-R6 outputs, evidence, hashes, or read-only behavior
- P7-UX1 verification: Phase 7 94/94; Phase 7 through Phase 9 175/175;
  targeted Phase 6 185/185; full regression 603/603
- P7-UX1 local visual acceptance: pending three-view browser review

## Phase 8 — Experiments and evaluation
Status: Complete

- P8-R0 evidence and thesis-claim scope gate: complete
- D-091 finds no thesis-critical empirical runtime gap and records
  `NO_NEW_EXPERIMENT_REQUIRED`
- Accepted evidence inventory: six roles spanning P1-P7, with P6-R6
  retained as the final numerical evaluation
- Thesis-claim matrix: eight bounded supported claims and eight explicit
  prohibited claims
- Remaining gaps: immutable full evidence archive and thesis-ready
  evaluation synthesis; neither requires experimental runtime
- New experiment, E02/E06 reopening, refit, policy reselection, metric
  recalculation, new metric, and artifact mutation in P8-R0: absent
- P8-R0 tests: 15/15; combined Phase 7 plus P8-R0 tests: 100/100;
  targeted Phase 6: 185/185; full regression: 528/528
- P8-R1 immutable final evidence registry and private archive: complete
- D-092 accepts the P6-R5/P6-R6 final-chain registry, deterministic
  external private archive, opaque estimator preservation, and tracked
  receipt without recomputation
- P8-R1 tests: 15/15; combined Phase 7 plus Phase 8: 115/115;
  targeted Phase 6: 185/185; full regression: 543/543
- P8-R2 thesis-ready final evaluation synthesis: complete
- D-093 accepts three exact-value CSV tables, two deterministic SVG
  figures, five bounded findings, and the claim-to-evidence matrix
  without recomputation or new empirical claims
- P8-R2 tests: 15/15; combined Phase 7 plus Phase 8: 130/130;
  targeted Phase 6: 185/185; full regression: 558/558
- P8-R3 Phase 8 closeout and Phase 9 handoff: complete
- D-094 accepts the four-input tracked closeout, full private-archive
  verification, five thesis assets, 8/8 supported and 8/8 prohibited
  claim boundary, and fail-closed Phase 9 writing contract
- P8-R3 tests: 15/15; combined Phase 7 plus Phase 8: 145/145;
  targeted Phase 6: 185/185; full regression: 573/573
- Phase 8 closeout and HANDOFF: completed

## Phase 9 — Thesis writing and defense
Status: In progress

- P9-R0 Thesis Structure and Source/Citation Gate: complete
- D-095 aligns seven chapter roles and an 8,100–10,000-word body outline
  with the verified 2026 University of Prishtina Bachelor guide
- Five bounded research questions map to C01–C08 without presupposing
  Hybrid superiority
- Verified source seed: 16 records, including nine scientific
  publications; final scientific-reference target remains at least 30
- APA author-date, originality/AI disclosure, table/figure, DOI, and
  source-admission controls: frozen
- Public FIEK-specific format guide: not located; documented unit or
  mentor formatting override remains guarded
- P9-R0 tests: 21/21; Phase 7 through Phase 9: 166/166; targeted Phase
  6: 185/185; full regression: 594/594
- P9-R1 Thesis Skeleton and Traceability Matrix: complete
- P9-R1 adds only front-matter placeholders, seven chapter/subsection maps,
  a 16-row verified source-to-section matrix, C01–C08 paragraph plan,
  B01–B08 non-draftable guards, and five accepted Phase 8 asset locations
- Preserve exact P8 values, claim limitations, and blocked-claim scope
- P9-R2 Controlled Chapter Drafting: not started; separate authorization
  required

## H1 — Runtime Safety and Reproducibility Hardening
Status: Complete

H1 is inserted after P7-UX1 and P9-R0 as a non-scientific maintenance gate.
It adds durable/idempotent Phase 6 recovery, bounded external commands,
clean-clone-safe tests, an opt-in real infrastructure cycle, and a trusted P4
Joblib CLI boundary. It neither changes the accepted Phase 6 result chain nor
advances Phase 9 writing.

H1 acceptance passed exact-preimage installation, unchanged private archive
and P8/P9 gates, the materialized and clean-clone suites, and the opt-in real
Containerlab lifecycle. Later X1 verification re-proved the same safety tests
and infrastructure cycle without changing accepted results.

P9-R1 remains paused by user request.

## Expansion Track X — Original ambitious technical vision
Status: X2 and X3 closed; X4-R0 accepted design-only; X4-R1 accepted locally after official E2E, publication pending

This track extends the frozen Phase 6/7/8 baseline append-only. It does not
reopen accepted results or resume the separately paused P9-R1 thesis milestone.

### X0 — Scope and compatibility freeze
Status: Complete

- Canonical 24-fault, six-domain target taxonomy frozen
- Source-document 23/24 inconsistency resolved by retaining `vlan_missing`
- Five implemented, one partial-mechanism, and eighteen missing fault types
  recorded
- Existing six-class order and v3/method contracts protected
- X0–X10 sequence and release gates frozen
- All ten runtime authorization flags false
- Verification: X0 18/18, Phase 6 185/185, H1 6/6, full clean-checkout
  regression 625 passed/3 skipped

### X1 — Extended contracts and modular collection
Status: Complete

- Topology Context v1
- Evidence v4 and collector-run structure
- Feature Catalog v1 and Feature Vector v2
- Dataset Row v4 and Diagnosis Result v2
- Evidence Mask Plan v2
- Read-only compatibility with the frozen v3 baseline
- Seven-spec metadata-only collector registry with complete catalog ownership
- 39 typed features: 10 frozen baseline and 29 planned X2–X6 extensions
- No collector executor or new empirical runtime

### X2 — Addressing
Status: Complete — X2-R0 through X2-R5 accepted

- Wrong IP address
- Wrong subnet mask
- Missing default route
- Duplicate IP with temporal ARP/MAC evidence
- X2-R0: disjoint signatures, X1 feature binding, safety invariants, and
  non-inherited runtime gate complete
- X2-R1: wrong IP plus isolated addressing runtime foundation complete
- X2-R2: wrong subnet mask runtime slice complete
- X2-R3: missing default route runtime slice accepted
- X2-R4: duplicate IP with active and temporal evidence accepted
- X2-R5: source/evidence closeout and hash-bound receipt accepted

### X3 — Layer 2 and VLAN
Status: Complete — X3-R0 through X3-R5 accepted

- Wrong access VLAN
- VLAN missing
- VLAN not allowed on trunk
- Native VLAN mismatch
- X3-R0: two-switch Linux-bridge design, tagged VLAN 10 flow, native VLAN 99
  flow, five-feature disjoint signatures and 0/10 runtime authorization
- X3-R1: real Wrong Access VLAN lifecycle, exact diagnosis, restoration and
  zero-container acceptance complete at public `0563fcd`
- X3-R2: real VLAN Missing lifecycle, exact diagnosis, restoration and
  zero-container acceptance complete at public `36c9747`
- X3-R3: real trunk allow-list lifecycle, exact diagnosis, restoration and
  zero-container cleanup accepted at public d75b5ab
- X3-R4: real native-VLAN mismatch lifecycle with the HostC-to-HostD context,
  exact diagnosis, restoration and zero-container cleanup accepted at public
  7bddd3a
- X3-R5: four-run hash-bound source/evidence closeout accepted at public
  2a763c6

### X4 — DHCP, DNS, and service security
Status: X4-R0 design gate and X4-R1/R2 runtime slices accepted; current D3 is canonically X4_R3_DNS_SERVICE_DOWN (X4_R3_DNS_SERVICE_UNAVAILABLE is its one-to-one compatibility alias)

- DHCP server unavailable and pool misconfiguration
- DNS service down and wrong DNS record
- Service-specific firewall block
- X4-R0: six-node service topology, nine X1-owned features, five disjoint
  signatures, safety boundary and 0/10 runtime authorization are frozen;
  no deployment or empirical work occurred

### X5 — Dynamic routing with OSPF
Status: Planned

- Adjacency root causes
- Route filtering and advertisement
- BGP only if a later OSPF gate establishes additional value

### X6 — Performance faults
Status: Planned

- Packet loss
- High latency
- Congestion
- Bandwidth/rate limiting

### X7 — Extended grouped single-fault dataset
Status: Planned

- Whole-group train/validation/report-only split
- Frozen feature and class catalogs
- No early report-only test access

### X8 — Rule, ML, and Hybrid v2 evaluation
Status: Planned

- Hierarchical category/type/location evaluation
- Simple ML baselines retained
- Added model complexity only with validation evidence
- Objective Hybrid comparison with no required winner

### X9 — Missing evidence and unseen variants
Status: Planned

- Real collection failures reported separately from masks
- Unseen configuration variants
- Unseen topology instances of known fault domains

### X10 — Selected multiple faults and extended interface
Status: Planned

- Two pilot pairs before the bounded six-to-ten-pair study
- Injected, effective, and diagnosable truth sets
- Dataset Row v5 and Diagnosis Result v3
- Versioned interface separate from frozen Phase 7 `/api/v1`
### X2-R3 — Missing Default Route

Accepted with real Evidence v4, exact diagnosis, restoration and cleanup.

### X2-R4 — Duplicate IP

Accepted with active duplicate response, temporal MAC churn, exact diagnosis,
restoration and cleanup. X2-R5 closes the addressing group.

### X2-R5 — Addressing Closeout

Accepted. Four real runs are bound by the committed receipt and retained in a
private local archive. Next: X3-R0 design gate.

### X3-R0 — Layer 2/VLAN Design Gate

Accepted design-only. The six-node, five-link context and four disjoint fault
signatures are frozen without deploying Containerlab or collecting evidence.
Next: X3-R1 Wrong Access VLAN.

### X3-R1 — Wrong Access VLAN

Accepted. SW1 moved only HostA's access PVID from VLAN 10 to VLAN 20; the
tagged flow failed while native VLAN 99 remained healthy. Direct VLAN/FDB
evidence, exact diagnosis, full regressions, restoration and zero-container
cleanup passed. Public boundary: `0563fcd`.

### X3-R2 — VLAN Missing

Accepted. VLAN 10 was removed from the SW1 access and trunk memberships as one
controlled switch-level fault. The real false/false/false/true/false
signature, exact diagnosis, restoration and zero-container cleanup passed.
Public boundary: `36c9747`.

### X3-R3 — VLAN Not Allowed on Trunk

Implemented locally. Tagged VLAN 10 is removed only from SW1 `eth3`; access
membership, SW2 and native VLAN 99 remain unchanged. Collector v3 derives the
exact true/true/false/true/true signature, and the combined rule engine
preserves X3-R1/X3-R2. Real transactional acceptance is pending.
