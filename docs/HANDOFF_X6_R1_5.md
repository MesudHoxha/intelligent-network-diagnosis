# X6-R1.5 handoff

The prospective production entrypoint is
`python -m src.orchestration.x6_r1_5_production_path`. Standalone
classification, ownership-scoped restoration/cleanup, and read-only replay use
`python -m src.orchestration.x6_r1_5_recovery`.

Neither command is authorized by this source-only successor. A future runtime
review must first accept and publish the exact source, then freshly confirm the
source/tree/files, accepted image ID, tools and loaded module, topology,
absence of conflicting resources, output root, consumption ledger, current
boot, and authorization validity. It must prepare a separate one-attempt
authorization bound to the eventual commit and exact frozen manifest.

The runtime attempt, if later authorized, must execute B01-B10 as validation
only, apply the exact single owned F1 mutation, execute F01-F03, restore exact
healthy controls, observe cooldown, execute R01-R03, clean owned resources,
terminalize durably, and pass independent replay. Fault effectiveness,
diagnosis, restoration, cleanup, and verification remain separate results.
Scientific acceptance requires all governing criteria and is not established
by source-only verification.

The next step is review of the finalized R1.5 source and its durable
verification evidence. Do not issue authorization or execute runtime work from
this handoff.

Review must confirm that the materialized verifier compares independently
rebuilt fault effectiveness, Evidence v4, Feature Vector v2, and diagnosis to
the persisted artifacts, and that interrupted terminal paths reconstruct any
claimed owned cleanup. A cleanup-failed classification is evidence of failure,
not evidence that cleanup completed.
