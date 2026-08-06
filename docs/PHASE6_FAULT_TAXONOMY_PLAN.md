# Phase 6 Extended Fault Taxonomy and Evaluation Plan

Version: 1

Date: 2026-08-05

Status: DESIGN FROZEN; CONTRACT IMPLEMENTED; NO NETWORK EXECUTION

## 1. Purpose

P6-R0 freezes the bounded design for extending the controlled network
diagnosis experiment before any new scenario, injector, topology,
dataset row, model, or hybrid result is produced.

The design has three academic goals:

1. broaden the single-fault taxonomy beyond static-route faults;
2. make the new classes distinguishable through observable network
   evidence rather than through labels or scenario identities; and
3. evaluate Rule-based, Machine Learning, and Hybrid diagnosis under
   unseen contexts and controlled missing evidence.

P6-R0 is design-only. It does not execute Containerlab, collect data,
train a model, change a frozen baseline, or report a Phase 6 metric.

## 2. Relationship to the accepted P2-P5 campaign

The P2_ROUTING_5CTX_V1 campaign and all P3-P5 method artifacts remain
immutable historical references. Their bytes, labels, split, models,
policy, predictions, and reports are not rewritten.

Phase 6 requires a new evidence and dataset contract because the
seven Dataset Row v2 features cannot reliably separate:

- a wrong source default gateway;
- a down forwarding interface; and
- an access-control rule that blocks the observed flow.

For that reason, Phase 6 does not append new labels to the accepted
30-row Dataset Row v2 dataset. It recollects all classes under the
same future Evidence v3 and Dataset Row v3 contracts. Historical rows
may support regression checks, but they are not Phase 6 training rows.

## 3. Frozen class taxonomy

The exact class order is:

1. `no_fault`;
2. `missing_static_route`;
3. `wrong_next_hop`;
4. `wrong_default_gateway`;
5. `interface_down`; and
6. `acl_block`.

The earlier candidate term `wrong_gateway` is resolved to the
canonical label `wrong_default_gateway`. The longer name distinguishes
a source-host default-route error from the already implemented
`wrong_next_hop` fault on a route observer.

| Class | Category | Fault location role | Controlled mechanism |
| --- | --- | --- | --- |
| `no_fault` | normal | none | no mutation; baseline revalidation only |
| `missing_static_route` | routing | route observer | remove the exact destination route |
| `wrong_next_hop` | routing | route observer | replace the exact route with a wrong next-hop |
| `wrong_default_gateway` | routing | source host | replace the source default gateway |
| `interface_down` | link | observer egress | set the selected forwarding interface down |
| `acl_block` | access control | observer forwarding policy | insert one exact tagged flow-drop rule |

The taxonomy remains single-label and single-fault. Multiple
simultaneous faults are excluded from the first Phase 6 campaign
because the current ground-truth and evaluation contracts cannot
represent multiple root causes. A later reviewed milestone must
define multi-label truth, partial matches, causal masking, and
non-identifiability before any combined injection is authorized.

## 4. Planned Evidence v3 feature contract

Evidence v3 and Dataset Row v3 are planned, not implemented by P6-R0.
Their exact predictor feature order is frozen as follows:

| # | Feature | Meaning |
| ---: | --- | --- |
| 1 | `source_expected_gateway_reachable` | Source can reach the expected local gateway address |
| 2 | `source_default_gateway_matches_expected` | Installed source default route uses the expected gateway |
| 3 | `destination_reachable` | Source reaches the observed destination |
| 4 | `route_to_destination_exists_on_observer` | Observer has the destination route |
| 5 | `route_next_hop_matches_expected` | Installed route next-hop equals the expected next-hop |
| 6 | `route_next_hop_reachable_from_observer` | Observer reaches the installed route next-hop |
| 7 | `expected_next_hop_reachable_from_observer` | Observer reaches the expected transit next-hop |
| 8 | `observer_egress_interface_oper_up` | Selected observer egress interface is operationally up |
| 9 | `destination_reachable_from_transit` | Transit reaches the destination downstream of the fault location |
| 10 | `flow_blocked_by_policy` | Exact inspected forwarding policy blocks the observed flow |

Every predictor value uses the existing tri-state domain `true`,
`false`, or `unavailable`. Unavailable remains distinct from false;
no imputation is authorized by this design.

Raw identifiers, addresses, interface names, commands, timestamps,
scenario IDs, mask IDs, labels, ground truth, partitions, predictions,
correctness flags, metrics, and explanation text are not predictors.

The planned contract must preserve raw evidence needed for audit while
exporting only the ten frozen role-neutral features to Dataset Row v3.
Evidence v2 and Dataset Row v2 remain supported for historical
regression without alteration.

## 5. Expected complete-evidence signatures

These signatures are controlled expectations and implementation
acceptance targets. They are not experimental results.

