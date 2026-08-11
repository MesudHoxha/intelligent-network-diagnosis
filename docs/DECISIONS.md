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

Status: Implemented and tested through the deterministic group-aware
splitter specified in D-055 and corrected by D-058.

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
generation has started at pilot scale. Complete evaluation-context
splitting is implemented and tested under D-058, but P1 uses
historical class-specific groups that do not contain the complete
required class set. Dataset Row v1 remains the immutable historical
P1 contract and adapts Evidence v2 only for the legacy TOP-01 r1/r2
binding. Dataset Row v2 supersedes it as the canonical contract for
new rows under D-057. ML training has not started.

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
the order N0, C1, and C2. The complete automated suite has 126
passing tests.

Limitation:
Validation and deterministic expansion of a batch plan do not by
themselves demonstrate successful laboratory execution. Real
execution must be verified separately through batch metadata,
Dataset Row v1 records, and the final laboratory baseline.

## D-051 — Batch execution and aggregation contract

Decision: Use Batch Runner v1 as the canonical orchestration layer
between Batch Plan v1, the existing experiment runner, and versioned
Dataset Row aggregation. This decision was initially implemented with
Dataset Row v1; D-057 makes v2 the canonical output for new runs.

The runner must preserve listed order, use failure_policy=stop,
require a COMPLETED experiment result, validate every generated
Dataset Row, require sample_id to match experiment_id, and reject
duplicate sample identifiers, experiment directories, or mixed row
versions.

Batch-level metadata is persisted throughout execution. The final
JSONL dataset is written atomically only after every planned
experiment succeeds. Existing dataset and batch-result outputs must
not be overwritten.

Default experiment and batch-run identifiers use UTC timestamps with
microsecond precision plus UUID values to avoid collisions during
repeated execution.

Status: Implemented and verified through the real B0 smoke batch and
the 12-experiment P1 routing-variants pilot. Under D-057, the default
row builder now produces Dataset Row v2. The batch boundary validates
either supported row version, records the batch dataset version, and
rejects mixed-version aggregation. The complete automated suite has
126 passing tests.

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
## D-055 — Group-aware dataset splitting contract

Decision: Use a deterministic, class-stratified, group-aware
train/validation/test splitter.

The original implementation assigned every split_group_id wholly to
one partition, required exactly one fault_type in each group, and used
the algorithm identifier stratified_group_hash_v1.

Status: The original contract was implemented and tested. Its
single-class grouping semantics and per-class allocation were
superseded by D-058 after the P2-R2 audit showed that classes from the
same laboratory context could otherwise cross partitions. The
requirements for deterministic whole-group allocation, homogeneous
Dataset Row versions, pre-output feasibility validation, output
hashes, and a split manifest remain in force under D-058.

Limitation:

The original splitter did not make P1 training-ready and did not
prevent shared laboratory context from appearing across partitions
through different fault classes. D-058 defines the corrected
evaluation-context boundary.

## D-056 — Role-neutral observation and evidence contract

Decision: Represent diagnostic context through topology and node
roles rather than fixed TOP-01, hosta_to_hostb, r1, and r2
identifiers.

Observation Profile v1 derives topology_id from topology.id and
accepts validated generic direction, route-observer, and transit
roles. Evidence v2 is the canonical contract for newly collected
evidence and records these roles with role-neutral observation names.
It is enforced by both a runtime validator and a JSON Schema.

The collector must validate Evidence v2 before writing it. The Rule
Engine must validate collected Evidence v2 when reading it, while a
compatibility adapter preserves diagnosis of historical Evidence v1.
Diagnosis location, supporting evidence, and recommendations must use
the actual observer and transit roles.

Dataset Row v1 remains a historical P1 contract. It may adapt
Evidence v2 only for the legacy TOP-01 r1/r2 binding and must reject
other topology or observer/transit bindings. A role-neutral Dataset
Row v2 must be defined before TOP-02 evidence is exported for Machine
Learning.

Status: Implemented and covered by the full suite of 114 passing
tests. A real B0 regression completed N0, C1, and C2 with Evidence v2,
three exact rule-based matches, and valid TOP-01 13/13 baselines
before and after execution.

Limitation:

Synthetic unit fixtures exercise TOP-02 role names, and Dataset Row
v2 is now implemented under D-057. P2-R4 later verified one real
TOP_02_CHAIN context, but a multi-context campaign with materially
different observer/transit bindings remains pending.

## D-057 — Role-neutral Dataset Row v2 contract

Decision: Use Dataset Row v2 as the canonical contract for newly
generated dataset rows.

Dataset Row v2 keeps fault_type as the supervised-learning target and
uses seven tri-state diagnostic features named through source,
destination, route-observer, and transit roles. Its metadata records
the explicit topology, direction, route-observer, transit, variant,
and split-group context. Concrete IP addresses, ground truth, rule
outputs, and evaluation results remain excluded from model features.

Dataset Row v1 remains an immutable historical contract with explicit
builders and validators. Migration from v1 to v2 must be an explicit
operation and is defined only for the historical TOP_01,
hosta_to_hostb, r1/r2 context. Migration maps only the approved
feature names and preserves sample identity, split_group_id, labels,
and quality fields.

Batch Runner uses the v2 builder by default, persists
dataset_row_schema_version, and must reject mixed row versions in one
dataset. The group-aware splitter accepts either a homogeneous v1 or
homogeneous v2 source, records source_dataset_schema_version, and
must also reject mixed-version input.

Status: Implemented and covered by the complete automated suite of
126 passing tests. The real B0 regression
b0_smoke_canonical-20260730T115517979203Z-
24c80549d03d4e84ad7e066f19409ecb produced three validated Dataset
Row v2 records for N0, C1, and C2, with three exact rule-based
matches and valid TOP-01 13/13 baselines before and after execution.

Limitation:

The P2-R1 regression used only TOP-01. P2-R4 later verified Dataset
Row v2 through one real TOP_02_CHAIN context, but sufficient complete
evaluation contexts, ML readiness, and general diagnostic performance
remain unestablished.

## D-058 — Evaluation-context grouping protocol

Decision: Use split_group_id as the complete evaluation-context
boundary for train/validation/test splitting.

One evaluation context is defined by its topology graph and forwarding
configuration, directed diagnostic path, route-observer and transit
role binding, logical fault-injection location, and diagnostic
evidence producers. All approved no-fault and fault classes generated
from that context must use the same split_group_id and remain wholly
inside one partition.

Repetitions, alternate IP addresses or subnets on the same logical
path, node renaming, timestamps, experiment identifiers, and small
parameter variations do not create new groups. A nominal reverse
direction also does not create a group when it only relabels an
otherwise equivalent causal path.

The splitter uses algorithm identifier
complete_context_group_hash_v2. It requires every group to contain
every required fault_type, supports an explicit expected_fault_types
set, requires at least three complete context groups for a three-way
split, and produces a deterministic whole-group allocation. Dataset
Row v2 remains unchanged; no parallel evaluation_context_id field is
introduced.

Five complete contexts are the readiness target for the first ML
experiment. With the default 0.6/0.2/0.2 ratios, they produce a 3/1/1
group allocation. With three current classes and two repetitions per
class and context, the minimum planned campaign contains 30 rows.

The planned context matrix contains one TOP-01 context, three
materially distinct TOP-02 contexts, and one TOP-03 asymmetric
context. These are planned coverage slots, not claims that TOP-02 or
TOP-03 has been implemented. Any two designs that collapse to the
same causal context must share one group, and another reviewed context
must be added.

The historical P1 and P2-R1 smoke datasets remain unchanged. Their
class-specific split_group_id values are valid historical metadata but
do not satisfy this protocol and must be rejected as ML split sources.

Status: Approved and implemented in src/dataset/splitter.py. The
complete automated suite has 128 passing tests. The historical P1
dataset was verified to be rejected because its evaluation-context
groups do not contain the complete current class set. The protocol is
recorded in docs/EVALUATION_GROUP_PROTOCOL.md.

ML readiness remains blocked until all five reviewed contexts are
implemented, each contains the complete approved class set, the
expanded campaign succeeds, and the generated split manifest passes
an explicit no-cross-partition group audit.

## D-059 — Frozen TOP-02 evaluation-context designs

Decision: Freeze concrete static-routing designs and future
split-group bindings for G01-G04 before implementing a TOP-02
laboratory.

The frozen identifiers are:

- G01: TOP_01 with CTX_G01_TOP01_LINEAR_2R;
- G02: TOP_02_CHAIN with CTX_G02_TOP02_CHAIN_3R;
- G03: TOP_02_BRANCH with CTX_G03_TOP02_BRANCH_MID; and
- G04: TOP_02_DUAL_TRANSIT with
  CTX_G04_TOP02_DUAL_TRANSIT.

G02 uses a three-router forwarding chain and observes r1 through
transit r2 while destination reachability from r2 depends on r3.

G03 uses an interior route observer at a real two-arm branch. The
source gateway and route observer are different, and C1/C2 are
injected at the interior branch router.

G04 uses two live transit arms. Its selected path uses one transit,
while C2 points the destination route to an unreachable address on
the other active transit segment and egress interface.

Every current class inside one context must use the same frozen
split_group_id. Static routing and the existing Observation Profile
v1, Evidence v2, and Dataset Row v2 contracts remain in force.
Historical artifacts are not rewritten.

The semantic design descriptors are normative under
docs/TOP02_CONTEXT_DESIGN.md. Cryptographic SHA-256 fingerprints are
recorded only after real topology, validator, and scenario files
exist.

Implementation order: P2-R4 implements G02 first, P2-R5 implements
G03 only after the real G02 pipeline succeeds, and P2-R6 implements
G04 only after the successful G03 gate. OSPF remains proposed under
D-034 and is not introduced by this decision.

Status: Design reviewed and approved. P2-R4 implemented and verified
G02, P2-R5 implemented and verified G03, and P2-R6 implemented and
verified G04 without changing their frozen descriptors or group
bindings.

Limitation:

Distinct designs establish a controlled implementation plan. They do
not count as experimental contexts, dataset samples, or evidence of
ML readiness until each laboratory and complete class set has been
executed and audited.

## D-060 — First real TOP-02 context

Decision: Accept G02 TOP_02_CHAIN as the first implemented and
verified non-TOP-01 evaluation context.

The implementation contains:

- the five-node hosta-r1-r2-r3-hostb Containerlab chain;
- 10.20.1.0/24, 10.20.12.0/29, 10.20.23.0/29, and
  10.20.3.0/24 addressing;
- a 28-check baseline validator;
- N0, C1, and C2 scenario bindings that all use
  CTX_G02_TOP02_CHAIN_3R;
