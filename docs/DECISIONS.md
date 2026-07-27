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
