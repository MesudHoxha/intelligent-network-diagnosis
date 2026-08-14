# H1 Runtime Safety and Reproducibility Hardening

Date: 2026-08-14

Status: IMPLEMENTED; AUTOMATED PACKAGE VERIFICATION REQUIRED; OPTIONAL
INFRASTRUCTURE SMOKE NOT EXECUTED BY DEFAULT

## 1. Purpose and boundary

H1 is a maintenance hardening milestone. It addresses restoration safety,
bounded external commands, clean-checkout reproducibility, one opt-in real
infrastructure cycle, and trusted `joblib` entry points. It does not reopen
P6-R5 or P6-R6, create a new experiment result, resume P9-R1, or change a
scientific method, dataset, split, metric, prediction, finding, figure, API,
or Dashboard projection.

The accepted ignored runtime archive and every P8/P9 tracked value remain
immutable. The optional infrastructure smoke writes only to a pytest
temporary directory and is not accepted evidence.

## 2. Finding-by-finding assessment

### H1-F01 — Fault restoration after partial failure

- **Status:** Fixed.
- **File and function:** `src/fault_injection/phase6_common.py` —
  `write_recovery_intent`, `require_restorable_record`, and
  `load_confirmed_restoration`; the five Phase 6 fault injector/restorer
  pairs; `src/orchestration/phase6_experiment_runner.py` —
  `_recovery_required`, `run_phase6_experiment`, and
  `recover_phase6_experiment`.
- **Concrete problem:** a real network mutation could succeed and a later
  exception could occur before `injection_record.json` was persisted. The
  orchestrator previously inferred restoration need only from that record.
- **Impact:** the lab could remain mutated after an exception or interrupted
  process.
- **Applied fix:** each injector atomically persists a scenario-bound recovery
  intent after healthy preconditions and before the first mutation command.
  Both normal cleanup and the explicit recovery replay entry point accept the
  intent as a restoration obligation. Restorers validate identity, restore
  toward the reviewed healthy state, verify final postconditions, and return
  an already confirmed record on retry. ACL restoration is a verified no-op
  when the exact tagged rule is already absent.
- **Proof test:** `test_runner_restores_when_exception_precedes_injection_record`,
  `test_recovery_entry_point_restores_abandoned_intent`, and the idempotency
  assertions in `test_p6_r4_injectors.py` and
  `test_p6_r5_route_faults.py`.
- **Frozen-result regression risk:** low. The control applies to future
  mutation runs only. It does not modify accepted experiment artifacts or
  successful diagnostic/evaluation logic.

An operating-system or host failure still requires a surviving filesystem
and a later recovery invocation. No application can restore a lost lab host
without an external supervisor. H1 makes the restoration obligation durable
and provides the deterministic replay command; it does not claim distributed
transaction semantics.

### H1-F02 — Clean-checkout test reproducibility

- **Status:** Fixed.
- **File and function:** `pyproject.toml` pytest markers and
  `tests/unit/test_p8_r0_scope_gate.py` — `_require_accepted_runtime`.
- **Concrete problem:** two acceptance checks directly required ignored P6-R6
  runtime files, so a clean clone could fail despite a correct tracked tree.
- **Impact:** the default suite was not reproducible from source alone.
- **Applied fix:** the two real-archive checks are explicitly marked
  `accepted_runtime` and skip with the exact missing paths when the private
  archive is not materialized. Fixture-backed contract tests remain mandatory.
  The local materialized acceptance tier still executes both checks.
- **Proof test:** the commit package runs the complete suite once in the
  materialized repository and once in a temporary clean local clone.
- **Frozen-result regression risk:** none. No accepted artifact is generated,
  copied, or weakened; the stronger real-archive tier still runs when its
  required bytes exist.

### H1-F03 — Real infrastructure integration cycle

- **Status:** Partially Fixed.
- **File and function:** `tests/e2e/test_phase6_containerlab_smoke.py` —
  `test_real_phase6_cycle_restores_and_cleans_up`.
- **Concrete problem:** configuration/YAML validation alone did not prove the
  integration of deployment, collection, diagnosis, restoration, and cleanup.
- **Impact:** component contract tests could pass while the actual toolchain
  failed.
- **Applied fix:** an opt-in test now performs a real Containerlab deploy,
  baseline validation, missing-static-route injection, Evidence v3 collection,
  verification and rule diagnosis, confirmed restoration, restored baseline,
  topology destruction, and zero-container cleanup assertion.
- **Proof test:** run `IND_RUN_INFRA_E2E=1 pytest -q -m infrastructure
  tests/e2e/test_phase6_containerlab_smoke.py` after `sudo -v` on a host with
  Docker and Containerlab.
- **Frozen-result regression risk:** none when used as specified. Output is
  temporary and cannot be promoted to accepted evidence without a separate
  authorization.

The code and reproducible workflow are present, but H1 does not claim a new
real-infrastructure pass until that opt-in command is executed on the user's
lab host. Therefore the status remains Partially Fixed rather than overstated.

### H1-F04 — Unbounded subprocess calls

- **Status:** Fixed.
- **File and function:** `src/runtime/subprocesses.py` — `run_capture`; migrated
  Docker, Containerlab, shell, network, campaign, orchestration, collection,
  and Git command adapters.
- **Concrete problem:** external commands could wait indefinitely.
- **Impact:** one experiment or campaign could hang with no bounded failure
  artifact.
- **Applied fix:** every production `subprocess.run()` now has a positive
  timeout through one wrapper. `TimeoutExpired` is normalized to return code
  124 with captured partial output and an explicit timeout message. Callers
  preserve their existing structured failure paths.
