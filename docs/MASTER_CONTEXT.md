# MASTER CONTEXT

## Project

Intelligent Network Diagnosis

## Working title in Albanian

Zhvillimi i një sistemi hibrid inteligjent për diagnostikimin dhe
shpjegimin e problemeve në rrjetet kompjuterike

## Working title in English

Development of a Hybrid Intelligent System for Diagnosing and
Explaining Problems in Computer Networks

## Main objective

To design, implement, and evaluate a hybrid intelligent system that
combines expert rules and Machine Learning to diagnose selected
computer-network problems, identify likely root causes, explain the
supporting evidence, and recommend diagnostic actions.

## Required comparison

1. Rule-based diagnosis
2. Machine Learning diagnosis
3. Hybrid diagnosis

## Core principles

- Zero-budget or minimal-budget implementation
- Local execution
- Open-source tools
- Reproducible experiments
- No fabricated results
- Clear separation between proposed, implemented, and tested work
- Ground truth generated through controlled fault injection
- Diagnosis must include evidence and not only a class label

## Primary environment

- Windows 11
- Ubuntu 24.04 on WSL2
- Docker Engine running natively inside Ubuntu WSL2
- Containerlab
- Linux containers
- FRRouting
- Python

## Initial proof of concept

Topology:

HostA -- R1 -- R2 -- HostB

Initial fault:

Missing static route on R1 toward the destination network.

## Current scope

The architecture targets addressing, Layer 2/VLAN, routing, network
services, security policy, and performance problems. Implementation
will proceed incrementally.

## Out of scope for the base system

- Universal diagnosis of every network technology
- Production-network deployment
- Mandatory paid APIs, cloud services, software, or datasets
- Training large language models
- Autonomous configuration changes without administrator approval

## Current implemented baseline

The currently tested laboratory baseline is TOP-01:

HostA -- R1 -- R2 -- HostB

Implemented and tested controlled experiments:

- N0_NORMAL_OPERATION as the first real no-fault control
- C1_MISSING_STATIC_ROUTE
- C2_WRONG_NEXT_HOP

Current rule-based coverage:

- R_ROUTING_001 diagnoses a missing static route on R1.
- R_ROUTING_002 diagnoses an unreachable configured next-hop
  on the static route on R1.
- Healthy evidence produces NO_FAULT_DETECTED without a fault
  diagnosis.

The evidence collector currently records seven diagnostic
features covering source reachability, destination reachability,
route presence, configured next-hop presence and reachability,
transit reachability, and destination reachability from the transit
node.

The observation and evidence layer is now role-neutral. Observation
Profile v1 derives topology_id from topology.id and validates generic
direction, route-observer, and transit roles instead of requiring the
TOP-01, hosta_to_hostb, r1, and r2 identifiers.

Evidence v2 is the canonical contract for newly collected evidence.
It records topology_id, direction, route_observer_node, transit_node,
destination addressing, and role-neutral diagnostic observations.
The contract has both a runtime validator and a JSON Schema. The
collector validates Evidence v2 before writing it, and the Rule Engine
validates it when reading a collected artifact.

The Rule Engine adapts legacy Evidence v1 for historical
compatibility. For Evidence v2, diagnosis locations, explanations,
and recommendations are derived from the actual observation roles
rather than fixed r1/r2 names. Synthetic fixtures verify alternate
role identifiers. The real G02 TOP_02_CHAIN execution verifies the
contract outside TOP-01, and the real G03 TOP_02_BRANCH execution
verifies the distinct r2 observer and r4 transit binding.

The experiment runner supports both fault and normal scenarios.
Normal experiments do not call fault injection or restoration.
Every new run produces Experiment Manifest v2 with scenario
metadata, split-group metadata, timestamps, and state history.

Dataset Row v2 is the canonical contract for newly generated dataset
rows. It defines one row per completed experiment with fault_type as
the supervised-learning target. Its seven diagnostic features use the
tri-state values true, false, and unavailable and are named through
source, destination, route-observer, and transit roles rather than
fixed r1/r2 identifiers.

Dataset Row v2 metadata preserves topology_id, direction,
route_observer_node, transit_node, variant_id, and split_group_id.
Scenario identity, concrete IP addresses, ground truth, rule outputs,
and evaluation results remain excluded from model features.

Dataset Row v1 remains an immutable historical P1 contract. Dedicated
v1 builders and validators remain available, while the generic
validator accepts either supported version. Migration from v1 to v2
is explicit, maps only the seven approved feature names, preserves
sample, split-group, label, and quality data, and is limited to the
historical TOP_01, hosta_to_hostb, r1/r2 context. There is no silent
or inferred migration for other observation contexts.

C1 and C2 have completed end-to-end with exact-match evaluation
and successful restoration of the TOP-01 9/9 baseline. Their
historical experiment artifacts can be exported as Dataset Row
v1.

The first real normal experiment,
n0_normal_operation-20260728T133851Z, completed with
NO_FAULT_DETECTED, exact_match true, seven true features, no
unavailable features, and valid baselines before and after the
run.

These three individual experiments validate the artifact
contracts and controlled execution paths. They do not yet form
a training dataset or establish general diagnostic performance.

Batch Plan v1 defines the validated input contract for reproducible
dataset-batch planning. It preserves listed execution order, expands
repetition counts into a deterministic experiment sequence, and
rejects invalid plan structure or scenario references before
execution.

Batch Runner v1 consumes the validated plan, invokes the existing
experiment runner in planned order, validates every completed dataset
row, rejects duplicate experiment outputs, and applies
failure_policy=stop. Its canonical builder now produces Dataset Row
v2. The version-aware batch boundary still supports explicitly
provided v1 builders for compatibility, records
dataset_row_schema_version, and rejects datasets that mix v1 and v2.
Batch metadata is persisted during execution, while the aggregated
JSONL dataset is written atomically only after every planned
experiment succeeds.

New experiment identifiers and default batch-run identifiers use UTC
timestamps with microsecond precision plus UUID values to prevent
collisions during repeated execution.

These behaviors are implemented, covered by automated tests, and
verified through the first real B0_SMOKE_CANONICAL laboratory batch.
The batch completed on 2026-07-29 in the listed order N0, C1, and C2,
with three COMPLETED experiments, three validated Dataset Row v1
records, and a final valid TOP-01 9/9 baseline.

The first parameterized routing pilot was verified through
P1_ROUTING_VARIANTS. The accepted batch run is
p1_routing_variants-20260730T082450785454Z-
f283bfdd9ccc4b04afbc6462f6073a63.

P1 executed canonical and alternate HostB-subnet variants for N0,
C1, and C2 with two repetitions per variant. All 12 experiments
completed, all 12 Dataset Row v1 records passed validation, all 12
rule-based evaluations produced exact_match true, and TOP-01 ended
with a valid 13/13 baseline.

Batch status COMPLETED represents successful technical execution and
dataset aggregation. It does not imply diagnostic correctness.
Rule-based exact-match evaluation is verified separately and remains
excluded from Dataset Row v1 model features.

The earlier P1 batch with 8/12 exact matches is retained as
regression evidence and is not accepted for subsequent ML work.
The corrected 12-row batch validates the parameterized pipeline, but
it remains a small pilot dataset and does not establish general
diagnostic performance.

A deterministic evaluation-context-aware dataset splitter is now
implemented with the algorithm identifier
complete_context_group_hash_v2. It assigns every split_group_id wholly
to one of train, validation, or test.

Under D-058, split_group_id represents one complete causal diagnostic
context rather than one class-specific scenario group. Each group must
contain every required fault_type. The current approved class set is
no_fault, missing_static_route, and wrong_next_hop. Repetitions and
cosmetic or parameter-only variants remain in the same group.

The splitter can validate an explicit expected_fault_types set,
requires at least three complete context groups for a three-way split,
and validates feasibility before creating its output directory. A
successful split writes a manifest with the required class set,
per-group class coverage, partition statistics, and source and output
hashes. It accepts a homogeneous Dataset Row v1 or Dataset Row v2
source, records source_dataset_schema_version, and rejects
mixed-version input.

Five complete contexts are the target before the first ML experiment,
which produces a 3/1/1 group allocation under the default
0.6/0.2/0.2 ratios. With the three current classes and two repetitions
per class and context, the minimum planned campaign contains 30 rows.
The reviewed plan reserves one TOP-01 context, three materially
different TOP-02 contexts, and one TOP-03 asymmetric context. G02
TOP_02_CHAIN, G03 TOP_02_BRANCH, and G04 TOP_02_DUAL_TRANSIT are
implemented and smoke-verified. G05
TOP_03_ASYMMETRIC_RETURN is also implemented and smoke-verified as
CTX_G05_TOP03_ASYMMETRIC_RETURN. The five planned laboratory
contexts now exist, but future G01 campaign rows still require their
frozen complete-context binding and none of the five contexts yet has
the planned two campaign repetitions per class.

The accepted P1 dataset retains its historical class-specific
split_group_id values. It is correctly rejected because each old
group is missing the other classes required for a complete evaluation
context. P1 remains an accepted pipeline-validation artifact, not an
ML-training dataset.

P2-R0 removed the fixed topology and node-name coupling from the
observation, collection, and rule-diagnosis layers while preserving
the P1 Dataset Row v1 boundary. Its completed automated suite had 114
passing tests.

The real B0 regression batch
b0_smoke_canonical-20260730T112109248368Z-
e589527badc546feb1426f41b78fdb1a completed all three N0, C1, and C2
experiments. All three artifacts used Evidence v2 with the TOP-01
r1/r2 binding, all three rule evaluations produced exact_match true,
and TOP-01 remained valid with 13/13 checks before and after the
batch.

P2-R1 completed the role-neutral dataset boundary. Dataset Row v2,
its runtime validator, and its JSON Schema are implemented; the
canonical builder and Batch Runner produce v2, while explicit v1
compatibility remains available without mixing versions inside one
dataset.

The real P2-R1 B0 regression batch
b0_smoke_canonical-20260730T115517979203Z-
24c80549d03d4e84ad7e066f19409ecb completed all three N0, C1, and C2
experiments and produced three validated Dataset Row v2 records. Each
record contained the seven role-neutral features with the TOP-01
hosta_to_hostb, r1/r2 observation context in metadata. All three rule
evaluations produced exact_match true, and TOP-01 remained valid with
13/13 checks before and after the batch. The complete automated suite
had 126 passing tests.