- a three-entry fail-stop smoke plan; and
- static contract and topology tests.

The HostB baseline includes the explicit return route
10.20.23.0/29 via 10.20.3.1. This route is required so the r2 transit
probe can receive its reply through r3. It does not change the frozen
forwarding graph, observation roles, fault target, or evidence
producers.

The normalized topology, validator, and N0/C1/C2 scenario bundle has
SHA-256:

fa411079e19fa7047a467ae46ff1ba7edd54657daee254f74f6c57cd58e4adc3

The accepted real batch run is
p2_g02_smoke-20260730T133227173375Z-
c74243e48485444fa795cb0f852f58d7.

Status: Implemented and verified on 2026-07-30. Six targeted tests and
the complete 134-test suite passed. The initial and final G02
baselines each passed 28/28 checks. All three planned experiments
completed, all Evidence v2 and Dataset Row v2 artifacts passed
contract audits, all three rule-based evaluations had exact_match
true, and C1/C2 restoration returned the full baseline to VALID.

Limitation:

This accepted smoke batch contains one execution of each current
class in one context. It verifies the first real non-TOP-01 pipeline
and one complete G02 class set; it does not satisfy the two-repetition
campaign target, the five-context ML-readiness gate, a valid
train/validation/test split, or general diagnostic performance.

## D-061 — First real interior branched observation context

Decision: Accept G03 TOP_02_BRANCH as the implemented and verified
interior branched evaluation context.

The implementation contains:

- the seven-node hosta-r1-r2-{r3-hostb,r4-hostc} Containerlab graph;
- the two live destination arms rooted at the interior r2 branch;
- a 40-check baseline validator covering addressing, forwarding,
  routes, both destination arms, and wrong-next-hop preconditions;
- N0, C1, and C2 scenario bindings that all use
  CTX_G03_TOP02_BRANCH_MID;
- the hosta_to_hostc direction with observer r2 and transit r4;
- C1/C2 injection only on the r2 route toward 10.30.4.0/24;
- a three-entry fail-stop smoke plan; and
- static contract, topology, and cross-context distinction tests.

Separate C1 and C2 runtime audits are required evidence for the
material branch. In each fault state, HostA cannot reach HostC, while
HostA can still reach HostB through r3. R2 can still reach the correct
r4 next hop, and r4 can still reach HostC. The selected fault
therefore affects only the observed HostC arm and does not collapse
G03 into a renamed linear context.

The normalized topology, validator, and N0/C1/C2 scenario bundle has
SHA-256:

2092d0702a8e107a7757ff1754872f518f0be25c89883edb2c5638371a18f0fc

The accepted real batch run is
p2_g03_smoke-20260731T065808868462Z-
a2b3766efaa449aeaf9007d4d1b664ea.

Status: Implemented and verified on 2026-07-31. Seven targeted tests
and the complete 141-test suite passed. The initial and final G03
baselines each passed 40/40 checks. Both branch-isolation audits
passed. All three planned experiments completed, all Evidence v2 and
Dataset Row v2 artifacts passed contract and semantic audits, the
r2/r4 role binding was verified, all three rule-based evaluations had
exact_match true, and C1/C2 restoration returned the complete
baseline to VALID.

Limitation:

This accepted smoke batch contains one execution of each current
class in one context. At P2-R5 closeout, G02 and G03 provided two
verified complete-class smoke contexts. P2-R6 later verified G04.
None has the planned two repetitions, and future G01 campaign
bindings plus G05 implementation remain pending, so the five-context
ML-readiness gate, valid train/validation/test split, and general
diagnostic performance are not established.

## D-062 — First real dual-transit cross-segment context

Decision: Accept G04 TOP_02_DUAL_TRANSIT as the implemented and
verified source-gateway dual-transit evaluation context.

The implementation contains:

- the six-node hosta-r1-{r2-hostb,r3-hostc} Containerlab graph;
- two live transit arms rooted at the r1 route observer;
- a 33-check baseline validator covering addressing, forwarding,
  routes, both transit arms, and wrong-next-hop preconditions;
- N0, C1, and C2 scenario bindings that all use
  CTX_G04_TOP02_DUAL_TRANSIT;
- the hosta_to_hostc direction with observer r1 and transit r3;
- C1 injection only on the r1 route toward 10.40.3.0/24;
- C2 replacement of the selected route from correct
  10.40.13.2/eth3 to unreachable 10.40.12.6/eth2 on the other live
  transit segment;
- a three-entry fail-stop smoke plan; and
- static contract, topology, and cross-context distinction tests.

Separate C1 and C2 runtime audits are required evidence for the
material dual-transit context. The selected HostC path must fail while
the r2-HostB alternate arm remains reachable. For C2, the real r2
neighbor and correct r3 neighbor must remain reachable, the
r3-HostC segment must remain healthy, and the configured destination
route must use 10.40.12.6 through eth2. These checks establish a
cross-segment wrong-next-hop fault rather than a same-link or renamed
branch variant.

The normalized topology, validator, and N0/C1/C2 scenario bundle has
SHA-256:

1e9aa7d2ea8ea1f1691821f8639c60820bbdcd9c0d0bd182e4b72b810b948d54

The accepted real batch run is
p2_g04_smoke-20260731T074745682481Z-
5c865fccfdf244858aa04003187730a4.

Status: Implemented and verified on 2026-07-31. Seven targeted tests
and the complete 148-test suite passed. The initial and final G04
baselines each passed 33/33 checks. The C1 isolation audit, C2
cross-segment next-hop audit, and runtime distinction audit passed.
All three planned experiments completed, all Evidence v2 and Dataset
Row v2 artifacts passed contract and semantic audits, the r1/r3 role
binding was verified, all three rule-based evaluations had
exact_match true, and C1/C2 restoration returned the complete
baseline to VALID. Laboratory cleanup also passed.

Limitation:

This accepted smoke batch contains one execution of each current
class in one context. Together, G02, G03, and G04 provide three
verified complete-class TOP-02 smoke contexts, but none has the
planned two repetitions. Future G01 campaign bindings and the G05
TOP-03 asymmetric implementation remain pending, so the five-context
ML-readiness gate, valid train/validation/test split, and general
diagnostic performance are not established.

## D-063 — Frozen TOP-03 asymmetric-return context design

Decision: Freeze G05 as TOP_03_ASYMMETRIC_RETURN with
split_group_id CTX_G05_TOP03_ASYMMETRIC_RETURN before creating its
laboratory.

The physical router graph is the cycle r1-r2-r3-r4-r1, with HostA
attached to r1 and HostB attached to r3. The selected forward path is
hosta-r1-r2-r3-hostb. The selected return path is
hostb-r3-r4-r1-hosta.

The diagnostic direction is hosta_to_hostb. R2 is the forward-only
route observer and r3 is the selected transit. C1 removes the r2
route toward 10.50.3.0/24. C2 retains that route but replaces correct
next hop 10.50.23.2 with unassigned 10.50.23.6 on the r2-r3 segment.

The material distinction is the forwarding asymmetry: r2 is present
only on the selected forward path, while r4 is present only on the
selected return path. IP-address variation, node renaming, or a
nominal reverse direction is not the basis for a separate group.

The implementation must disable and verify reverse-path filtering on
the asymmetric routed path. Its baseline and runtime audits must
prove the frozen forward route lookups, return route lookups,
adjacent-hop health, selected fault isolation, and restoration.
Fault-state return-corridor health is established through route
lookups and adjacent-hop reachability rather than a reverse
end-to-end ping whose reply would traverse the intentionally faulty
forward direction.

Observation Profile v1, Evidence v2, Dataset Row v2, the seven
approved features, static routing, and the current no_fault,
missing_static_route, and wrong_next_hop class set remain unchanged.
The return-only r4 corridor is distinction evidence outside Dataset
Row v2, not a new model feature.

The normative graph, addressing, route intent, bindings, acceptance
rules, and semantic descriptor are recorded in
docs/TOP03_CONTEXT_DESIGN.md. A real artifact SHA-256 is recorded
only after the topology, validator, and scenario files exist and
pass runtime verification.

Status: Design reviewed and approved. No G05 topology, validator,
scenario, experiment, Evidence v2 artifact, Dataset Row v2 record,
artifact SHA-256, or split has been implemented or verified.

Limitation:

The frozen design does not count as the fifth implemented context or
satisfy ML readiness. G05 implementation, future G01 campaign
bindings, the two-repetition 30-row campaign, and a valid D-058
grouped split remain required before ML training.

## D-064 — First real asymmetric-return context

Decision: Accept G05 TOP_03_ASYMMETRIC_RETURN as the implemented and
verified asymmetric-return evaluation context.

The implementation contains:

- the six-node hosta-r1-r2-r3-r4 routed cycle with HostB attached to
  r3;
- a selected forward path
  hosta-r1-r2-r3-hostb and a distinct return path
  hostb-r3-r4-r1-hosta;
- a 52-check baseline validator covering addressing, forwarding,
  reverse-path filtering, routes, both directed paths, adjacency
  health, and wrong-next-hop preconditions;
- N0, C1, and C2 scenario bindings that all use
  CTX_G05_TOP03_ASYMMETRIC_RETURN;
- the hosta_to_hostb direction with observer r2 and transit r3;
- C1 injection only on the r2 route toward 10.50.3.0/24;
- C2 replacement of correct 10.50.23.2 with unreachable
  10.50.23.6 on the r2-r3 segment;
- a three-entry fail-stop smoke plan; and
- static contract, topology, reverse-path-filter, and cross-context
  distinction tests.

Separate C1 and C2 runtime audits are required evidence for the
material asymmetric context. The selected forward path must fail
while r2 can still reach r3, r3 can still reach HostB, r3 continues
to resolve HostA through r4, r4 continues through r1, and the
r3-r4-r1 adjacencies remain healthy. These fault-state route and
adjacency checks isolate the return corridor without relying on a
reverse end-to-end echo reply that would traverse the intentionally
faulty forward direction. Reverse-path filtering must remain
disabled as frozen by D-063.

The normalized topology, validator, and N0/C1/C2 scenario bundle has
SHA-256:

6bd4de9818ba0c3b589e5a17cf47553f523fc743d6feb12334bd525ea79ca870

The accepted real batch run is
p2_g05_smoke-20260731T083408705159Z-
4badf5fdf6da4141af74af11d4b5f1a2.

