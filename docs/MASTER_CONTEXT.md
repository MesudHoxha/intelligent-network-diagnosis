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

G02, G03, G04, and G05 now provide one complete current-class smoke
set in four reviewed non-G01 contexts. TOP-01 is an implemented and
verified laboratory, but its future campaign rows still require the
frozen CTX_G01_TOP01_LINEAR_2R binding without rewriting historical
artifacts. No context has the planned two campaign repetitions per
class, no consolidated 30-row campaign has executed, and no valid
train/validation/test split exists.

The Machine Learning and hybrid diagnostic approaches have not yet
been implemented or evaluated.
