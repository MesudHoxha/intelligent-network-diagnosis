# Dataset Campaign Design — P2_ROUTING_5CTX_V1

Date: 2026-07-31
Status: DESIGN FROZEN; INPUT CONTRACT IMPLEMENTED; NOT EXECUTED

## 1. Purpose

This document defines the first complete multi-context routing
campaign used to decide whether the project may begin its first
Machine Learning experiment.

The campaign is deliberately small and controlled:

- five materially reviewed evaluation contexts;
- three approved classes;
- two repetitions per class and context;
- 30 expected Dataset Row v2 records; and
- a deterministic whole-context 3/1/1 split.

The campaign validates the first cross-context experimental boundary.
It is not evidence of general network-diagnosis performance and is
not the final thesis dataset.

## 2. Scope and exclusions

P2_ROUTING_5CTX_V1 includes only:

- no_fault;
- missing_static_route; and
- wrong_next_hop;
- static-routing laboratories G01-G05;
- Observation Profile v1;
- Evidence v2;
- Dataset Row v2; and
- the seven approved role-neutral tri-state features.

The campaign does not add:

- new model features;
- OSPF or BGP;
- missing-evidence experiments;
- unseen contexts;
- multiple simultaneous faults;
- paid services or external datasets;
- Machine Learning training;
- hybrid diagnosis; or
- automatic network remediation.

Those items require later reviewed stages.

## 3. Why the campaign contains five context batches

Batch Runner v1 accepts one Batch Plan v1 and one baseline validator.
It assumes that the referenced laboratory is already deployed. A
single 30-entry Batch Plan v1 could list scenarios from five
topologies, but it could not safely switch deployed laboratories or
validators between entries.

P2_ROUTING_5CTX_V1 is therefore one logical fail-stop campaign with
five ordered context jobs. Every job references:

- one topology;
- one executable baseline validator;
- one six-experiment Batch Plan v1;
- one frozen split_group_id; and
- one observation-role binding.

The future campaign coordinator owns topology deployment, baseline
verification, per-context batch execution, cleanup, merge, campaign
audit, and split. Batch Runner v1 remains the per-context experiment
executor and is not weakened or overloaded.

## 4. Frozen campaign matrix

| Slot | Topology | Split group | Direction | Observer | Transit | Batch | Rows |
| --- | --- | --- | --- | --- | --- | --- | ---: |
| G01 | TOP_01 | CTX_G01_TOP01_LINEAR_2R | hosta_to_hostb | r1 | r2 | P2_G01_CAMPAIGN | 6 |
| G02 | TOP_02_CHAIN | CTX_G02_TOP02_CHAIN_3R | hosta_to_hostb | r1 | r2 | P2_G02_CAMPAIGN | 6 |
| G03 | TOP_02_BRANCH | CTX_G03_TOP02_BRANCH_MID | hosta_to_hostc | r2 | r4 | P2_G03_CAMPAIGN | 6 |
| G04 | TOP_02_DUAL_TRANSIT | CTX_G04_TOP02_DUAL_TRANSIT | hosta_to_hostc | r1 | r3 | P2_G04_CAMPAIGN | 6 |
| G05 | TOP_03_ASYMMETRIC_RETURN | CTX_G05_TOP03_ASYMMETRIC_RETURN | hosta_to_hostb | r2 | r3 | P2_G05_CAMPAIGN | 6 |

Each context batch contains the class order:

1. no_fault, repetitions 1 and 2;
2. missing_static_route, repetitions 1 and 2; and
3. wrong_next_hop, repetitions 1 and 2.

Context jobs execute in the listed order G01, G02, G03, G04, G05.
The resulting global planned sequence contains exactly 30
experiments.

## 5. G01 binding

Historical TOP-01 scenarios predate the complete evaluation-context
grouping protocol. Their artifacts and split_group_id values must not
be rewritten.

The campaign therefore adds three new scenario files:

- N0_NORMAL_OPERATION_G01_TOP01_LINEAR_2R.yml;
- C1_MISSING_STATIC_ROUTE_G01_TOP01_LINEAR_2R.yml; and
- C2_WRONG_NEXT_HOP_G01_TOP01_LINEAR_2R.yml.

