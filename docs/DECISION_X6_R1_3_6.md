# X6-R1.3.6 decisions

## D-X6-R1.3.6 — Integrate the future production path without authorizing it

Retain every published R1.3.1--R1.3.5 file unchanged and append one
production-only integration boundary. The entrypoint accepts only a later R1.4
canonical authorization, independently derives source identity, consumes its
one attempt before any command, and constructs only repository-owned timing
and command adapters. Recovery validates authority, run, source, inventory and
ownership before cleanup. The historical ten-field vector remains false, the
authorization artifact remains absent, and no terminal may be `QUALIFIED`.

## D-X6-R1.3.6a — Frozen predecessor snapshot evaluation

A frozen predecessor gate is evaluated against the exact Git commit whose
bytes its plan bound. A successor separately binds its own versioned records.
This corrects evaluation context only and neither weakens nor rewrites R1.3.5.

## D-X6-R1.3.6b — Versioned successor documentation

Because R1.3.5 byte-binds the cumulative decision and status documents, later
successors must leave those shared files byte-identical to the bound commit and
record new decision/status material in versioned successor-owned documents.
