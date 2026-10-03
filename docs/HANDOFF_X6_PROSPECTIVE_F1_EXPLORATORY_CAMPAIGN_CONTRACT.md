# HANDOFF — X6 Prospective F1 Exploratory Campaign Contract

Status: `REVIEW_ONLY_NOT_ACCEPTED`

Published source boundary: `babde86fd863d105b30262d205ced09995251515`
Direct parent: `287809ecc74bc3962de67fb903058fc6db09e899`

## Accepted input

The exploratory study design is accepted only under its stated assumptions and limitations. The append-only acceptance record binds:

- `plans/expansion/X6_PROSPECTIVE_F1_SUCCESSOR_STUDY_DESIGN_PROPOSAL_V1.json` — SHA-256 `3bce7a8264d059f1dbfb772eafbecc6e1782e7d74ecfe092c6d6eaa8c2ca7388`.
- `docs/HANDOFF_X6_PROSPECTIVE_F1_SUCCESSOR_STUDY_DESIGN.md` — SHA-256 `40fedd19de8a9d0ec0a8a2aa8c3725f0afabb4d80b15513bc9068df785e616ee`.
- The embedded 50-block, 100-slot inventory — SHA-256 `c1ff4d276705936111b12c918cad7a387d44369859b828ca13c7e28a5dba2c2c`.

This acceptance establishes neither classifier validity nor runtime authority.

## Campaign-contract proposal

The review-only proposal is:

`plans/expansion/X6_PROSPECTIVE_F1_EXPLORATORY_CAMPAIGN_CONTRACT_PROPOSAL_V1.json`

It translates the accepted design into a prospective `X6_R1_5_2_EXPLORATORY_F1_CAMPAIGN_SOURCE_ONLY` successor with the entrypoint `python -m src.orchestration.x6_r1_5_2_campaign`. `run-slot` may perform one bounded action for one bound slot. No command authorizes an entire campaign or multiple attempts.

The proposal reuses the accepted R1.5.1 authorization, durable-observation, recovery, performance-rule, and independent-verification components by exact source hash. It requires successor-specific orchestration, slot accounting, campaign verification, deterministic analysis, and model-freeze support. Published source and the accepted frozen thresholds remain unchanged.

## Concrete conflicts and narrow resolutions

Five current R1.5.1 contracts cannot represent the accepted study directly:

1. Runtime authorization permits only an F1 single-fault attempt and prohibits dataset, model, and metrics artifacts. The successor therefore requires a separate slot-scoped authorization schema, a separate campaign artifact inventory, and separately reviewed single-action authorizations for development freeze/model fitting and final evaluation/analysis.
2. The current lifecycle always enters the F1 mutation path. The successor requires distinct `N0_CONTROL` and `F1_PACKET_LOSS_SINGLE_FAULT` slot scopes.
3. Current fault-effectiveness failure stops the normal path before restoration measurements. The successor must retain assigned F1 slots and continue cooldown and restoration observations after ineffective mutation or diagnostic abstention when operational safety, integrity, ownership, timing, and cleanup prerequisites remain valid.
4. The accepted historical comparator consumes six features, while learned methods may consume only packet loss, successful-reply ICMP RTT, TCP throughput, and utilization. Queue and rate-limit observations remain common eligibility controls and full-denominator outcomes, never learned inputs or hybrid routing signals.
5. The current verifier and inventory describe one F1 attempt. The successor needs independent slot and campaign reconstruction without weakening the existing verifier.

These are prospective successor requirements. They do not revise the historical comparator, frozen thresholds, spent attempt, or published files.

## Durable execution and analysis requirements

The proposal binds every slot to campaign, block, stage, position, assignment, environment epoch, authorization, run, output root, source, topology, image, threshold manifest, command catalog, and boot evidence. Reservation is exclusive and durable; partial reservation is spent. Slots are never retried or replaced, and recovery never resumes traffic or measurements.

Model fitting and final analysis have distinct authorization record kinds. Each binds the exact action, canonical input inventory, source, campaign/stage, prior freeze state, canonical output, reservation ledger, validity, and one-action consumption. Atomic reservation under the campaign lock prevents concurrent or replayed action. An interrupted or partially admitted action remains spent; recovery may classify and verify it but cannot silently refit, rerun analysis, publish staged output, or reuse authority. Read-only verification is separate and cannot publish canonical campaign state.

Cleanup must be independently verified before the second member of a pair. A blocked member is recorded as `NOT_RUN_OPERATIONAL_FAILURE` with no replacement. Boot or material environment changes close the current epoch and require a separately reviewed epoch record before later slots.

All development preprocessing and fitting use development blocks only. The serialized preprocessing, model coefficients, thresholds, dependency and implementation identities, and hashes are frozen before evaluation collection or access. Evaluation access is sealed until the development freeze is valid. Missing slots remain in the planned denominator and can make the study inconclusive.

The four learned predictors carry the accepted aggregation exactly: loss is the mean of three normalized target-window values; RTT is nearest-rank p95 over pooled individual successful ICMP replies; throughput and utilization are three-window medians. Window and aggregate normalization use finite Decimal values and six-place `ROUND_HALF_EVEN` in the accepted order. Secondary effectiveness-qualified sensitivity and clean-control specificity retain the accepted denominators and return `NOT_ESTIMABLE` on a zero denominator.

Method outputs are limited to `F1_PRESENT`, `F1_ABSENT`, `ABSTAIN`, and `UNAVAILABLE_EVIDENCE`. `NO_PREDICTION_OPERATIONAL` is slot accounting only. A NOT_RUN slot has no run root, raw command, measurement, predictor row, method invocation, output, or prediction; any such artifact is contradictory evidence.

Slot and non-slot actions use explicit legal transitions and prerequisites. Raw observations, reconstructed values, method results, and cleanup evidence become durable before the state event that references them. Development-freeze and final-analysis bundles are reconstructed in bound staging areas and atomically published before the final `PUBLISHED` event. Orphan staging, missing manifests, broken event chains, or state events referring to absent evidence are incomplete or contradictory, never successful publication.

The independent verifier reconstructs raw measurements, common controls, effectiveness, predictions, model bindings, paired-block accounting, deterministic metrics, bootstrap inputs, and reported results. It never trusts stored summaries as reconstruction inputs.

## Expected implementation scope

If separately accepted and authorized, the proposed implementation inventory is sixteen append-only successor files: the campaign contract, authorization schema and gate, orchestration CLI, durable state, slot collector, development freeze, deterministic analysis, independent verifier, focused tests, gate, decision/status records, and implementation handoff. Its exact bytes and modes must be finalized before source-only verification.

Focused source-only acceptance must cover identity and ordering, one-attempt spending, interruption and reboot behavior, cleanup gating, N0/F1 phase behavior, abstention and ineffectiveness, predictor leakage, development-only fitting, immutable freeze and evaluation seal, deterministic paired analysis, missing-slot accounting, tamper rejection, and materialized reconstruction. It must also exercise crashes at every durability boundary, partial publication, concurrent and replayed slot/model/analysis actions, contradictory transitions, and fabricated NOT_RUN observations. Only contract-required impacted regressions may follow; exactly the six approved historical diagnostics remain separate.

## Boundaries and next step

The campaign contract remains `REVIEW_ONLY_NOT_ACCEPTED`. No implementation, model fitting, dataset creation, runtime readiness, authorization, reservation, consumption, collection, classifier validity, or scientific acceptance is established. Historical authorization remains `0/10_FALSE`.

Next step: separately review and explicitly accept, revise, or reject the exact campaign-contract proposal. Implementation requires a later, distinct authorization after contract acceptance.
