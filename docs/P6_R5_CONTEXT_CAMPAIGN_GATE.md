# P6-R5 Complete-Context Campaign Gate

Date: 2026-08-11

Status: IMPLEMENTED; RECOVERED REAL RUNTIME ACCEPTED

## Scope

P6-R5 implements the frozen six-class, six-context clean-data campaign.
It does not authorize model fitting, prediction, metric generation,
missing-evidence result claims, report-only test evaluation, or
multiple-fault execution.

The class order is:

1. `no_fault`;
2. `missing_static_route`;
3. `wrong_next_hop`;
4. `wrong_default_gateway`;
5. `interface_down`; and
6. `acl_block`.

Every E01-E06 context contains the complete class set with two
repetitions per class. The reviewed campaign therefore contains exactly
72 clean Evidence v3 experiments and 72 unmasked Dataset Row v3 records.

## Context boundary

The reviewed context bindings are:

- E01: TOP-01 linear source-edge path;
- E02: TOP-02 three-router chain;
- E03: TOP-02 branch selected destination arm;
- E04: TOP-02 dual-transit selected arm;
- E05: TOP-03 asymmetric forward path; and
- E06: new TOP-04 routed forwarding-policy boundary.

Each context has a dedicated topology, full baseline validator, six
Observation Profile v2 scenarios, unique ACL tag, batch plan, and
normalized SHA-256 bundle fingerprint. The source flow uses its reviewed
default route so `wrong_default_gateway` controls the selected flow. A
separate non-selected route is retained where the topology needs one.

## Execution contract

The coordinator requires zero existing containerlab containers, executes
contexts and experiments in listed order, validates the baseline before
and after every experiment, and stops at the first failure. Every applied
fault must be exactly restored. Every context is destroyed and checked for
residual containers, including on failure.

Each accepted experiment must provide:

- a COMPLETED Experiment Manifest v2;
- Evidence v3 with no collection-unavailable feature;
- an exact frozen six-class feature signature;
- confirmed baseline recovery and fault restoration;
- one clean, unmasked Dataset Row v3 bound to the source evidence hash;
  and
- no diagnosis, prediction, evaluation, or metric artifact.

The coordinator refuses a second completed P6-R5 campaign in the same
metadata root. A failed runtime may be reviewed, but the gate script never
retries it automatically.

## Frozen split

The splitter uses `explicit_complete_context_v1`, not a hash allocation:

- train: E01, E03, E05 — 36 rows;
- validation: E04 — 12 rows; and
- test: E02, E06 — 24 rows.

No `split_group_id` may cross partitions. The test partition is created
once and marked `SEALED_FOR_P6_R6_REPORT_ONLY`; P6-R5 does not read it for
selection, fitting, prediction, or metrics.

## Interface-contract recovery

The first real campaign,
`p6_r5_clean_campaign-20260811T063119Z`, stopped as designed in E01
after eight completed experiments. The ninth attempt exposed an
implementation mismatch: all six C4 scenarios and their validator used
the obsolete `preserved_routes` key, while the accepted D-081 injector
requires explicit `baseline_routes`. The failed attempt created no
Dataset Row v3 record, cleanup left zero containers, and the eight
earlier rows remain diagnostic-only. The failed runtime tree SHA-256 is
`531c872cd392ac7308ae4684ab422b06736e7d1c894f04c7ac5780745fd69d79`.

Recovery changed only the six C4 scenario bindings, the campaign-plan
validator, the context fingerprints, and their contract test. All six
isolated C4 recovery smokes completed with confirmed injection, exact
restoration, and zero exported Dataset Row v3 records under
`p6_r5_c4_recovery_smoke-20260811T070536Z`. This is an implementation
contract correction, not a change to D-081, the six-class taxonomy, the
ten-feature boundary, the allocation, or the test-use policy.

## Verification

The recovered implementation passed 144/144 Phase 6 tests and the full
387/387 regression suite in the real local environment. These results
validate the contracts, fail-stop behavior, exact split arithmetic,
C1/C2 injection/restoration, Evidence v3 verification, and absence of
evaluation outputs.

The clean recovery campaign
`p6_r5_clean_campaign_recovery-20260811T070536Z` then completed all six
contexts and 72/72 experiments. Every context contributed two clean rows
per class, for 12 rows per context and 12 rows per class. All 72 Dataset
Row v3 records were unmasked, every context cleanup was verified, and no
collection-unavailable feature was accepted.

The merged dataset SHA-256 is
`50dd030e51e4873eac7665980e033a0236e4ddf26e446b66bd3d11613c4a0a9d`.
The split-manifest SHA-256 is
`adf70942a740be43e085aca67f9acb4085dd118827ceba8482913dbc6adb5f9f`.
The campaign-result SHA-256 is
`c4c45e19e8b98d00a3fa2ed3b4d4a8ad2ba6debd04baae05c2d7d7377f9df4d2`.

## Accepted boundary

P6-R5 is accepted after 72/72 experiments, six clean context teardowns,
72 valid Dataset Row v3 records, an exact 36/12/24 split with no group
leakage, a sealed test partition, zero diagnosis/prediction/metric
outputs, and zero remaining containerlab containers. The test groups E02
and E06 remain `SEALED_FOR_P6_R6_REPORT_ONLY` and were not read for
fitting, selection, prediction, or metric calculation.

P6-R5 establishes a clean, controlled six-class dataset and its frozen
partition boundary. It does not establish ML or Hybrid performance,
missing-evidence robustness, statistical superiority, production
validity, or real-world generalization. Those claims remain outside this
gate.