| Feature | Normal | Missing route | Wrong next-hop | Wrong default gateway | Interface down | ACL block |
| --- | --- | --- | --- | --- | --- | --- |
| Expected gateway reachable | T | T | T | T | T | T |
| Default gateway matches | T | T | T | F | T | T |
| Destination reachable | T | F | F | F | F | F |
| Observer route exists | T | F | T | T | T | T |
| Route next-hop matches | T | U | F | T | T | T |
| Installed next-hop reachable | T | U | F | T | F | T |
| Expected next-hop reachable | T | T | T | T | F | T |
| Observer egress operational | T | T | T | T | F | T |
| Transit reaches destination | T | T | T | T | T | T |
| Flow blocked by policy | F | F | F | F | F | T |

`T`, `F`, and `U` mean true, false, and structurally unavailable.

The configured next-hop fields are structurally unavailable for
`missing_static_route`; this is not an artificial missing-evidence
case. Artificial masks are tracked separately and never overwrite the
clean evidence artifact.

## 6. Injection and restoration contracts

Every future fault injector must be fail-stop and idempotence-aware.
It must persist exact preconditions, the applied mutation,
postconditions, timestamps, command results, and restoration evidence.

Common gates for every fault are:

- complete baseline valid before injection;
- target node, container, interface, addresses, and expected state
  match the scenario contract;
- no conflicting P6 mutation already exists;
- expected end-to-end path succeeds before injection;
- the exact expected effect is observed after injection;
- unrelated downstream health checks remain valid where specified;
- restoration reverses only the recorded mutation;
- complete baseline valid after restoration; and
- any failed restoration stops the campaign before another scenario.

Class-specific requirements are:

### Missing static route

- The exact route and expected next-hop must exist before deletion.
- Only that route may be removed.
- Restoration replaces the exact route and next-hop.

### Wrong next-hop

- The correct route must exist and the chosen wrong next-hop must be
  unreachable before injection.
- The route remains present but uses the wrong next-hop afterward.
- Restoration replaces the exact correct route.

### Wrong default gateway

- The source default route must use the expected gateway initially.
- The wrong gateway must be on the controlled source segment and must
  not forward the observed traffic.
- The expected gateway remains directly reachable, separating this
  class from a physical source-link failure.
- Restoration replaces the expected source default route.

### Interface down

- The selected observer egress interface, its peer, and the route must
  be healthy before injection.
- Only the selected observer interface is set down.
- The route stays present and continues to name the expected next-hop,
  while the interface and neighbor reachability become false.
- Restoration sets the interface up and requires full baseline
  revalidation; a command return code alone is insufficient.

### ACL block

- Future implementation must first add and verify open-source
  `iptables` tooling in the local laboratory image.
- The baseline must prove that no P6-tagged rule exists.
- Injection inserts one uniquely tagged forwarding rule scoped to the
  observed source, destination, direction, and protocol.
- Route, next-hop, interface, and downstream destination health remain
  valid while only the selected flow fails.
- Restoration deletes the exact recorded rule and proves that no
  tagged rule remains.

The implementation may not use a broad firewall flush, reset all
routes, recreate an entire container as the normal restoration path,
or hide a failed post-restoration baseline.

## 7. Complete-context campaign

The first extended campaign is
`P6_EXTENDED_6CLASS_6CTX_V1`.

It contains:

- six complete evaluation contexts;
- six classes in every context;
- two repetitions for every class/context pair;
- 12 clean rows per context; and
- 72 expected clean Dataset Row v3 records.

| Slot | Frozen split group | Semantic context | Implementation status |
| --- | --- | --- | --- |
| E01 | `CTX_P6_E01_TOP01_LINEAR_SOURCE_EDGE` | Linear two-router source-edge path | Design only; reuse TOP-01 structure |
| E02 | `CTX_P6_E02_TOP02_CHAIN_OBSERVER_EDGE` | Three-router chain with downstream reachability | Design only; reuse TOP_02_CHAIN structure |
| E03 | `CTX_P6_E03_TOP02_BRANCH_TARGET_ARM` | Branched topology and selected destination arm | Design only; reuse TOP_02_BRANCH structure |
| E04 | `CTX_P6_E04_TOP02_DUAL_TRANSIT_SELECTED_ARM` | Dual transit with selected forwarding arm | Design only; reuse TOP_02_DUAL_TRANSIT structure |
| E05 | `CTX_P6_E05_TOP03_ASYMMETRIC_FORWARD` | Asymmetric forward and return paths | Design only; reuse TOP_03 structure |
| E06 | `CTX_P6_E06_TOP04_FILTER_BOUNDARY` | New explicit forwarding-policy boundary | Design only; new TOP-04 required |

Reusing a topology structure does not authorize reuse of old rows.
Every E01-E06 row must be newly collected through the same Evidence
v3 pipeline and complete six-class scenario bundle.

The Phase 6 group boundary consists of the topology, directed path,
observation roles, evidence producers, and a frozen class-specific
injection-location map. The entire six-class bundle stays in one
partition. This Phase 6 rule does not reinterpret or rename any P2
split group.

## 8. Frozen split and unseen-context definition

The allocation is explicit and frozen before any Phase 6 runtime
result:

| Partition | Groups | Rows | Use |
| --- | --- | ---: | --- |
| Train | E01, E03, E05 | 36 | model fitting only |
| Validation | E04 | 12 | candidate and policy selection only |
| Test | E02, E06 | 24 | one report-only evaluation after freeze |

