# Status — X6 R1.5.2 exploratory campaign source successor

Milestone: `X6_R1_5_2_SOURCE_ONLY_IMPLEMENTED_PENDING_ACCEPTANCE`

- Published predecessor: `babde86fd863d105b30262d205ced09995251515`
- Accepted contract: `2e6ea92cb329088c981f03fdebb4a206def53eb8a19321458e531b9641e0e9a3`
- Embedded campaign inventory: `c1ff4d276705936111b12c918cad7a387d44369859b828ca13c7e28a5dba2c2c`
- Historical authorization vector: `0/10_FALSE`
- Runtime campaign: not authorized and not executed
- Source-only acceptance: pending separate review
- Eight contract-compliance findings are addressed in the uncommitted successor; finalized-source focused, semantic, and required exhaustive verification must be reconciled before separate acceptance review.

Synthetic fixtures may exercise persistence, authorization consumption, fitting, and analysis only inside temporary test locations. They establish no runtime outcome or classifier validity.
The prospective NOT_RUN accounting extension is implemented source-only and remains pending separate acceptance. No real accounting action or runtime authority has been created or exercised.


## Original production CLI launcher-return correction

The supported slot invocation is now
python -m src.orchestration.x6_r1_5_2_launcher --campaign-root PATH --input PATH --authorization PATH --timeout-seconds FINITE_POSITIVE_BOUND.
The existing campaign CLI remains the inner lifecycle and read-only interface.
Its run-slot command requires the exclusive launcher start record and real child
registration before reservation. This grants no authority and creates no real run.

Receipts are outside the inner run inventory, at
<campaign_root>/launcher-receipts/<run_id>/. They preserve actual argv, source,
run/output/authorization identity, launcher and child process identity, timestamps,
direct observed child exit or signal status, streams and original run hashes.
A timeout-normalized124, launcher interruption, or missing terminal publication
is explicitly unknown, never inferred from the lifecycle or replay. Public slot
verification requires a known original exit and consistent child consumption
identity. inspect-launcher permits read-only examination of unknown status.
Recovery can append evidence but cannot rewrite the original bound snapshot.

The outer bound must be explicit and finite; it changes no inner command timeout,
five-second reference,0.250-second skew limit, measurement schedule or TTL.
The accepted bounded subprocess layer and published historical files are unchanged.
Synthetic copied snapshots are test input only, not execution evidence for copied
slots. Actual launcher/CLI integration tests use owned external substitutes.

Earlier full-suite receipts describe the preserved32-file candidate, not these
changed bytes. Final verification and separate acceptance remain pending; durable
correction evidence is external at
/home/mesud/x6-r1-5-2-source-verification/launcher-correction-v1/.
No runtime readiness, real authority, classifier validity or scientific acceptance
is established. Historical authorization remains0/10_FALSE.

Interrupted launcher signalling requires pinned process identity, live parent and exact command ownership; ambiguous ownership is recorded without a signal. A CONSUMED interruption before lifecycle entry retains its observed original exit and permits only the independently checked no-lifecycle terminal to be appended. No cleanup observations are fabricated. Earlier focused failures and their corrections remain preserved outside the repository.

The receipt wrapper_return_code is the accepted bounded capture layer result, not an observation of the outer launcher process exit. The child_return_code is the directly observed original CLI wait status; negative signal status may have a different outer Python exit encoding. Receipt verification enforces typed versions, numeric bounds, canonical string argv, original process/boot identity, and retained text streams for observed exits. Canonical decoding already rejects nonfinite JSON.
