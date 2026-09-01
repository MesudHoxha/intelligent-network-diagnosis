# X6-R1.3 baseline-stability and host-provenance method gate handoff

## Boundary

This append-only source-only gate follows X6-R1.2. It preserves the consumed
X6-R1 pilot as `DIAGNOSTIC_NON_AUTHORITATIVE`, `PILOT_CONSUMED`, and
`BASELINE_INVALID_AFTER`, with audit classification `C — INSUFFICIENT_EVIDENCE`.
It creates no accepted Evidence v4, Feature Vector v2, diagnosis, acceptance
manifest, scientific result, or additional pilot authority.

## What this gate defines

`x6_host_runtime_provenance_v1` requires static image/topology/tool and host
identity plus dynamic load, cgroup, process lifecycle, interface-counter,
timing, command-result, and clock observations. Every field has an owner,
source command, parser, unit, availability state, timestamp, raw provenance
path/hash, and fail-closed absence effect.

The prospective qualification is baseline-only: 20 calibration windows then
10 independent holdout windows, fixed ordering, no mutation, no selective
retry/removal, all raw observations retained, and no source-derived numeric
limit. Its only source-only decision is `INCONCLUSIVE`; any future runtime
authorization must be reviewed separately.

## Historical clarification

The prior measurements identify an unresolved provenance gap/failure mode.
Possible explanations include host scheduling, WSL variability, TCP transients,
warmup/recovery effects, methodology instability, and another environmental
factor. None is established as the cause; future raw evidence is required.
The historical NetEm provenance likewise does not prove an earlier unpreserved
WSL-kernel state.

## Next action

X6-R1.3.1 resolves the prospective cardinality decision without changing the
X6-R0.2 mathematics: C01--C10 construct the exact ten-value manifest;
C11--C20 only validate it; H01--H10 are independent holdout. It adds
fail-closed NetEm, tool, image, topology, Git and raw-command provenance.
This remains source-only and grants no runtime or scientific authority.

`X6_R1_4_BASELINE_ONLY_RUNTIME_AUTHORIZATION_REVIEW` is the next source-only
review. It must not authorize a new F1 pilot directly. F2--F4, X7, and P9-R2
remain paused.
