# P8-R0 Evidence-Completeness and Thesis-Claim Scope Gate

Date: 2026-08-11

Status: FROZEN — NO NEW EXPERIMENT REQUIRED

## 1. Purpose

P8-R0 decides whether the accepted project evidence is sufficient for
the bachelor thesis research question and freezes what may and may not
be claimed. It is a scope and evidence gate, not an experimental run.

The gate reads the already accepted P7-R1 catalog and its 15 JSON/JSONL
sources through the fail-closed artifact loader. It does not start
Containerlab, deserialize the estimator, execute a diagnosis, recompute
a metric, revise a rule, refit a model, reselect a policy, or reopen the
consumed E02/E06 report-only test partition.

The machine-readable outcome is
`plans/phase8/P8_R0_EVIDENCE_CLAIM_SCOPE_V1.json`. Its exact numeric
snapshot is generated from the locally accepted, hash-verified
comparison rather than copied from prose.

## 2. Evidence inventory

The evidence is separated by role so that development milestones are
not silently promoted into final performance evidence.

| ID | Stage | Evidence role | Acceptance basis | Thesis use |
| --- | --- | --- | --- | --- |
| E01 | P1 | End-to-end pipeline validation | Accepted central records | Explain controlled injection, passive collection, diagnosis, evaluation, restoration, and baseline recovery |
| E02 | P2 | Pilot multiclass dataset | P2-R10 accepted runtime identities | Explain the 30-row, three-class, five-context pilot and grouped split |
| E03 | P3-P5 | Method development | Accepted Rule, ML, and Hybrid HANDOFFs | Explain why the three methods and frozen comparison protocol exist |
| E04 | P6-R5 | Final clean dataset | Accepted campaign and dataset identities | Support the six-class, six-context, 72-row, 36/12/24 whole-context dataset claim |
| E05 | P6-R6 | Final method evaluation | Hash-verified now through the P7 catalog | Supply the final clean, missing-evidence, and overall three-method comparison |
| E06 | P7 | Local presentation | Phase 7 closeout | Demonstrate local read-only inspection of accepted results and limitations |

E05 is the final numerical result. Earlier metrics remain useful for
development history and method justification, but they do not replace
or enlarge the P6-R6 final evaluation.

## 3. Final evaluation completeness

The accepted final evaluation satisfies the thesis-critical comparison
requirements:

- exactly three methods are present: Rule-based, Machine Learning, and
  Hybrid;
- the methods share the same 24 clean E02/E06 test inputs and the same
  96 deterministic masked transformations;
- the selected ML model and Hybrid policy were frozen before test
  access;
- the test authorization was consumed once;
- no post-freeze refit, policy reselection, or test-guided revision is
  recorded;
- all three methods have clean, masked, and overall metrics under one
  comparison contract;
- the comparison is explicitly descriptive-only; and
- no statistical-superiority test is reported.

The evidence therefore answers the bounded bachelor-level question:
how a traditional Rule-based method, an interpretable supervised ML
baseline, and a rule-first/ML-fallback Hybrid method behave in the
implemented controlled taxonomy under complete and deterministically
missing evidence.

The research goal does not require the Hybrid method to numerically
outperform ML. The accepted result instead supports the narrower
architectural finding: the Hybrid keeps the deterministic rule path
when it can resolve the case and uses the frozen ML fallback when the
strict rule path lacks evidence. Its final aggregate metrics equal ML,
so no Hybrid performance advantage is claimed.

## 4. Frozen supported claims

The machine-readable matrix freezes eight bounded claims:

1. the controlled end-to-end diagnostic and dataset pipeline is
   implemented;
2. the final clean dataset covers six classes and six contexts with a
   36/12/24 whole-context split;
3. Rule-based, ML, and Hybrid methods are compared under one frozen
   report-only protocol;
4. all three methods completely classify the 24 clean final test
   inputs;
