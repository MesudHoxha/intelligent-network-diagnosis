# X0 Scope and Compatibility Freeze

Date: 2026-08-14

Status: ACCEPTED — DESIGN ONLY; NO EXPERIMENTAL RUNTIME AUTHORIZED

## 1. Purpose

X0 reopens the original ambitious technical vision as an append-only
expansion track. It does not reinterpret Phase 8 as failed or incomplete for
its accepted six-class research question. Phase 6 through Phase 8 remain the
strong frozen baseline; X0 establishes what may be built after that boundary.

The initial project document is treated as the intended technical vision, not
only as historical motivation. The current six-class taxonomy is therefore a
serious first experimental baseline rather than the final project taxonomy.

X0 performs no Containerlab execution, network mutation, evidence collection,
dataset generation, estimator deserialization, model fit, prediction, metric
calculation, report-only test access, or multiple-fault experiment.

## 2. Relationship to the accepted baseline

The frozen Phase 6 class order remains exactly:

1. `no_fault`;
2. `missing_static_route`;
3. `wrong_next_hop`;
4. `wrong_default_gateway`;
5. `interface_down`; and
6. `acl_block`.

Evidence v3, Dataset Row v3, the Phase 6 method contracts, the P6-R6 method
protocol, accepted model and result artifacts, consumed E02/E06 report-only
test outputs, Phase 7 `/api/v1` projection, and Phase 8 claim/evidence archive
remain immutable.

D-085 and D-091 remain historically correct for the bounded Bachelor
baseline. X0 does not rewrite them. D-085 closed multiple-fault runtime for
Phase 6 and explicitly left it as a separate future study. D-091 established
that no further experiment was necessary for the accepted six-class thesis
claim boundary. Neither decision establishes that the original technical
vision was fully implemented.

P9-R0 remains accepted and P9-R1 remains paused by the user's explicit
request. The expansion track is separate from the paused thesis-writing track.

## 3. Canonical taxonomy resolution

The detailed taxonomy in the initial document describes 24 fault types across
six domains. A later prioritization paragraph states 23 and omits the already
described `VLAN missing` case. X0 records this as an editorial inconsistency
and includes all 24 detailed fault types.

| Domain | Fault types | Current status |
| --- | --- | --- |
| Addressing | wrong IP, wrong mask, wrong gateway, duplicate IP | one frozen, three missing |
| Layer 2/VLAN | interface down, wrong access VLAN, missing VLAN, trunk allow-list, native mismatch | one frozen, four missing |
| Routing | missing static route, wrong next-hop, missing default route, dynamic adjacency, advertisement/filtering | two frozen, three missing |
| Services | DHCP down, DHCP pool error, DNS down, wrong DNS record | four missing |
| Security | ACL block, firewall/service block | one frozen, one partial mechanism |
| Performance | loss, latency, congestion, rate limiting | four missing |

The resulting implementation gap is:

- five frozen implemented fault types;
- one partial mechanism without a distinct diagnostic class; and
- eighteen missing fault types.

`no_fault` remains a separate frozen healthy class. Dynamic-routing adjacency
may later be represented hierarchically with concrete root-cause subtypes, but
that semantic decision belongs to X1 and cannot modify the Phase 6 flat class
order.

## 4. Versioning boundary

X1 must design new contracts before any new data is collected. The planned
single-fault family is:

- Topology Context v1;
- Evidence v4;
- Feature Catalog v1;
- Feature Vector v2;
- Dataset Row v4;
- Diagnosis Result v2; and
- Evidence Mask Plan v2.

These are new contracts, not edits to their frozen predecessors. A read-only
adapter may represent accepted v3 evidence through a later interface, but it
may not rewrite an accepted source artifact.

Multiple faults require a later Dataset Row v5 and Diagnosis Result v3. They
must distinguish injected, effective, and diagnosable fault sets and must not
be forced into the single-label v4 boundary.

