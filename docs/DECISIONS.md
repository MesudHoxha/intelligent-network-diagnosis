# DECISIONS

## D-001 — Domain

Decision: Combine computer networking with AI/ML.
Status: Approved.

## D-002 — Main problem

Decision: Diagnose and explain computer-network problems.
Status: Approved.

## D-003 — Methodology

Decision: Compare rule-based, Machine Learning, and hybrid approaches.
Status: Approved.

## D-004 — Budget

Decision: Use zero-budget or minimal-budget tools. No paid dependency
is mandatory.
Status: Approved.

## D-005 — Execution model

Decision: Prefer local execution and open-source technologies.
Status: Approved.

## D-006 — Ambition level

Decision: Develop an ambitious bachelor project incrementally, with a
working end-to-end baseline before advanced extensions.
Status: Approved.

## D-007 — Remediation

Decision: The base system diagnoses and recommends actions but does
not automatically modify network configurations.
Status: Approved.

## D-008 — Laboratory platform

Decision: Use Ubuntu on WSL2, Docker, Containerlab, Linux containers,
and FRRouting as the primary laboratory platform.
Status: Technically confirmed.

## D-009 — Dataset origin

Decision: Generate the dataset from controlled virtual-laboratory
experiments rather than manually invented rows.
Status: Approved.

## D-010 — Experimental scope

Decision: Include single faults, missing evidence, unseen variants,
and a controlled subset of multiple-fault scenarios.
Status: Approved.

## D-034 — Dynamic routing

Decision: Use OSPF as the first dynamic routing protocol. BGP remains
optional.
Status: Proposed.

## D-037 — First proof of concept

Decision: Use HostA--R1--R2--HostB with a missing static route as the
first end-to-end experiment.
Status: Approved for implementation.

## D-040 — Normal class

Decision: Include valid no-fault experiments in the dataset.

Status: Implemented and tested for canonical and alternate
HostB-subnet variants. Both variants completed twice in the
accepted P1_ROUTING_VARIANTS pilot batch.

## D-041 — Missing evidence

Decision: Distinguish true, false, and unavailable evidence.
Status: Approved.

## D-042 — Dataset splitting

Decision: Split datasets by scenario or topology groups rather than
only random row-level splitting.
Status: Approved.

## D-043 — Main development environment

Decision: Use Ubuntu 24.04 under WSL2 rather than the existing
VirtualBox Ubuntu VM.
Status: Confirmed and tested.

## D-044 — PoC-A completion

Decision: The first end-to-end proof of concept is accepted as
technically complete.

Verified scenario:
- Missing static route on R1 toward the HostB network

Verified components:
- Baseline validator
- Fault injector
- Evidence collector
- Rule-based engine
- Evaluator
- Experiment runner
- Automatic restoration

Status: Implemented and tested.

Limitation:
The result applies only to the implemented controlled scenario and
must not be interpreted as general model or system performance.

## D-045 — PoC-B completion

Decision: Accept C2_WRONG_NEXT_HOP as the second end-to-end
controlled proof of concept while preserving the verified
behavior of C1_MISSING_STATIC_ROUTE.

Verified C2 behavior:

- R1's correct next-hop is replaced with 10.10.12.254.
- HostB becomes unreachable during the injected fault.
- The collector identifies the configured next-hop.
- The collector determines that this next-hop is unreachable.
- Rule R_ROUTING_002 diagnoses wrong_next_hop.
- Automatic evaluation reports exact_match: true.
- Restoration returns TOP-01 to its 9/9 baseline.
- C1 continues to match R_ROUTING_001 after the extension.

Status: Implemented and tested.

Limitation:
The result covers two deterministic controlled routing scenarios.
It is not evidence of general system or model performance.

## D-046 — Static-routing evidence

Decision: For the current static-routing scenarios, collect route
presence, parse the configured next-hop, and test that next-hop
through an active reachability probe.

The neighbor table from `ip neigh` is not mandatory at this stage.
It may be added later as complementary evidence if another
scenario requires it.

Status: Implemented and tested for TOP-01 C1 and C2.

## D-047 — Ground-truth isolation

Decision: Evidence collection and diagnostic methods must not
read ground-truth data. Ground truth may be used by the evaluator
only after a diagnosis has been produced.

Status: Confirmed for the current Collector and Rule Engine
through source audit.

## D-048 — Experiment manifest contract

Decision: Use Experiment Manifest v2 as the canonical contract
for newly executed experiments.

The manifest records the experiment, scenario and topology
identities; scenario schema version and kind; variant and split
group; diagnostic method; artifact paths; timestamps; current
state; and complete state history.

The contract is represented by a runtime validator and a
JSON Schema document.

Status: Implemented and covered by automated tests. Its real
normal execution path was verified through
n0_normal_operation-20260728T133851Z.

## D-049 — Dataset row contract

Decision: Use Dataset Row v1 with one row per completed
experiment and fault_type as the initial supervised-learning
target.