- **Proof test:** `test_timeout_is_bounded_and_normalized` and
  `test_all_production_subprocess_calls_are_bounded`.
- **Frozen-result regression risk:** low. Successful commands retain their
  previous return code/stdout/stderr semantics; only over-time execution gains
  a bounded failure.

### H1-F05 — Large modules and functions

- **Status:** Present.
- **File and function:** notably campaign, evaluation/reporting, Hybrid/ML,
  dataset, and coordinator modules identified by the original review.
- **Concrete problem:** some functions still combine multiple responsibilities
  and are costly to test in isolation.
- **Impact:** maintainability and future change risk, but H1 found no current
  result defect that justified a broad refactor.
- **Recommended fix:** split only a function with a demonstrated correctness or
  test seam need, under a separately reviewed milestone with characterization
  tests and frozen-source impact analysis.
- **Proof test:** not applicable to unchanged structure; H1 regression tests
  characterize the safety seams added here.
- **Frozen-result regression risk:** potentially high if changed casually.
  H1 deliberately performs no style-only refactor.

### H1-F06 — Duplicated infrastructure helpers

- **Status:** Present.
- **File and function:** local `utc_now`, SHA-256, JSON read/write, and atomic
  write helpers across phase-specific modules.
- **Concrete problem:** duplication can drift over time.
- **Impact:** maintainability risk; no incompatible current output was proven.
- **Recommended fix:** consolidate only helpers whose contracts and byte output
  are identical. Keep phase-local functions where timestamps, error types,
  serialization, or frozen hash behavior differ.
- **Proof test:** not applicable because H1 does not consolidate frozen output
  helpers. `src/runtime/subprocesses.py` is consolidated because command timeout
  semantics were demonstrably cross-cutting and output-compatible.
- **Frozen-result regression risk:** medium to high for JSON/atomic/hash helpers;
  none from leaving them unchanged.

### H1-F07 — Phase 6 coordinator hard-coded bindings

- **Status:** Present, intentional.
- **File and function:** `src/phase6/coordinator.py` constants and accepted
  P6-R5/P6-R6 paths/hashes.
- **Concrete problem:** a generic coordinator would be brittle if it silently
  depended on one campaign.
- **Impact:** limited reuse, but the current module is an acceptance gate for
  one frozen campaign rather than a generic campaign runner.
- **Recommended fix:** keep the frozen coordinator immutable. If reuse is
  required, create a new versioned generic coordinator and leave the accepted
  gate as the reproducibility verifier.
- **Proof test:** existing P6-R6/P8/P9 hash and closeout gates verify the exact
  binding. H1's commit package reruns them against unchanged accepted bytes.
- **Frozen-result regression risk:** high if the constants or implementation
  source are edited. H1 makes no such edit.

### H1-F08 — Trusted `joblib.load()` boundary

- **Status:** Fixed for user-facing execution paths.
- **File and function:** `src/ml/baseline.py` — accepted P4-R1 selection/model
  constants, `build_parser`, and `validate_frozen_pipeline` ordering;
  `src/phase6/coordinator.py` accepted offline freeze gate.
- **Concrete problem:** Python deserialization is unsafe for untrusted files;
  a caller-supplied file and caller-supplied matching hash are not a trust
  anchor.
- **Impact:** arbitrary code execution if an attacker-controlled Joblib file
  reached deserialization.
- **Applied fix:** the P4 CLI paths that deserialize now accept only the exact
  D-073 selection and estimator hashes, and validation checks matrix,
  selection, model hash, schema, and cross-bindings before `joblib.load()`.
  Hash drift is proven to stop before the loader. The final P6 coordinator
  remains an offline, fixed-path, accepted-freeze gate; it is not exposed by
  the Dashboard/API and accepts no arbitrary model argument.
- **Proof test:** `test_model_hash_drift_stops_before_joblib_deserialization`
  and `test_verify_selection_cli_requires_accepted_trust_hashes`.
- **Frozen-result regression risk:** low. Accepted D-073 hashes are unchanged;
  non-accepted artifacts are rejected. The final estimator is not
  deserialized by H1, Phase 7, Phase 8, or Phase 9.

Programmatic callers of Python functions remain responsible for supplying a
trusted artifact identity. The safety boundary is integrity plus provenance,
not the Joblib format itself.

## 3. Verification tiers

The commit package must pass, in order:

1. syntax compilation, whitespace checks, and static timeout inventory;
2. six H1 unit tests;
3. 185 targeted Phase 6 tests;
4. 175 combined Phase 7 through Phase 9 tests;
5. the complete materialized suite: 609 passed and one opt-in infrastructure
   skip;
6. the complete clean-clone suite: 607 passed and three explicit skips (two
   accepted-runtime checks and one infrastructure test); and
7. unchanged Phase 8 closeout/private-archive and P9-R0 gates.

The real infrastructure test is intentionally outside the default suite. A
pass may be recorded later, but its temporary output remains non-accepted.

## 4. Recovery operation

Normal Python exceptions trigger restoration in the experiment runner. After
an interpreter or shell interruption, use the same reviewed scenario and the
existing experiment directory:

```bash
python -m src.orchestration.phase6_experiment_runner \
  --scenario scenarios/phase6/E01_C1_MISSING_STATIC_ROUTE.yml \
  --baseline-validator labs/topologies/p6_e01_top01/scripts/validate_baseline.sh \
  --recover-experiment-directory data/raw/<interrupted-experiment>
```

The restorer validates the recovery identity, is safe to retry after a
confirmed restoration, and writes `recovery_replay.json` plus a post-recovery
baseline record.

