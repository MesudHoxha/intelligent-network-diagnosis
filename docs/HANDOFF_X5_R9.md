# X5-R9 crash-safe C5 runtime revalidation

X5-R9 will create a new durable C5 tree under `data/raw/x5_r9` without changing
any earlier X5 evidence. The first X5-R9 tree is retained as diagnostic history
only and is non-authoritative for acceptance because the subsequent source gate
identified an unbounded direct subprocess call. Its action journal is durable before the attached
prefix-list denial is attempted. It separately records command acceptance,
bounded physical effectiveness, in-process recovery, and a new-process
standalone recovery replay.

The next official run must have both R2--R3 and R1--R2 adjacencies Full,
attached-policy denial, absent expected LSA and route, the exact
`true,false,false,false` signature, and `R_X5_OSPF_002`. It must record the
expected FRR repository digest, baseline before/after and zero-container cleanup.

Next: `X5_R10_C5_CRASH_SAFE_AUTHORITATIVE_CLOSEOUT`. X6-R1 and P9-R2 remain
paused.
