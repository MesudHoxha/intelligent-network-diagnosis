# P6-R4 New-Class Smoke Gate

Date: 2026-08-10

Status: VERIFIED AND ACCEPTED UNDER D-082

## 1. Scope

P6-R4 implements and smoke-verifies the three new Phase 6 single-fault
classes in one reviewed TOP-01 context:

- `wrong_default_gateway`;
- `interface_down`; and
- `acl_block`.

The gate covers injector preconditions, exact mutation verification,
Evidence v3 collection, Rule Engine v3 exact matching, exact
restoration, healthy Evidence v3 recovery, complete baseline recovery,
and cleanup. It does not create Dataset Row v3 records or execute the
six-context campaign.

## 2. Implementation boundary

The implementation adds three fail-stop injectors, shared Phase 6
mutation helpers, three reviewed Observation Profile v2 scenarios, a
bounded smoke runner, Rule Engine v3 signatures, fault-evidence
verification, and unit tests. Registry dispatch remains backwards
compatible with the accepted injectors.

The source-default-route profile is applied after TOP-01 deployment so
the accepted historical topology and G01 fingerprint remain unchanged.
The ACL mutation is one uniquely tagged iptables/filter/FORWARD DROP
rule matching the reviewed flow selector.

## 3. Runtime amendment lineage

The first interface runtime,
`p6_r4_new_class_smoke-20260810T114903Z`, proved that Linux removes both
routes bound to R1 `eth2` when the interface is set down. The second,
`p6_r4_interface_recovery_smoke-20260810T122212Z`, proved that the routes
cannot be recreated while the device remains down; both `onlink`
attempts returned code 2 with `Error: Nexthop device is not up.`

Both gates restored the exact interface, routes, healthy Evidence v3,
and 13/13 baseline before cleanup. They remain immutable diagnostic
evidence, not accepted class samples. D-081 amended only the expected
`interface_down` signature and restoration ordering.

## 4. Accepted smoke results

The accepted results combine:

- `wrong_default_gateway` from
  `p6_r4_new_class_smoke-20260810T114903Z`; and
- `interface_down` plus `acl_block` from
  `p6_r4_d081_amended_smoke-20260810T130119Z`.

| Gate | Result |
| --- | --- |
| New-class smokes | 3/3 verified |
| Injection status | 3/3 `FAULT_CONFIRMED` |
| Rule exact match | 3/3 |
| Restoration status | 3/3 `RESTORATION_CONFIRMED` |
| Restored healthy Evidence v3 | 3/3 verified |
| Fault raw artifacts | 26/26 SHA-256 bound |
| Fault-feature availability | 28 observed, 2 structural |
| Final TOP-01 baseline | 13/13 valid |
| Containers after cleanup | 0 |

The exact rules are `R_P6_ROUTING_003`, `R_P6_LINK_001`, and
`R_P6_POLICY_001`. The two structural values belong only to the D-081
installed-next-hop fields for `interface_down`.

The gate-summary SHA-256 is:

`d7d8dd30e0ad537c1a2897209c2a58285ba7fbe241653fa561649869e8c46a4b`

## 5. Verification

- targeted P6-R4 and D-081 tests: 46/46 passed;
- complete regression suite: 373/373 passed;
- amended and immutable boundaries: 11/11 passed;
- original D-077 and amended D-081 plan hashes: 2/2 present;
- previous stopped-runtime digests: 2/2 unchanged; and
- Dataset Row v3, campaign, model, prediction, and metric: absent.

The 36 regression warnings are existing scikit-learn/joblib NumPy 2.5
deprecations in P4-R1 tests. They are not P6-R4 failures.

## 6. Limitation and next gate

P6-R4 verifies feasibility, evidence signatures, rule separation, and
restoration for one controlled TOP-01 smoke per new class. It does not
prove complete six-class behavior across E01-E06, cross-topology
generalization, campaign completeness, missing-evidence robustness, ML
performance, Hybrid performance, or real-world diagnostic accuracy.

P6-R5 must implement or review every E01-E06 six-class bundle and then
execute the frozen 72-row clean campaign with the 36/12/24 whole-context
split. Model fitting and report-only evaluation remain later gates.
