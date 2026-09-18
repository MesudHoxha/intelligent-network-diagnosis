# X6-R1.4 handoff

The prospective production entrypoint is
`python -m src.orchestration.x6_r1_4_production_path`; standalone recovery and
successful materialized replay use `python -m
src.orchestration.x6_r1_4_recovery`. Neither command is authorized by this
source release.

The repository template is never a production authorization. After a finalized
R1.4 commit exists, a separate external concrete record must be populated with
that commit/tree/file identity, presented to the user with every bound field and
its canonical SHA-256, and explicitly approved. A later separate instruction is
required for its one baseline-only attempt.

Before issuance, reconfirm clean source, inactive experiment state, ethtool,
loaded matching `sch_netem`, exact image ID and RepoDigests, and every other
accepted provenance prerequisite. R1.4 execution remains paused.
