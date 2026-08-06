# P6-R2 Evidence v3 Collector

Date: 2026-08-06

Status: IMPLEMENTED AND SYNTHETICALLY VERIFIED

## 1. Scope

P6-R2 implements the raw measurement boundary required by Evidence v3.
It does not run a network laboratory, inject a fault, build Dataset Row
v3, change a diagnosis method, or claim that a frozen class signature
has been observed.

The implementation is intentionally separate from
`src/collection/evidence_collector.py`. The historical Experiment
Runner still invokes the unchanged Evidence v2 collector, and Dataset
Row v2 remains the runtime default.

The new entry point is:

```text
collect_evidence_v3(output_directory, observation_profile_v2)
```

It accepts no ground truth, scenario label, fault type, expected
signature, split, prediction, evaluation result, or metric.

## 2. Bounded probes

The collector derives the ten frozen features from the following raw
measurements.

| Feature | Container role | Command or source |
| --- | --- | --- |
| `source_expected_gateway_reachable` | source | `ping -c 2 -W 1 EXPECTED_GATEWAY` |
| `source_default_gateway_matches_expected` | source | `ip -j route show default` |
| `destination_reachable` | source | `ping -c 2 -W 1 DESTINATION` |
| `route_to_destination_exists_on_observer` | observer | `ip -j route show exact DESTINATION_PREFIX` |
| `route_next_hop_matches_expected` | observer | derived from the same exact route output |
| `route_next_hop_reachable_from_observer` | observer | conditional ping of the parsed installed next-hop |
| `expected_next_hop_reachable_from_observer` | observer | separate ping of the expected next-hop |
| `observer_egress_interface_oper_up` | observer | `ip -j link show dev EGRESS_INTERFACE` |
| `destination_reachable_from_transit` | transit | `ping -c 2 -W 1 DESTINATION` |
| `flow_blocked_by_policy` | observer | `iptables -w 2 -t filter -S FORWARD` |

The installed and expected next-hop pings are distinct commands even
when both addresses are equal. This preserves independent provenance
and lets a wrong installed next-hop be tested without losing the health
measurement for the expected next-hop.

## 3. Raw artifact and persistence contract

Every executed probe is written under `raw/v3` before the parsed
Evidence v3 artifact is created. A raw artifact contains exactly the
probe identity, container, full Docker command, return code, stdout,
stderr, and UTC timestamp.

Files are encoded as sorted, indented UTF-8 JSON with a trailing
newline. They are written to a temporary file, flushed, fsynced, and
atomically renamed. The SHA-256 in Evidence v3 is calculated over
those exact persisted bytes.

Evidence is written atomically to `parsed/evidence.json`. Collector
status is written atomically to `collector_status.json` only after the
Evidence v3 semantic validator passes.

The collector refuses to start if `raw/v3`, `parsed/evidence.json`, or
`collector_status.json` already exists. A retry therefore requires a
new experiment directory and cannot overwrite an earlier audit trail.

## 4. Availability and parsing semantics

### Ping

- return code 0: observed true;
- return code 1: observed false; and
- any other return code: collection_unavailable.

### Installed default gateway

One valid default route with one IPv4 gateway is observed and compared
with the expected gateway. An empty route list is observed as no
installed gateway and therefore a false agreement. Invalid JSON,
multiple defaults, or an invalid gateway is collection_unavailable.

### Observer route and installed next-hop

An empty exact-route list is an observed absent route. Only this state
makes route next-hop agreement and installed-next-hop reachability
structurally_unavailable, with no raw artifact claimed for those two
non-applicable features.

A command failure, invalid JSON, multiple matching routes, an invalid
gateway, or a present route without the required gateway is a
collection failure. It must not be converted to missing_static_route.
The route-existence, next-hop-agreement, and installed-next-hop-
reachability features are then collection_unavailable and bind the
failed route artifact.

### Interface state

The exact selected interface must produce one JSON object. Only
operstate UP and DOWN are accepted and normalized to `up` and `down`.
Missing, ambiguous, or other state is collection_unavailable rather
than an invented boolean.

### Forwarding policy

Policy inspection is frozen to iptables/filter/FORWARD. A flow is
blocked only when exactly one rule:

- appends to FORWARD;
- has the required P6 tag prefix;
- matches the exact source and destination host addresses;
- matches the exact protocol;
- matches both ports for TCP or UDP; and
- jumps to DROP.

A tagged rule for another selector is not a block for the observed
flow. Duplicate exact matches, malformed output, ambiguous options, or
a command failure become collection_unavailable. This fail-closed
parser avoids reporting a healthy policy state when inspection is not
reliable.

## 5. Verification

P6-R2 verification passed:

- 22 new collector v3 tests;
- 4 accepted collector v2 tests in the targeted boundary;
- 26/26 targeted tests total;
- 338/338 complete regression tests;
- healthy Evidence v3 with ten observed features;
- synthetic frozen signatures for missing route, wrong next-hop,
  wrong default gateway, interface down, and ACL block;
- structural-versus-collection-unavailable negative tests;
- command and parser failure-artifact tests;
- exact raw-file SHA-256 verification;
- policy selector, duplicate-rule, and TCP-port tests;
- existing-output protection; and
- no Evidence v2 collector regression.

The isolated runtime emitted 21 scikit-learn deprecation warnings from
the accepted P4 tests. They are unrelated to P6-R2 and non-blocking.

No Containerlab command ran. No real Evidence v3 artifact, Dataset Row
v3, fault injection, rule diagnosis, model, prediction, or metric was
created.

## 6. Acceptance boundary and next gate

P6-R2 accepts implementation behavior only. It does not prove:

- that the current laboratory image contains iptables;
- that real `ip -j` output matches the synthetic fixtures in every
  planned context;
- that the selected interface reports UP/DOWN as expected;
- that a real healthy topology produces ten observed features; or
- that any fault injector or expected class signature works.

P6-R3 must therefore create a reviewed Observation Profile v2 binding
for one existing healthy context, verify all required open-source tools,
run only the normal Evidence v3 path, audit every raw hash, and preserve
the v2 regression path. It must stop before new fault injection.
