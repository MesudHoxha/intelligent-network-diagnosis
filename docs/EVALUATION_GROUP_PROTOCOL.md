# Evaluation Group Protocol

Version: 1
Date: 2026-07-30

## 1. Purpose

This protocol defines the dependency boundary used when splitting the
controlled network-diagnosis dataset into train, validation, and test
partitions.

The goal is leakage control. It does not claim that deterministic
laboratory samples are statistically independent observations from a
real-world population.

## 2. Grouping unit

`split_group_id` identifies one evaluation context. It is the smallest
set of experiments that must remain in the same partition because they
share the same experiment-generating context.

One evaluation context is defined by the combination of:

- the topology graph and forwarding configuration;
- the directed source-to-destination diagnostic path;
- the route-observer and transit role binding;
- the logical fault-injection location; and
- the components that produce the diagnostic evidence.

All no-fault and fault-class experiments for the same context use the
same `split_group_id`. For the current campaign, one complete group
therefore contains `no_fault`, `missing_static_route`, and
`wrong_next_hop`.

No additional `evaluation_context_id` field is added. Dataset Row v2
already carries `split_group_id`, so the dataset contract remains
unchanged.

## 3. What does not create a new group

The following remain in the existing group:

- repetitions;
- alternate IP addresses or subnets on the same logical path;
- alternate destination addresses reached through the same path;
- node renaming;
- timestamps and experiment identifiers;
- small parameter changes that preserve the topology, roles, evidence
  producers, and injection location; and
- a nominal reverse direction that only relabels an otherwise
  equivalent path.

## 4. What may create a new group

A new group requires a material change in the causal diagnostic
context, such as:

- a structurally different forwarding graph;
- a different directed path with a different role binding;
- a different logical location of the injected fault; or
- different network components producing the observed evidence.

A second path inside one laboratory does not automatically count as a
new group. Before it receives a new `split_group_id`, its graph,
binding, injection location, and evidence producers must be recorded
in the campaign matrix. If the distinction is unclear, both paths stay
in the same group.

## 5. Split Contract v2

The splitter uses `complete_context_group_hash_v2`.

It enforces the following rules:

1. Every `split_group_id` is assigned wholly to one partition.
2. Every group contains every required `fault_type`.
3. The expected class set can be supplied explicitly and must match
   the source dataset exactly.
4. At least three complete context groups are required for a
   train/validation/test split.
5. Five complete context groups are the target before the first ML
   experiment, producing a 3/1/1 group allocation under the default
   0.6/0.2/0.2 ratios.
6. Dataset Row versions cannot be mixed in one split source.
7. Group identifiers are frozen before splitting and must not be
   renamed to influence their deterministic hash allocation.

With five groups, two repetitions, and the three current classes, the
minimum planned campaign contains 30 rows. The repetitions improve
execution coverage but do not increase the independent-group count.

## 6. Planned context matrix

The following matrix fixes the required coverage before topology
implementation. Names after TOP-01 are design labels, not claims of
implemented laboratories.

| Group slot | Planned context | Material distinction | Status |
| --- | --- | --- | --- |
| G01 | TOP-01 linear two-router path | Existing two-router observer/transit chain | Laboratory verified; shared multi-class group binding pending |
| G02 | TOP-02 three-router chain profile | Longer forwarding path and additional routing component | Planned |
| G03 | TOP-02 branched profile | Branching forwarding graph and distinct destination-side evidence path | Planned |
| G04 | TOP-02 dual-transit profile | Different transit role and next-hop failure context | Planned |
| G05 | TOP-03 asymmetric profile | Separate topology family for broader context coverage | Planned |

Each planned profile must receive a distinct `topology_id` and a
documented graph/configuration fingerprint. If two profiles collapse
to the same causal context during design review, they collapse to one
group and another context must be added before dataset generation.

TOP-03 is therefore planned now rather than being discovered as a late
requirement after TOP-02. TOP-02 remains the next implementation
milestone because it is the first real test of the role-neutral
pipeline outside TOP-01.

## 7. Historical data

P1 and the P2-R1 smoke dataset remain unchanged historical artifacts.
Their class-specific `split_group_id` values do not satisfy this
protocol and do not become new context groups through migration or
renaming.

They remain valid for pipeline regression, but the Split Contract v2
must reject them as ML split sources.

## 8. ML readiness gate

ML training remains blocked until:

- all five planned contexts are implemented or replaced by reviewed
  contexts satisfying this protocol;
- every context supports the complete approved class set;
- the real expanded campaign completes successfully;
- the generated split manifest reports the expected groups and
  classes; and
- an explicit audit confirms that no group crosses partitions.
