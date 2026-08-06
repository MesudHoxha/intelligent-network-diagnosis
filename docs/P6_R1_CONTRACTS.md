# P6-R1 Observation, Evidence, and Dataset Contracts

Version: 1

Date: 2026-08-06

Status: IMPLEMENTED AND CONTRACT-TESTED; NO NETWORK EXECUTION

## 1. Purpose and boundary

P6-R1 implements the versioned data boundary required by the frozen
six-class plan in D-077. It does not implement a network collector,
fault injector, topology, campaign, model, diagnostic method, or
evaluation result.

The milestone introduces:

- Observation Profile v2;
- Evidence v3;
- Dataset Row v3;
- strict Draft 2020-12 JSON Schemas;
- explicit backwards-compatible version dispatch;
- feature-level raw-probe provenance;
- non-imputing unavailable-reason semantics; and
- deterministic non-destructive mask semantics.

Evidence v2 and Dataset Row v2 schemas remain byte-for-byte
unchanged. Dataset Row v2 remains the runtime default until the real
Evidence v3 collector is implemented and separately accepted.

## 2. Observation Profile v2

Observation Profile v2 extends the role-neutral v1 profile with the
inputs required to collect the ten D-077 features safely.

Its role and addressing fields include:

- source node and container;
- source address and canonical source prefix;
- expected source gateway address;
- destination address and canonical destination prefix;
- route-observer node and container;
- expected observer next-hop;
- observer egress interface; and
- transit node and container.

The source, route-observer, and transit nodes must be distinct. The
source address and expected source gateway must be different members
of the source prefix, and the destination must belong to the
destination prefix.

The exact inspected flow is represented by protocol and nullable
source/destination ports. ICMP requires null ports. TCP and UDP
require ports between 1 and 65535.

The first policy-inspection backend is frozen to:

- backend: iptables;
- table: filter; and
- chain: FORWARD.

This is a contract binding, not proof that iptables is installed in
the laboratory image. Tooling installation and real probe execution
remain P6-R2 work.

Fault-parameter alignment is role-specific:

- missing_static_route and wrong_next_hop target the route observer;
- wrong_default_gateway targets the source node;
- interface_down targets the observer egress interface; and
- acl_block targets the observer forwarding policy and the exact
  flow selector.

Observation Profile v1 remains unchanged. The explicit versioned
dispatcher accepts v1 or v2 and rejects every other version.

## 3. Evidence v3

Evidence v3 stores the ten ordered D-077 predictors in a dedicated
features object:

1. source_expected_gateway_reachable;
2. source_default_gateway_matches_expected;
3. destination_reachable;
4. route_to_destination_exists_on_observer;
5. route_next_hop_matches_expected;
6. route_next_hop_reachable_from_observer;
7. expected_next_hop_reachable_from_observer;
8. observer_egress_interface_oper_up;
9. destination_reachable_from_transit; and
10. flow_blocked_by_policy.

The order is checked against the frozen P6-R0 plan. The feature object
cannot contain labels, scenario identity, ground truth, partitions,
mask identity, predictions, metrics, hashes, or explanations.

Evidence v3 separately records raw values needed to audit the derived
features, including:

- expected and installed source default gateways;
- expected and installed observer next-hops;
- observer egress interface and operational state; and
- the exact flow-policy backend, table, chain, and matching block-rule
  identifier.

The validator checks that default-gateway agreement, next-hop
agreement, interface-operational state, and flow-policy blocking match
these raw values. An absent observer route requires the dependent
installed-next-hop features to be structurally unavailable.

## 4. Probe provenance and unavailable reasons

Every Evidence v3 feature has an availability value and a probe
record.

| Availability | Feature value | Probe status | Raw artifact |
| --- | --- | --- | --- |
| observed | true or false | completed | required with SHA-256 |
| structurally_unavailable | null | not_applicable | forbidden |
| collection_unavailable | null | failed | required with SHA-256 |

Raw artifact paths must be normalized relative paths. Absolute paths,
parent traversal, missing hashes, and non-lowercase SHA-256 digests
are rejected.

Structural unavailability means the measurement has no defined value
in the network state, such as an installed next-hop when the route is
absent. Collection unavailability means the measurement was defined
but its probe failed. These states must not be conflated.

Evidence v3 does not contain masked_missing. Missing-evidence masks are
derived non-destructively from a clean Dataset Row v3 and never modify
the source Evidence v3 artifact.

## 5. Dataset Row v3

Dataset Row v3 exports exactly the ten Evidence v3 feature values as
the strings true, false, or unavailable. It adds no identifier or
provenance field to the predictor object.

Metadata remains outside predictors and records the experiment,
scenario, variant, complete split group, topology, direction, source,
observer, transit, and collection timestamp.

The provenance section records:

- source_evidence_schema_version = 3;
- the lowercase SHA-256 of the exact Evidence v3 file;
- one availability reason per feature; and
- a nullable mask_id.

Dataset Row v3 availability reasons are:

- observed;
- structurally_unavailable;
- collection_unavailable; and
- masked_missing.

Quality counters record the total unavailable values and the three
unavailable reason counts. The validator requires the feature values,
availability map, and all counters to agree exactly.

## 6. Missing-evidence mask semantics

The four D-077 masks are implemented as deterministic contract
transformations:

- mask_source_gateway_family;
- mask_route_family;
- mask_interface_state; and
- mask_policy_state.

A mask may be applied only to a clean Dataset Row v3. Within its
frozen family it changes observed values to unavailable and records
masked_missing. Existing structural or collection-unavailable reasons
are preserved. At least one observed feature must change.

The transformation preserves:

- sample and metadata identity;
- labels;
- clean source Evidence v3 SHA-256;
- all features outside the selected family; and
- every pre-existing structural or collection-unavailable reason.

Mask identity remains provenance, never a predictor. No value is
imputed.

## 7. Version dispatch and compatibility

The implemented dispatch boundaries are:

- Observation Profile v1 or v2;
- Evidence v2 or v3; and
- Dataset Row v1, v2, or v3.

Dataset aggregation validation rejects mixed row versions. The
historical Dataset Row v1 and canonical Dataset Row v2 validators
retain their existing behavior. The v2 schemas are immutable inputs
to the P6-R1 closeout audit.

Although explicit Dataset Row v3 export is implemented for future
Evidence v3 experiment directories, the generic runtime default stays
at Dataset Row v2. A later accepted milestone must change that default
only after the real collector path produces valid Evidence v3.

## 8. Verification

P6-R1 verification passed:

- 57/57 targeted contract tests;
- 316/316 full regression tests in the isolated environment;
- all three Draft 2020-12 schema checks;
- exact ten-feature order binding to D-077;
- v1-v3 version dispatch and version-mixing negative tests;
- predictor leakage negative tests;
- raw artifact path/hash negative tests;
- derived-feature/raw-value consistency tests;
- unavailable reason and quality-count consistency tests; and
- non-destructive mask/source-hash preservation tests.

No Containerlab command ran. No Phase 6 experiment, real Evidence v3
artifact, Dataset Row v3 campaign record, model, prediction, or metric
was created.

## 9. Next boundary

P6-R2 may implement the Evidence v3 collector and raw probes. It must
preserve the accepted v2 collector path and stop before new fault
injectors or topology execution. Only after the collector is accepted
may later milestones implement and smoke-verify the new faults.
