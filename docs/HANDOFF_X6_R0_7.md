# X6-R0.7 NetEm runtime-prerequisite handoff

X6-R0.7 records the bounded prerequisite recovery after the X6-R1 mutation
journal's first NetEm command was rejected with `Specified qdisc kind is
unknown.` The failed X6-R1 tree remains durable, diagnostic, and
non-authoritative: no fault window, Evidence v4, or diagnosis exists.

The operator proved that WSL kernel `6.18.33.2-microsoft-standard-WSL2`
provides `CONFIG_NET_SCH_NETEM=m`, and that `sudo modprobe sch_netem` loads a
vermagic-compatible module. The frozen `ind-linux:0.1` image
`sha256:66392daabae6054416fba5043f312bfc464bcc18246956867870e4953847ff5c`
uses iproute2 `6.1.0-1ubuntu6.4`; a disposable `--network none`/`NET_ADMIN`
smoke installed the exact frozen NetEm `10:` and pfifo `20:` chain and restored
`noqueue 0:`. No image, topology, qdisc command, parameter, threshold, or
scientific claim changed.

After a WSL restart, the operator must run `sudo modprobe sch_netem` before a
future X6-R1 pre-baseline validator may accept the environment. The scientific
runner must only verify and record the prerequisite; it must never load a host
kernel module. One replacement X6-R1 pilot is authorized only after X6-R0.7
is published. X6-R1, F2--F4, and P9-R2 remain paused now.