## 5. Architecture and method policy

The existing orchestration, recovery journal, campaign controls, raw-evidence
hashing, availability semantics, grouped splitting, method freeze, evaluation,
and read-only artifact projection are retained and extended incrementally.
There is no rewrite authorization.

OSPF is the first dynamic-routing protocol. BGP remains optional and requires
a later OSPF gate to show a concrete additional research need.

Logistic Regression and Decision Tree remain required interpretable baselines.
Additional models are candidates only when validation evidence justifies the
added complexity. The Hybrid method is compared objectively and is not
required to win. Automatic remediation remains outside the project boundary.

## 6. Expansion sequence

| Phase | Objective |
| --- | --- |
| X0 | Freeze scope and compatibility boundaries |
| X1 | Version extended contracts and modular collection |
| X2 | Addressing faults |
| X3 | Layer 2 and VLAN |
| X4 | DHCP, DNS, and service security |
| X5 | Dynamic routing with OSPF |
| X6 | Performance faults |
| X7 | Extended grouped single-fault dataset |
| X8 | Rule, ML, and Hybrid v2 evaluation |
| X9 | Missing evidence and unseen variants/topologies |
| X10 | Selected multiple faults and versioned extended interface |

Every future phase requires its own design and runtime gate. Listing a phase
here does not authorize its network commands or empirical claims.

## 7. Release gates

Every release must end with:

- completed implementation;
- green unit and integration tests;
- real infrastructure E2E when the release touches the laboratory;
- a green full regression suite;
- real raw evidence when empirical runtime is authorized;
- valid baseline before and after fault execution;
- confirmed cleanup;
- unchanged accepted Phase 6/7/8 artifact bytes; and
- an explicit acceptance decision before the next release.

An ML-ready single-fault class requires at minimum three train groups, one
validation group, two report-only test groups, and two repetitions per group.
This is a minimum campaign admission gate, not a real-world generalization
claim.

Multiple faults remain bounded to approximately six to ten technically
meaningful pairs, starting with two pilots. A Cartesian product is prohibited.
Each pair requires an identifiability, composition, recovery-order, and truth
semantics gate.

## 8. Change control

Future technical changes are expected and allowed when evidence or
implementation experience justifies them. A semantic change requires:

1. technical justification;
2. a new contract version when meaning changes;
3. a backward-compatibility assessment;
4. tests appropriate to the risk;
5. preservation of report-only test isolation; and
6. a recorded decision and acceptance gate.

No change may alter accepted scientific results merely to simplify new code.
No future design may silently convert a proposed capability into an
implemented claim.

## 9. Machine-readable gate

The normative design artifact is
`plans/expansion/X0_SCOPE_COMPATIBILITY_FREEZE_V1.json`. It validates against
`schemas/x0_scope_compatibility_freeze_v1.schema.json` and is additionally
checked by `src/expansion/scope_gate.py` for exact class order, taxonomy rows,
gap counts, roadmap order, version boundaries, release gates, and an all-false
runtime authorization map.

The validator also requires every protected baseline contract to remain a
regular tracked file. Scope drift, missing fault types, reordered baseline
classes, weakened compatibility rules, or any X0 runtime authorization fails
closed.

## 10. Acceptance boundary

X0 is accepted only as a design and compatibility freeze. It establishes the
ambitious roadmap and preserves the strong baseline. It creates no new claim
that an additional fault, topology, collector, model, or multiple-fault case
already works.

Final verification passed 18/18 X0 tests, 185/185 targeted Phase 6 tests,
6/6 H1 safety tests, and 625 passed with three explicit clean-checkout skips in
the full suite. The three skips are the opt-in real Containerlab smoke and two
accepted-runtime checks whose ignored private artifacts are not materialized
in the clean verification tree.

The next milestone is X1: Extended Contracts and Modular Collection. X1 must
remain design/contract-first and may not begin fault runtime until its own gate
is accepted.
