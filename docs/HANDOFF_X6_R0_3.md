# X6-R0.3 F1 pre-runtime validation correction

X6-R0.3 is source-only and append-only after published X6-R0.2. The prior gate
and all five bindings remain unchanged. Future X6 code must import the current
contract from `src/collection/x6_r0_3_pre_runtime_validation.py`.

The exact probe remains `LC_ALL=C /usr/bin/ping -n -i 0.2 -c 50 -W 1 -s 56
<destination>`. Return code zero accepts complete 50-packet runs with 1--50
unique replies; return code one accepts only a complete 50/0, 100-percent-loss
chain. All observations still require consistent summaries and reply records.

Before any X6-R1 mutation, build the unchanged threshold manifest from ten
baseline windows for every numeric X1 feature, run the independent X6-R0.3
semantic validator, freeze canonical bytes, and only then mutate. Schema plus
hash is insufficient. The runtime pilot must still verify NetEm `10:` versus
child pfifo `20:` behavior and the conditional F1 predicates.

X5 authority is unchanged and no evidence was reopened. F3 and F4 wait for
X6-R3 and X6-R4. P9-R2 remains paused. The exact next milestone is
`X6_R1_PACKET_LOSS`, limited to source implementation and its controlled pilot.