Diagnostic features use true, false, or unavailable. Scenario
identity, concrete IP addresses, ground truth, rule outputs, and
evaluation results must not be used as model features.
Dataset splitting must use split_group_id to prevent related
scenario variants from crossing dataset partitions.

Status: Implemented and tested through historical C1/C2 exports,
the first real N0 no-fault row, the three-row B0 smoke batch, and
the accepted 12-row P1 routing-variants pilot. Parameterized
generation has started at pilot scale; group-aware splitting and
ML training have not started.

## D-050 — Dataset-batch planning contract

Decision: Use Batch Plan v1 as the canonical input contract for
reproducible dataset-batch planning.

The first version uses execution.order=listed and
execution.failure_policy=stop. Repetition counts are expanded into a
deterministic sequence before execution, and referenced scenario
files must pass plan validation.

The contract is represented by a runtime validator and a JSON
Schema document.

Status: Implemented and covered by automated tests. The canonical
B0_SMOKE_CANONICAL plan validates as three planned experiments in
the order N0, C1, and C2. The current full test suite has 80 passing
tests.

Limitation:
Validation and deterministic expansion of a batch plan do not by
themselves demonstrate successful laboratory execution. Real
execution must be verified separately through batch metadata,
Dataset Row v1 records, and the final laboratory baseline.

## D-051 — Batch execution and aggregation contract

Decision: Use Batch Runner v1 as the canonical orchestration layer
between Batch Plan v1, the existing experiment runner, and Dataset
Row v1 aggregation.

The runner must preserve listed order, use failure_policy=stop,
require a COMPLETED experiment result, validate every generated
Dataset Row v1, require sample_id to match experiment_id, and reject
duplicate sample identifiers or experiment directories.

Batch-level metadata is persisted throughout execution. The final
JSONL dataset is written atomically only after every planned
experiment succeeds. Existing dataset and batch-result outputs must
not be overwritten.

Default experiment and batch-run identifiers use UTC timestamps with
microsecond precision plus UUID values to avoid collisions during
repeated execution.

Status: Implemented, covered within the full automated suite of
80 passing tests, and verified through the real B0 smoke batch and
the 12-experiment P1 routing-variants pilot.

Limitation:
The contract establishes technical execution and valid aggregation.
Batch status COMPLETED does not by itself establish diagnostic
correctness or general model performance.

## D-052 — First real canonical smoke batch

Decision: Accept the successful B0_SMOKE_CANONICAL execution as the
first end-to-end validation of Batch Runner v1 and real Dataset Row
v1 aggregation.

The accepted batch run is
b0_smoke_canonical-20260729T110541686889Z-3866a05ce64f4363afec8ae7ace6ef97.
It executed N0_NORMAL_OPERATION, C1_MISSING_STATIC_ROUTE, and
C2_WRONG_NEXT_HOP in listed order with failure_policy=stop.

Status: Completed and semantically verified on 2026-07-29. All three
experiments completed, all three Dataset Row v1 records passed
contract and cross-artifact checks, and TOP-01 finished with a valid
9/9 baseline.

Limitation:
This is a smoke-validation artifact with three rows. Repeated and
parameterized variants, group-aware splitting, ML training, hybrid
diagnosis, and comparative evaluation have not yet been completed.

## D-053 — Batch completion and diagnostic quality

Decision: Preserve COMPLETED as the technical batch-execution and
aggregation status. Diagnostic correctness, including exact_match,
is a separate evaluation result and must not redefine batch
completion.

A technically completed experiment may still provide a valid
ground-truth-labelled Dataset Row v1 when the rule-based method makes
an incorrect prediction. Rejecting such rows according to rule-based
accuracy would bias the dataset and weaken the later comparison
between rule-based, Machine Learning, and hybrid methods.

Rule outputs and evaluation results remain excluded from model
features. A reusable batch-level evaluation summary or
validation_status may be implemented later as a separate reporting
layer, but it is not part of Batch Runner v1 completion semantics.

Status: Approved after audit on 2026-07-30.

## D-054 — First parameterized routing pilot batch

Decision: Accept the corrected P1_ROUTING_VARIANTS execution as the
first verified parameterized routing pilot dataset.

The accepted batch run is
p1_routing_variants-20260730T082450785454Z-
f283bfdd9ccc4b04afbc6462f6073a63.

It contains canonical and alternate HostB-subnet variants for N0,
C1, and C2 with two repetitions per variant. It produced 12 completed
experiments, 12 valid Dataset Row v1 records, 12/12 rule-based exact
matches, and a final valid TOP-01 13/13 baseline.

The earlier batch
p1_routing_variants-20260730T074627928794Z-
2b0c7bd987aa4a25aca81133275ae2d3
remains unchanged as regression evidence. Its COMPLETED status is
technically valid, but its 8/12 exact-match result means it is not the
accepted P1 artifact for subsequent ML work.

Status: Completed and semantically verified on 2026-07-30.

Limitation:
Twelve rows, three classes, two subnet variants, and two repetitions
are sufficient for pipeline validation, not for final ML training or
claims of general diagnostic performance.