Status: Implemented and verified on 2026-07-31. Seven targeted tests
and the complete 155-test suite passed. The initial and final G05
baselines each passed 52/52 checks. The baseline and runtime
forward/return distinction audits, C1 asymmetric-isolation audit, C2
same-segment next-hop audit, and reverse-path-filter checks passed.
All three planned experiments completed, all Evidence v2 and Dataset
Row v2 artifacts passed contract and semantic audits, the r2/r3 role
binding was verified, all three rule-based evaluations had
exact_match true, and C1/C2 restoration returned the complete
baseline to VALID. Laboratory cleanup also passed.

Limitation:

This accepted smoke batch contains one execution of each current
class in one context. All five planned laboratory contexts now exist,
but future G01 rows still require their frozen complete-context
binding and none of the five contexts has the planned two campaign
repetitions per class. The consolidated 30-row campaign, valid
D-058 train/validation/test split, ML baseline, hybrid diagnosis, and
general diagnostic performance remain unestablished.

## D-065 — First five-context dataset campaign contract

Decision: Freeze Dataset Campaign Plan v1 and
P2_ROUTING_5CTX_V1 as the first ML-readiness campaign input.

The campaign retains the approved class set:

- no_fault;
- missing_static_route; and
- wrong_next_hop.

It contains the five frozen evaluation contexts G01-G05, one Batch
Plan v1 job per context, and two repetitions per class and context.
Each context batch therefore expands to six experiments, and the
complete campaign expands to exactly 30 experiments and 30 expected
Dataset Row v2 records.

The campaign is one logical fail-stop unit, but it is not one
Batch Runner invocation. Batch Runner v1 accepts one baseline
validator and runs against one deployed laboratory. The campaign
therefore lists five ordered context jobs, each with its own topology,
validator, and six-experiment Batch Plan v1. Cross-topology execution,
merge, campaign audit, and split are separate coordinator stages.

New G01 campaign scenarios bind N0, C1, and C2 to
CTX_G01_TOP01_LINEAR_2R. They preserve the TOP_01,
hosta_to_hostb, r1/r2 observation context and the existing canonical
fault semantics. Historical TOP-01 scenario files, experiment
artifacts, rows, and class-specific split groups remain unchanged.
G02-G05 reuse their verified scenario bindings without modification.

Dataset Campaign Plan v1 validates:

- exact plan structure and fail-stop listed execution;
- Dataset Row v2 as the only campaign row contract;
- unique group slots, split groups, and context batch plans;
- existing topology, validator, batch-plan, and scenario paths;
- executable baseline validators;
- topology, direction, observer, transit, and split-group bindings;
- exact ordered class coverage in every context;
- two repetitions for every class and context;
- six experiments per context and 30 in total; and
- the deterministic expected group allocation produced by
  complete_context_group_hash_v2.

The split seed remains 20260730 and the ratios remain 0.6/0.2/0.2.
With the frozen group identifiers, the deterministic allocation is:

- train: CTX_G03_TOP02_BRANCH_MID,
  CTX_G04_TOP02_DUAL_TRANSIT, and
  CTX_G05_TOP03_ASYMMETRIC_RETURN;
- validation: CTX_G01_TOP01_LINEAR_2R; and
- test: CTX_G02_TOP02_CHAIN_3R.

This produces 18 train rows, six validation rows, and six test rows
when every context supplies the required six rows. The allocation is
a pre-run consequence of the approved seed and frozen group
identifiers. Group identifiers and the seed must not be changed after
observing results to influence partition membership.

The normative plan, execution boundary, merge gates, quality gates,
rule-based reference audit, and split acceptance criteria are
recorded in docs/DATASET_CAMPAIGN_DESIGN.md.

Status: Approved and implemented as a validated planning contract on
2026-07-31. Nine targeted P2-R9 tests and the complete 164-test suite
passed. No real campaign experiment, merged 30-row dataset, campaign
result, or split artifact was created by this decision.

Limitation:

The campaign contract establishes executable inputs and precommits
the leakage-safe split. It does not establish that all 30 experiments
completed, that the rows passed merge and semantic audits, that the
split manifest passed the no-cross-partition audit, or that the
project is ML-ready. ML and hybrid work remain blocked until the real
campaign and split closeout succeed.

## D-066 — Class-conditional structural unavailability in P2

Decision: Correct the first campaign quality gate so that it matches
the already approved Dataset Row v2 tri-state semantics.

For P2_ROUTING_5CTX_V1, the exact unavailable-feature policy is:

- no_fault: zero unavailable features;
- missing_static_route: exactly one unavailable feature,
  route_next_hop_reachable_from_observer; and
- wrong_next_hop: zero unavailable features.

No other unavailable feature is accepted. All four execution-quality
booleans must remain true. The coordinator enforces both the exact
feature-name set and quality.unavailable_feature_count during each
context audit and again after the atomic merge.

Reason: C1 removes the observer route. With no configured route,
there is no configured next-hop address whose reachability can be
probed. Evidence v2 and the existing Dataset Row tests intentionally
represent that dependent observation as null/unavailable while the
independent expected-next-hop probe remains available. Requiring zero
unavailable features for C1 contradicted that contract and made the
frozen three-class campaign impossible to accept.

The correction does not change Evidence v2, Dataset Row v2, the seven
approved feature names, any label, the five contexts, repetitions,
split groups, seed, or expected 3/1/1 allocation. It does not impute a
value and does not weaken the missing-evidence gate: an unavailable
feature outside the exact class-conditional set still stops the
campaign.

Status: Approved as a corrective P2-R10 decision after the real
campaign attempt
p2_routing_5ctx_v1-20260804T070959526851Z-
9f1062d3dbdd44258657c144ec3755fc stopped safely at the G01 artifact
audit. The G01 batch completed 6/6, the final baseline and cleanup
completed, and no partial dataset was accepted. The corrected gate is
implemented with realistic C1 test fixtures and a negative test for
unexpected unavailable features. A complete new campaign attempt is
still required; selective reuse of rows from the failed attempt is
not permitted.

## D-067 — First accepted five-context campaign and grouped split

Decision: Accept the complete P2_ROUTING_5CTX_V1 campaign run
p2_routing_5ctx_v1-20260804T073429388394Z-
617194fea9954ed98ec120bdefea23d9 as the canonical first P2 dataset
campaign and accept its deterministic D-058 split as the input to the
reviewed baseline stages.

The accepted run is bound to:

- campaign-plan SHA-256
  b0d054001136358b51eb08620de2d5e500c32b755183ee812a4ad3cd8d09a0e4;
- context-fingerprint-manifest SHA-256
  f1e69b0d048785a45967593a12071b536027c65e2daddebafbaec296746c88b3;
- merged Dataset Row v2 JSONL SHA-256
  be92cef4e78764e772909e15f43ab5cba98ef9610f4a446fc95e8afb5e830c80;
- 30 unique experiments, samples, Evidence v2 artifacts, and Dataset
  Row v2 records;
- six rows per frozen context and ten rows per approved class;
- exactly one structurally unavailable
  route_next_hop_reachable_from_observer feature in each of the ten
  missing_static_route rows, and no unexpected unavailable feature;
- 30/30 rule-based exact matches and 30/30 correct affected-prefix
  results in the separate reference audit; and
- five valid initial baselines, five valid final baselines, and 5/5
  verified laboratory cleanup.

The split retains complete_context_group_hash_v2, seed 20260730, and
ratios 0.6/0.2/0.2. It contains:

- train: 18 rows in G03, G04, and G05, SHA-256
  cc196711cd2170bbd3393b3097b8b86d8bb12f8f8324f39f15b4a302c74859e8;
- validation: six rows in G01, SHA-256
  52c2215ebf97b7e9fb66720b3631431dddd2ede7462cf10163df3362a99bf5c4;
  and
- test: six rows in G02, SHA-256
  03383705cdab2368446cbf4a967e3c7bb71ae63379ab63dcad8a8ab678cc8a08.

No split_group_id crosses partitions. The failed earlier run remains
an incomplete diagnostic artifact and contributes no row to the
accepted merge or split. Generated datasets, experiment metadata, and
reports remain local runtime artifacts under the repository's
existing ignore policy; the accepted run identifier and cryptographic
bindings are recorded in the central documents.

Status: Implemented and verified on 2026-08-04. The corrected P2-R10
targeted suite passed 11/11 tests and the complete suite passed
175/175. The coordinator result passed its JSON Schema, all 30
artifacts were independently revalidated, the merged dataset and
partition hashes matched the written files, and cleanup passed.

Limitation:

This decision establishes reproducible execution, dataset integrity,
complete-context leakage control, and readiness for the reviewed
baseline stages. The 30 rows come from controlled deterministic
laboratories and only three classes. They do not establish real-world
generalization, statistical independence, ML performance, hybrid
performance, or superiority over the rule-based method. The frozen
test group must not be used for later model or feature selection.

## D-068 — Comparable partition-aware evaluation protocol

Decision: Use Method Evaluation Result v1 as the shared reporting
contract for the rule-based, Machine Learning, and hybrid diagnostic
methods.

The primary supervised target is fault_type with the frozen class
order no_fault, missing_static_route, and wrong_next_hop. Every method
must report partition-specific accuracy, per-class precision, recall,
F1 and support, unweighted macro precision, recall and F1, and the
same actual-row/predicted-column confusion matrix. Macro F1 is the
primary comparison metric. A zero metric denominator produces 0.0.

The protocol separately reports exact diagnosis match over every row
and affected-prefix correctness over fault rows only. Classification
metrics and full-diagnosis checks must not be presented as the same
measurement.

The accepted D-067 split roles are immutable:

- train: development;
- validation: selection; and
- test: report_only.

Only train and validation may influence future feature processing,
method selection, hyperparameters, thresholds, or hybrid policy. The
G02 test group cannot be used for any of those decisions. An overall
30-row summary is descriptive_only.

Every sample-level result must retain path and SHA-256 references to
its Experiment Manifest, ground truth, Evidence v2, method prediction,
and per-experiment evaluation. These are report provenance and do not
become Dataset Row v2 model features.

The first adapter consumes the separate P2-R10 rule audit, verifies
its one-to-one mapping to the frozen split, normalizes a
NO_FAULT_DETECTED result to the comparable no_fault class, recalculates
all metrics, validates the formal JSON Schema, and writes the report
atomically without overwriting an existing result.

Status: Approved, implemented, and runtime-verified on 2026-08-05.
Ten targeted tests and the complete 185-test regression suite pass.
The accepted real execution and report binding are recorded in
D-069.

Limitation:

This protocol makes future method results structurally comparable; it
does not itself establish their performance. The accepted dataset has
only 30 controlled rows and validation/test contain one context each.
The Machine Learning and hybrid methods remain unimplemented, and no
metric comparison or superiority claim is yet possible.

## D-069 — First accepted partition-aware rule-based baseline

