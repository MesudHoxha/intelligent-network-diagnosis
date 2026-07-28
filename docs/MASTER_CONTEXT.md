# MASTER CONTEXT

## Project

Intelligent Network Diagnosis

## Working title in Albanian

Zhvillimi i një sistemi hibrid inteligjent për diagnostikimin dhe
shpjegimin e problemeve në rrjetet kompjuterike

## Working title in English

Development of a Hybrid Intelligent System for Diagnosing and
Explaining Problems in Computer Networks

## Main objective

To design, implement, and evaluate a hybrid intelligent system that
combines expert rules and Machine Learning to diagnose selected
computer-network problems, identify likely root causes, explain the
supporting evidence, and recommend diagnostic actions.

## Required comparison

1. Rule-based diagnosis
2. Machine Learning diagnosis
3. Hybrid diagnosis

## Core principles

- Zero-budget or minimal-budget implementation
- Local execution
- Open-source tools
- Reproducible experiments
- No fabricated results
- Clear separation between proposed, implemented, and tested work
- Ground truth generated through controlled fault injection
- Diagnosis must include evidence and not only a class label

## Primary environment

- Windows 11
- Ubuntu 24.04 on WSL2
- Docker Engine running natively inside Ubuntu WSL2
- Containerlab
- Linux containers
- FRRouting
- Python

## Initial proof of concept

Topology:

HostA -- R1 -- R2 -- HostB

Initial fault:

Missing static route on R1 toward the destination network.

## Current scope

The architecture targets addressing, Layer 2/VLAN, routing, network
services, security policy, and performance problems. Implementation
will proceed incrementally.

## Out of scope for the base system

- Universal diagnosis of every network technology
- Production-network deployment
- Mandatory paid APIs, cloud services, software, or datasets
- Training large language models
- Autonomous configuration changes without administrator approval

## Current implemented baseline

The currently tested laboratory baseline is TOP-01:

HostA -- R1 -- R2 -- HostB

Implemented and tested controlled scenarios:

- C1_MISSING_STATIC_ROUTE
- C2_WRONG_NEXT_HOP

Current rule-based coverage:

- R_ROUTING_001 diagnoses a missing static route on R1.
- R_ROUTING_002 diagnoses an unreachable configured next-hop
  on the static route on R1.

The evidence collector currently records route presence, the
configured next-hop, and active next-hop reachability. Both
controlled scenarios have completed end-to-end with exact-match
evaluation and successful restoration of the 9/9 baseline.

The Machine Learning and hybrid diagnostic approaches have not
yet been implemented or evaluated.