P2-R2 formalized the evaluation-group protocol without changing
Dataset Row v2. The splitter now enforces complete multi-class
evaluation-context groups, exact expected-class coverage when
provided, a minimum of three groups, and deterministic whole-group
allocation. The full suite has 128 passing tests. A direct audit of
the real historical P1 JSONL confirmed its required rejection under
the new protocol.

P2-R3 completed the TOP-02 context-design review without changing
laboratory or implementation files. The future G01 binding is frozen
as CTX_G01_TOP01_LINEAR_2R. The three TOP-02 designs are frozen as:

- G02: TOP_02_CHAIN and CTX_G02_TOP02_CHAIN_3R;
- G03: TOP_02_BRANCH and CTX_G03_TOP02_BRANCH_MID; and
- G04: TOP_02_DUAL_TRANSIT and
  CTX_G04_TOP02_DUAL_TRANSIT.

G02 is a three-router chain with downstream forwarding after the
observed transit. G03 places the route observer at an interior,
two-arm branch. G04 uses two live transit arms and moves the C2 route
to an unreachable next hop on the other transit segment.

The designs retain static routing, Observation Profile v1, Evidence
v2, Dataset Row v2, and the approved N0/C1/C2 semantics. Their
semantic descriptors are recorded in docs/TOP02_CONTEXT_DESIGN.md.
The real G02 artifact bundle is bound to SHA-256
fa411079e19fa7047a467ae46ff1ba7edd54657daee254f74f6c57cd58e4adc3.
The real G03 artifact bundle is bound to SHA-256
2092d0702a8e107a7757ff1754872f518f0be25c89883edb2c5638371a18f0fc.
The real G04 artifact bundle is bound to SHA-256
1e9aa7d2ea8ea1f1691821f8639c60820bbdcd9c0d0bd182e4b72b810b948d54.
The real G05 artifact bundle is bound to SHA-256
6bd4de9818ba0c3b589e5a17cf47553f523fc743d6feb12334bd525ea79ca870.

The current scenario files and historical datasets have not been
relabelled to manufacture new groups. P2-R4 implemented G02
TOP_02_CHAIN, P2-R5 implemented G03 TOP_02_BRANCH, P2-R6 implemented
G04 TOP_02_DUAL_TRANSIT, P2-R7 froze the TOP-03 design, and P2-R8
implemented G05 TOP_03_ASYMMETRIC_RETURN.

The real P2-R4 batch
p2_g02_smoke-20260730T133227173375Z-
c74243e48485444fa795cb0f852f58d7 completed N0, C1, and C2 in listed
order. It produced three validated Evidence v2 artifacts and three
validated Dataset Row v2 records sharing
CTX_G02_TOP02_CHAIN_3R. All three rule-based evaluations produced
exact_match true, and the complete 28-check G02 baseline was valid
before and after the batch.

The first deployment exposed a missing HostB return route for probes
sourced from the r2-r3 transit network. Adding
10.20.23.0/29 via 10.20.3.1 preserved the frozen causal design and
made the transit-to-destination assertion valid. The complete
automated suite then passed 134 tests. The three-row smoke dataset
verifies one complete G02 class set, but it does not satisfy the
two-repetition campaign target or create a valid three-way split.

The real P2-R5 batch
p2_g03_smoke-20260731T065808868462Z-
a2b3766efaa449aeaf9007d4d1b664ea completed N0, C1, and C2 in listed
order. It produced three validated Evidence v2 artifacts and three
validated Dataset Row v2 records sharing
CTX_G03_TOP02_BRANCH_MID. The artifacts bind TOP_02_BRANCH,
hosta_to_hostc, observer r2, and transit r4. Their feature values
matched the expected N0, C1, and C2 semantics, and all three
rule-based evaluations produced exact_match true.

Separate C1 and C2 runtime audits proved that each injected r2 route
fault made the selected HostC arm unreachable while the independent
r3-HostB arm remained reachable. The expected r4 next hop and the
r4-to-HostC segment also remained healthy. This establishes the
frozen branched causal context rather than a renamed linear graph.
Fault restoration, the initial and final 40-check baselines, and
laboratory cleanup all passed. The complete automated suite passed
141 tests.

The real P2-R6 batch
p2_g04_smoke-20260731T074745682481Z-
5c865fccfdf244858aa04003187730a4 completed N0, C1, and C2 in listed
order. It produced three validated Evidence v2 artifacts and three
validated Dataset Row v2 records sharing
CTX_G04_TOP02_DUAL_TRANSIT. The artifacts bind
TOP_02_DUAL_TRANSIT, hosta_to_hostc, observer r1, and transit r3.
Their feature values matched the expected N0, C1, and C2 semantics,
and all three rule-based evaluations produced exact_match true.

Separate runtime audits proved that C1 removed only the selected
HostC route and that C2 moved it from the correct
10.40.13.2/eth3 transit to unreachable 10.40.12.6/eth2 on the other
live transit segment. In both fault states, the r2-HostB alternate
arm and the correct r3 path remained healthy. This establishes the
frozen cross-segment dual-transit context rather than a same-link or
renamed branch variant. Fault restoration, the initial and final
33-check baselines, and laboratory cleanup all passed. The complete
automated suite passed 148 tests.

P2-R7 completed the G05 TOP-03 design review without changing source
contracts, laboratory files, scenarios, schemas, or historical
artifacts. The frozen G05 identifiers are
TOP_03_ASYMMETRIC_RETURN and
CTX_G05_TOP03_ASYMMETRIC_RETURN.

Its physical router graph is the cycle r1-r2-r3-r4-r1, with HostA
attached to r1 and HostB attached to r3. The selected forward path is
hosta-r1-r2-r3-hostb, while the return path is
hostb-r3-r4-r1-hosta. R2 is the forward-only route observer and r3
is the selected transit. C1 and C2 target the r2 route toward
10.50.3.0/24; C2 replaces correct 10.50.23.2 with unreachable
10.50.23.6.

The design retains static routing, Observation Profile v1, Evidence
v2, Dataset Row v2, and the approved class semantics. Its material
distinction is the forward/return divergence, including a return-only
r4 corridor and required reverse-path-filter controls. The normative
descriptor, addressing, baseline, and runtime distinction rules are
recorded in docs/TOP03_CONTEXT_DESIGN.md.

P2-R8 implemented that frozen design without changing Observation
Profile v1, Evidence v2, Dataset Row v2, or the approved feature set.
The real P2_G05_SMOKE batch
p2_g05_smoke-20260731T083408705159Z-
4badf5fdf6da4141af74af11d4b5f1a2 completed N0, C1, and C2 in listed
order. It produced three validated Evidence v2 artifacts and three
validated Dataset Row v2 records sharing
CTX_G05_TOP03_ASYMMETRIC_RETURN. The artifacts bind
TOP_03_ASYMMETRIC_RETURN, hosta_to_hostb, observer r2, and transit
r3. Their feature values matched the approved class semantics, and
all three rule-based evaluations produced exact_match true.

The initial and final 52-check baselines verified the frozen forward
path through r2, return path through r4, reverse-path-filter controls,
route lookups, adjacent-hop health, and wrong-next-hop
preconditions. Separate C1 and C2 audits verified that the selected
forward fault isolated HostB reachability while the r3-r4-r1 return
corridor remained configured and healthy through route and adjacency
checks. Fault restoration, runtime distinction, artifact semantics,
and laboratory cleanup all passed. The complete automated suite
passed 155 tests.

At P2-R8 closeout, G02, G03, G04, and G05 provided one complete
current-class smoke set in four reviewed non-G01 contexts. TOP-01 was
an implemented and verified laboratory, but its future campaign rows
still required the frozen CTX_G01_TOP01_LINEAR_2R binding without
rewriting historical artifacts. No context had the planned two
campaign repetitions per class, no consolidated 30-row campaign had
executed, and no valid train/validation/test split existed.

P2-R9 implemented and verified the first complete campaign input
contract without executing the campaign. Dataset Campaign Plan v1
binds the five contexts to five ordered per-laboratory Batch Plan v1
jobs because Batch Runner v1 accepts one deployed laboratory and one
baseline validator per invocation.

The canonical plan is
plans/campaigns/P2_ROUTING_5CTX_V1.yml. It requires Dataset Row v2,
the no_fault, missing_static_route, and wrong_next_hop classes, two
repetitions per class and context, six rows per group, and exactly 30
rows overall. Three new G01 scenario files use
CTX_G01_TOP01_LINEAR_2R while leaving historical TOP-01 scenarios and
rows unchanged. G02-G05 reuse their verified bindings.

Dataset Campaign Plan v1 validates paths, executable validators,
topology and role bindings, split groups, exact class order,
repetitions, context and campaign counts, and the expected
deterministic split. With complete_context_group_hash_v2, seed
20260730, and ratios 0.6/0.2/0.2, the precommitted allocation is:

- train: G03, G04, and G05;
- validation: G01; and
- test: G02.

The nine targeted P2-R9 tests and complete 164-test suite passed.
The normative execution, merge, quality, rule-audit, and split gates
are recorded in docs/DATASET_CAMPAIGN_DESIGN.md.

P2-R9 did not implement the cross-topology coordinator, execute a
real campaign, merge a 30-row dataset, or create a split. The
validated campaign plan is therefore not an ML-readiness result.

The first real P2-R10 campaign attempt,
p2_routing_5ctx_v1-20260804T070959526851Z-
9f1062d3dbdd44258657c144ec3755fc, exercised the new coordinator and
stopped safely at the G01 artifact audit. G01 completed its six
experiments, final baseline, destroy, and cleanup, but campaign row 3
was rejected by the original zero-unavailable gate. Because row 3 is
the first missing_static_route repetition, its only unavailable
feature is structurally required by the existing contract:
route_next_hop_reachable_from_observer cannot be observed when the
configured route and configured next-hop are absent.

D-066 corrects the P2 campaign gate without changing Evidence v2,
Dataset Row v2, the approved seven-feature set, labels, context
bindings, repetitions, or split precommitment. Every no_fault and
wrong_next_hop row must have zero unavailable features. Every
missing_static_route row must have exactly one, specifically
route_next_hop_reachable_from_observer. Any other unavailable feature
still blocks the campaign. The failed attempt remains incomplete
evidence and cannot contribute rows to a later accepted dataset.