Decision: Accept p3_r0_rule_based_baseline_v1 as the traditional
baseline result for the frozen D-067 campaign and D-068 evaluation
protocol.

The accepted local runtime report is bound to:

- path:
  reports/experiments/p3_r0_rule_based_baseline_v1.json;
- SHA-256:
  7158f1de31a892779bbce2eaad8f5c5e5bb7c2fc08e0766b49a55047ddc56424;
- campaign run:
  p2_routing_5ctx_v1-20260804T073429388394Z-
  617194fea9954ed98ec120bdefea23d9;
- merged Dataset Row v2 SHA-256:
  be92cef4e78764e772909e15f43ab5cba98ef9610f4a446fc95e8afb5e830c80;
- 30 unique records mapped one-to-one to the accepted split;
- 18/6/6 rows in 3/1/1 whole context groups; and
- 150/150 source-artifact references verified by SHA-256.

The deterministic rule engine reported accuracy 1.0 and unweighted
macro F1 1.0 independently for train, validation, and test. It also
reported 30/30 exact diagnosis matches and 20/20 correct affected
prefixes over fault rows. The G02 test group remained report_only,
the overall view remained descriptive_only, and no training occurred.

The report is a generated local runtime artifact and remains excluded
from the implementation commit under the existing repository policy.
Its stable identity is the result identifier, accepted path, and
SHA-256 recorded here and in the P3-R0 handoff.

Status: Implemented and verified on 2026-08-05. The Method Evaluation
Result v1 validator and JSON Schema passed, all 30 split and rule-audit
records mapped exactly once, all 150 artifact references matched their
files, ten targeted tests passed, and the complete suite passed
185/185.

Limitation:

The perfect metrics apply only to 30 controlled records from five
known laboratory contexts and three known classes. Validation and
test each contain one context, and the two rows per class within a
context are execution repetitions rather than independent topology
samples. D-069 does not establish real-world generalization,
statistical significance, Machine Learning or hybrid performance, or
superiority of one method over another.

## D-070 — Leakage-safe Machine Learning baseline protocol

Decision: Freeze Leakage-Safe Machine Learning Baseline Protocol v1
and ML Feature Matrix v1 before fitting any estimator.

The supervised target remains labels.fault_type with the D-068 class
order no_fault, missing_static_route, and wrong_next_hop. Predictors
come only from the seven ordered Dataset Row v2 feature values. Every
tri-state feature is encoded as the binary pair available/true:

- true becomes [1, 1];
- false becomes [1, 0]; and
- unavailable becomes [0, 0].

The pair [0, 1] is invalid. The transformation produces 14 ordered
binary columns, is lossless for the three states, and requires no
fitted imputer or partition-derived statistic. It preserves the
structural C1 unavailability accepted by D-066 without assigning an
artificial ordinal value.

labels, metadata, quality, ground truth, rule predictions, evaluation
results, identifiers, paths, hashes, and explanation text are
excluded from predictors. sample_id, split_group_id, target_class,
and source-row SHA-256 remain audit fields outside feature_vector.

The only candidate families are multinomial L2 logistic regression
and a shallow decision tree. Six configurations are fixed in the
protocol. The model seed is 20260730. Candidates fit only on train and
are selected only on validation by macro F1, then accuracy, then the
declared lower complexity rank, then candidate_id. The selected model
is not refitted on train plus validation. Prediction uses argmax and
no threshold tuning is permitted.

G02 test remains held out from fitting and selection. It may be used
once for report-only evaluation only after the entire winning ML
pipeline is frozen and persisted. P4-R0 itself produces no model,
prediction, or metric.

The normative details are recorded in docs/ML_BASELINE_PROTOCOL.md.
The machine-readable contract is defined by
schemas/ml_feature_matrix_v1.schema.json and
src/ml/feature_matrix.py.

Status: Approved, implemented, and runtime-verified on 2026-08-05.
The real D-067 feature matrix passed the frozen runtime, schema,
partition, hash, tri-state, and predictor-leakage gates. Its accepted
artifact binding is recorded in D-071.

Limitation:

This decision establishes deterministic preprocessing, predictor
whitelisting, and partition discipline. It does not establish ML
performance, model selection, test performance, generalization,
hybrid behavior, or superiority over the D-069 rule-based baseline.

## D-071 — First accepted leakage-safe ML feature matrix

Decision: Accept p4_r0_ml_feature_matrix_v1 as the deterministic
pre-fit input artifact for the first Machine Learning baseline.

The accepted local runtime artifact is bound to:

- path:
  reports/experiments/p4_r0_ml_feature_matrix_v1.json;
- SHA-256:
  9193b4b8c676bf94ef9af05562d9d0047faef61bc94c9d81b0485b88bf599730;
- campaign run:
  p2_routing_5ctx_v1-20260804T073429388394Z-
  617194fea9954ed98ec120bdefea23d9;
- merged Dataset Row v2 SHA-256:
  be92cef4e78764e772909e15f43ab5cba98ef9610f4a446fc95e8afb5e830c80;
- 30 unique Dataset Row v2 samples;
- 18/6/6 rows in 3/1/1 whole context groups;
- seven raw tri-state predictors transformed losslessly to 14 ordered
  binary columns;
- ten expected structural unavailable values;
- 30/30 source-row references verified by SHA-256; and
- predictor-leakage audit passed with G02 test use report_only.

The artifact is a generated local runtime result and remains excluded
from the implementation commit under the existing repository policy.
Its stable identity is the matrix identifier, accepted path, and
SHA-256 recorded here and in the P4-R0 handoff.

Status: Implemented and verified on 2026-08-05. ML Feature Matrix v1
runtime and JSON Schema validation passed, ten targeted tests passed,
and the complete suite passed 195/195. No estimator was fitted, no
prediction was produced, and no metric was calculated.

Limitation:

D-071 establishes input integrity and leakage-safe partition roles,
not Machine Learning performance. The accepted matrix contains only
30 controlled rows from five contexts and three classes. It does not
establish model selection, test performance, generalization, hybrid
behavior, or superiority over the D-069 rule-based baseline.

## D-072 — Frozen ML pipeline and one-time report gate

Decision: Implement P4-R1 as two ordered, fail-stop stages over the
accepted D-071 feature matrix.

The selection stage must instantiate exactly the six D-070
candidates, fit each candidate once on the 18 train rows, calculate
candidate metrics only for train and validation, apply the frozen
validation macro-F1, validation accuracy, complexity-rank, and
candidate-ID order, and serialize the selected train-only estimator.
It must persist ML Pipeline Selection v1 with the selected candidate,
all six train/validation summaries, feature and sample bindings,
software versions, model SHA-256, and explicit evidence that no test
prediction or metric was produced.

The report stage is a separate command. It may access G02 test only
after independently revalidating the accepted matrix, selection JSON
Schema, selected-candidate order, reproduced train/validation
predictions, fitted train-sample binding, selection SHA-256, and model
SHA-256. It must not refit the estimator or change preprocessing,
candidates, thresholds, or selection policy.

The independent ML baseline predicts fault_type. Every prediction
also records the seven decoded evidence states and a model-specific
explanation: linear feature contributions for logistic regression or
the decision path for a tree. It does not infer fault_location or
affected_prefix. Those fields remain null for predicted faults, so
the existing full-diagnosis and affected-prefix checks expose this
limitation instead of granting correctness from ground truth or
metadata.

Method Evaluation Result v1 remains the shared result contract. Its
provenance definition is extended backwards-compatibly because the
original JSON Schema required a rule_audit artifact even for the
future Machine Learning and hybrid method identifiers. Existing
rule-based reports retain rule_audit. Machine Learning reports instead
must bind the feature matrix, selection result, and model artifact;
the common campaign, split, per-sample five-artifact, metric, and test
policies remain unchanged.

The implementation uses local open-source scikit-learn and joblib.
The supported scikit-learn range is frozen to >=1.5,<1.8 for the
precommitted LogisticRegression and DecisionTreeClassifier APIs.

Status: Approved, implemented, and runtime-verified. Ten targeted
tests and the complete 205-test regression suite passed. The real
D-071 execution satisfied the freeze and report gates without refit;
D-073 records the accepted candidate, metrics, and artifact hashes.

Limitation:

The two-stage gate prevents test-guided selection and fabricated
localization, but it cannot make the 18-row train partition, one-
context validation partition, or one-context test partition
statistically representative. The successful P4-R1 execution is a
controlled baseline, not evidence of real-world generalization or
method superiority.

## D-073 — First accepted independent Machine Learning baseline

Decision: Accept the real P4-R1 train-only pipeline, validation-only
selection, and one-time report-only G02 evaluation as the first
independent Machine Learning baseline for the frozen D-067 campaign.

The six D-070 candidates were fitted only on the 18 train rows. Three
logistic-regression candidates and two of the three decision-tree
candidates reached validation macro-F1 and accuracy of 1.0. The
precommitted complexity and candidate-ID tie-breakers selected
logreg_l2_c0_1, a multinomial logistic-regression estimator with
L2 regularization and C=0.1. The fitted estimator was not refitted on
validation or test.

The accepted frozen artifacts are:

- ML Pipeline Selection v1 SHA-256:
  a02536d6f2478d9fdc40510275dd3b48a2824ee7b1f0fa08c1aed472611fb6fb;
- selected estimator SHA-256:
  90db38e625f4bcf6a234b6a0516371b76f98e01b4437f684ffea119cbc09cdb2;
  and
- Method Evaluation Result v1 SHA-256:
  8fc6e77e5008cd7cc74e5ce130b901ed750afab9a35eb62652ff55f9205b0e92.

The accepted report contains 30 records and preserves the 18/6/6-row
and 3/1/1-group partition allocation. Train, validation, and test each
report fault_type accuracy 1.0 and macro-F1 1.0. Every one of the 150
source-artifact references passed SHA-256 verification, all 30 ML
predictions contain evidence-bearing model explanations, and the G02
partition remained report_only.

The independent classifier does not infer fault_location or
affected_prefix. Consequently, each partition reports full-diagnosis
exact-match rate 1/3 and fault-only affected-prefix correctness 0.0.
These values are accepted as an explicit scope boundary rather than
repaired from labels, metadata, or rule output. They establish the
technical motivation for the future hybrid method, which may combine
independent ML fault classification with evidence-based rule
localization only under a separately frozen policy.

Status: Implemented, executed, and independently verified on
2026-08-05. Ten targeted tests and the complete 205-test regression
suite passed before the real run. The recovery step corrected only the
experiments root from reports/experiments to the canonical data/raw;
it reverified the already frozen pipeline and did not refit the model.

Limitation:

