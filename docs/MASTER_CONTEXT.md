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
rather than fixed r1/r2 names. Synthetic TOP-02 unit fixtures verify
this role-neutral behavior, but no real TOP-02 laboratory has yet
been implemented or executed.

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
different TOP-02 contexts, and one TOP-03 asymmetric context. TOP-02
and TOP-03 remain planned and have not been implemented.

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

The current scenario files and historical datasets have not been
relabelled to manufacture new groups. Shared multi-class bindings for
future TOP-01 campaign rows and the concrete TOP-02 and TOP-03
laboratories remain to be implemented and verified.

The Machine Learning and hybrid diagnostic approaches have not yet
been implemented or evaluated.
