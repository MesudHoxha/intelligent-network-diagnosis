# HANDOFF — P6-R0 Extended Fault Taxonomy and Evaluation Plan

Date: 2026-08-05

Status: COMPLETED

## 1. What was completed

P6-R0 froze and runtime-verified the bounded Phase 6 design before
any new scenario implementation or experimental execution.

The milestone:

- resolved the deferred wrong_gateway candidate to the precise
  canonical label wrong_default_gateway;
- froze six single-fault classes in a fixed order;
- demonstrated that the seven Evidence/Dataset v2 predictors are
  insufficient for the expanded taxonomy;
- froze a planned ten-feature Evidence v3 and Dataset Row v3 boundary;
- defined class-specific complete-evidence signatures;
- defined injection, postcondition, restoration, and baseline gates;
- precommitted six complete contexts, two repetitions per class and
  context, and a 72-row clean campaign;
- precommitted an explicit 36/12/24 whole-context split across 3/1/2
  groups with two report-only test contexts;
- defined four deterministic non-destructive missing-evidence masks;
- retained all P2-P5 artifacts as immutable references and prohibited
  historical-row reuse for Phase 6 fitting;
- deferred multiple-fault execution until a separate multi-label
  design gate; and
- implemented a strict JSON Schema and semantic validator for the
  machine-readable plan.

Accepted verification evidence:

- plan ID: p6_extended_fault_taxonomy_v1;
- plan SHA-256:
  f2cf0feced412af5fa76f1ffa861b3500389c430209d8e5b09a4d9e985f1b4f9;
- classes: 6/6 frozen;
- planned features: 10/10 frozen;
- contexts: 6/6 design-only;
- clean campaign arithmetic: 72 = 36 + 12 + 24 PASS;
- missing-evidence masks: 4/4 frozen;
- targeted tests: 16/16 PASS;
- complete regression suite: 259/259 PASS;
- Containerlab executions: 0;
- Phase 6 dataset rows: 0;
- Phase 6 training, predictions, and metrics: absent; and
- P2-P5 artifact modifications: absent.

## 2. What was decided

D-077 is approved, implemented as a design contract, and
runtime-verified.

The canonical class order is:

1. no_fault;
2. missing_static_route;
3. wrong_next_hop;
4. wrong_default_gateway;
5. interface_down; and
6. acl_block.

The planned Phase 6 feature boundary contains exactly ten tri-state
predictors. It adds source default-gateway agreement, route next-hop
agreement, observer egress operational state, and exact flow-policy
blocking to the necessary role-neutral connectivity and routing
evidence. No unavailable value is imputed, and no label, ground truth,
partition, mask ID, identifier, metric, or explanation is a predictor.

The first extended campaign must recollect all six classes through
Evidence/Dataset v3. It may not append new rows to or train from the
accepted Dataset Row v2 campaign. Train contains E01/E03/E05,
validation contains E04, and report-only test contains E02/E06. Test
access remains closed until the future six-class model and hybrid
policy are independently frozen.

The expected signatures are design acceptance targets, not measured
results. P6-R0 does not establish feasibility of an injector,
diagnostic performance, generalization, or method superiority.

## 3. Files created or changed

P6-R0 committed files:

- docs/DECISIONS.md;
- docs/HANDOFF_P6_R0.md;
- docs/MASTER_CONTEXT.md;
- docs/PHASE6_FAULT_TAXONOMY_PLAN.md;
- docs/ROADMAP.md;
- docs/STATUS.md;
- plans/taxonomies/P6_EXTENDED_FAULT_TAXONOMY_V1.json;
- schemas/fault_taxonomy_plan_v1.schema.json;
- src/planning/__init__.py;
- src/planning/fault_taxonomy.py; and
- tests/unit/test_p6_r0_fault_taxonomy_plan.py.

No topology, image, scenario, injector, collector, Dataset Row v2,
rule, ML, hybrid, frozen policy, model, report, or runtime artifact was
changed.

## 4. Open issues

- Implement Observation Profile v2, Evidence v3, and Dataset Row v3.
- Preserve Evidence/Dataset v1-v2 compatibility and accepted hashes.
- Define and validate raw probes for default-route agreement, link
  operational state, next-hop agreement, and exact flow-policy state.
- Add and verify open-source iptables tooling before acl_block smoke.
- Implement fail-stop wrong_default_gateway, interface_down, and
  acl_block injectors and exact restoration.
- Implement/review the six complete contexts, including new E06.
- Execute and audit the 72-row campaign only after all design gates.
- Implement the four source-hash-bound missing-evidence transforms.
- Define new six-class Rule-based, ML, and Hybrid versions without
  altering the accepted P3-P5 baselines.
- Design multi-label truth before considering multiple faults.
- Define a reproducible final archive for generated thesis evidence.
- Keep OSPF proposed until separately reviewed.

## 5. Next step

Start P6-R1 — Evidence v3, Dataset Row v3, and Observation Profile v2
Contracts.

P6-R1 must:

- preserve Evidence v2, Dataset Row v2, and all accepted P2-P5 bytes;
- implement strict backwards-compatible version dispatch;
- add the ten frozen predictor features and necessary raw provenance;
- keep metadata, labels, masks, and evaluation fields outside the
  predictor object;
- implement JSON Schemas and semantic validators;
- define structural-unavailable versus masked-missing semantics;
- add negative leakage, version-mixing, and unexpected-field tests;
- stop before any new injector or topology execution;
- produce no Phase 6 dataset row, model, prediction, or metric; and
- create its own HANDOFF before P6-R2.

## 6. Impact on central documents

- DECISIONS adds D-077 and the canonical plan hash.
- MASTER_CONTEXT records the six-class boundary, planned v3 features,
  72-row campaign, split, and missing-evidence strategy.
- PHASE6_FAULT_TAXONOMY_PLAN contains the normative design.
- ROADMAP marks Phase 6 in progress, closes P6-R0, and names P6-R1.
- STATUS records the verified design and distinguishes all planned
  work from implemented or tested network behavior.
