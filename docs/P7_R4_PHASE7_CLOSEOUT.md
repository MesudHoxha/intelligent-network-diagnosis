# P7-R4 Phase 7 Closeout and Reproducible Local Handoff

Date: 2026-08-11

Status: CLOSED — LOCAL READ-ONLY INTERFACE ACCEPTED

## 1. Purpose and frozen boundary

P7-R4 closes Phase 7 after the P7-R0 contract, P7-R1 artifact
projection, P7-R2 local FastAPI transport, and P7-R3 static Dashboard
have all passed their acceptance gates. This milestone adds no runtime
feature. It records the reproducible operating procedure, final
acceptance commands, and archive/publication policy for the completed
local interface.

The accepted interface remains limited to:

- exactly six versioned data routes, all `GET`;
- exactly four Dashboard views and three static repository assets;
- the 15 SHA-256- and size-bound JSON/JSONL projection sources in
  `plans/phase7/P7_R1_ACCEPTED_ARTIFACT_CATALOG_V1.json`;
- one startup verification followed by immutable in-memory reads; and
- loopback-only Uvicorn at `127.0.0.1:8000` with reload disabled.

P7-R4 does not deserialize the estimator, execute Rule-based, ML, or
Hybrid diagnosis, run Containerlab, collect evidence, fit or select a
model or policy, calculate a metric, modify an accepted artifact, or
authorize a production or remote deployment.

## 2. Accepted Phase 7 inventory

| Milestone | Accepted result | Verification at closeout input |
| --- | --- | --- |
| P7-R0 | Read-only interface plan and OpenAPI 3.1 contract | 10 contract tests |
| P7-R1 | 15-source catalog, fail-closed loader, and immutable projections | 23 catalog/projection tests |
| P7-R2 | Six-route local FastAPI transport and normalized envelopes | 32 API tests |
| P7-R3 | Four-view same-origin static Dashboard | 10 Dashboard tests plus visual desktop/390 px checks |
| P7-R4 | Closeout, local operating procedure, and archive policy | 10 closeout tests |

The final combined Phase 7 suite contains 85 tests. The P6-R6
report-only result remains the only empirical source presented by the
interface. Display formatting does not create a new result.

## 3. Local prerequisites and readiness

Run from the repository root. The virtual environment must contain the
declared project and test dependencies. The 15 accepted projection
sources must be present at their catalog paths with their accepted byte
sizes and SHA-256 values. They are intentionally ignored by Git, so a
fresh source-only clone is expected to fail closed with `503` until the
separately preserved accepted projection bundle is restored.

The selected estimator is not a Dashboard dependency. Do not copy it
into a projection-only bundle and do not load it to start the interface.

Readiness can be checked without starting a server:

```bash
cd "$HOME/projects/intelligent-network-diagnosis"
source .venv/bin/activate

PYTHONDONTWRITEBYTECODE=1 python - <<'PY'
from pathlib import Path

from src.phase7.catalog import ArtifactCatalog
from src.phase7.projections import ProjectionLayer

root = Path.cwd()
catalog = ArtifactCatalog.load(repository_root=root)
projection = ProjectionLayer(catalog)
assert len(catalog.roots) == 4
assert len(catalog.artifacts_by_path) == 15
assert projection.health()["status"] == "READY"
assert projection.overview()["total_input_count"] == 120
print("phase7_readiness=PASS")
PY
```

This reads and verifies only the accepted catalog sources. It does not
read or deserialize the estimator and writes no runtime artifact.

## 4. Reproducible local start, smoke, and stop

Start the application from the repository root:

```bash
cd "$HOME/projects/intelligent-network-diagnosis"
source .venv/bin/activate
PYTHONDONTWRITEBYTECODE=1 python -m src.phase7.server
```

The expected listener is only `http://127.0.0.1:8000`. Open that URL in
a local browser. In a second terminal, verify the health envelope and
the Dashboard document:

```bash
curl --fail --silent http://127.0.0.1:8000/api/v1/health \
  | python -m json.tool
curl --fail --silent --output /dev/null \
  http://127.0.0.1:8000/
```

