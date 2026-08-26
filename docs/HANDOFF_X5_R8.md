# X5-R8 C5 runtime-safety correction gate

X5-R8 is a source-only, append-only correction from published X6-R0. It does
not alter X5-R6 execution, X5-R7's accepted receipt, or any accepted raw tree.
The X5-R6 C5 tree and X5-R7 receipt remain observationally valid historical
records, but are non-authoritative for crash-safety and complete raw-chain
receipt claims.

The new future lifecycle writes a planned-action journal before the approved
attached-prefix-list deny command is attempted. It keeps planned, attempted,
command-accepted/rejected, mutation-effective/not-effective, restored and
failed states distinct. A standalone process reads only the durable intent and
journal, validates the approved action identity, reconstructs the inverse
command, and supports safe idempotent replay after a partial mutation.

Source-only checks no longer require ignored `data/raw` evidence. Materialized
receipt verification remains required whenever the archived trees exist or is
explicitly requested.

Next: `X5_R9_C5_RUNTIME_SAFETY_REVALIDATION`. X6-R1 and P9-R2 remain paused.