The complete fresh P2-R10 campaign
p2_routing_5ctx_v1-20260804T073429388394Z-
617194fea9954ed98ec120bdefea23d9 completed successfully on
2026-08-04. All five context batches completed 6/6, producing 30
validated Evidence v2 artifacts and 30 Dataset Row v2 records. The
atomic merged dataset has SHA-256
be92cef4e78764e772909e15f43ab5cba98ef9610f4a446fc95e8afb5e830c80.
It contains six rows per context, ten rows per class, and exactly the
ten structurally unavailable C1 next-hop observations required by
D-066, with no unexpected unavailable feature.

The separate rule-based reference audit reported 30/30 exact matches
and 30/30 correct affected-prefix results. The deterministic D-058
split completed with 18/6/6 rows and 3/1/1 complete context groups:
G03/G04/G05 in train, G01 in validation, and G02 in test. No group
crosses partitions, every context passed its initial and final
baseline, and cleanup passed 5/5. The targeted P2-R10 suite passed
11/11 tests and the complete regression suite passed 175/175.

This closes the first five-context dataset-readiness milestone. It
establishes a reproducible, leakage-controlled input for the reviewed
baseline stages; it does not establish general diagnostic accuracy.

P3-R0 has frozen Method Evaluation Result v1 as the comparable
partition-aware reporting contract for the rule-based, Machine
Learning, and hybrid methods. The primary target is fault_type and
the primary comparison metric is unweighted macro F1. The contract
also reports accuracy, per-class precision/recall/F1 and support, a
fixed-order confusion matrix, full-diagnosis exact-match rate, and
fault-only affected-prefix correctness.

The accepted split roles are explicit: train is development,
validation is selection, and test is report_only. Only train and
validation may influence future feature processing, model choice,
hyperparameters, thresholds, or hybrid policy. The overall result is
descriptive_only.

The first implementation maps the separate P2-R10 rule audit to the
frozen partitions, verifies the accepted run and dataset hashes, and
binds each sample to hashed Manifest, ground-truth, Evidence,
prediction, and evaluation artifacts. It changes no rule, feature,
label, campaign row, split group, or prediction. Ten targeted tests
and the complete 185-test suite pass.

The adapter was executed once against the accepted local runtime
artifacts on 2026-08-05. The resulting
p3_r0_rule_based_baseline_v1 report contains 30 records, preserves
the 18/6/6-row and 3/1/1-group allocation, and verifies 150/150
artifact references. Train, validation, and report-only test each
have accuracy 1.0 and unweighted macro F1 1.0. Exact diagnosis match
is 30/30 and fault-only affected-prefix correctness is 20/20.

The accepted report remains a generated local artifact at
reports/experiments/p3_r0_rule_based_baseline_v1.json. Its SHA-256 is
7158f1de31a892779bbce2eaad8f5c5e5bb7c2fc08e0766b49a55047ddc56424.
D-069 accepts this as the traditional baseline and closes P3-R0.

These perfect controlled-campaign values mainly confirm that the
existing deterministic rules cover the same known fault semantics.
They do not establish real-world generalization or superiority. The
independent Machine Learning approach was implemented and accepted
later in D-073; the hybrid approach remains unimplemented.

P4-R0 freezes the leakage-safe pre-fit Machine Learning boundary.
The target remains fault_type, and only the seven ordered Dataset Row
v2 diagnostic features may supply predictors. Each tri-state feature
uses a lossless available/true binary pair: true maps to [1, 1], false
to [1, 0], and unavailable to [0, 0]. This produces 14 ordered binary
columns without a learned imputer or partition-derived statistic.

The candidate set is limited to three L2 multinomial logistic-
regression configurations and three shallow decision-tree
configurations, all declared before fitting. Candidates may fit only
on train and may be selected only on validation by macro F1, accuracy,
complexity rank, and candidate ID in that order. The selected model is
not refitted on train plus validation. G02 test remains available only
for a single report-only evaluation after the complete ML pipeline is
frozen.

ML Feature Matrix v1 separates target and audit identity fields from
the predictor vector, verifies the D-067 campaign and partition
hashes, rejects non-v2 rows or predictor leakage, and writes an atomic
byte-deterministic artifact.

The builder was executed against the accepted D-067 runtime artifacts
on 2026-08-05. The resulting p4_r0_ml_feature_matrix_v1 artifact
contains 30 rows, preserves the 18/6/6-row and 3/1/1-group allocation,
encodes seven raw tri-state features as 14 ordered binary columns, and
preserves exactly ten structural unavailable values. All 30 source-row
references passed SHA-256 verification, the predictor-leakage audit
passed, and G02 test remained report_only.

The accepted matrix remains a generated local artifact at
reports/experiments/p4_r0_ml_feature_matrix_v1.json. Its SHA-256 is
9193b4b8c676bf94ef9af05562d9d0047faef61bc94c9d81b0485b88bf599730.
D-071 accepts the deterministic pre-fit input and closes P4-R0. Ten
targeted tests and the complete 195-test regression suite pass.

P4-R1 is implemented as a two-command freeze boundary. The first
command consumes only train and validation records, fits the six
precommitted candidates, selects by the D-070 order, and atomically
persists the selected train-only estimator plus ML Pipeline Selection
v1. That artifact contains no test prediction or metric. A separate
report command refuses to open G02 until the matrix, selection order,
reproduced train/validation behavior, fitted-sample binding, and both
selection/model hashes pass verification.

The ML implementation uses local open-source scikit-learn and joblib.
Its model inputs remain exactly the 14 D-071 binary columns. It does
not fit on validation, refit on train plus validation, or use test for
selection.

The independent ML prediction contract reports fault_type, all seven
decoded evidence states, and either linear feature contributions or a
tree decision path. It deliberately leaves fault_location and
affected_prefix unset. Method Evaluation Result v1 therefore keeps
classification metrics separate from full-diagnosis and prefix
metrics and does not manufacture localization correctness.

The shared result schema now accepts method-specific provenance
without invalidating D-069: rule-based results retain rule_audit,
whereas Machine Learning results must bind their feature matrix,
selection result, and fitted-model artifact.

The real P4-R1 run completed on 2026-08-05. All six candidates fitted
only on the 18 train rows, selection used only the six validation
rows, and the frozen tie-break order selected logreg_l2_c0_1. The
selected estimator remained train-only. Its selection SHA-256 is
a02536d6f2478d9fdc40510275dd3b48a2824ee7b1f0fa08c1aed472611fb6fb
and its model SHA-256 is
90db38e625f4bcf6a234b6a0516371b76f98e01b4437f684ffea119cbc09cdb2.

Only after those hashes and all 90 canonical data/raw source artifacts
were reverified did the report stage open G02 once. The resulting
p4_r1_ml_baseline_v1 Method Evaluation Result contains 30 rows,
preserves the 18/6/6-row and 3/1/1-group split, and verifies all 150
source-artifact references. Train, validation, and report-only test
each have fault_type accuracy 1.0 and macro F1 1.0. Every prediction
has a local evidence/model explanation.

Because the independent ML baseline does not infer fault_location or
affected_prefix, each partition has exact-diagnosis match 1/3 and
affected-prefix correctness 0.0. These lower structured-diagnosis
metrics are retained rather than filled from ground truth or rules.
The report SHA-256 is
8fc6e77e5008cd7cc74e5ce130b901ed750afab9a35eb62652ff55f9205b0e92.
D-073 accepts this controlled independent ML baseline and closes
Phase 4.

The perfect fault_type values do not establish real-world
generalization or superiority over the D-069 rule-based method. The
dataset has only 30 controlled rows, and validation and test each
contain one context. The hybrid method remains unimplemented and must
be precommitted before any hybrid result or cross-method conclusion is
accepted.

P5-R0 precommits Hybrid Diagnosis Policy v1 before Hybrid Engine
implementation. It binds the accepted D-067 campaign, D-058 split,
D-069 rule report, D-071 feature matrix, and D-073 ML selection,
estimator, and report identities without modifying any of them.

The hybrid prediction-time boundary permits only sample identity,
Evidence v2 provenance, immutable rule and ML predictions, the frozen
policy, and the frozen model binding. Ground truth, labels, partition
identity, correctness flags, evaluation documents, and method metrics
are forbidden. Only the Evaluator reads ground truth.

Two policy candidates are frozen. consensus_abstain_v1 accepts only
rule/ML class agreement and otherwise abstains.
rule_guarded_fallback_v1 adds a disagreement fallback to the rule
class only when all five deterministic rule guards pass. Both
candidates abstain on non-final input. Any accepted fault takes
location and affected_prefix only from a complete rule diagnosis; ML
and ground truth cannot supply those fields.

Candidate selection is reserved for P5-R1 and uses only G01
validation. The fixed order is full-denominator macro F1, exact
diagnosis, coverage, complexity rank, and candidate ID. Abstentions
count as incorrect and are also reported explicitly. G02 remains
closed until a selected-policy artifact is persisted and independently
verified.

P5-R0 implements only the versioned policy artifact, JSON Schema,
semantic validator, documentation, and synthetic contract tests. It
does not implement fusion behavior, select a policy, create hybrid
predictions or metrics, or access test.

The local P5-R0 verification completed on 2026-08-05 against commit
753e075. The policy SHA-256 is
a25467e9cfd8bb52cc67b0c3886eb439466ee51a27b22d292ee468d060bdecc7,
all five accepted baseline hash bindings remained unchanged, and the
two frozen candidates passed 11/11 targeted tests and the complete
216/216 regression suite. No selected candidate, Hybrid Engine
prediction API, hybrid prediction, hybrid metric, or test access was
created. D-074 and the P5-R0 policy-freeze milestone are therefore
accepted. Phase 5 remains in progress; P5-R1 must implement both
candidates and select only on validation without changing the frozen
policy.

P5-R1 implemented and runtime-verified the Hybrid Engine under D-075.
Its prediction API contains no ground-truth, target, partition,
correctness, evaluation, or metric input. The canonical run generated
both frozen candidates for all 24 train/validation rows before the
Evaluator read development ground truth, then computed
full-denominator abstention metrics and selected only from G01
validation summaries.

The implementation adds strict Hybrid Prediction v1 and Hybrid
Selection v1 schemas and a backwards-compatible hybrid extension to
Method Evaluation Result v1. The future hybrid report will require
seven hashed sample references, while the accepted D-069 and D-073
five-reference reports remain valid and immutable.

