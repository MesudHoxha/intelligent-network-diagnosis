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
