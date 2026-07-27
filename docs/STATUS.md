# STATUS

## Current phase

04.5 — First controlled fault injection

## Completed

- Selected networking + AI/ML direction
- Defined the hybrid diagnosis concept
- Defined the preliminary research problem and objectives
- Created the preliminary fault taxonomy
- Designed the laboratory architecture
- Designed the first proof of concept
- Installed and tested Ubuntu 24.04 on WSL2
- Confirmed Docker client/server communication
- Confirmed Git and Python availability

## Active

- Install Containerlab in WSL2
- Create the physical repository
- Create central project documents
- Prepare the first Containerlab topology

## Open issues

- Final FRRouting container image
- Final topology syntax
- Detailed experiment manifest schema
- Final set of pilot classes

## Next milestone

Deploy and manually validate TOP-01:
HostA -- R1 -- R2 -- HostB

## Latest verified milestone

- TOP-01 baseline validated with 9/9 checks
- End-to-end traceroute verified
- First missing-route fault scenario implemented
- Ground truth and injection metadata generated

## Milestone — PoC-A completed

The first end-to-end controlled diagnostic experiment has been
implemented and tested successfully.

Scenario:
- C1_MISSING_STATIC_ROUTE

Verified pipeline:
- Baseline validation
- Controlled fault injection
- Ground-truth recording
- Evidence collection
- Rule-based diagnosis
- Automatic evaluation
- Fault restoration
- Post-restoration baseline validation

Verified result:
- Experiment status: COMPLETED
- Rule-based exact match: true
- Baseline restored: true

Important limitation:
This result validates the technical pipeline for one controlled
scenario. It is not yet a general experimental result about the
performance of the diagnostic system.
