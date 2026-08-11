# HANDOFF P6-R5

Date: 2026-08-11

Status: COMPLETED AND ACCEPTED

## 1. What was completed

P6-R5 implemented and runtime-verified six complete Phase 6 contexts,
E01-E06. Each context contains the six frozen classes with two
repetitions per class, a dedicated topology and full baseline validator,
Observation Profile v2 scenarios, one batch plan, and a normalized
context fingerprint.

The first campaign stopped safely after eight completed experiments
because the C4 scenario contract still used `preserved_routes`. Those
rows and the failed ninth attempt remain diagnostic-only. The recovery
aligned all six C4 scenarios to the D-081 `baseline_routes` contract,
then verified six isolated interface-down injections and restorations
without exporting dataset rows.

The replacement clean campaign
`p6_r5_clean_campaign_recovery-20260811T070536Z` completed 72/72
experiments and produced 72 clean, unmasked Dataset Row v3 records. The
explicit whole-context split is 36 train, 12 validation, and 24 sealed
test rows. No model, selection, prediction, evaluation, or metric was
created.

## 2. What was decided

D-083 accepts the recovered campaign as the canonical Phase 6 clean
dataset boundary. The stopped campaign is not merged, split, or reused.
The C4 recovery is an implementation correction under D-081, not a
taxonomy or signature amendment.

E01/E03/E05 are development-train contexts, E04 is the
development-validation context, and E02/E06 remain report-only test
contexts. The test partition stays `SEALED_FOR_P6_R6_REPORT_ONLY` until
the new ML model and Hybrid policy are independently frozen.

## 3. Files created or changed

The accepted implementation adds or updates 69 P6-R5 files:

- six E01-E06 topology and validator bundles;
- 36 Phase 6 scenario files and six clean batch plans;
- the campaign plan and six-context fingerprint manifest;
- Phase 6 campaign plan/result schemas;
- the Phase 6 plan loader, coordinator, explicit Dataset Row v3
  splitter, route injectors, registry, experiment runner, and Evidence
  v3 verification boundary;
- two P6-R5 unit-test modules; and
- `docs/P6_R5_CONTEXT_CAMPAIGN_GATE.md`.

Closeout also creates this HANDOFF and updates `docs/DECISIONS.md`,
`docs/MASTER_CONTEXT.md`, `docs/PHASE6_FAULT_TAXONOMY_PLAN.md`,
`docs/ROADMAP.md`, and `docs/STATUS.md`.

## 4. Open issues

- implement and verify the four precommitted non-destructive
  missing-evidence masks;
- implement the new six-class Rule-based, ML, and Hybrid versions;
- fit only on E01/E03/E05 and select only with E04;
- independently freeze the chosen model and Hybrid policy before any
  E02/E06 access;
- execute one report-only clean and missing-evidence evaluation without
  refitting or test-guided revision; and
- define a separate multi-label design before any multiple-fault work.

## 5. Next step

P6-R6 is the next milestone. It must implement the frozen missingness
transformations, construct the ten-feature development inputs, fit and
select the new ML and Hybrid versions using only train and validation,
and independently verify their frozen identities. Only afterward may
the E02/E06 report-only clean and missing-evidence evaluation run once.

## 6. Impact on central documents

- `DECISIONS.md`: adds D-083 and the test-use prohibition.
- `MASTER_CONTEXT.md`: records the failed diagnostic runtime, bounded
  recovery, accepted 72-row runtime, hashes, and P6-R6 boundary.
- `STATUS.md`: records P6-R5 as completed and makes P6-R6 current next.
- `ROADMAP.md`: marks the E01-E06 campaign and sealed split complete.
- `PHASE6_FAULT_TAXONOMY_PLAN.md`: records P6-R5 acceptance without
  changing the frozen taxonomy, masks, or multiple-fault exclusions.

## Accepted runtime identities

- failed diagnostic campaign:
  `p6_r5_clean_campaign-20260811T063119Z`;
- failed runtime tree SHA-256:
  `531c872cd392ac7308ae4684ab422b06736e7d1c894f04c7ac5780745fd69d79`;
- recovery smoke:
  `p6_r5_c4_recovery_smoke-20260811T070536Z`;
- accepted campaign:
  `p6_r5_clean_campaign_recovery-20260811T070536Z`;
- campaign-result SHA-256:
  `c4c45e19e8b98d00a3fa2ed3b4d4a8ad2ba6debd04baae05c2d7d7377f9df4d2`;
- merged Dataset Row v3 SHA-256:
  `50dd030e51e4873eac7665980e033a0236e4ddf26e446b66bd3d11613c4a0a9d`;
- split-manifest SHA-256:
  `adf70942a740be43e085aca67f9acb4085dd118827ceba8482913dbc6adb5f9f`;
- targeted tests: 144/144 passed;
- full regression: 387/387 passed; and
- final Containerlab containers: 0.
