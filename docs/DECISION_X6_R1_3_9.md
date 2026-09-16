# X6-R1.3.9 decisions

## D-X6-R1.3.9 — Bind cleanup pre-state and distinguish teardown absence

R1.3.9 is an append-only source-only correction over published R1.3.8
(`099b199f5b6bb72dd18060a3e0e168aa00a8178c`). It preserves every predecessor
file and changes no accepted topology, image, traffic, timing, cohort,
threshold, authorization, or scientific contract.

The active successor records each cleanup cycle as one contiguous group of
five host observations before cleanup, an owned-topology destroy action exactly
when owned containers are present, and five host observations afterward. The
independent verifier reconstructs those groups from bound raw commands, binds
them to the run and deployment identities, accepts a complete owned deployment
before normal successful cleanup, permits owned partial deployments on failure
and recovery paths, and requires the accepted clean host state afterward.

Server teardown first proves that the lifecycle-owned destination container is
executable and observes the exact `iperf3` process identity. Absence is accepted
only from a clean `pgrep -x iperf3` no-match result paired with the successful
container probe. A positively observed process requires bounded `pkill -x
iperf3` success and a second proved-absent observation. Failed teardown is
never converted to success by later cleanup.

The ping worker is reserved before its monotonic five-second deadline, avoiding
post-deadline thread-dispatch latency while retaining raw timestamp enforcement
and the unchanged 0.250-second startup-skew limit.

This correction creates no authorization and executes no runtime work. The
historical authorization vector remains exactly `0/10_FALSE`.
