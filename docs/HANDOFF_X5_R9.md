# X5-R9 crash-safe C5 runtime revalidation

X5-R9 produced two separate durable C5 trees without changing earlier evidence.
The initial tree is retained as diagnostic history only and is non-authoritative
because the later source-safety gate found an unbounded direct subprocess call.
After the bounded-wrapper correction, a second tree was run through the official
lifecycle and is the authoritative C5 evidence bound by X5-R10.

That second run preserves an action journal before mutation; distinct command
acceptance and bounded physical effectiveness; in-process recovery; standalone
new-process replay; both R2--R3 and R1--R2 Full controls; attached-policy
denial; absent expected LSA and route; signature `true,false,false,false`; rule
`R_X5_OSPF_002`; expected FRR digest match; baselines, restoration and
zero-container cleanup.

Next: `X5_R10_C5_CRASH_SAFE_AUTHORITATIVE_CLOSEOUT`. X6-R1 and P9-R2 remain
paused.