All three use:

- topology_id TOP_01;
- split_group_id CTX_G01_TOP01_LINEAR_2R;
- variant_id canonical;
- direction hosta_to_hostb;
- observer r1;
- transit r2;
- destination 10.10.2.10 and prefix 10.10.2.0/24; and
- expected next hop 10.10.12.2.

C1 removes the r1 route toward 10.10.2.0/24. C2 replaces the correct
10.10.12.2 next hop with unreachable 10.10.12.254 through eth2. These
are the verified canonical TOP-01 semantics under a new future-facing
complete-context binding.

## 6. Dataset Campaign Plan v1 contract

The canonical plan is:

plans/campaigns/P2_ROUTING_5CTX_V1.yml

Its validator is:

src/campaign/plan.py

The JSON Schema is:

schemas/dataset_campaign_plan_v1.schema.json

The runtime validator rejects a plan unless:

1. schema_version is 1;
2. execution order is listed and failure_policy is stop;
3. Dataset Row schema version is 2;
4. the expected classes are non-empty and unique;
5. context slots, split groups, and batch plans are unique;
6. every topology, validator, batch plan, and scenario file exists;
7. every baseline validator is executable;
8. every context scenario matches the declared topology, group,
   direction, observer, and transit;
9. every context batch contains the expected class order exactly;
10. every entry uses two repetitions;
11. every context expands to six experiments;
12. the complete campaign expands to 30 experiments; and
13. the declared split allocation equals the deterministic result
    of the frozen algorithm, seed, ratios, and group identifiers.

The validator does not deploy a laboratory, execute an experiment,
merge rows, or write a split.

## 7. Planned execution transaction

The future coordinator must treat the campaign as one fail-stop
transaction for acceptance purposes.

For each context, in listed order:

1. verify that the committed topology, validator, and scenario bundle
   still matches the accepted context fingerprint;
2. deploy only that context laboratory;
3. run its baseline validator and require VALID;
4. run the referenced six-experiment Batch Plan v1;
5. require Batch Runner status COMPLETED and 6/6 experiments;
6. audit the six Evidence v2 and Dataset Row v2 artifacts;
7. run the final baseline validator and require VALID; and
8. destroy the laboratory and verify cleanup.

If any step fails, the coordinator must stop before the next context.
Already produced raw artifacts remain evidence of an incomplete
attempt, but they must not be merged into the accepted dataset.

The campaign is accepted only from one coordinator result that binds
the exact five successful batch results from the same campaign run.
Historical smoke datasets and rows from incomplete attempts are not
eligible merge inputs.

## 8. Merge and dataset quality gates

The merged dataset must be written atomically and must pass all of
the following gates:

- exactly 30 non-empty JSONL records;
- Dataset Row v2 for all records;
- 30 unique sample_id and experiment_id values;
- exactly the five frozen split_group_id values;
- exactly six rows per group;
- exactly two rows for each group and fault_type pair;
- only the three approved fault_type values;
- exact topology, direction, observer, and transit binding per group;
- experiment_completed true;
- collector_completed true;
- baseline_before_valid true;
- baseline_after_valid true;
- no_fault and wrong_next_hop rows with
  unavailable_feature_count zero;
- missing_static_route rows with unavailable_feature_count one and
  route_next_hop_reachable_from_observer as the only unavailable
  feature;
- no other unavailable feature in any campaign row;
- no mixed schemas;
- no historical smoke row or incomplete-attempt row; and
- a recorded SHA-256 for every source context dataset and the merged
  JSONL payload.

The class-conditional unavailable-feature gate is campaign-specific.
For missing_static_route, the configured route and therefore its
configured next-hop do not exist. The reachability of that absent
configured next-hop is structurally undefined; it is not a failed
probe and must remain unavailable. The separate
expected_next_hop_reachable_from_observer feature must still be
available and true in the controlled C1 state. This policy preserves
the Dataset Row v2 tri-state contract without treating structural
non-applicability as missing evidence or imputing a false value.

## 9. Rule-based reference audit

Rule-based evaluation is not a model feature and is not part of
Dataset Row v2. It must remain a separate campaign report.