The perfect fault_type classification values describe 30 controlled
rows from five complete contexts and three known classes. Validation
and test each contain only one context. D-073 does not establish
real-world generalization, statistical superiority over D-069, robust
probability calibration, unseen-topology behavior, or hybrid
performance. Cross-method claims remain blocked until the hybrid
method is precommitted, implemented, and evaluated under the same
frozen protocol.

## D-074 — Precommitted Hybrid Diagnosis Policy v1

Decision: Freeze a deterministic, evidence-preserving hybrid policy
before implementing the Hybrid Engine or reading any hybrid test
result.

Hybrid Policy v1 is bound to the accepted D-067 campaign and D-058
split, the D-069 rule-based report, and the D-071/D-073 feature
matrix, selection, estimator, and ML report identities. A future
hybrid prediction may consume only sample identity, a reference to
Evidence v2, the immutable original rule and ML predictions, the
frozen policy, and the ML model binding. Ground truth, labels,
partition identity, correctness flags, evaluation artifacts, and
method metrics are forbidden prediction-time inputs. Only the
Evaluator may read ground truth.

Exactly two candidates are precommitted:

1. consensus_abstain_v1 accepts an agreed rule/ML class and abstains
   on disagreement or a non-final input; and
2. rule_guarded_fallback_v1 has the same agreement behavior but may
   accept the rule class on disagreement only when five deterministic
   rule-integrity guards all pass.

For an accepted fault, location and affected_prefix come only from a
complete rule diagnosis. ML-only localization and ground-truth
copying are forbidden. The future hybrid output retains references to
both original predictions, both explanation forms, the policy, and
the model binding. The original method outputs are never overwritten.

P5-R1 must implement both candidates and select only on the G01
validation group by maximizing, in order, full-denominator macro-F1,
full-denominator exact-diagnosis rate, and coverage; ties then minimize
complexity rank and use ascending candidate ID. Abstention counts as
incorrect on the supervised denominator and is reported separately.
G02 test remains closed until the selected-policy artifact is frozen
and independently verified.

A future hybrid Method Evaluation Result must add backwards-
compatible hybrid provenance and abstention accounting. Each sample
will carry seven hashed artifact references: manifest, ground truth,
Evidence v2, rule prediction, ML prediction, hybrid prediction, and
evaluation. Ground-truth and evaluation references are report
provenance and are not Hybrid Engine inputs.

Status: Approved, implemented, and runtime-verified on 2026-08-05.
The canonical policy SHA-256 is
a25467e9cfd8bb52cc67b0c3886eb439466ee51a27b22d292ee468d060bdecc7.
All five accepted baseline hash bindings remained unchanged, both
candidate definitions passed the frozen semantic contract, 11/11
targeted tests and the complete 216/216 regression suite passed, and
no hybrid prediction, metric, selected candidate, prediction API, or
test access was produced. This evidence closes P5-R0 and authorizes
P5-R1 candidate implementation under the unchanged D-074 contract.

Limitation:

D-074 freezes behavior and leakage boundaries; it does not select a
candidate, generate a hybrid prediction or metric, access G02, or
establish hybrid performance. The current validation group contains
only one controlled context, so later selection remains descriptive
and cannot establish real-world generalization.

## D-075 — P5-R1 Hybrid Engine and Validation-Only Freeze Gate

Decision: Implement the two D-074 candidates through separate
prediction, evaluation, and selection boundaries, and persist one
selected-policy artifact before any new G02 access.

The Hybrid Engine API accepts only sample identity, hashed Evidence v2
provenance, the immutable rule prediction, the immutable ML
prediction, Hybrid Policy v1, and the frozen ML model binding. It has
no ground-truth, label, partition, correctness, evaluation, or metric
parameter. All 48 candidate predictions for the 24 train/validation
samples must exist before the Evaluator reads any development ground
truth.

The Evaluator implements the D-074 full-denominator semantics.
Abstention is a false negative for the actual class, is not a false
positive for a predicted class, and is incorrect for accuracy, exact
diagnosis, and fault-only affected-prefix correctness. The
three-by-three confusion matrix retains resolved predictions and the
separate per-class abstention counts reconcile remaining support.

The Selector receives candidate summaries only after evaluation. It
uses G01 validation and the frozen lexicographic order: macro-F1,
exact-diagnosis rate, coverage, complexity rank, and candidate ID.
The atomic models/p5_r1_hybrid_policy_v1/selection.json artifact binds
the unchanged policy, all five accepted baselines, both candidate
manifests, the selected candidate, and a fail-stop leakage audit.

Method Evaluation Result v1 is extended backwards-compatibly for the
future P5-R2 hybrid report. Existing rule and ML reports retain their
five-reference records unchanged. A hybrid record uses seven hashed
references and adds abstention accounting; D-069 and D-073 artifacts
are not rewritten.

Status: Accepted and runtime-verified on 2026-08-05. The canonical
hash-bound run preserved the D-074 policy SHA-256 and all five
accepted baseline hashes. It generated 48 candidate predictions, 48
candidate evaluations, two candidate manifests, and 99 runtime JSON
files only for train and validation. Both candidates obtained 1.0
full-denominator macro-F1, 1.0 exact-diagnosis rate, 1.0 coverage,
and zero validation abstentions in both development partitions.

The frozen tie-break therefore selected consensus_abstain_v1 by its
lower complexity rank of 0. The selected-policy artifact SHA-256 is
59abc80339658a30ab82019c847dbb7a1c9348bc4ca82ad7e1378f2f339a9507.
Independent selection verification passed before any G02 access,
14/14 targeted tests and the complete 229/229 regression suite
passed, and no test prediction, test metric, raw hybrid diagnosis, or
P5-R2 report was produced. This evidence closes P5-R1 and authorizes
P5-R2 to verify the committed implementation and frozen selection
before the single report-only G02 evaluation.

Limitation:

The two candidates tied on every reported train/validation selection
metric. Selecting consensus_abstain_v1 records the precommitted
complexity tie-break, not empirical superiority over the guarded
fallback. Validation contains only one controlled context, G02 test
remains unobserved by the hybrid method, and no cross-method or
real-world generalization claim is authorized by D-075.

## D-076 — P5-R2 report-only execution and comparison gate

Decision: Permit exactly one new held-out hybrid evaluation only
through an atomic report coordinator that independently reverifies
the complete P5-R1 freeze before traversing G02.

The coordinator must verify the unchanged Hybrid Policy v1 SHA-256,
all five accepted baseline hashes, selected-policy SHA-256, selected
candidate identity, both candidate manifests, and all 96 P5-R1
development prediction/evaluation artifacts. It must fail before G02
source collection on any mismatch.

After the gate, only consensus_abstain_v1 may generate the six G02
predictions. All six predictions must exist before the Evaluator
reads any test ground truth. The coordinator may not refit the ML
model, rerun selection, change policy, tune a threshold, generate the
second candidate, or regenerate train/validation outputs.

The first complete hybrid Method Evaluation Result v1 must reuse the
24 selected P5-R1 development outputs and add the six P5-R2 test
outputs. Every record carries seven hash-bound references, yielding
210 sample-level references. The output directory is atomic,
non-overwriting, and contains exactly six G02 predictions, six G02
evaluations, one hybrid report, and one cross-method comparison.

Cross-Method Comparison v1 must bind the immutable D-069 rule report,
D-073 ML report, and new hybrid report. It compares accuracy, macro
precision/recall/F1, exact diagnosis, affected-prefix correctness,
coverage, and abstention values for the same train, validation, test,
and overall scopes. It is descriptive_only, preserves G02 as
report_only, performs no statistical superiority test, and records
that test did not influence policy or selection.

Status: Accepted and runtime-verified on 2026-08-05. The canonical
report-only execution passed the complete freeze gate before G02,
preserved the policy, five accepted baselines, and selected-policy
artifact, and generated exactly six consensus_abstain_v1 predictions
before test ground truth was evaluated.

The atomic output contains six G02 predictions, six evaluations, one
30-row hybrid report, and one cross-method comparison. The hybrid
report verified 210/210 sample references and has SHA-256
e990a29882f1b7cec4fe003ee5ee65b3fa3dfd25250092a0f9f2a908074a9c75.
The comparison has SHA-256
eebf97dfe340a05feba70874f54727e1a8ccf7ce4224301f162544537d8ecf80.

On the six-row G02 test group, the frozen hybrid policy obtained 1.0
macro-F1, 1.0 exact-diagnosis rate, 1.0 affected-prefix correctness,
1.0 coverage, and zero abstentions. Test use remained report_only and
did not influence policy design or selection. Independent output
verification, 14/14 targeted tests, and the complete 243/243
regression suite passed. D-076 and P5-R2 are therefore closed, and
Phase 5 is complete for the frozen controlled campaign.

Limitation:

D-076 defines the only authorized execution and reporting path. The
accepted values describe one six-row held-out context in a small,
controlled campaign. Equal class metrics and stronger hybrid
localization than the independent ML baseline do not establish
statistical superiority or real-world generalization.

## D-077 — Bounded Phase 6 taxonomy and evaluation design

Decision: Freeze Phase 6 Extended Fault Taxonomy and Evaluation Plan
v1 before implementing or executing a new fault scenario.

The canonical class order is no_fault, missing_static_route,
wrong_next_hop, wrong_default_gateway, interface_down, and acl_block.
The earlier wrong_gateway candidate name is replaced by the precise
wrong_default_gateway label so a source default-route error is not
confused with the existing observer wrong_next_hop class.

The accepted P2-P5 rows, split, reports, model, and hybrid policy
remain immutable reference artifacts. Phase 6 does not append new
labels to Dataset Row v2 or reuse historical rows for fitting. It
must recollect all six classes through planned Evidence v3 and
Dataset Row v3 contracts because the seven existing predictors do not
distinguish the three new classes safely.

The planned feature contract contains exactly ten ordered tri-state
features covering expected source-gateway reachability, installed
default-gateway agreement, end-to-end reachability, observer route
existence, route next-hop agreement and reachability, expected
next-hop reachability, observer egress operational state, downstream
transit reachability, and exact flow-policy blocking. Labels, ground
truth, partitions, mask IDs, identifiers, metrics, and explanation
text remain forbidden predictors. No unavailable value is imputed.

The first Phase 6 clean campaign is frozen at six complete contexts,
six classes per context, and two repetitions per class/context pair:
72 rows. The explicit split is 36 train rows in E01/E03/E05, 12
validation rows in E04, and 24 report-only test rows in E02/E06. The
entire six-class context bundle stays in one partition, and group IDs
cannot be renamed after freeze. Both test groups are unseen by Phase
6 fitting/selection; E06 additionally requires a new topology with an
explicit forwarding-policy boundary.

