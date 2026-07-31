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