5. under deterministic missing evidence, Rule-based fails closed while
   ML and Hybrid retain full coverage and non-zero aggregate accuracy;
6. the Hybrid rule-first/ML-fallback policy and provenance are
   implemented, without a Hybrid-advantage claim;
7. accepted evidence and limitations are available through a local
   fail-closed read-only interface; and
8. the accepted run preserves the frozen development/test boundary and
   records no test-guided revision.

Each claim must carry its recorded limitation. A thesis paragraph,
table, figure, slide, or defense answer must not remove that limitation
or broaden the subject from the implemented controlled laboratory to
general networks.

## 5. Frozen prohibited claims

The following statements remain outside the evidence:

- Hybrid statistically outperforms ML or Rule-based diagnosis;
- the metrics generalize to real-world or unseen production networks;
- the 96 deterministic masks are independent network experiments;
- the system diagnoses simultaneous multiple faults;
- the system supports OSPF or arbitrary dynamic-routing failures;
- the Dashboard performs live inference, remediation, or production
  monitoring;
- confidence values are calibrated uncertainty estimates; or
- the results establish population-level statistical significance.

These are not merely missing phrases. They are explicit claim
prohibitions and must remain visible in the final thesis limitations.

## 6. Gap decision

No thesis-critical empirical runtime gap remains. P8-R0 therefore
records `NO_NEW_EXPERIMENT_REQUIRED`.

Two thesis-critical non-empirical gaps remain:

1. **Reproducibility archive.** The Phase 7 private bundle contains the
   15 sources needed to present the final comparison, but it is not a
   complete archive of the accepted experimental chain. P8-R1 must
   create an immutable registry and private archive from already
   existing accepted artifacts. It may hash and copy them, but may not
   execute experiments, mutate evidence, or deserialize the estimator.
2. **Evaluation synthesis.** P8-R2 must create thesis-ready tables,
   figures, and claim-to-evidence references from accepted metrics. It
   may format or visualize values, but may not recompute the experiment,
   invent a metric, or introduce a new empirical claim.

After those two steps, P8-R3 performs the final Phase 8 acceptance and
handoff to Phase 9 thesis writing and defense preparation.

## 7. Frozen Phase 8 sequence

| Milestone | Authorized work | Explicitly absent |
| --- | --- | --- |
| P8-R0 | Evidence inventory, claim matrix, gap and scope decision | New experiment, new metric, test reopening |
| P8-R1 | Immutable evidence registry and private reproducibility archive | Artifact mutation, inference, estimator deserialization |
| P8-R2 | Thesis-ready evaluation tables, figures, and evidence references | Refit, reselection, recomputation, new empirical claim |
| P8-R3 | Phase 8 acceptance closeout and Phase 9 handoff | Scope expansion |

## 8. Acceptance conditions

P8-R0 is acceptable only when:

- the P7 catalog loads all 15 sources and fails closed on drift;
- the final comparison has the frozen methods, scopes, counts, and
  protocol roles;
- the generated scope manifest validates against
  `p8_evidence_claim_scope_v1.schema.json`;
- its catalog, comparison, and method-gate bindings match the current
  accepted bytes;
- every supported claim references inventoried evidence and includes a
  limit;
- all ten runtime authorization flags are false;
- central documents and the HANDOFF record D-091 and P8-R1 as next;
  and
- the full regression suite remains green.

Final development verification passed 15/15 P8-R0 tests, 100/100
combined Phase 7 plus P8-R0 tests, 185/185 targeted Phase 6 tests, and
528/528 full regression tests. The 15 accepted projection sources
retained their bytes throughout verification.

## 9. Interpretation boundary

P8-R0 is evidence of disciplined claim control, not new diagnostic
performance. The final thesis may accurately report the accepted
numeric values from the generated scope manifest and accepted reports.
It may not reinterpret a descriptive controlled comparison as a
statistical or real-world conclusion.
