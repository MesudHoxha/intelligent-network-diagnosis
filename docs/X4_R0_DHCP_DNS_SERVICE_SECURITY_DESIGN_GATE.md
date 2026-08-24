# X4-R0 — DHCP, DNS, and Service Security Design Gate

Status: ACCEPTED DESIGN ONLY — NO EMPIRICAL RUNTIME AUTHORIZED

X4-R0 starts the X4 track as an append-only contract boundary from accepted
X3-R5 commit `2a763c6c6cd44f984ce08331e20d3e03445a0037`. It hash-binds the
accepted X0/X1 contracts and X3-R5 source closeout/receipt, without
materializing private X3 evidence or changing any accepted X2/X3 source.

## Scope and release sequence

The six-node `X4_TOP_01_DHCP_DNS_SERVICE_SECURITY` design has a client,
service-segment switch, DHCP server, DNS server, application server and an
observer. Its independent flows are DHCP UDP/67, DNS UDP/53 and application
TCP/8080. The planned single-fault releases are DHCP Server Unavailable, DHCP
Pool Misconfiguration, DNS Service Down, Wrong DNS Record and Firewall Service
Block, followed by X4-R6 closeout.

The exact nine-feature baseline is all healthy service state with
`service_flow_blocked_by_policy=false`. The five fault signatures are complete
and disjoint: DHCP unavailable is false/false/false on DHCP reachability,
lease and scope; pool misconfiguration preserves reachability but is
true/false/false; DNS service down preserves IP reachability but has a failed
query, absent expected answer, stopped process and closed port; wrong DNS
record preserves service/query state but has an incorrect answer; and the
firewall slice preserves DHCP, DNS and service process state while the service
port is unavailable and direct policy evidence is true.

`service_state_collector:v1` owns the eight DHCP/DNS/service-state features;
`service_policy_state_collector:v1` owns only the policy feature. Both remain
X1 design-only metadata. Generic connectivity and active flow probes are
effectiveness controls, never a classifier.

## Safety and scientific boundary

Every future runtime slice requires a durable pre-mutation recovery intent,
atomic journal, best-effort and idempotent confirmed restoration, exact service
configuration restoration, baseline validation before/after, zero-container
cleanup, raw Evidence v4 hashes, collector provenance and a real E2E.

All ten runtime/scientific authorization flags are false in X4-R0. It performs
no deployment, mutation, collection, prediction, dataset/model/ML/Hybrid work,
metric, API change, report-only access or multiple-fault execution. It proves
only a design with disjoint planned signatures and does not establish fault
effectiveness, diagnosis, accuracy, generalization or production readiness.

Frozen Phase 6–9, API v1, accepted X2/X3 sources/evidence and the P9-R1 pause
remain unchanged. Next release: X4-R1 DHCP Server Unavailable.
