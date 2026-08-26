# X5-R6 corrected C5 operational-policy runtime revalidation

X5-R6 is an append-only runtime revalidation from published X5-R5. It creates
a new durable C5 tree under `data/raw/x5_r6`; no X5-R1 through X5-R5 evidence
or receipt is changed. R3 originates the expected connected prefix only through
the attached `redistribute connected route-map X5-R5-C5-EXPORT` mechanism.
The mutation adds sequence 1 denial to the attached target prefix list and
does not remove an OSPF `network` statement.

The lifecycle requires exact target/control neighbor identity, structured LSDB
and route JSON before absence is observed, raw configuration proof of the
attachment and denial, Feature Vector v2 validation at rule entry, bounded
state-based effectiveness, separate command acceptance/effectiveness records,
and recovery replay. The expected signature is `true,false,false,false`; the
only diagnosis is `R_X5_OSPF_002` for
`route_filtering_or_advertisement_problem`.

Next: `X5_R7_C5_CORRECTED_SUCCESSOR_CLOSEOUT`. X6 and P9-R2 remain paused.
