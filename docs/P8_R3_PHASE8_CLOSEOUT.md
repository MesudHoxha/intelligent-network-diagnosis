# P8-R3 Phase 8 Acceptance Closeout and Phase 9 Handoff

Date: 2026-08-12

Status: CLOSED — FINAL EVIDENCE AND EVALUATION ACCEPTED

## 1. Purpose and frozen boundary

P8-R3 closes Phase 8 after the P8-R0 scope decision, P8-R1 immutable
evidence archive, and P8-R2 thesis-ready synthesis have passed their
acceptance gates. This milestone adds no experiment, diagnostic method,
metric, figure, or interface behavior. It verifies the complete accepted
chain and freezes the handoff that Phase 9 must use while writing the thesis.

The final Phase 8 boundary remains:

- `NO_NEW_EXPERIMENT_REQUIRED` under D-091;
- 1,488 accepted runtime artifacts in the final P6-R5 through P6-R6 chain;
- one deterministic private archive with 1,490 members and its tracked
  SHA-256 receipt;
- three exact-value CSV tables and two deterministic SVG figures;
- eight supported bounded claims, each with a required limitation; and
- eight explicitly prohibited claim expansions.

No Containerlab process, network mutation, diagnosis execution, estimator
deserialization, model refit, policy reselection, test evaluation, metric
recalculation, new metric, accepted-artifact mutation, or claim broadening is
authorized or performed.

## 2. Final accepted Phase 8 chain

| Milestone | Accepted result | Final closeout check |
| --- | --- | --- |
| P8-R0 | Evidence-completeness and thesis-claim scope | Decision is `NO_NEW_EXPERIMENT_REQUIRED`; 8 supported and 8 blocked claims retained |
| P8-R1 | Immutable registry, deterministic private archive, and tracked receipt | 1,488 runtime artifacts and all 1,490 archive members verified by path, size, and SHA-256 |
| P8-R2 | Thesis-ready evaluation synthesis | 3 CSV tables and 2 SVG figures verify byte-identically against the accepted source chain |
| P8-R3 | Phase 8 acceptance and Phase 9 handoff | Machine-readable closeout, final tests, and central-document transition verified |

The P8-R3 manifest is generated from the exact local P8-R2 Git checkpoint. It
binds the P8-R0 scope, P8-R1 registry and receipt, P8-R2 synthesis, five thesis
assets, private-archive identity, claim boundary, and Phase 9 writing
constraints. The full P8-R2 commit is recorded at execution time; its accepted
short identity is `cb489a3` and its parent is the exact P8-R1 commit
`c55c803dbb42752f1597b2276026204267e35e0f`.

## 3. Final evaluation statement

The accepted comparison is descriptive and limited to the controlled final
laboratory boundary. The final clean dataset contains 72 rows across six
classes and six complete contexts, split 36/12/24 by whole context. The
report-only comparison evaluates three methods on 24 clean inputs and 96
deterministic missing-evidence transformations, for 120 inputs per method.

All three methods achieve complete fault-type classification on the 24 clean
inputs. Under missing evidence, the strict Rule-based method fails closed,
while Machine Learning and Hybrid retain full coverage. Hybrid is
operationally distinct through rule-first and Machine-Learning-fallback
provenance, but its accepted aggregate numerical results equal Machine
Learning in every scope. No Hybrid advantage or statistical superiority is
claimed.

The 96 masked inputs are transformations of the same 24 clean cases. They are
not independent network experiments. The accepted results do not establish
population significance, calibrated uncertainty, external replication,
production readiness, or generalization to real networks.

## 4. Reproducibility and preservation

The tracked Git repository is the public source boundary. The private archive
is the accepted ignored-runtime boundary and must remain preserved separately
with the tracked receipt:

```text
Archive: P8-R1-final-evidence-private.tar.gz
SHA-256: e9eea5fe520779eee4f4eba4df442ae46c0fd43ea382eed9f5ad5de94cbd14b6
Size: 639729 bytes
Members: 1490
Runtime artifacts: 1488
```

The selected estimator is present only as opaque archived bytes. Preservation
and hashing do not deserialize it or authorize new inference. Likewise, the
test partition is preserved without reopening or reevaluation.

After restoring the repository and the private archive, the closeout can be
verified from the repository root with:

```bash
python -m src.phase8.closeout \
  --repository-root . \
  --private-archive "$HOME/intelligent-network-diagnosis-private-archives/P8-R1-final-evidence-private.tar.gz" \
  --verify
```

The verifier rebuilds the tracked closeout from accepted tracked inputs,
requires byte-identical manifest content, and verifies the private archive and
all registry-bound runtime bytes. It imports no estimator serialization
loader.

## 5. Phase 9 thesis-writing entry contract

P9-R0 is the next milestone. It must establish the thesis structure and the
source/citation gate before drafting result claims. The final chapter names
may be adapted to the University template, but the following evidence roles
must remain traceable:

| Chapter role | Required content boundary | Primary accepted evidence/assets |
| --- | --- | --- |
| Introduction | Problem, motivation, bounded research question, contribution | E01, E04, E05 |
| Background | Network diagnosis, Rule-based, ML, and Hybrid concepts with external academic citations | E01, E03; citations to be verified in P9-R0 |
| Methodology | Controlled lab, taxonomy, contexts, split, freeze, and report-only protocol | E02, E04, E05; Table T01 |
| Architecture and implementation | Pipeline, three methods, provenance, and read-only interface | E01, E03, E06 |
| Results | Exact accepted descriptive values only | Tables T01-T02; Figures F01-F02 |
| Discussion and validity | Interpretation, claim-to-evidence links, and limitations | Table T03; C01-C08 and B01-B08 |
| Conclusions | Bounded findings and explicitly scoped future work | E01, E05, E06 |

During Phase 9:

1. exact values must be copied from the accepted JSON/CSV assets, not
   recomputed from runtime data;
2. every supported claim must retain its recorded limitation;
3. blocked claims remain prohibited even if prose or figure styling changes;
4. implemented, tested, proposed, and out-of-scope work must stay distinct;
5. the masks must not be described as independent experiments; and
6. Hybrid must not be described as numerically or statistically superior.

External academic sources and citations are not frozen by P8-R3. P9-R0 must
verify them separately and connect them to the background and methodology
without using literature to enlarge the empirical claims of this project.

## 6. Final acceptance commands

The final acceptance sequence is:

```bash
python -m pytest -q tests/unit/test_p8_r3_phase8_closeout.py
python -m pytest -q tests/unit/test_p7_r*.py tests/unit/test_p8_r*.py
python -m pytest -q tests/unit/test_p6_r*.py
python -m pytest -q
```

Acceptance also requires the P8-R3 manifest to validate against its Draft
2020-12 schema, the tracked closeout to rebuild byte-identically, all five
thesis assets to retain their accepted hashes, all 1,488 runtime artifacts and
the private archive to remain unchanged, the laboratory to remain stopped,
and the worktree to contain only the intended P8-R3 files before commit.

## 7. Phase 8 closure

Phase 8 is complete. The project now has a frozen empirical boundary, a
byte-preserving final-evidence archive, thesis-ready exact-value tables and
figures, a bounded claim-to-evidence matrix, and a machine-readable writing
handoff. Phase 9 may write and present this work; it may not silently reopen or
extend the accepted experiment.

P9-R0 is next: Thesis Structure and Source/Citation Gate.
