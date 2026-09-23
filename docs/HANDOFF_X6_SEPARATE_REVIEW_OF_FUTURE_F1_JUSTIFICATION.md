# X6 future F1 justification review handoff

Status: `REVIEW_ONLY_NOT_ACCEPTED`

The append-only review proposal is
`plans/expansion/X6_SEPARATE_REVIEW_OF_FUTURE_F1_JUSTIFICATION_PROPOSAL_V1.json`
with SHA-256 `6c03445e0b4a851f7c1c484a891577407eeb2fbf8a22f967aa3b1ee05161d9eb`.
It is bound to published commit
`ff327c10e69e0f08a5c3586e169392667fe2d893`, its accepted baseline-only
freeze, and the original qualification and source-verification evidence.

The evidence supports a future append-only source implementation after explicit
acceptance of this proposal. It does not establish future-F1 applicability by
itself. The historical F1 runner must not be invoked directly: it regenerates
thresholds from runtime baseline windows, derives utilization over a different
elapsed interval, and does not provide raw monotonic command timestamps from
which the independent verifier can reconstruct that interval.

The proposed minimum correction is a versioned F1 successor that preserves all
published files, consumes the exact accepted manifest without rebuilding or
retuning it, treats ten pre-fault baseline windows as validation only, and uses
the R1.4.1 raw-observation interval for baseline, fault, and restoration. The
successor must keep baseline noqueue controls distinct from intentional fault
NetEm/pfifo controls, retain the exact effectiveness and diagnosis contracts,
and independently verify restoration, replay, terminalization, and owned
cleanup.

Open runtime values are intentionally unset: authorization ID, run ID, output
root, validity interval, execution commit, and fresh readiness observations.
The recorded qualified image has no RepoDigests, so a future attempt must match
the exact accepted image ID and other bound identity evidence. The missing
original baseline launcher return code remains an evidence limitation.

Central `MASTER_CONTEXT`, `DECISIONS`, and `STATUS` files are unchanged because
this is a pending review proposal. Historical authorization remains
`0/10_FALSE`; the baseline-only freeze scope, X5 authority, consumed-pilot
classification, and protected evidence remain unchanged.

The next step is explicit review and acceptance or rejection of the exact
proposal bytes. Acceptance would authorize only the described append-only
source implementation and source-only verification. It would not authorize a
runtime attempt, mutation, or scientific acceptance.
