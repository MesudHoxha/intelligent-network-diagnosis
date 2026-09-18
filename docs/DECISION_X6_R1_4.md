# X6-R1.4 decisions

## D-X6-R1.4 — Prepare local-operator baseline-only authorization

R1.4 is an append-only source-only successor to published R1.3.9
(`2dde4972cd2228a38da7dee12a31506673e45b12`). It preserves every historical
file and keeps the ten historical runtime/scientific fields exactly false.

The local user/operator is the authorization issuer. The host account and
processes with that account's permissions are inside the trust boundary.
Canonical SHA-256 binds record content; it is not cryptographic issuer
authentication and cannot distinguish the user from another process with the
same privileges. This approved model requires no signature, MAC, key, or trust
anchor. Before any future concrete record is issued or used, the user must
review and explicitly approve its exact scope, authorization and run identities,
final committed source identity, output root, image identity, validity interval,
contract, and canonical digest.

The committed JSON is a non-executable template. It is deliberately outside the
concrete authorization schema and the production validator rejects it. A future
real authorization remains external and may be created only after the R1.4
execution commit exists, avoiding a self-referential commit binding.

The fixed-topology coordination lock may be acquired or created before
authorization consumption solely for mutual exclusion. It grants no authority
for deployment, traffic, measurement, network changes, cleanup, qualification,
or scientific work. Exclusive fsynced consumption still precedes the command
recorder and every lifecycle command.

R1.4 creates and consumes no real authorization and performs no runtime work.
