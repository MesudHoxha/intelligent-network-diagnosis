# HANDOFF — P6-R2 Evidence v3 Collector

Date: 2026-08-06

Status: COMPLETED

## 1. What was completed

P6-R2 implemented and isolated-test verified the Evidence v3 collector
required by D-077 and D-078.

The milestone completed:

- a separate `collect_evidence_v3` entry point requiring Observation
  Profile v2;
- bounded source, observer, transit, route, interface, and policy
  probes;
- separate installed and expected next-hop reachability probes;
- fail-safe JSON and iptables parsing;
- exact tagged flow-block rule matching;
- observed, structurally unavailable, and collection-unavailable
  feature construction;
- atomic raw JSON, Evidence v3, and collector-status persistence;
- exact raw-artifact SHA-256 provenance;
- existing-output protection;
- a CLI that explicitly requires Observation Profile v2; and
- 22 new tests plus the four accepted collector v2 regression tests.

The targeted boundary passed 26/26 tests. The complete regression suite
passed 338/338 tests in the isolated verification environment.

## 2. What was decided

D-079 is approved and implemented.

An observed empty route is the only condition that creates structural
unavailability for installed-next-hop agreement and reachability. A
failed or ambiguous route probe creates collection unavailability and
retains a raw failure artifact.

Exact policy blocking requires one P6-tagged iptables DROP rule matching
the selected FORWARD chain, source, destination, protocol, and
applicable ports. Failed inspection and duplicate exact matches remain
unavailable; they are never reported as an unblocked flow.

The accepted Evidence v2 collector, historical Experiment Runner path,
and Dataset Row v2 runtime default remain unchanged. P6-R2 is an
implementation acceptance gate, not a laboratory-result gate.

## 3. Files created or changed

P6-R2 files are:

- docs/DECISIONS.md;
- docs/HANDOFF_P6_R2.md;
- docs/MASTER_CONTEXT.md;
- docs/P6_R2_EVIDENCE_COLLECTOR.md;
- docs/PHASE6_FAULT_TAXONOMY_PLAN.md;
- docs/ROADMAP.md;
- docs/STATUS.md;
- src/collection/evidence_collector_v3.py; and
- tests/unit/test_p6_r2_evidence_collector_v3.py.

Evidence v2 and v3 contracts and schemas, Dataset Row v1-v3 contracts,
the Evidence v2 collector, Experiment Runner, accepted datasets,
P3-P5 method artifacts, model, and hybrid policy were not changed.

## 4. Open issues

- Verify ping, iproute2 JSON, interface-state, and iptables behavior in
  the real local image.
- Add or confirm the open-source iptables dependency before ACL work.
- Bind one existing healthy topology to Observation Profile v2.
- Integrate an explicit Evidence v3 experiment path without changing
  historical v2 execution.
- Implement fail-stop wrong_default_gateway, interface_down, and
  acl_block injection and exact restoration only after the healthy
  runtime gate.
- Implement/review E01-E06 before the 72-row campaign.
- Keep Dataset Row v2 as default until the complete v3 runtime path is
  accepted.
- Keep masked validation/test generation and six-class method work
  outside the collector milestone.
- Define multi-label truth before any multiple-fault experiment.

## 5. Next step

Start P6-R3 — Healthy Evidence v3 Runtime and Toolchain Gate.

P6-R3 must:

- review one existing topology for Observation Profile v2 roles;
- verify required open-source commands in the laboratory image;
- add only the minimal image dependency if iptables is absent;
- run a normal, fault-free Evidence v3 collection;
- validate all ten observed healthy feature values;
- verify every raw artifact path and SHA-256;
- preserve the accepted Evidence v2 regression path;
- keep Dataset Row v2 as default until runtime integration is accepted;
- stop before any new fault injection; and
- produce no Phase 6 campaign, model, prediction, or metric.

## 6. Impact on central documents

- DECISIONS adds D-079 and the fail-safe collector boundary.
- MASTER_CONTEXT records the implemented collector without claiming a
  network result.
- P6_R2_EVIDENCE_COLLECTOR is the normative implementation document.
- PHASE6_FAULT_TAXONOMY_PLAN resolves the stale milestone sequence by
  inserting collector and healthy-runtime gates before injector work.
- ROADMAP closes P6-R2 and names P6-R3.
- STATUS records 26/26 targeted and 338/338 regression verification,
  with Containerlab and real Evidence v3 still absent.
