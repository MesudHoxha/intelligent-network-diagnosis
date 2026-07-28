# DECISIONS

## D-001 — Domain

Decision: Combine computer networking with AI/ML.
Status: Approved.

## D-002 — Main problem

Decision: Diagnose and explain computer-network problems.
Status: Approved.

## D-003 — Methodology

Decision: Compare rule-based, Machine Learning, and hybrid approaches.
Status: Approved.

## D-004 — Budget

Decision: Use zero-budget or minimal-budget tools. No paid dependency
is mandatory.
Status: Approved.

## D-005 — Execution model

Decision: Prefer local execution and open-source technologies.
Status: Approved.

## D-006 — Ambition level

Decision: Develop an ambitious bachelor project incrementally, with a
working end-to-end baseline before advanced extensions.
Status: Approved.

## D-007 — Remediation

Decision: The base system diagnoses and recommends actions but does
not automatically modify network configurations.
Status: Approved.

## D-008 — Laboratory platform

Decision: Use Ubuntu on WSL2, Docker, Containerlab, Linux containers,
and FRRouting as the primary laboratory platform.
Status: Technically confirmed.

## D-009 — Dataset origin

Decision: Generate the dataset from controlled virtual-laboratory
experiments rather than manually invented rows.
Status: Approved.

## D-010 — Experimental scope

Decision: Include single faults, missing evidence, unseen variants,
and a controlled subset of multiple-fault scenarios.
Status: Approved.

## D-034 — Dynamic routing

Decision: Use OSPF as the first dynamic routing protocol. BGP remains
optional.
Status: Proposed.

## D-037 — First proof of concept

Decision: Use HostA--R1--R2--HostB with a missing static route as the
first end-to-end experiment.
Status: Approved for implementation.

## D-040 — Normal class

Decision: Include valid no-fault experiments in the dataset.
Status: Approved.

## D-041 — Missing evidence

Decision: Distinguish true, false, and unavailable evidence.
Status: Approved.

## D-042 — Dataset splitting

Decision: Split datasets by scenario or topology groups rather than
only random row-level splitting.
Status: Approved.

## D-043 — Main development environment

Decision: Use Ubuntu 24.04 under WSL2 rather than the existing
VirtualBox Ubuntu VM.
Status: Confirmed and tested.

## D-044 — PoC-A completion

Decision: The first end-to-end proof of concept is accepted as
technically complete.

Verified scenario:
- Missing static route on R1 toward the HostB network

Verified components:
- Baseline validator
- Fault injector
- Evidence collector
- Rule-based engine
- Evaluator
- Experiment runner
- Automatic restoration

Status: Implemented and tested.

Limitation:
The result applies only to the implemented controlled scenario and
must not be interpreted as general model or system performance.

## D-045 — PoC-B completion

Decision: Accept C2_WRONG_NEXT_HOP as the second end-to-end
controlled proof of concept while preserving the verified
behavior of C1_MISSING_STATIC_ROUTE.

Verified C2 behavior:

- R1's correct next-hop is replaced with 10.10.12.254.
- HostB becomes unreachable during the injected fault.
- The collector identifies the configured next-hop.
- The collector determines that this next-hop is unreachable.
- Rule R_ROUTING_002 diagnoses wrong_next_hop.
- Automatic evaluation reports exact_match: true.
- Restoration returns TOP-01 to its 9/9 baseline.
- C1 continues to match R_ROUTING_001 after the extension.

Status: Implemented and tested.

Limitation:
The result covers two deterministic controlled routing scenarios.
It is not evidence of general system or model performance.

## D-046 — Static-routing evidence

Decision: For the current static-routing scenarios, collect route
presence, parse the configured next-hop, and test that next-hop
through an active reachability probe.

The neighbor table from `ip neigh` is not mandatory at this stage.
It may be added later as complementary evidence if another
scenario requires it.

Status: Implemented and tested for TOP-01 C1 and C2.

## D-047 — Ground-truth isolation

Decision: Evidence collection and diagnostic methods must not
read ground-truth data. Ground truth may be used by the evaluator
only after a diagnosis has been produced.

Status: Confirmed for the current Collector and Rule Engine
through source audit.