The health response must report `READY`. Stop the foreground server by
pressing `Ctrl+C` in its terminal. No Containerlab topology or separate
frontend process is required. Do not use `--reload`, `0.0.0.0`, a public
reverse proxy, or a remote bind; those modes are outside the accepted
Phase 7 boundary.

## 5. Final acceptance commands

The final acceptance sequence is:

```bash
cd "$HOME/projects/intelligent-network-diagnosis"
source .venv/bin/activate

python -m pytest -q \
  tests/unit/test_p7_r0_interface_contract.py \
  tests/unit/test_p7_r1_catalog.py \
  tests/unit/test_p7_r1_projections.py \
  tests/unit/test_p7_r2_api.py \
  tests/unit/test_p7_r3_dashboard.py \
  tests/unit/test_p7_r4_closeout.py

python -m pytest -q tests/unit/test_p6_*
python -m pytest -q
```

The accepted counts are 85/85 combined Phase 7 tests, 185/185 targeted
Phase 6 tests, and 513/513 full regression tests. The 48 known
NumPy/joblib deprecation warnings are not failures. Acceptance also
requires the 15 catalog sources to retain their hashes after all checks,
the estimator to remain unread and undeserialized, and the worktree to
contain only the intended tracked closeout files before commit.

## 6. Archive and publication policy

Phase 7 distinguishes two archives with different purposes.

### Public source archive

The public/repository archive contains only tracked source, tests,
contracts, plans, and documentation:

```bash
git archive --format=tar.gz \
  --output ../intelligent-network-diagnosis-phase7-source.tar.gz \
  HEAD
```

Because `git archive` uses the tracked tree, it excludes `.venv`, cache
directories, Containerlab state, editor output, generated datasets,
generated reports, model files, and the 15 ignored projection sources.
It is therefore a source archive, not a self-contained accepted-result
archive. Secrets, credentials, host configuration, and personal files
must never be added.

### Private accepted-projection archive

For reproducible local presentation, preserve a separate private bundle
containing exactly the 15 catalog-listed sources plus the tracked
catalog itself. The selected estimator, source development/test split,
unlisted runtime files, `.venv`, caches, and Containerlab state are not
part of this bundle.

```bash
P7_PRIVATE_ARCHIVE="$HOME/intelligent-network-diagnosis-p7-projections.tar.gz"
P7_FILE_LIST="$(mktemp)"

python - <<'PY' > "$P7_FILE_LIST"
import json
from pathlib import Path

catalog_path = Path("plans/phase7/P7_R1_ACCEPTED_ARTIFACT_CATALOG_V1.json")
catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
assert catalog["artifact_count"] == 15
print(catalog_path.as_posix())
for artifact in catalog["artifacts"]:
    print(artifact["path"])
PY

tar --create --gzip --file "$P7_PRIVATE_ARCHIVE" \
  --files-from "$P7_FILE_LIST"
sha256sum "$P7_PRIVATE_ARCHIVE" > "$P7_PRIVATE_ARCHIVE.sha256"
rm -- "$P7_FILE_LIST"
```

The private bundle contains 16 files: one tracked catalog plus 15
accepted sources. Preserve it with its SHA-256 sidecar. After restoring
it at the repository root, the P7-R1 loader remains the authoritative
integrity gate. The bundle is not a license to change, recompute, or
select results, and it should not be published automatically merely
because the source repository is published.

## 7. Final Phase 7 acceptance

Phase 7 is complete when the catalog loads, the temporary live-server
smoke returns the accepted health and Dashboard responses, all final
test gates pass, the server stops cleanly, the 15 sources remain
unchanged, and the closeout commit contains documentation and closeout
tests only.

The interface is a local read-only presentation of accepted controlled-
laboratory evidence. It is not a production NMS, remote diagnostic
service, real-time inference engine, automatic remediation system, or
claim of statistical superiority or real-world generalization.

The next milestone is P8-R0, a scope and evidence-completeness gate for
Phase 8. It must first audit the accepted experimental evidence and
thesis claims. It does not inherit authorization to reopen the consumed
E02/E06 report-only evaluation or to create new experiments merely
because Phase 7 has closed.