The canonical run produced 48 candidate predictions, 48 evaluations,
two manifests, and 99 runtime JSON files, with no test output. Both
candidates achieved 1.0 macro-F1, exact diagnosis, and coverage on
train and validation with zero validation abstentions. The frozen
complexity tie-break selected consensus_abstain_v1, complexity rank
0. The selection SHA-256 is
59abc80339658a30ab82019c847dbb7a1c9348bc4ca82ad7e1378f2f339a9507.

The selected-policy freeze was independently verified, 14/14
targeted and 229/229 regression tests passed, and the policy plus all
five baselines remained unchanged. P5-R1 is closed. Phase 5 remains
in progress because G02 is still unobserved by the hybrid method;
P5-R2 alone may perform its one report-only evaluation after
reverifying the committed implementation and selection artifact.

P5-R2 completed the single authorized report-only G02 evaluation
under D-076. The src/hybrid/reporting.py coordinator verified the
unchanged policy, five accepted baselines, complete P5-R1 runtime,
and selection SHA-256 before indexing G02. It then generated only six
consensus_abstain_v1 predictions, completed that prediction batch
before ground-truth evaluation, and atomically created the hybrid
report plus a three-method comparison.

The complete hybrid report reuses the 24 selected P5-R1 development
outputs and adds six P5-R2 report-only test outputs. Its 30 records
carry seven artifact references each, for 210 hash-bound references.
Cross-Method Comparison v1 compares Rule-based, Machine Learning, and
Hybrid results for the same frozen partitions and marks the result as
descriptive only, with no statistical-superiority claim.

The real hybrid result obtained 1.0 macro-F1, 1.0 exact-diagnosis
rate, 1.0 affected-prefix correctness, 1.0 coverage, and zero
abstentions on the six-row G02 test group. The hybrid report SHA-256
is e990a29882f1b7cec4fe003ee5ee65b3fa3dfd25250092a0f9f2a908074a9c75,
and the cross-method comparison SHA-256 is
eebf97dfe340a05feba70874f54727e1a8ccf7ce4224301f162544537d8ecf80.

Independent verification passed 210/210 sample references, the exact
14-file runtime set, 14/14 targeted tests, and 243/243 regression
tests. G02 remained report_only and did not influence policy or
selection. D-076 and P5-R2 are accepted, and Phase 5 is complete for
the frozen controlled campaign. The descriptive comparison does not
establish statistical superiority or real-world generalization.

P6-R0 freezes Phase 6 Extended Fault Taxonomy and Evaluation Plan v1
under D-077 before any new network execution. The six canonical
classes are no_fault, missing_static_route, wrong_next_hop,
wrong_default_gateway, interface_down, and acl_block. The precise
wrong_default_gateway label resolves the earlier wrong_gateway
candidate without changing the historical wrong_next_hop class.

The seven Evidence/Dataset v2 predictors are insufficient to separate
the three new faults. Phase 6 therefore plans Evidence v3 and Dataset
Row v3 with ten ordered tri-state predictors, including installed
source default-gateway agreement, route next-hop agreement, observer
egress operational state, and exact flow-policy blocking. Evidence v2,
Dataset Row v2, the accepted 30-row campaign, and all P3-P5 baseline
artifacts remain immutable. Historical rows are not reused for Phase
6 model fitting.

The first extended clean campaign is precommitted at six complete
contexts, six classes per context, two repetitions per class/context,
and 72 rows. Its explicit whole-context split is 36 train, 12
validation, and 24 report-only test rows across 3/1/2 groups. The two
test groups are unseen by Phase 6 fitting and selection, and one
requires a new forwarding-policy-boundary topology.

Four non-destructive missing-evidence masks are planned separately
from the class taxonomy. They preserve clean source hashes, forbid
imputation and mask identity as a predictor, use validation only for
development, and keep masked test evaluation report-only after model
and policy freeze. Multiple faults remain outside the first campaign
until a later multi-label design defines causal masking and
non-identifiability.

The canonical plan SHA-256 is
f2cf0feced412af5fa76f1ffa861b3500389c430209d8e5b09a4d9e985f1b4f9.
P6-R0 implements only the plan, strict schema, semantic validator,
documentation, and contract tests. Sixteen targeted tests and the
complete 259-test regression suite pass. It creates no Phase 6
experiment, dataset, model, prediction, or metric. P6-R1 must
implement the new evidence, dataset, and observation contracts before
injector work.

P6-R1 implements the D-078 contract boundary without executing the
laboratory. Observation Profile v2 adds explicit source-node and
source-prefix roles, the expected source gateway, observer egress
interface, flow protocol and ports, and the frozen
iptables/filter/FORWARD policy-inspection binding. Its validator
aligns future wrong_default_gateway faults to the source role and
future interface_down and acl_block faults to the route-observer role.
Observation Profile v1 remains supported through explicit versioned
dispatch.

Evidence v3 contains exactly the ten D-077 features plus raw values
needed to audit gateway agreement, route next-hop agreement, interface
operational state, and exact policy blocking. Each feature has one of
observed, structurally_unavailable, or collection_unavailable status
and a corresponding probe record. Observed and failed probes bind a
normalized raw-artifact path and SHA-256; structural non-applicability
has no raw artifact. Evidence v2 and its schema are unchanged.

Dataset Row v3 exports the ten tri-state predictors and keeps source
Evidence v3 SHA-256, availability reasons, mask ID, identifiers,
labels, and quality counters outside the predictor object. It
distinguishes structural_unavailable, collection_unavailable, and
masked_missing without imputing values. The four frozen mask
transformations preserve the clean source hash and any pre-existing
structural reason. Generic validation accepts Dataset Row v1-v3 and
rejects mixed-version aggregation.

Dataset Row v2 remains the runtime default until the Evidence v3
collector is separately implemented and accepted. P6-R1 passed 57/57
targeted tests and the complete 316/316 regression suite in isolated
verification. It created no Phase 6 runtime evidence, dataset row,
model, prediction, or metric. P6-R2 must implement the Evidence v3
collector and raw probes in isolated tests before any new injector or
Containerlab execution.

P6-R2 implements the separate Evidence v3 collector under D-079. The
collector consumes only Observation Profile v2 and has no access to a
scenario label, ground truth, fault type, expected signature,
partition, prediction, or metric. It runs bounded ping, ip -j route,
ip -j link, and iptables/filter/FORWARD inspections, persists exact raw
success or failure records atomically under raw/v3, and binds every
non-structural feature to the exact raw bytes with SHA-256.

Fail-safe parsing distinguishes an observed absent route from a failed
route probe. Only the former makes installed next-hop agreement and
reachability structurally unavailable. Other command, executor, JSON,
interface-state, or policy ambiguity becomes collection_unavailable
with a raw failure artifact. Exact policy blocking requires one tagged
DROP rule matching the selected chain, source, destination, protocol,
and applicable ports.

P6-R2 passed 26/26 targeted collector tests, including the accepted v2
collector regression, and the complete 338/338 regression suite in the
isolated verification environment. The v2 collector file, historical
Experiment Runner path, and Dataset Row v2 runtime default remain
unchanged. P6-R2 performed no Containerlab execution and created no real
Evidence v3, Dataset Row v3, injector result, model, prediction, or
metric. P6-R3 must verify the healthy Evidence v3 path and required
open-source tools in the laboratory before new injector work.

P6-R3 accepts the healthy Evidence v3 runtime and toolchain gate under
D-080. The Ubuntu 24.04 ind-linux image now declares the open-source
iptables package in addition to ip and ping. Before rebuild, the prior
image was preserved locally as ind-linux:p6-r2-preflight. The accepted
historical TOP-01 topology and G01 fingerprint are unchanged; an
isolated post-deploy script adds the Phase 6 source default route without
altering the topology file.

The reviewed N0_NORMAL_OPERATION_P6_TOP01 Observation Profile v2 binds
HostA as source, R1 as route observer, R2 as transit, HostB as
destination, eth2 as observer egress, and iptables/filter/FORWARD as the
policy boundary. Real experiment
p6_r3_healthy_top01-20260806T090542Z produced a contract-valid Evidence
v3 artifact with all ten healthy features observed and nine raw JSON
probe artifacts bound by exact SHA-256. Evidence SHA-256 is
654cb717aa823091b6832d586b22503eb26f37aad81dc3e2f40f7d1f64c75ac2.

TOP-01 remained 13/13 valid before the Phase 6 binding, before
collection, and after collection. The gate passed 31/31 targeted tests
and 343/343 full regression tests, then removed every TOP-01 container.
No fault injection, Dataset Row v3, Phase 6 campaign row, model,
prediction, or metric was produced, and Dataset Row v2 remains the
runtime default. P6-R4 may now implement the three reviewed single-fault
injectors and rule signatures, but it must stop after one fail-stop smoke
execution per new class.

P6-R4 produced one accepted `wrong_default_gateway` smoke and two
fail-stop `interface_down` diagnostics on 2026-08-10. The first runtime
proved that Linux removes the exact R1 routes bound to `eth2` when the
interface is set down. The second proved that `onlink` cannot recreate
those routes while the device remains down; both commands returned code
2 with `Error: Nexthop device is not up.` The controlled interface,
routes, complete baseline, and healthy Evidence v3 were restored after
each stopped gate. Neither failed runtime is an accepted fault Evidence
v3 result or dataset input.

D-081 therefore amends only the `interface_down` feature signature to
T,T,F,F,U,U,F,F,T,F. The exact route absence is observed, while installed
next-hop agreement and reachability are structurally unavailable under
the existing Evidence v3 contract. The class remains distinct from
`missing_static_route` through expected-next-hop reachability and
observer-interface state. Injection performs only `eth2 down` and
verifies kernel route removal; restoration raises the interface and
replaces the exact recorded baseline routes before complete healthy
revalidation.

The original D-077 plan hash remains a historical identity. The amended
canonical plan hash is
571cc26518d81a1768261970fb2d3847587fc4bbc1a9c62678c8f97f3e524746.

The amended runtime
`p6_r4_d081_amended_smoke-20260810T130119Z` then accepted both the
`interface_down` and `acl_block` smokes. Together with the previously
accepted `wrong_default_gateway` smoke, P6-R4 closed with three exact
rule matches, three confirmed restorations, three restored healthy
Evidence v3 signatures, and 26/26 raw fault artifacts bound by SHA-256.
The amended interface case contributed the only two structurally
unavailable values; the other 28 fault-feature values were observed.