Missing evidence is a separate robustness track, not a fault class.
Four deterministic non-destructive masks cover source-gateway, route,
interface-state, and policy-state feature families. Masked rows do not
fit the first model; validation masks are development-only and test
masks remain report-only until model and hybrid-policy freeze. Source
artifacts and hashes must remain unchanged, no values are imputed, and
insufficient-evidence or abstention outputs stay in full denominators.

Multiple faults are not authorized in the first campaign. The current
single-label ground-truth and evaluation contracts cannot represent
multiple root causes, causal masking, or non-identifiability. A later
reviewed milestone must define those semantics before any combined
injection.

The machine-readable plan is
plans/taxonomies/P6_EXTENDED_FAULT_TAXONOMY_V1.json. Its SHA-256 is
f2cf0feced412af5fa76f1ffa861b3500389c430209d8e5b09a4d9e985f1b4f9.
The strict Draft 2020-12 schema is
schemas/fault_taxonomy_plan_v1.schema.json and the semantic validator
is src/planning/fault_taxonomy.py.

Status: Approved, implemented as a design contract, and
runtime-verified on 2026-08-05. Sixteen targeted tests and the complete
259-test regression suite pass. P6-R0 performed no Containerlab
execution, scenario injection, dataset collection, model fitting,
prediction, or Phase 6 metric calculation.

Limitation:

D-077 freezes a bounded experimental design, not a realized dataset
or result. The expected evidence signatures are acceptance targets
that still require implementation and real smoke verification. The
planned six deterministic contexts do not establish population-level
generalization or statistical superiority. OSPF remains proposed
under D-034 and is outside this decision.

## D-078 — Phase 6 observation, evidence, and dataset contracts

Decision: Accept Observation Profile v2, Evidence v3, and Dataset Row
v3 as the strict contract boundary for future Phase 6 collection while
preserving the accepted v1-v2 contracts and keeping Dataset Row v2 as
the runtime default until a real Evidence v3 collector is accepted.

Observation Profile v2 adds the source-node role, source address and
prefix, expected source gateway, observer egress interface, exact flow
selector, and the frozen iptables/filter/FORWARD policy-inspection
binding. Its semantic validator requires distinct source, observer,
and transit roles; validates IPv4 and Linux-interface constraints; and
checks fault parameters against the correct role for the three new
single-fault classes. Existing Observation Profile v1 consumers remain
unchanged. Explicit versioned dispatch supports v1 and v2.

Evidence v3 contains exactly the ten D-077 predictor values inside a
dedicated features object. For each feature it records an independent
availability reason and a probe-provenance record. Observed and failed
probes bind a normalized raw-artifact path and lowercase SHA-256;
structurally unavailable features cannot claim a raw artifact. Derived
gateway agreement, route next-hop agreement, interface state, and
policy blocking must match their recorded raw values. Evidence v2 and
its schema remain byte-for-byte unchanged, and explicit evidence
dispatch supports v2 and v3.

Dataset Row v3 exports only the ten frozen tri-state predictors. A
separate provenance section binds the source Evidence v3 SHA-256,
records one availability reason per feature, and stores an optional
non-predictor mask ID. Structural unavailability, collection
unavailability, and deterministic masked missingness are distinct
reasons for the same predictor value unavailable. Quality counters
must exactly match those reasons and the feature values.

The four D-077 masks are non-destructive transformations of a clean
Dataset Row v3. They may change only observed features in their frozen
family, preserve structural reasons, labels, metadata, and the source
Evidence v3 hash, and never impute a value. Dataset aggregation must
be homogeneous by schema version. Labels, scenario/topology/group
identifiers, partitions, mask IDs, predictions, metrics, hashes, and
explanation text remain outside the predictor object.

Status: Implemented and contract-tested in P6-R1 on 2026-08-06.
Fifty-seven targeted tests and the complete 316-test regression suite
pass in the isolated verification environment. The three Draft
2020-12 schemas pass schema validation. No Containerlab execution,
Phase 6 experiment, real Evidence v3 artifact, campaign row, model,
prediction, or metric was produced.

Limitation:

D-078 establishes data contracts and synthetic contract behavior. It
does not prove that the required commands work in the laboratory, that
iptables exists in the image, that any new injector is feasible, or
that the expected class signatures are observed. Dataset Row v2 stays
the runtime default specifically to prevent premature Phase 6 export.

## D-079 — Evidence v3 collector and raw-probe boundary

Decision: Accept a separate, explicitly invoked Evidence v3 collector
that implements the ten D-077 measurements without changing the
accepted Evidence v2 collector, Experiment Runner path, or Dataset Row
runtime default.

The collector receives only a validated Observation Profile v2 and an
output directory. It has no scenario label, ground truth, fault type,
expected class signature, prediction, partition, correctness, or metric
input. Its bounded command set measures the expected source gateway,
the installed source default route, end-to-end reachability, the exact
observer destination route, installed and expected next-hop
reachability, the observer egress operational state, downstream transit
reachability, and iptables/filter/FORWARD policy state.

Every executed command is persisted atomically under raw/v3 before
Evidence v3 is written. The raw artifact records the exact container,
command, return code, stdout, stderr, and UTC timestamp; its exact bytes
are bound to the corresponding feature-provenance record with SHA-256.
The collector refuses existing Evidence v3 output and never overwrites
an earlier collection.

Ping return codes zero and one mean observed true and false. Other
return codes, malformed executor results, invalid JSON, ambiguous
routes, unsupported interface state, a failed iptables command, or an
ambiguous exact policy match become collection_unavailable with a
failure artifact. An observed absent route alone makes the installed
next-hop agreement and reachability features
structurally_unavailable; a failed route probe may not be relabeled as
an absent route.

The policy parser reports a block only for one uniquely tagged DROP
rule whose chain, source /32, destination /32, protocol, and, for TCP
or UDP, both ports exactly match Observation Profile v2. A nonmatching
tagged rule does not block the selected flow, while duplicate exact
matches or unparsable policy output fail closed as
collection_unavailable.

Status: Implemented and synthetically verified in P6-R2 on 2026-08-06.
The targeted collector boundary passed 26/26 tests, including the four
accepted v2 collector tests, and the complete regression suite passed
338/338 tests in the isolated verification environment. No Containerlab
command, real Evidence v3 artifact, Phase 6 Dataset Row, fault
injection, model, prediction, or metric was produced.

Limitation:

D-079 accepts the implementation and fail-safe parsing semantics, not
laboratory feasibility. It does not establish that iptables is present
in the current image, that real interface state is represented as
expected, or that any D-077 class signature occurs in a deployed
topology. Dataset Row v2 remains the runtime default and the historical
Experiment Runner still invokes only the unchanged v2 collector. P6-R3
must perform a separately reviewed healthy runtime and toolchain gate
before any new injector is implemented or executed.

## D-080 — Healthy Evidence v3 runtime and toolchain gate

Decision: Accept the first real, fault-free Evidence v3 collection on
the reviewed TOP-01 hosta-to-hostb binding as the runtime prerequisite
for Phase 6 injector work.

The accepted laboratory image remains Ubuntu 24.04 and now declares the
open-source iptables package alongside iproute2 and iputils-ping. The
pre-existing image was retained locally under the recovery tag
ind-linux:p6-r2-preflight before ind-linux:0.1 was rebuilt. The rebuilt
image exposed ip, ping, and iptables, with iptables v1.8.10 using the
nf_tables backend.

The reviewed Observation Profile v2 binding is isolated in
N0_NORMAL_OPERATION_P6_TOP01. It observes HostA as source, R1 as route
observer, R2 as transit, and HostB as destination. A separate fail-stop
setup script adds HostA's default route through 10.10.1.1 only after
deployment. The accepted historical TOP-01 topology and its frozen G01
fingerprint remain byte-for-byte unchanged.

The real experiment
p6_r3_healthy_top01-20260806T090542Z completed with collector return code
zero. All ten features were observed with the frozen healthy signature,
all nine raw JSON probes completed with return code zero, and every raw
artifact matched its Evidence v3 SHA-256 binding. Evidence SHA-256 is
654cb717aa823091b6832d586b22503eb26f37aad81dc3e2f40f7d1f64c75ac2
and collector-status SHA-256 is
d68b14f65b80f72ab7f0b8c7f3709b37b2f0a18165167ec3dd3593c914aed88d.

TOP-01 passed all 13 baseline checks before the Phase 6 binding, before
collection, and after collection. No fault was injected or restored.
The targeted boundary passed 31/31 tests and the complete regression
suite passed 343/343 tests. Containerlab cleanup removed all four lab
containers. Dataset Row v2 remains the runtime default; no Dataset Row
v3, campaign row, model, prediction, or metric was created.

Status: Implemented, real-runtime verified, and accepted in P6-R3 on
2026-08-06.

Limitation:

D-080 proves tool availability, the reviewed healthy TOP-01 binding,
the no-fault ten-feature signature, raw-probe provenance, and baseline
preservation in one local controlled context. It does not prove any
fault signature, injector restoration, cross-topology behavior,
six-class separability, campaign completeness, ML performance, or
real-world generalization. P6-R4 must implement and smoke each new
single-fault class through separately reviewed fail-stop injectors
before the 72-row campaign is authorized.

## D-081 — Runtime amendment to the interface-down signature

Decision: Amend only the `interface_down` route-family expectation in
D-077 after two fail-stop P6-R4 runtimes disproved the assumption that
Linux retains or permits re-adding routes through an administratively
down device.

Runtime `p6_r4_new_class_smoke-20260810T114903Z` set R1 `eth2` down
successfully and observed the exact destination route as absent, the
expected next-hop and end-to-end destination as unreachable, and the
independent R2-to-HostB path as healthy. Runtime
`p6_r4_interface_recovery_smoke-20260810T122212Z` then proved that both
attempts to recreate the recorded routes with `onlink` while `eth2`
was down returned code 2 with `Error: Nexthop device is not up.` Both
failed gates restored the controlled baseline safely; neither produced
accepted fault evidence, a dataset row, a campaign result, a model,
prediction, or metric.

The amended `interface_down` signature is T,T,F,F,U,U,F,F,T,F in the
unchanged D-077 feature order. The route-existence probe is observed
false; installed next-hop agreement and reachability are structurally
unavailable under the existing Evidence v3 contract. The class remains
distinct from `missing_static_route`, whose expected next-hop remains
reachable and observer egress interface remains operationally up.

Injection sets only the selected interface down and verifies the
kernel removal of every explicitly bound baseline route. It must not
attempt route insertion through the down device. Restoration raises the
interface, replaces every exact recorded baseline route without
`onlink`, and requires complete healthy-baseline revalidation.

