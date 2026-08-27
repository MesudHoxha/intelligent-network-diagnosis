# X6-R0.4 F1 runtime parameter freeze

Use `labs/topologies/x6_r1_packet_loss/runtime_context_v1.json` as the sole
runtime-parameter authority for X6-R1. The topology is `x6r1`, five
`ind-linux:0.1` nodes and four fixed `/30` links. Traffic runs from
`clab-x6r1-hosta` to `10.61.3.2`; mutate only `clab-x6r1-r2:eth2`.

The fault is random 10% NetEm loss with zero correlation and no deterministic
packet-position claim. Install root `netem 10:` limit 1000, then child
`pfifo 20:` at `10:1` limit 1000. Accept only exact baseline `noqueue 0:` with
no filters. Journal intent and PLANNED before the first command; recovery may
delete only the approved hierarchy and must return to exact noqueue.

Run one five-second warm-up, ten baseline, three fault and three restoration
windows. In each composite window, start the 20-second single-stream TCP iperf3
client at t=0 and the exact 50-packet ping at t=5; reject skew over 0.250
seconds. All windows are mandatory. Measure link speed directly and require
matching positive r2/r3 provenance; never assume nominal capacity.

Physical effectiveness requires exact qdisc state, available NetEm counters,
three valid ping windows and 6--25 aggregate drops out of 150. Child pfifo drops
must remain zero or the pilot is diagnostic/non-authoritative. Only after
independent effectiveness may predicates and `R_X6_PERFORMANCE_001` be
evaluated. A non-separating result is preserved and not rerun opportunistically.

X6-R0.4 itself is 0/10 and source-only. Next: `X6_R1_PACKET_LOSS` source plus
one controlled pilot. Do not begin F2--F4 or P9-R2.