The closeout gate passed 46/46 targeted tests and the complete 373/373
regression suite. TOP-01 was 13/13 healthy after the final restoration,
all prior failed-runtime digests remained unchanged, and no TOP-01
container remained. D-082 accepts the bounded three-new-class smoke
gate only. Dataset Row v3 aggregation, E01-E06, the 72-row campaign,
fitting, prediction, and metrics were not executed and move to P6-R5
or later milestones.

P6-R5 implements the six complete E01-E06 context bundles and a
versioned fail-stop campaign path for Evidence v3 and Dataset Row v3.
Every context binds the same six classes with two repetitions per class,
uses its own topology and complete baseline validator, and is protected
by a normalized nine-file context fingerprint. The explicit splitter
allocates E01/E03/E05 to train, E04 to validation, and E02/E06 to the
sealed report-only test partition.

The first real campaign,
`p6_r5_clean_campaign-20260811T063119Z`, stopped at E01 C4 because the
generated interface-down scenarios used the obsolete
`preserved_routes` key instead of the D-081 `baseline_routes` contract.
Its eight completed rows and one failed attempt are retained only as
diagnostic evidence; no merged dataset or split was created. Cleanup
left zero containers.

The bounded recovery corrected six C4 scenarios, their validator,
fingerprints, and contract test without changing D-081 or the frozen
taxonomy. Runtime `p6_r5_c4_recovery_smoke-20260811T070536Z` then
verified interface-down injection and exact restoration in all six
contexts without exporting Dataset Row v3 records.

The clean runtime
`p6_r5_clean_campaign_recovery-20260811T070536Z` completed 72/72
experiments. It produced 72 clean, unmasked Dataset Row v3 records,
with 12 per class and 12 per context, and the exact 36/12/24 split with
no group leakage. E02 and E06 are sealed as
`SEALED_FOR_P6_R6_REPORT_ONLY`. Campaign-result, merged-dataset, and
split-manifest SHA-256 values are respectively
`c4c45e19e8b98d00a3fa2ed3b4d4a8ad2ba6debd04baae05c2d7d7377f9df4d2`,
`50dd030e51e4873eac7665980e033a0236e4ddf26e446b66bd3d11613c4a0a9d`,
and
`adf70942a740be43e085aca67f9acb4085dd118827ceba8482913dbc6adb5f9f`.

The recovered source passed 144/144 Phase 6 tests and 387/387 full
regression tests. All contexts cleaned up, zero containers remained,
and no diagnosis, model, selection, prediction, evaluation, or metric
artifact was created. D-083 accepts the P6-R5 clean-data boundary only;
method fitting, missing-evidence evaluation, and report-only test access
remain blocked until P6-R6 freezes and independently verifies the new
methods.

P6-R6 implements Method Input, Prediction, Freeze, and Report v1
contracts around the ten frozen Evidence v3 features. Each tri-state
feature is encoded as an `available/true` pair, for 20 binary predictor
columns. Labels, ground truth, partition identity, mask identity,
provenance hashes, metrics, correctness, and explanations remain outside
the predictor vector. The four D-077 masks preserve source-row and
Evidence v3 hashes and make only their declared observed feature family
unavailable without imputation.

Development fit used only 36 clean E01/E03/E05 rows. Six precommitted ML
candidates and five immutable Hybrid candidates were selected only with
12 clean plus 48 masked E04 validation inputs. The accepted selections
are `logreg_l2_c1` and `rule_then_ml_fallback_v1`. The development freeze
manifest and an independent verifier bound all method-affecting source
and development artifacts before producing a one-use report-only
authorization.

The authorization was consumed once on 2026-08-11. The immutable E02/E06
source supplied 24 clean test inputs; four deterministic masks produced
96 additional robustness inputs. No model refit, Hybrid-policy
reselection, test-guided revision, or statistical-superiority test
occurred. The freeze-manifest, freeze-receipt, run-manifest, and
cross-method comparison SHA-256 values are respectively
`fa98a17e2ffae42f6dd009a13af65ad32174035eca8352bf26f321531a4fe0f5`,
`5c6c6537cb233efdeb52c6872f7a6ef7fb32eb3ac7b2474e2514b2908cd29bcc`,
`44c505b451c6211b4515564f4b889633b6d74ed0c618f19cc0ab3b9bdfe72b1d`,
and
`ca1c15d04828c0ae61cacaf80a5ee6f49f64a9cf3ac151a4b4ccd2386987e570`.

All three methods achieved clean accuracy and macro-F1 of 1.0 on 24
inputs. Rule-based returned `INSUFFICIENT_EVIDENCE` for all 96 masked
inputs, so masked accuracy, macro-F1, and coverage were zero. ML and
Hybrid both achieved masked accuracy 0.791667, macro-F1 0.810486, and
coverage 1.0. Overall Rule-based accuracy/macro-F1/coverage were
0.200000/0.333333/0.200000; both ML and Hybrid obtained
0.833333/0.846672/1.000000. Because ML and Hybrid are identical in every
aggregate scope, P6-R6 establishes no empirical Hybrid advantage.

The implementation passed 185/185 targeted Phase 6 tests and 428/428
full regression tests. Containerlab was not required or started. D-084
accepts P6-R6 only as a descriptive controlled robustness result. The 96
masks are transformations of the same 24 clean inputs, not independent
experiments, and no population-level, statistical, production, or
real-world superiority claim is authorized. P6-R7 is next and may only
decide whether a separate multi-label multiple-fault experiment is
academically justified and feasible.

P6-R7 completes that decision gate under D-085 without authorizing or
executing a multiple-fault runtime. The review distinguishes injected,
effective, and diagnosable fault sets and finds that the current
single-label contracts cannot score them validly. Several of the ten
nominal two-fault pairs are mutually exclusive, causally dominated, or
injection-order dependent. A nominal balanced pair-only campaign would
require 120 clean rows yet provide only 6/2/4 rows per pair across the
accepted 3/1/2 context split, before invalid pairs are removed.

A defensible extension would require new composition and rollback,
multi-set truth, Dataset Row, Rule/ML/Hybrid prediction, grouped split,
freeze, and multi-label evaluation contracts. That separate track is
disproportionate to the incremental bachelor-scope value after P6-R6.
No Containerlab command, combined injection, collection, fitting,
prediction, or metric occurs in P6-R7, and all P6-R6 artifacts remain
immutable. Phase 6 is complete. P7-R0 is next and must freeze a
read-only Dashboard/API scope around accepted artifacts without network
mutation, model retraining, or new empirical claims.

P7-R0 freezes that boundary under D-086 without implementing or starting
an application. The selected local stack is FastAPI/Uvicorn plus static
same-origin HTML/CSS/JavaScript bound by default to `127.0.0.1`. It adds
no database, React/Node build, cloud dependency, external asset, paid
service, telemetry, or production deployment requirement.

The interface contract binds the accepted P6-R6 freeze-manifest,
freeze-receipt, run-manifest, and descriptive comparison hashes. A
machine-readable allowlist limits projection to 15 JSON/JSONL gate,
selection, report, input, target, and prediction artifacts. The selected
estimator is neither served nor deserialized; development inputs, the
source test split, arbitrary paths, and generic downloads are excluded.

The API surface is six versioned `GET` routes: health, overview,
comparison, case list, case detail, and provenance. The Dashboard scope
is overview, method comparison, case explorer, and provenance/
limitations. Missing or drifted artifacts must fail closed. Network
mutation, fault injection, collection, live diagnosis, inference,
training, selection, new metrics, automatic remediation, subprocesses,
and filesystem writes are prohibited.

P7-R0 creates the plan, OpenAPI contract, documentation, and static
contract tests only. It reads no runtime artifact and creates no server,
UI, evidence, prediction, or metric. P7-R1 is next and may implement
only the verified artifact catalog and immutable 120-case projection
layer before any HTTP or Dashboard implementation is authorized.

P7-R1 implements that boundary under D-087. An integrity audit found
that the four D-086 roots did not themselves anchor the gate bytes and
all non-root case/prediction sources. P7-R1 therefore adds one
Git-tracked catalog containing the canonical path, role, SHA-256, and
size of every one of the same 15 allowed sources. The four accepted
root identities and the P6-R6 result remain unchanged.

The loader verifies 4/4 roots, 15/15 catalog bindings, all allowed
transitive references, 120 inputs and targets, 120 predictions per
method, clean/masked structure, class balance, accepted status
boundaries, and report/comparison consistency before it constructs an
in-memory index. Parsed dictionaries become read-only mapping proxies
and arrays become tuples. Case IDs resolve only against that index.

The projection layer now returns deterministic Python data for health,
overview, three-scope comparison, filtered/paginated case listing, case
detail, and provenance. It preserves accepted numeric values and claim
limitations. It starts no server, performs no inference, does not read
the estimator or source test split, and writes no runtime artifact.
P7-R2 is next and may add only the six frozen FastAPI GET routes and
response/error normalization over this layer; Dashboard rendering
remains P7-R3.

P7-R2 implements the HTTP boundary under D-088. The FastAPI application
contains exactly the six P7-R0 `GET` routes and disables automatic docs,
Redoc, and generated OpenAPI endpoints. It loads and verifies the P7-R1
catalog once during startup and serves only immutable in-memory
projections. Requests never reread an artifact.

Success envelopes preserve the frozen contract metadata. FastAPI
validation is normalized to `400 INVALID_QUERY`; unknown verified-index
case IDs return `404 CASE_NOT_FOUND`; mutating methods return
`405 METHOD_NOT_ALLOWED`; missing or drifted accepted artifacts return
the two frozen `503` codes; and unexpected failures return a generic
path-free `500`. The local entry point binds Uvicorn to
`127.0.0.1:8000` with reload disabled.

All response families validate against the P7-R0 OpenAPI 3.1 schemas.
The API path was tested with no estimator file and with all 15 source
hashes unchanged. Verification passed 32/32 P7-R2 tests, 65/65 combined
Phase 7 tests, 185/185 targeted Phase 6 tests, and 493/493 full
regression tests. P7-R3 is next and may implement only the four static
same-origin Dashboard views; the API remains read-only and no live
diagnosis, inference, experiment, remediation, or new metric is
authorized.

P7-R3 implements the browser presentation boundary under D-089. The
same FastAPI application mounts one dedicated repository directory
containing semantic HTML, responsive CSS, and dependency-free
JavaScript after the unchanged six data routes. The Dashboard adds no
data operation and requests only those routes with same-origin `GET`.