The original D-077 plan hash
f2cf0feced412af5fa76f1ffa861b3500389c430209d8e5b09a4d9e985f1b4f9
is retained as historical identity. The amended canonical plan at the
same versioned path has SHA-256
571cc26518d81a1768261970fb2d3847587fc4bbc1a9c62678c8f97f3e524746.
Git history preserves the original bytes. All later Phase 6 work must
use the amended hash and may not claim the superseded signature as an
observed result.

Status: Approved, implementation-corrected, and real-runtime verified
on 2026-08-10. The amended `interface_down` smoke passed in runtime
`p6_r4_d081_amended_smoke-20260810T130119Z` with eight observed and two
structurally unavailable features, exact rule match, exact restoration,
healthy Evidence v3 recovery, and a 13/13 final baseline.

Limitation:

D-081 is a runtime-informed contract correction whose amended
single-context smoke is now accepted under D-082. It does not authorize
Dataset Row v3 aggregation, E01-E06 execution, the 72-row campaign,
fitting, prediction, metrics, or any claim beyond the reviewed TOP-01
kernel and diagnostic behavior.

## D-082 — Phase 6 new-class injector and smoke gate

Decision: Accept the three new fail-stop injectors, their Rule Engine
v3 signatures, and one reviewed TOP-01 smoke per new class as the P6-R4
prerequisite for the later six-context campaign.

The accepted classes and rules are:

- `wrong_default_gateway` through `R_P6_ROUTING_003`;
- `interface_down` through `R_P6_LINK_001`; and
- `acl_block` through `R_P6_POLICY_001`.

Each injector records explicit preconditions, applies only its reviewed
mutation, verifies the exact fault state, restores the recorded
baseline, validates the complete 13-check TOP-01 baseline, and verifies
the restored healthy Evidence v3 signature before another class may
run. The ACL injector uses one exact tagged iptables/FORWARD DROP rule.
The interface injector follows D-081: it treats removal of the two
device-bound routes as a kernel side effect and recreates both routes
only after raising the interface.

The accepted smoke evidence combines the saved
`wrong_default_gateway` result from
`p6_r4_new_class_smoke-20260810T114903Z` with `interface_down` and
`acl_block` from
`p6_r4_d081_amended_smoke-20260810T130119Z`. All three injectors and
restorers were confirmed, all three rules were exact matches, all three
post-restoration healthy signatures passed, and 26/26 raw fault
artifacts were SHA-256 bound. Across the three fault signatures, 28
features were observed and the two D-081 installed-next-hop features
were structurally unavailable.

The final TOP-01 baseline passed 13/13 checks and cleanup left zero lab
containers. The implementation passed 46/46 targeted tests and 373/373
full regression tests. The gate summary SHA-256 is
d7d8dd30e0ad537c1a2897209c2a58285ba7fbe241653fa561649869e8c46a4b.
The two stopped interface diagnostics remain immutable diagnostic
evidence and are not accepted samples.

Status: Implemented, real-runtime verified, and accepted in P6-R4 on
2026-08-10.

Limitation:

D-082 proves bounded single-fault feasibility and rule separability in
one reviewed TOP-01 context per new class. It does not establish all six
classes across E01-E06, campaign completeness, cross-topology
generalization, ML or Hybrid performance, missing-evidence robustness,
or real-world accuracy. No Dataset Row v3, campaign, model, prediction,
or metric was produced by P6-R4.

## D-083 — Phase 6 clean six-context campaign and sealed split

Decision: Accept the recovered P6-R5 campaign as the canonical clean
Dataset Row v3 source for later six-class method development, while
retaining the first stopped campaign as diagnostic-only evidence.

The first runtime,
`p6_r5_clean_campaign-20260811T063119Z`, stopped in E01 before the first
`interface_down` row because all C4 scenarios still used the obsolete
`preserved_routes` key. D-081 had already established
`baseline_routes` as the accepted explicit restoration contract. Eight
earlier experiments completed, but no merged dataset or split was
created and those rows are not accepted campaign inputs. The ninth
attempt produced no Dataset Row v3. Cleanup completed with zero
containers, and the failed runtime tree SHA-256 is
`531c872cd392ac7308ae4684ab422b06736e7d1c894f04c7ac5780745fd69d79`.

The recovery changed only the six C4 scenario bindings, their static
validator, the six normalized context fingerprints, and the associated
contract test. It did not amend D-081, the class order, Evidence v3,
Dataset Row v3, the ten-feature signatures, the context allocation, or
the test-use policy. Runtime
`p6_r5_c4_recovery_smoke-20260811T070536Z` confirmed all six
interface-down injections and exact restorations without exporting a
Dataset Row.

The replacement clean runtime
`p6_r5_clean_campaign_recovery-20260811T070536Z` completed 72/72
experiments across all six context groups. Every group contains two
rows for each of the six classes. All 72 rows are unmasked, no accepted
row contains a collection-unavailable feature, all context baselines
were restored, every cleanup passed, and zero lab containers remained.
The campaign-result SHA-256 is
`c4c45e19e8b98d00a3fa2ed3b4d4a8ad2ba6debd04baae05c2d7d7377f9df4d2`;
the merged-dataset SHA-256 is
`50dd030e51e4873eac7665980e033a0236e4ddf26e446b66bd3d11613c4a0a9d`.

The accepted allocation is the precommitted explicit whole-context
split: E01/E03/E05 provide 36 train rows, E04 provides 12 validation
rows, and E02/E06 provide 24 report-only test rows. No group crosses a
partition. The split-manifest SHA-256 is
`adf70942a740be43e085aca67f9acb4085dd118827ceba8482913dbc6adb5f9f`,
and the test partition remains `SEALED_FOR_P6_R6_REPORT_ONLY`.

The recovered implementation passed 144/144 targeted Phase 6 tests and
387/387 full regression tests. No diagnosis, model, selection,
prediction, evaluation, or metric artifact was created. P6-R6 may use
only train and validation for fitting and selection until the new ML
model and Hybrid policy are independently frozen.

Status: Implemented, real-runtime verified, and accepted in P6-R5 on
2026-08-11.

Limitation:

D-083 establishes a balanced clean dataset and a leakage-safe partition
boundary in six controlled local contexts. It does not establish method
performance, missing-evidence robustness, statistical superiority,
production readiness, or real-world generalization. Report-only E02 and
E06 results may not influence fitting, feature design, rules, thresholds,
candidate selection, or policy selection.

## D-084 — Phase 6 six-class method freeze and one report-only evaluation

Decision: Accept the P6-R6 six-class Rule-based, Machine Learning, and
Hybrid implementation, the independently verified development freeze,
and the single descriptive E02/E06 clean/missing-evidence evaluation.

The four D-077 missing-evidence masks are implemented as deterministic,
non-destructive Method Input v1 transformations. They preserve the clean
Dataset Row v3 and Evidence v3 hashes, change only the frozen feature
family to unavailable, and keep mask identity, partition, labels,
ground truth, hashes, and evaluation metadata outside the 20-column
encoded predictor vector.

Six precommitted ML candidates were fit only on 36 clean E01/E03/E05
train rows. Validation-only selection used 12 clean and 48 masked E04
inputs and selected `logreg_l2_c1`. Five immutable Hybrid candidates
were evaluated on the same validation boundary and selected
`rule_then_ml_fallback_v1`. Neither selection was changed after the
development freeze.

An independent verifier rebound the accepted P6-R5 campaign and split,
the protocol, every method-affecting implementation file, all
development artifacts, the selected estimator, and the selected Hybrid
policy before authorizing exactly one report-only test evaluation. The
authorization was consumed once. The accepted run opened 24 immutable
E02/E06 clean inputs, derived 96 deterministic masked copies, and
produced 120 predictions per method without refitting, reselection, or
test-guided revision.

On the 24 clean inputs, all three methods achieved 1.0 accuracy,
macro-F1, exact-diagnosis rate, affected-prefix rate, and coverage. On
the 96 masked inputs, Rule-based returned
`INSUFFICIENT_EVIDENCE` in all cases, giving zero coverage, accuracy,
and macro-F1. ML and Hybrid both achieved 0.791667 accuracy, 0.810486
macro-F1, and full coverage. Across all 120 inputs, Rule-based accuracy,
macro-F1, and coverage were 0.200000, 0.333333, and 0.200000; ML and
Hybrid both obtained 0.833333, 0.846672, and 1.000000.

The accepted identities are:

- freeze-manifest SHA-256:
  `fa98a17e2ffae42f6dd009a13af65ad32174035eca8352bf26f321531a4fe0f5`;
- independent freeze-receipt SHA-256:
  `5c6c6537cb233efdeb52c6872f7a6ef7fb32eb3ac7b2474e2514b2908cd29bcc`;
- report-only run-manifest SHA-256:
  `44c505b451c6211b4515564f4b889633b6d74ed0c618f19cc0ab3b9bdfe72b1d`;
- descriptive comparison SHA-256:
  `ca1c15d04828c0ae61cacaf80a5ee6f49f64a9cf3ac151a4b4ccd2386987e570`.

The implementation and accepted source boundary passed 185/185 targeted
Phase 6 tests and 428/428 full regression tests. Containerlab was not
required or started.

Status: Implemented, independently frozen, real report-only runtime
verified, and accepted in P6-R6 on 2026-08-11.

Limitation:

The comparison is descriptive only. No statistical-superiority test was
performed, and ML and Hybrid produced identical aggregate results in
every reported scope; P6-R6 therefore establishes no Hybrid advantage.
The 96 masked inputs are deterministic transformations of 24 clean test
rows, not independent network experiments or observed production
missingness. The results do not establish population-level
generalization, production suitability, or real-world accuracy.

The E02/E06 one-use report-only authorization is consumed. These test
results must not cause refitting, reselection, or revision of features,
rules, thresholds, models, or Hybrid policy. Multiple simultaneous
faults remain unauthorized. P6-R7 may only decide whether a bounded
multi-label design is academically justified and feasible before any
combined injection is considered.

## D-085 — Exclude multiple-fault runtime from the current bachelor scope

Decision: Close P6-R7 and Phase 6 without authorizing a simultaneous-
fault or multi-label runtime.

The design audit distinguishes the set of injected mutations from the
set of effective faults and the set of root causes diagnosable from the
available evidence. Those sets are not guaranteed to be equal. The
current single-label ground truth cannot score a hidden, dominated, or
non-identifiable second cause without either penalizing a correct
evidence-bounded diagnosis or overstating what the system observed.

