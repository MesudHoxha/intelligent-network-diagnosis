# P6-R3 Healthy Evidence v3 Runtime and Toolchain Gate

Date: 2026-08-06

Status: COMPLETED

## 1. Scope

P6-R3 verifies one real fault-free Evidence v3 path before any new
Phase 6 injector is implemented or executed. It accepts only:

- the minimal open-source laboratory toolchain;
- one reviewed TOP-01 Observation Profile v2 binding;
- the exact frozen healthy ten-feature signature;
- the exact nine raw-probe provenance bindings;
- pre- and post-collection baseline preservation; and
- complete regression compatibility.

It does not authorize a new fault, Dataset Row v3 export, the 72-row
campaign, model fitting, prediction, or metric calculation.

## 2. Runtime and topology binding

The laboratory used native Docker under Ubuntu 24.04 in WSL2 and
Containerlab 0.77.0. The existing ind-linux:0.1 image lacked iptables.
Before rebuild it was preserved locally as ind-linux:p6-r2-preflight.
The Dockerfile now installs the open-source iptables package alongside
iproute2 and iputils-ping. The rebuilt image reported:

- image ID:
  sha256:66392daabae6054416fba5043f312bfc464bcc18246956867870e4953847ff5c;
- ip: present;
- ping: present; and
- iptables: v1.8.10 using nf_tables.

The reviewed scenario is N0_NORMAL_OPERATION_P6_TOP01. Its Observation
Profile v2 binds:

- source: hosta, 10.10.1.10, expected gateway 10.10.1.1;
- destination: hostb, 10.10.2.10;
- route observer: r1;
- expected next-hop: 10.10.12.2;
- observer egress interface: eth2;
- transit: r2; and
- policy selector: iptables/filter/FORWARD for ICMP.

TOP-01 historically used specific data-plane routes rather than a
source default route. P6-R3 therefore uses a separate fail-stop
post-deploy script to add exactly one HostA default route through
10.10.1.1. It does not alter topology.clab.yml or the frozen G01
fingerprint.

## 3. Real gate execution

The accepted experiment is:

```text
p6_r3_healthy_top01-20260806T090542Z
```

Collector runtime return code was zero. The Evidence v3 artifact passed
its contract and the independent healthy verifier. All ten features
were observed:

| Feature | Healthy value |
| --- | --- |
| source_expected_gateway_reachable | true |
| source_default_gateway_matches_expected | true |
| destination_reachable | true |
| route_to_destination_exists_on_observer | true |
| route_next_hop_matches_expected | true |
| route_next_hop_reachable_from_observer | true |
| expected_next_hop_reachable_from_observer | true |
| observer_egress_interface_oper_up | true |
| destination_reachable_from_transit | true |
| flow_blocked_by_policy | false |

No feature was structurally unavailable or collection unavailable.
Nine raw JSON probes existed under raw/v3, completed with return code
zero, and matched every Evidence v3 SHA-256 binding.

The accepted top-level hashes are:

- Evidence v3:
  654cb717aa823091b6832d586b22503eb26f37aad81dc3e2f40f7d1f64c75ac2;
- collector status:
  d68b14f65b80f72ab7f0b8c7f3709b37b2f0a18165167ec3dd3593c914aed88d.

Generated runtime artifacts remain under data/raw and are excluded from
Git by the accepted repository policy. Their identity and verification
summary are recorded here and in STATUS, DECISIONS, and the P6-R3
HANDOFF.

## 4. Preservation and test results

TOP-01 baseline validation passed:

- before the Phase 6 binding: 13/13;
- after binding and before collection: 13/13; and
- after collection: 13/13.

The historical topology and G01 fingerprint remained byte-for-byte
unchanged. No fault was injected or restored. Containerlab cleanup
removed all four TOP-01 containers.

The targeted boundary passed 31/31 tests: 26 accepted collector tests
plus five P6-R3 profile, healthy-signature, provenance-tampering, and
status-drift tests. The complete regression suite passed 343/343. The
36 NumPy/joblib deprecation warnings remain known and non-blocking.

## 5. Accepted boundary

P6-R3 accepts:

- the minimal iptables image dependency;
- the reviewed Phase 6 TOP-01 profile and isolated setup;
- the independent healthy Evidence v3 verifier;
- the real no-fault signature and raw provenance;
- baseline preservation and cleanup; and
- no regression to accepted v2 behavior.

Dataset Row v2 remains the runtime default. Evidence v2, historical
Experiment Runner behavior, accepted P2-P5 datasets, model, reports,
and hybrid policy remain unchanged.

## 6. Limitations and next gate

One healthy TOP-01 execution is a runtime feasibility gate, not a fault
evaluation. It provides no evidence about:

- wrong_default_gateway, interface_down, or acl_block signatures;
- injector preconditions or restoration;
- other Phase 6 contexts or the future E06 topology;
- six-class separability;
- the 72-row campaign;
- ML or Hybrid performance; or
- production-network or real-world generalization.

P6-R4 must implement fail-stop injectors and rule signatures for the
three new single-fault classes and smoke each class in one reviewed
context. It must stop before the complete campaign and method work.