The four frozen views are now implemented: overview, three-scope method
comparison, filterable/paginated case exploration with evidence and all
three accepted predictions, and provenance/limitations. Display-only
rounding never replaces API values. Loading, empty, fail-closed error,
retry, keyboard, reduced-motion, desktop, and 390-pixel behaviors are
implemented and visually checked. No external asset, React/Node build,
browser persistence, model read, inference, network action, new metric,
or runtime write is part of the application.

Verification passed 10/10 P7-R3 tests, 75/75 combined Phase 7 tests,
185/185 targeted Phase 6 tests, and 503/503 full regression tests. The
estimator remained absent from the full UI/API fixture and 15/15 source
hashes remained unchanged. P7-R4 is next and may perform only the Phase
7 closeout gate, reproducible local run instructions, and archive
handoff; it may not reopen the interface or experimental result.

P7-R4 closes Phase 7 under D-090 without adding runtime functionality.
The final acceptance boundary remains six versioned `GET` routes, four
Dashboard views, three static assets, one startup catalog verification,
15 immutable projection sources, and loopback-only
`127.0.0.1:8000` operation. A temporary live-server smoke exercised the
health, overview, comparison, case, provenance, and Dashboard paths and
then stopped cleanly. It started no laboratory and wrote no result.

The reproducible handoff separates the tracked public source archive
from the private accepted-projection archive. The public Git tree omits
ignored generated runtime artifacts. The private presentation bundle
contains the tracked P7-R1 catalog plus exactly its 15 accepted sources;
the selected estimator is excluded, unread, and undeserialized. A fresh
source-only clone is expected to fail closed until this bundle is
restored and independently verified by the catalog loader.

Final verification passed 10/10 P7-R4 tests, 85/85 combined Phase 7
tests, 185/185 targeted Phase 6 tests, and 513/513 full regression tests.
The 15 source hashes remained unchanged. Phase 7 is complete. P8-R0 is
next and must first audit evidence completeness and freeze the final
evaluation/thesis-claim scope; it may not implicitly reopen the consumed
P6-R6 report-only evaluation or create a new experiment.

P8-R0 performs that audit under D-091. It distinguishes developmental
pipeline evidence from the final P6-R6 numerical evaluation, then loads
the Git-tracked P7-R1 catalog and all 15 accepted sources fail-closed.
The generated P8 scope manifest binds the catalog, comparison, and
method gate and preserves the exact accepted clean, masked, and overall
values without executing a method or recalculating a metric.

The evidence is sufficient for eight bounded thesis claims: the
controlled end-to-end pipeline; the six-class/six-context final dataset;
one frozen three-method comparison; complete clean fault-type
classification; the bounded missing-evidence behavior; the operational
rule-first/ML-fallback Hybrid policy; the local read-only presentation;
and the no-refit/no-test-guided-revision protocol boundary. Eight
opposite expansions remain prohibited, including Hybrid or statistical
superiority, real-world generalization, independent-sample treatment of
the 96 masks, multiple faults, OSPF, live production diagnosis,
calibrated-confidence, and population-significance claims.

No thesis-critical empirical runtime gap remains, so P8-R0 records
`NO_NEW_EXPERIMENT_REQUIRED`. The only thesis-critical gaps are the
private full-evidence reproducibility archive and the thesis-ready final
evaluation synthesis. P8-R1 must address the archive without modifying
or deserializing accepted artifacts; P8-R2 may format accepted values
into tables and figures without recomputation or new metrics; P8-R3
then closes Phase 8 and hands off to Phase 9.

P8-R0 verification passed 15/15 targeted tests, 100/100 combined Phase
7 plus P8-R0 tests, 185/185 targeted Phase 6 tests, and 528/528 full
regression tests. All 15 accepted projection sources retained their
hashes; the selected estimator was not read or deserialized.

P8-R1 closes the reproducibility-archive gap under D-092. It inventories
the accepted final numerical chain from the P6-R5 campaign through the
P6-R6 report-only comparison: the complete 72-experiment raw tree, six
context datasets, merged Dataset Row v3, four split files, method gate,
13 development/model files, and 10 report-only files. The generated
tracked registry records the exact artifact count, byte total, path,
role, size, and SHA-256 for the real local accepted bytes.

The tracked Git checkpoint remains the public source archive. A separate
deterministic private bundle contains the registry, archival README, and
ignored runtime artifacts only. Its tracked receipt binds archive hash,
size, member count, registry, and source commit. P1-P5 runtime remains
development history represented by tracked HANDOFFs; it is not promoted
into the D-091 final P6 numerical archive.

The selected estimator is preserved as opaque bytes. P8-R1 imports no
serialization loader and performs no deserialization, inference,
Containerlab execution, refit, policy selection, metric calculation,
test-guided revision, or accepted-artifact write. Verification passed
15/15 targeted tests, 115/115 combined Phase 7 plus Phase 8 tests,
185/185 targeted Phase 6 tests, and 543/543 full regression tests. P8-R2
is next and may only synthesize accepted values for the thesis.

P8-R2 resolves the thesis-ready synthesis gap under D-093. It verifies
the P8-R0 scope hash against the P8-R1 immutable registry and verifies
that registry against the tracked private-archive receipt. It then
formats the frozen accepted snapshot into three CSV tables, two
deterministic accessible SVG figures, five bounded findings, and the
eight-claim evidence matrix. Every generated asset is bound by path,
size, and SHA-256 in the tracked P8-R2 manifest.

The exact accepted decimal metrics remain unchanged in JSON and CSV.
Percentage conversion and rounding in prose and SVG labels are
presentation formatting only. The final interpretation remains that
Hybrid is operationally distinct through rule-first/ML-fallback
provenance but numerically equal to Machine Learning in all accepted
aggregate scopes. Neither Hybrid nor statistical superiority is
claimed.

P8-R2 performs no Containerlab execution, network mutation, diagnosis,
estimator deserialization, test evaluation, refit, policy reselection,
metric recalculation, new metric, or accepted-artifact mutation.
Verification passed 15/15 targeted tests, 130/130 combined Phase 7 plus
Phase 8 tests, 185/185 targeted Phase 6 tests, and 558/558 full
regression tests. P8-R3 is next and must perform only the Phase 8 final
acceptance and Phase 9 handoff.

P8-R3 closes Phase 8 under D-094. Its machine-readable manifest binds
the exact local P8-R2 Git checkpoint, the P8-R0 scope, P8-R1 registry
and receipt, P8-R2 synthesis, all five thesis assets, and the accepted
private archive. The final verification covers 1,488 runtime artifacts
and 1,490 deterministic archive members without deserializing the
estimator or reopening the test partition.

The final claim boundary remains eight supported limitation-bearing
claims and eight prohibited expansions. Hybrid is operationally
distinct through rule-first/ML-fallback provenance but numerically
equal to Machine Learning in every accepted aggregate scope. The 96
masks remain deterministic transformations, not independent
experiments. No new experiment, metric, artifact, or inference is
created in the closeout.

The Phase 9 handoff maps seven thesis chapter roles to accepted evidence
and assets and freezes six writing constraints: preserve exact values;
retain claim limitations; keep prohibited claims blocked; distinguish
implemented, tested, proposed, and out-of-scope work; do not treat masks
as independent experiments; and do not claim Hybrid or statistical
superiority. External academic citations remain a separate P9-R0
verification task.

Verification passed 15/15 targeted P8-R3 tests, 145/145 combined Phase
7 plus Phase 8 tests, 185/185 targeted Phase 6 tests, and 573/573 full
regression tests. Phase 8 is complete. P9-R0 is next: Thesis Structure
and Source/Citation Gate.

P9-R0 establishes the thesis-writing gate under D-095. It binds the exact
public P8-R3 checkpoint and aligns the seven frozen chapter roles with the
verified 2026 University of Prishtina Bachelor thesis guide. The accepted
body outline contains seven chapters and targets 8,100–10,000 words while
preserving the guide's 8,000–10,000 word, 30–50 page, abstract, keyword,
APA, originality, and AI-use requirements.

The primary research question compares Rule-based, Machine Learning, and
Hybrid diagnosis without presupposing Hybrid superiority. Five total
questions map to the accepted C01–C08 boundary. Hybrid remains
operationally distinct but numerically equal to Machine Learning, and the
96 masks remain transformations rather than independent experiments.

The source gate contains 16 verified records: nine scientific
publications, two Internet standards, two institutional records, and three
official technical sources. This is a core seed, not the final
bibliography. The final thesis should meet the University recommendation
of at least 30 credible and relevant scientific references. Every source
must have verified metadata, a chapter role, and a bounded use; literature
cannot enlarge internal empirical claims.

No separate public FIEK chapter-format guide was located as of 2026-08-12.
Any later documented FIEK or mentor formatting instruction may be applied
without changing the evidence or claim boundary. P9-R1 then created only the
University-aligned structural skeleton: front-matter placeholders, seven
chapter/subsection maps, the verified source-to-section matrix, the
claim-to-paragraph plan, blocked-claim guards, and five accepted Phase 8 asset
locations. It does not draft thesis prose, recalculate an accepted value,
reopen test data, or extend an empirical claim. P9-R2 Controlled Chapter
Drafting requires separate authorization.

P7-UX1 subsequently applies a controlled presentation-only amendment to
the already closed Phase 7 Dashboard under D-096. The six-route API,
four-view/three-asset runtime shape, 15 immutable projection sources,
accepted P6-R6 values, evidence, predictions, ground truth, hashes, and
limitations remain unchanged.

The Dashboard now leads with the network problem, diagnostic result,
plain-language explanation, and evidence before methodology and internal
metadata. Original and missing-evidence scopes receive user-facing names;
metric and feature meanings receive short explanations; `RESOLVED` is
shown as `Diagnosis available`; and Case detail makes the evaluation-only
ground truth explicit. Case/context IDs, accepted reason strings,
artifact paths, selected candidate/policy IDs, and SHA-256 roots remain
available under advanced or technical disclosures.

Explanation text is a closed presentation mapping over accepted
prediction reasons. It does not infer a new causal result from the feature
vector. Per-case correctness is a non-persisted display comparison of the
already returned prediction and ground truth, not a new aggregate metric.
Verification passed 94/94 Phase 7, 175/175 Phase 7-through-9, 185/185
targeted Phase 6, and 603/603 full regression tests. P9-R1 remains paused
by explicit user request. Automated implementation acceptance is complete;
final visual acceptance remains pending the local-browser screenshot review.