The five non-healthy labels nominally yield ten unordered pairs. Some
pairs are not valid joint states: a destination route cannot be both
missing and installed through a wrong next hop, and an interface-down
mutation removes routes bound to that interface. Other pairs are
order-dependent or require independent direct evidence to distinguish a
second fault from the same end-to-end symptom. The accepted individual
injector preconditions and restoration snapshots do not constitute an
atomic composition contract.

A balanced pair-only six-context, two-repetition design would nominally
require 120 clean rows before incompatible pairs are removed, while the
accepted 3/1/2 whole-context split would still provide only six train,
two validation, and four test rows per pair. Applying four masks would
create 240 validation/test transformations rather than independent
experiments. The existing 72 single-label rows cannot be reinterpreted
as interaction observations, and D-084 prohibits using the consumed
E02/E06 results to guide a new design.

A valid future study would require new versioned contracts for injected,
effective, and diagnosable truth; compositional injection and rollback;
multi-label Dataset Rows; Rule-based, ML, and Hybrid label-set outputs;
multi-label metrics; a newly frozen grouped split; independent method
freeze; and one-use report-only evaluation. This is a separate
experimental track whose cost is disproportionate to its incremental
bachelor-scope claim after the completed six-class and missing-evidence
comparison.

Status: Accepted as a design-only no-runtime decision on 2026-08-11.
No Containerlab command, combined injection, evidence collection,
dataset row, fitting, prediction, or metric was executed. No P6-R6
artifact or result was changed. Phase 6 is complete, and P7-R0 is the
next milestone.

Limitation:

D-085 does not claim that multiple-fault diagnosis lacks research value
or is technically impossible. It records only that the required truth,
identifiability, data, method, and evaluation expansion is not justified
inside the current bachelor scope. Any future attempt requires a new
precommitted protocol and may not use P6-R6 test outcomes for tuning or
selection.

## D-086 — Freeze a local read-only Dashboard/API projection boundary

Decision: Accept P7-R0 as the version-1 interface contract and permit
Phase 7 to present only verified projections of accepted P6-R6
artifacts.

The application architecture is FastAPI served by Uvicorn on
`127.0.0.1`, with static same-origin HTML, CSS, and JavaScript for the
Dashboard. It requires no React/Node toolchain, database, cloud service,
external asset host, telemetry system, paid API, license, or dataset.
The server and Dashboard are not implemented in P7-R0.

The application must verify the accepted freeze-manifest,
freeze-receipt, run-manifest, and cross-method comparison SHA-256 values
before reporting readiness. Its projection source is restricted to the
15 JSON/JSONL files frozen in
`plans/phase7/P7_R0_READ_ONLY_INTERFACE_V1.json`; transitive artifact
references must also verify. The estimator, development train/validation
inputs, source test split, arbitrary paths, and generic downloads are
not runtime sources.

The version-1 API contains exactly six `GET` routes for health,
overview, comparison, case listing, case detail, and provenance. It has
no mutation, inference, experiment, remediation, file-path, or model-
download route. Missing or drifted artifacts fail closed. Stable success
and error envelopes, deterministic pagination, filters, and claim limits
are frozen in `contracts/api/p7_readonly_api_v1.openapi.yml`.

The interface may filter, sort, paginate, and format accepted values for
display. It may not deserialize the model, execute Rule/ML/Hybrid
methods, fit or select a model or policy, calculate a new empirical
performance or superiority statistic, execute Docker/Containerlab or a
subprocess, write an artifact, or imply real-world generalization.

Status: Accepted as a contract-only decision on 2026-08-11. No API
server, Dashboard, artifact catalog, runtime read, prediction, metric,
network command, or filesystem mutation was executed by P7-R0. P7-R1 is
next and is limited to a fail-closed artifact catalog and immutable
projection layer.

Limitation:

D-086 does not establish that the Dashboard or API works. It freezes the
scope against which later implementation is tested. The accepted P6-R6
results remain descriptive-only, the E02/E06 authorization remains
consumed, and ML and Hybrid remain empirically identical in the accepted
aggregate scopes.

## D-087 — Bind all read-only projection sources before serving data

Decision: Accept the P7-R1 fail-closed artifact catalog, Git-tracked
15-source SHA-256/size manifest, immutable 120-case join, and
deterministic Python projection layer.

P7-R1 identified that the four D-086 root hashes do not, by themselves,
cryptographically anchor the P6-R6 gate and every case, target,
prediction, and method-report file. The gate binds the ten report-only
files, but no accepted D-086 root binds the gate's own bytes. Checking
only transitive references could therefore accept a coordinated change
to an unanchored source and its reference. This is an integrity gap in
the planned verification mechanism, not a change to the accepted P6-R6
result or to the 15-file allowlist.

`P7_R1_ACCEPTED_ARTIFACT_CATALOG_V1.json` closes the gap by committing
the artifact ID, canonical path, role, SHA-256, and byte size of all 15
projection sources after the four accepted roots and the full P6-R6
artifact graph verify. The original four root hashes remain unchanged
and retain their scientific roles. The catalog is trusted as versioned
repository metadata and is not an additional runtime data source.

The loader fails closed on absence, symlinks, path escape, byte or size
drift, invalid JSON/JSONL, transitive-reference mismatch, Phase 6
contract violation, case/target/prediction join mismatch, or accepted
scope drift. It deep-freezes all parsed values and exposes only
deterministic health, overview, comparison, case-list, case-detail, and
provenance projections. Raw accepted numeric values are preserved.

The estimator remains forbidden. Its JSON reference is validated, but
the `.joblib` path is not resolved, read, imported, or deserialized. No
FastAPI server, Dashboard, diagnosis method, fitting, selection, metric,
Containerlab command, subprocess, or runtime artifact write is part of
P7-R1.

Status: Implemented and test-verified on 2026-08-11. P7-R2 is next and
may implement only the six frozen FastAPI GET routes and response/error
envelopes over the verified projection layer. Verification passed
23/23 P7-R1 tests, 33/33 combined Phase 7 tests, 185/185 targeted Phase
6 tests, and 461/461 full regression tests.

Limitation:

D-087 proves deterministic integrity and projection behavior for the
accepted local artifact set. It does not add independent experiments,
change the descriptive P6-R6 metrics, establish Hybrid superiority,
generalize beyond the controlled laboratory, or establish that an HTTP
API or Dashboard is implemented.

## D-088 — Serve only the verified immutable projection over local HTTP

Decision: Accept the P7-R2 FastAPI transport as the only HTTP boundary
for the accepted P7-R1 projection layer.

The application exposes exactly the six `GET` operations frozen by
D-086: health, overview, comparison, case listing, case detail, and
provenance. FastAPI's automatic documentation and OpenAPI routes are
disabled so they do not enlarge the runtime route set. `POST`, `PUT`,
`PATCH`, and `DELETE` requests to the API are rejected with the frozen
`405 METHOD_NOT_ALLOWED` envelope.

The artifact catalog is loaded and verified once during application
startup. Successful startup retains only the immutable P7-R1 projection
in memory; requests do not reread files. Missing sources and integrity
drift leave the process available only to return the corresponding
fail-closed `503` envelope. Framework query-validation failures are
normalized from FastAPI defaults to `400 INVALID_QUERY`, unknown case
identities to `404 CASE_NOT_FOUND`, and unexpected failures to a
path-free `500 INTERNAL_ERROR` response.

The Uvicorn entry point binds to `127.0.0.1:8000` with reload disabled.
There is no configurable remote bind, CORS policy, authentication
system, database, cloud service, telemetry, or external asset
dependency. FastAPI, Starlette, Uvicorn, and the HTTP test client are
open-source local dependencies. P7-R2 adds no Dashboard files.

The API responses were validated against the P7-R0 OpenAPI 3.1 schemas.
The complete request path was exercised while the fixture estimator was
absent and while all 15 accepted source hashes remained unchanged. No
method executes, no model is deserialized, and no new evidence,
prediction, metric, or runtime artifact is written.

Status: Implemented and test-verified on 2026-08-11. Verification passed
32/32 P7-R2 tests, 65/65 combined Phase 7 tests, 185/185 targeted Phase
6 tests, and 493/493 full regression tests. P7-R3 is next and may add
only the four static same-origin Dashboard views over these six routes.

Limitation:

D-088 establishes a deterministic local presentation API, not a live
diagnosis service or a production deployment. It does not create new
experimental evidence, change any accepted P6-R6 value, establish
Hybrid superiority, provide remote-network security, or generalize the
controlled results beyond their accepted scope.

## D-089 — Present accepted projections through one static same-origin Dashboard

Decision: Accept the P7-R3 static Dashboard as the only browser client
for the D-088 local read-only API.

The Dashboard consists of exactly three repository assets: one semantic
HTML document, one responsive stylesheet, and one dependency-free
JavaScript client. FastAPI mounts only that dedicated directory after
the six data routes. The mount does not add a data API operation, expose
arbitrary repository files, enable generated documentation, or change
the P7-R0 OpenAPI contract.

The client implements the four D-086 views: overview, three-scope method
comparison, filterable and paginated case exploration with case detail,
and provenance/limitations. It performs only same-origin `GET` requests
to the six D-088 routes. It has no external asset, CDN, React/Node build,
browser persistence, telemetry, authentication, upload, mutation,
download, inference, experiment, remediation, or live-network path.

Accepted API numbers remain unchanged. Percentages and confidence may
be rounded only for display, while the exact API value remains available
as presentation metadata. The Dashboard explicitly identifies the
comparison as descriptive, states that no statistical-superiority test
was performed, distinguishes 96 deterministic masks from independent
experiments, states that ML and Hybrid aggregate results are identical,
and retains the controlled-laboratory non-generalization warning.

The interface has explicit loading, empty, fail-closed error, and retry
states. Keyboard-focus styling, a skip link, semantic landmarks and
tables, native dialog behavior, reduced-motion handling, responsive
desktop and 390-pixel layouts, and `Escape` dialog closing were checked.
Visual verification used a local contract-shaped fixture only; no
accepted result was recomputed. The full UI/API read path left all 15
fixture sources unchanged and did not require an estimator.

Status: Implemented and verified on 2026-08-11. Verification passed
10/10 P7-R3 tests, 75/75 combined Phase 7 tests, 185/185 targeted Phase
6 tests, and 503/503 full regression tests. P7-R4 is next and is limited
to the Phase 7 closeout gate and reproducible local run/archive handoff.

Limitation:

D-089 proves the bounded local presentation behavior, responsive layout,
and integration with accepted projections. It does not prove production
deployment, remote-user security, real-time diagnosis, statistical
superiority, new empirical performance, or real-world generalization.