No split group may cross partitions. Group IDs may not be renamed to
change allocation after results exist.

Both test contexts are unseen by Phase 6 fitting and selection. E06
is additionally a new topology implementation, while E02 provides a
known structural family recollected under the new contract. Reports
must provide both aggregate test metrics and per-context values so a
single easy group cannot hide failure in the other.

The explicit 3/1/2 group split gives two report-only test contexts.
It is a stronger descriptive check than the one-context P2 test, but
six deterministic contexts still do not support a population-level
generalization or statistical-superiority claim.

## 9. Missing-evidence robustness track

Missing evidence is not a seventh fault class.

The track creates deterministic, non-destructive masked copies of
clean Evidence v3 artifacts. Each copy binds the source artifact hash
and sets only the declared feature family to unavailable. It does not
delete or modify the clean source artifact and does not impute a value.

The frozen masks are:

1. `mask_source_gateway_family` — expected-gateway reachability and
   default-gateway match;
2. `mask_route_family` — route existence, next-hop match, and
   installed next-hop reachability;
3. `mask_interface_state` — observer egress operational state; and
4. `mask_policy_state` — flow-blocking policy state.

Mask identity and partition identity are metadata, not predictors.
Masked rows are not used to fit the first Phase 6 model. Validation
masks are development-only. Test masks remain closed until the model
and hybrid policy are frozen, then are evaluated report-only.

Rule and Hybrid methods are allowed to return `INSUFFICIENT_EVIDENCE`
or abstain. Such outputs must not disappear from denominators. Reports
must include coverage, abstention, insufficient-evidence rate, and
accuracy/macro-F1 on the complete supervised denominator.

## 10. Method and leakage boundaries

Phase 6 still compares:

1. deterministic Rule-based diagnosis;
2. an independent Machine Learning classifier; and
3. a Hybrid policy combining immutable method predictions.

The Phase 6 implementations may be new versions trained or selected
for the six-class campaign. The accepted P3-P5 baselines remain
unchanged references; their prior perfect class metrics are not
carried forward as Phase 6 results.

Prediction-time inputs exclude labels, ground truth, partitions,
evaluation artifacts, correctness flags, metrics, and result-derived
thresholds. Model fitting uses only train. Candidate and hybrid-policy
selection use only validation. Test clean and masked outputs are
created once after independent freeze verification and are report-only.

Required report scopes are overall, partition, class, context, and
missing-evidence mask. Required primary metrics are macro-F1, exact
diagnosis, affected-prefix correctness, coverage, abstention rate, and
insufficient-evidence rate.

## 11. Acceptance gates

P6-R0 accepts only the design artifact, schema, semantic validator,
tests, and documentation. Later execution remains blocked until:

- Evidence v3 and Dataset Row v3 are implemented with historical
  compatibility tests;
- every class has a reviewed scenario, injector, and restoration path;
- every E01-E06 context has a topology, validator, and complete
  six-class scenario bundle;
- the ACL tool dependency is present and baseline-audited;
- all clean signature expectations pass in smoke execution;
- 72/72 clean experiments complete in one fail-stop campaign;
- split output is exactly 36/12/24 with no group leakage;
- missing-evidence copies bind immutable clean-source hashes;
- method candidates and policies are frozen before test access; and
- independent verification passes before any report is accepted.

Any label ambiguity, non-unique signature, unexpected unavailable
value, incomplete context, restoration failure, baseline drift,
artifact overwrite, or test-guided change stops the stage.

## 12. Sequenced Phase 6 milestones

- P6-R0: freeze this taxonomy and evaluation plan.
- P6-R1: implement Evidence v3, Dataset Row v3, Observation Profile v2,
  and compatibility gates without running the full campaign.
- P6-R2: implement the separate Evidence v3 collector, raw-probe
  persistence, and fail-safe parsing in isolated tests without network
  execution.
- P6-R3: verify the healthy Evidence v3 runtime path and required
  open-source probe tools in one reviewed laboratory context without
  fault injection.
- P6-R4: implement the three new fail-stop injectors and rule
  signatures; smoke each new class in one reviewed context.
- P6-R5: implement/review E01-E06 and execute the 72-row clean
  fail-stop campaign with the frozen split.
- P6-R6: fit/select the new ML and Hybrid versions, then perform the
  one report-only clean and missing-evidence test evaluation.
- P6-R7: decide whether a bounded multi-label multiple-fault experiment
  is academically justified and feasible; it is not pre-authorized.

Each milestone requires its own HANDOFF and central-document update.

## 13. Explicit exclusions and limitations

P6-R0 does not authorize:

- OSPF or BGP;
- multiple simultaneous fault injection;
- automatic remediation;
- production-network execution;
- paid APIs, cloud services, licenses, or datasets;
- reuse of P2 rows as Phase 6 training data;
- modification of P3-P5 reports, model, or hybrid policy;
- test-guided feature, model, rule, threshold, or policy changes; or
- statistical or real-world superiority claims.

OSPF remains proposed under D-034. It may be reconsidered only through
a separate academic-value, scope, and test-plan decision.