H1 subsequently hardens runtime safety and reproducibility under D-097 without
reopening any accepted result. A durable recovery intent is now written before
each Phase 6 mutation, normal exception cleanup recognizes that intent even
without an injection record, and a separate recovery replay can restore an
interrupted experiment from the surviving journal. Confirmed restoration is
idempotent and every recovery path verifies the reviewed healthy final state.

All production external commands are bounded and timeout becomes a structured
return-code-124 failure. Two P8 checks that require ignored accepted runtime
are now an explicit acceptance tier, so a clean clone skips them rather than
failing. An opt-in Containerlab test covers the real deploy-to-cleanup cycle but
does not write accepted evidence and is not claimed as executed by H1.

P4 user-facing Joblib verification/report paths accept only the exact D-073
selection and model hashes and check integrity before deserialization. The
P6-R6 fixed coordinator, large scientific modules, and phase-specific hash/JSON
helpers remain unchanged where refactoring could invalidate frozen contracts.
P9-R1 remains paused.

X0 subsequently opens an append-only technical expansion under D-098. The
initial diploma document is treated as the intended vision rather than only as
historical context. Phase 8 remains the accepted six-class baseline and is not
reinterpreted as the end of the technical project.

The canonical expansion taxonomy contains 24 detailed fault types across
addressing, Layer 2/VLAN, routing, services, security, and performance, plus
the frozen `no_fault` class. The source document's later 23-item prioritization
list omitted its own detailed `vlan_missing` case; X0 explicitly retains it.
Five fault types are frozen implemented, one has only a partial reusable
mechanism, and eighteen are not implemented.

The expansion is sequenced X0 through X10: compatibility freeze, extended
contracts, addressing, Layer 2/VLAN, DHCP/DNS/service security, OSPF,
performance, an extended single-fault dataset, Rule/ML/Hybrid v2 evaluation,
missing evidence and unseen variants, then selected multiple faults and a
versioned extended interface. Every future phase requires its own gate.

Existing Evidence v3, Dataset Row v3, Phase 6 method contracts, class order,
accepted runtime artifacts, consumed report-only test results, Phase 7
`/api/v1`, and Phase 8 claims remain immutable. Future technical changes are
allowed only with justification, versioning where semantics change,
backward-compatibility assessment, tests, leakage control, and a recorded
decision. X0 itself authorizes no empirical runtime. P9-R1 remains paused; X1
is the next technical milestone. Verification passed 18/18 X0 tests, 185/185
targeted Phase 6 tests, 6/6 H1 tests, and 625 passed with three explicit skips
in the clean-checkout full regression suite.

X1 subsequently implements the contract-only expansion boundary under D-099.
Eight new schemas cover topology context, collector-run provenance, modular
Evidence v4, a typed feature catalog and vector, single-fault Dataset Row v4
and Diagnosis Result v2, and Evidence Mask Plan v2. None replaces a v3 or
Phase 6 method contract.

Feature Catalog v1 contains 39 entries: ten exact frozen Evidence v3 IDs and 29
planned X2–X6 extensions across connectivity, addressing, Layer 2/VLAN,
routing, services, security, and performance. Seven design specifications give
every feature exactly one collector owner. The registry plans capabilities but
contains no executor and always reports runtime as unauthorized.

The read-only v3 adapter requires the source-artifact SHA-256 and preserves all
ten values, availability states, raw paths, and raw hashes in an in-memory v4
projection. Multiple faults remain deferred to Dataset Row v5 and Diagnosis
Result v3. Phase 7 `/api/v1` remains frozen, a future expansion interface is
reserved for `/api/v2`, and P9-R1 remains paused. X2 addressing vertical slices
are next. X1 verification passed 29/29 targeted tests, 18/18 X0, 185/185
Phase 6, 6/6 H1, 175/175 Phase 7-through-9, 656 passed/1 skipped materialized,
654 passed/3 skipped in a clean clone, and 1/1 existing real Containerlab
lifecycle regression. The E2E is a baseline regression, not new X1 evidence.

X2-R0 subsequently freezes the addressing design and runtime boundary under
D-100. Four single-fault signatures are explicit and disjoint: wrong IP changes
address identity only; wrong subnet mask changes prefix identity only; missing
default route removes route presence without becoming wrong gateway; and
duplicate IP requires active detection plus temporal MAC churn.

The gate binds the X0 taxonomy, X1 contract manifest, five addressing feature
definitions, mask plan, Topology Context v1, Evidence v4, the metadata-only
collector registry, and the X1 verifier by SHA-256. The addressing collector
remains design-only. Runtime is divided into X2-R1 wrong IP, X2-R2 wrong mask,
X2-R3 missing default route, X2-R4 duplicate IP, and X2-R5 closeout. Every
slice requires a separate gate, recovery intent, idempotent restoration, real
Evidence v4, real E2E, restored baseline, and cleanup.

X2-R0 executes no Containerlab command, network mutation, new collection,
dataset generation, model operation, prediction, metric, report-only access,
or multiple-fault run. P9-R1 remains paused; X2-R1 is next.

X2-R1 subsequently implements the first isolated addressing runtime under
D-101. A new three-node Containerlab topology changes HostA from
`10.20.1.10/24` to `10.20.1.11/24` while preserving the expected /24 and the
default route through `10.20.1.1`. This makes address identity, not generic
connectivity failure, the decisive signal.

The injector persists a scenario-hash-bound recovery intent before mutation.
Every exception path attempts exact restoration, a surviving intent is enough
to recover when no injection record was written, confirmed restoration is
idempotent, and both the exact address/route state and the healthy baseline are
revalidated. The new collector produces native Evidence v4 with raw artifact
hashes and collector provenance. An active three-sample neighbor refresh
excludes duplicate IP in this controlled slice; temporal MAC churn is not
requested until X2-R4.

The exact four-feature vector feeds only Rule `R_X2_ADDRESSING_001` through
Feature Vector v2 and Diagnosis Result v2. X2-R1 creates no dataset row, model
fit, estimator load, ML/Hybrid output, metric, report-only access,
multiple-fault execution, or API change. The accepted Phase 6/7/8 baseline
remains immutable, P9-R1 stays paused, and X2-R2 wrong subnet mask is next.

X2-R2 subsequently implements Wrong Subnet Mask under D-102 without modifying
any X2-R1 hash-bound file. It reuses the verified three-node addressing
topology and changes HostA only from `10.20.1.10/24` to
`10.20.1.10/25`; the address identity and installed default route remain
unchanged.

The new durable recovery intent precedes mutation and is sufficient for exact
restoration even when no injection record exists. Restoration is idempotent
after confirmation and revalidates the healthy address, prefix, route,
gateway/destination reachability, and baseline. Native Evidence v4 from
`addressing_state_collector:v2` binds address, route, and active duplicate
artifacts by SHA-256.

The combined Rule-Based v2 engine retains X2-R1
`R_X2_ADDRESSING_001` and adds `R_X2_ADDRESSING_002` only for address true,
prefix false, default true, duplicate false. It fails closed on missing or
unreviewed signatures. X2-R2 creates no dataset, model operation, ML/Hybrid
result, metric, report-only access, multiple-fault run, or API change. The
accepted Phase 6/7/8 and X2-R1 boundaries remain immutable, P9-R1 stays
paused, and X2-R3 Missing Default Route is next after transactional
acceptance.
## X2-R3 Missing Default Route expansion (2026-08-17)

X2-R3 adds an isolated default-route-only runtime slice on the verified X2
topology. HostA remains `10.20.1.10/24`; only its exact default route is
removed. Evidence v4 and `R_X2_ADDRESSING_003` distinguish this fault from
wrong IP and wrong subnet mask. Frozen Phase 6/7/8 artifacts and API v1 remain
unchanged. X2-R4 Duplicate IP is next after transactional acceptance.

## X2-R4 Duplicate IP expansion (2026-08-17)

X2-R4 preserves HostA's address, prefix and route while creating a temporary
second L2 claimant with a distinct MAC. Evidence v4 requires both an active
duplicate response and temporal MAC churn. Frozen science and API v1 remain
unchanged; X2-R5 closeout is next only after real transactional acceptance.

## X2-R5 Addressing Closeout (2026-08-17)

X2-R1 through X2-R4 are accepted real single-fault addressing slices with four
disjoint rules. X2-R5 binds their source gates and accepted Evidence v4 runs,
authorizes 0/10 runtime operations and freezes the claim to four controlled
variants on one known topology. It creates no dataset, ML/Hybrid result,
metric, API change or multiple-fault claim. X3-R0 is the next design-only gate.

## X3-R0 Layer 2/VLAN design gate (2026-08-17)

X3-R0 binds the public X2-R5 closeout and its four-run receipt, the X0 taxonomy,
the X1 feature catalog, Evidence v4, Topology Context v1 and the metadata-only
collector registry. The exact X3 scope is Wrong Access VLAN, VLAN Missing,
VLAN Not Allowed on Trunk and Native VLAN Mismatch.

The design introduces `X3_TOP_01_L2_VLAN`: four hosts and two Linux bridges
with VLAN filtering. HostA/HostB exercise tagged VLAN 10; HostC/HostD exercise
native VLAN 99. VLAN 20 and VLAN 98 are reserved controlled wrong values. This
two-flow design prevents the native mismatch intervention from being conflated
with the tagged trunk allow-list intervention.

Five X1 features form four explicit disjoint signatures: access membership,
VLAN existence, trunk allowance, peer native-VLAN agreement and FDB location.
Runtime evidence must come from both switches plus an active effectiveness
probe; connectivity failure alone is forbidden as a diagnosis.

X3-R0 remains design-only with all ten authorization flags false. No topology
is deployed, no fault is injected, no X3 evidence or prediction is created,
and no claim of diagnostic accuracy is made. Frozen Phase 6/7/8 and API v1,
the accepted X2 boundary, and the P9-R1 pause remain unchanged. X3-R1 Wrong
Access VLAN is the next separately gated runtime release.

## X3-R1 Wrong Access VLAN runtime (2026-08-17)