For this controlled campaign, all 30 experiments are expected to
produce:

- an evaluation artifact;
- exact_match true; and
- the correct affected-prefix behavior for the relevant fault class.

A mismatch does not authorize relabelling, deleting, or selectively
re-running only the failed row. It blocks campaign closeout until the
cause is investigated and a complete new campaign attempt is
reviewed. Batch status COMPLETED alone never means diagnostic
correctness.

## 10. Frozen split

The split uses:

- algorithm complete_context_group_hash_v2;
- seed 20260730;
- ratios 0.6/0.2/0.2; and
- expected classes no_fault, missing_static_route, wrong_next_hop.

The frozen allocation is:

| Partition | Groups | Expected rows | Rows per class |
| --- | --- | ---: | ---: |
| train | G03, G04, G05 | 18 | 6 |
| validation | G01 | 6 | 2 |
| test | G02 | 6 | 2 |

The split manifest must additionally prove:

- source_row_count 30;
- source_group_count 5;
- class_count 3;
- group counts 3/1/1;
- row counts 18/6/6;
- complete three-class coverage in every group;
- no split_group_id occurs in more than one partition;
- source dataset SHA-256 matches the accepted merged dataset; and
- output SHA-256 values match the written train, validation, and test
  JSONL files.

The allocation is frozen before runtime results exist. The seed,
ratios, group identifiers, or partition membership must not be tuned
after reviewing rule or future ML performance.

## 11. Required closeout evidence

The real campaign closeout must record:

- the campaign run identifier and status;
- the exact committed campaign-plan hash;
- the five context artifact fingerprints;
- five accepted Batch Runner result identifiers;
- 30/30 completed experiments;
- 30/30 valid Evidence v2 artifacts;
- 30/30 valid Dataset Row v2 records;
- every merge and quality gate;
- the separate rule-based exact-match result;
- the merged dataset SHA-256;
- the split manifest and partition SHA-256 values;
- the no-cross-partition group audit;
- every initial and final baseline result; and
- laboratory cleanup for every context.

Only after that closeout may the project claim that the first dataset
is ready for the reviewed ML baseline stage.

## 12. Accepted implementation and runtime status

P2-R9 implemented and tested the static campaign inputs. P2-R10 then
implemented:

- the cross-topology fail-stop coordinator;
- the frozen five-context fingerprint manifest;
- Campaign Result v1 and its JSON Schema;
- per-context deploy, baseline, batch, destroy, and cleanup handling;
- artifact revalidation and class-conditional D-066 quality gates;
- atomic five-dataset merge;
- the separate rule-based reference audit; and
- invocation and verification of the existing deterministic splitter.

The first runtime attempt
p2_routing_5ctx_v1-20260804T070959526851Z-
9f1062d3dbdd44258657c144ec3755fc stopped at the G01 artifact audit.
It exposed the conflict between the original zero-unavailable gate
and the approved C1 tri-state semantics. D-066 corrected the gate,
and no row from that incomplete attempt was reused.

The accepted fresh campaign is
p2_routing_5ctx_v1-20260804T073429388394Z-
617194fea9954ed98ec120bdefea23d9. It completed and verified:

- five of five context batches and 30/30 experiments;
- 30/30 Evidence v2 and Dataset Row v2 artifact revalidations;
- six rows per group and ten rows per class;
- the exact N0:0/C1:1/C2:0 unavailable-feature policy;
- zero unexpected unavailable features;
- 30/30 rule exact matches and affected-prefix checks;
- a 30-row merged JSONL with SHA-256
  be92cef4e78764e772909e15f43ab5cba98ef9610f4a446fc95e8afb5e830c80;
- the frozen 18/6/6-row, 3/1/1-group split;
- no group crossing partitions;
- Campaign Result v1 schema validation; and
- five of five context cleanups.

The corrected targeted suite passed 11/11 tests and the full suite
passed 175/175. P2-R10 therefore satisfies every closeout item in
Section 11 and makes the accepted split available to the reviewed
baseline stages.

ML training and hybrid diagnosis remain unimplemented. The campaign
result is a dataset-readiness result, not a claim of general
diagnostic performance.