X3-R1 implements the six-node X3 topology as two VLAN-filtering Linux bridges.
HostA/HostB use tagged VLAN 10 across the trunk; HostC/HostD use native VLAN
99. The isolated mutation changes only SW1 `eth1` from VLAN 10 to VLAN 20,
breaks the tagged flow and preserves the native flow.

The crash-safe injector writes recovery intent before mutation and restores
the exact VLAN 10 PVID/untagged membership on every failure path. Native
Evidence v4 records both switches' VLAN and FDB inventories, link state and
active tagged/native probes. `R_X3_L2_VLAN_001` diagnoses only the exact
false/true/true/true/false signature; connectivity is never the classifier.

The slice authorizes only Containerlab execution, network mutation, Evidence
v4 collection and Rule-Based v2 prediction. It creates no dataset row,
ML/Hybrid output, metric, API change or multiple-fault claim. Real Containerlab
acceptance, complete regressions, restored baseline and zero containers remain
required before publication; X3-R2 follows only after that gate passes.

X3-R1 subsequently passed the full transactional WSL gate. The real topology,
exact false/true/true/true/false signature, tagged-flow fault, preserved native
flow, diagnosis, restoration and zero-container cleanup were confirmed before
publication at `0563fcd`.

## X3-R2 VLAN Missing runtime (2026-08-17)

X3-R2 reuses the accepted X3 topology and HostA-to-HostB observation roles
without changing any X3-R1 hash-bound source. Its single switch-level mutation
removes VLAN 10 from both SW1 `eth1` and SW1 `eth3`, making the expected VLAN
absent from the target switch while leaving SW2 and native VLAN 99 unchanged.

`l2_vlan_state_collector:v2` derives the exact
false/false/false/true/false signature from both-switch VLAN/FDB state and the
tagged/native probes. The combined X3-R2 engine adds `R_X3_L2_VLAN_002` and
regression-preserves `R_X3_L2_VLAN_001`; missing evidence remains insufficient
and unreviewed signatures abstain.

Recovery intent precedes deletion, partial mutations are restored, and exact
access PVID/untagged plus tagged trunk memberships are revalidated through the
complete baseline. The slice authorizes the same 4/10 runtime operations as
X3-R1 and creates no dataset, ML/Hybrid output, metric, API change or
multiple-fault claim.

X3-R2 subsequently passed the full transactional WSL gate. The real
false/false/false/true/false signature, exact diagnosis, preserved native
flow, restoration and zero-container cleanup were confirmed before
publication at `36c9747`.

## X3-R3 VLAN Not Allowed on Trunk runtime (2026-08-18)

X3-R3 reuses the accepted X3 topology and HostA-to-HostB context without
changing X3-R1/X3-R2 hash-bound sources. Its single mutation removes tagged
VLAN 10 only from SW1 `eth3`; SW1 access membership, the SW2 trunk endpoint,
both native VLAN 99 memberships and the HostC-to-HostD control flow remain
unchanged.

`l2_vlan_state_collector:v3` derives the exact
true/true/false/true/true signature from both-switch VLAN/FDB state and the
tagged/native probes. The combined engine adds `R_X3_L2_VLAN_003` while
preserving `R_X3_L2_VLAN_001/002`; unavailable evidence remains insufficient
and unreviewed signatures abstain.

Durable recovery intent precedes the mutation, every failure path attempts
exact tagged VLAN 10 restoration and the full baseline is checked before and
after. The slice authorizes 4/10 runtime operations and creates no dataset,
ML/Hybrid output, metric, API change or multiple-fault claim. Real acceptance
is required before X3-R4, where the planned HostC-to-HostD context variant must
be added before native-flow evidence collection.


## Current expansion status (2026-08-24)

The preceding X3-R3 text records its then-current acceptance condition. X3-R3
and X3-R4 subsequently passed real transactional acceptance, and X3-R5 closed
the four controlled Layer 2/VLAN slices with a hash-bound evidence receipt.
X3 is closed at public commit 2a763c6c6cd44f984ce08331e20d3e03445a0037.

X4-R0 is accepted design-only at public commit
f23f08cd6ef019b3cc0b4fd2c16f3a2609370cb7; all ten authorization flags are
false. X4-R1 and X4-R2 are accepted at public commits 00219ffd947cf4a7c8723c0341d6efdce9654ed4 and 980488cebfc0000fb8bd6e19b5b7e043bf163887. The current D3 release is canonically X4_R3_DNS_SERVICE_DOWN; X4_R3_DNS_SERVICE_UNAVAILABLE is its one-to-one X4-R2 compatibility alias, not a second slice. This status summary
does not alter historical X3 decisions, accepted evidence or frozen Phase 6-9
boundaries.

## X5-R0 OSPF dynamic-routing design gate (2026-08-25)

X5-R0 is an append-only, design-only expansion from accepted X4-R6 commit
`50f0624679d7b1577d88d66ba87eb1c7390e80f0`. It hash-binds X0/X1, X4-R6 and
the accepted P9-R1 traceability plan without changing them. P9-R1 remains
accepted and P9-R2 is intentionally paused while the technical expansion
proceeds.

The planned `X5_TOP_01_OSPF_DYNAMIC_ROUTING` context is a five-node FRRouting
OSPFv2 path. C4 Dynamic Routing Adjacency Failure and C5 Route
Filtering/Advertisement Problem have two direct-state, disjoint signatures
over the four X1 OSPF features. Neighbor, advertisement, route-table, policy,
interface, static-override and policy-block observations prevent interface,
addressing, static-routing, ACL/policy and generic-reachability faults from
being inferred solely from an end-to-end probe.

All ten X5-R0 runtime/scientific flags remain false. No topology deployment,
mutation, Evidence v4, prediction, dataset, ML/Hybrid operation, metric, API
change, BGP work or multiple-fault work is created. Frozen Phase 6–8 results,
API v1, X2–X4 evidence and hashes remain unchanged. X7/X8 will be a separate
extended scientific track. The next release is separately authorized
`X5_R1_OSPF_ADJACENCY_FAILURE`.

## X5-R3 OSPF dynamic-routing closeout (2026-08-25)

X5-R3 append-only binds the accepted X5-R1 C4 and X5-R2 C5 source boundaries
and their durable runtime trees. Its receipt hash-verifies raw provenance,
Evidence v4, exact Rule-Based diagnoses, mutation/restoration records, and
baseline-before/baseline-after records. The preserved disjoint signatures are
C4 `false,false,false,true` and C5 `true,false,false,false`.

The claim remains limited to two controlled single-fault OSPF variants on the
accepted five-node FRRouting topology. X5-R3 creates no runtime material and
makes no generalized OSPF, ML/Hybrid, dataset, metric, API, unseen-topology,
performance, or multiple-fault claim. P9-R2 remains intentionally paused;
next is `X6_R0_PERFORMANCE_FAULT_DESIGN_GATE`.

## X5-R4 targeted OSPF correction and revalidation (2026-08-25)

X5-R4 is the append-only authoritative successor to X5-R3. It retains the
original X5-R1 C4 tree unchanged as historical evidence, but it is not
authoritative for targeted-C4 scientific use after the later audit. The new C4
lifecycle establishes exact R2--R3 identity, a separate healthy R1--R2
control, separate command acceptance/effectiveness records, and a bounded
state-based postcondition before collection. Its receipt binds corrected C4 to
unchanged accepted C5. C5's suppression marker is provenance metadata and the
accepted mechanism is OSPF network-statement withdrawal. X4 audit observations
are non-blocking bounded limitations for a later robustness track. P9-R2 and
X6 remain paused; frozen Phase 6--8, X0--X4, API v1, datasets, ML/Hybrid,
metrics, and scientific claims remain unchanged.

## X5-R5 C5 operational-policy correction design (2026-08-25)

X5-R5 is source-only and append-only from X5-R4. It preserves the X5-R4 C4
tree as authoritative and the X5-R2 C5 tree/older receipts as immutable
history, while marking the latter non-authoritative for the C5 policy feature.
Future C5 evidence must use FRR `redistribute connected route-map` with an
attached prefix-list criterion, not a marker or a removed direct OSPF network
statement. The planned runtime mutation denies the expected prefix only through
that attached criterion. No runtime evidence, scientific result, dataset,
model, metric, API change or broad OSPF claim exists in X5-R5. X6 and P9-R2
remain paused; next is `X5_R6_C5_OPERATIONAL_POLICY_RUNTIME_REVALIDATION`.

## X5-R6 corrected C5 operational-policy runtime revalidation (2026-08-26)

X5-R6 is the only new C5 runtime tree after X5-R5. It uses an attached FRR
`redistribute connected route-map` plus prefix-list, retains healthy exact
adjacencies, and proves policy denial without an expected-prefix OSPF `network`
statement. Evidence requires valid structured LSDB/route output and Feature
Vector v2 validation before diagnosis. Command acceptance, physical
effectiveness, recovery replay, baseline before/after and cleanup are distinct
records. No claim extends beyond controlled single-fault C5. X5-R7 is next;
X6 and P9-R2 remain paused.

## X5-R8 C5 runtime-safety correction gate (2026-08-26)

Following a focused correctness audit, X5-R8 is an append-only source-only
correction from the published X6-R0 boundary. It preserves every X5-R6/X5-R7
artifact unchanged: their normal lifecycle observations remain historical, but
they are not the authoritative basis for crash-safety or complete
observation-to-raw receipt claims. The future C5 revalidation has a durable
planned-action journal before every mutation attempt, separate action-state
records, and a standalone idempotent recovery/replay entry point that reads
durable mutation state after a partial mutation. Source-only tests do not
depend on ignored archives; explicit materialized verification remains
mandatory when those archives are available. X6-R1 and P9-R2 remain paused.
The next release is `X5_R9_C5_RUNTIME_SAFETY_REVALIDATION`.

## X6-R0.1 performance measurement and traffic methodology (2026-08-26)

X6-R0.1 is an append-only design-only methodology gate. It freezes future
topology/traffic provenance, direct tool commands and versions, ten baseline
windows, warm-up/measurement timing, exact p95 calculation and a hash-bound
threshold-manifest boundary before a mutation. Collectors will retain numeric
measurements while rules alone derive predicates; neither threshold metadata
nor rule predicates is a future ML label. F1--F4 signatures remain conditional
until empirical pilot measurements show truthful separation. No performance
runtime evidence, threshold, dataset, model, metric, API, or scientific claim
is created. X5-R9 remains next; X6-R1 and P9-R2 remain paused.
