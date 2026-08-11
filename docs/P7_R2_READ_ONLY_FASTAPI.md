# P7-R2 Read-Only FastAPI Implementation

Date: 2026-08-11

Status: IMPLEMENTED AND TEST-VERIFIED

## Purpose

P7-R2 places the frozen P7-R0 HTTP contract over the verified immutable
P7-R1 projection. It is a presentation transport only. It does not run
Rule-based, Machine Learning, or Hybrid diagnosis and does not create or
change an experimental result.

## Runtime architecture

`src/phase7/api.py` builds one FastAPI application with exactly these
operations:

- `GET /api/v1/health`;
- `GET /api/v1/overview`;
- `GET /api/v1/comparison`;
- `GET /api/v1/cases`;
- `GET /api/v1/cases/{input_id}`; and
- `GET /api/v1/provenance`.

FastAPI's `/docs`, `/redoc`, and `/openapi.json` endpoints are disabled.
The canonical API description remains the Git-tracked P7-R0 OpenAPI 3.1
contract. No additional application route, generic artifact route, file
download, inference route, mutation route, or remediation route exists.

`src/phase7/server.py` starts Uvicorn on `127.0.0.1:8000` with reload
disabled. The entry point has no remote-host option. This is a local
bachelor-project presentation service, not a production deployment.

## Startup and fail-closed behavior

The accepted artifact catalog is loaded once in the ASGI lifespan. A
successful load stores one deep-immutable `ProjectionLayer` in
application state. All later requests project from that object and do
not reread JSON/JSONL files.

If a required source is missing, startup records
`ARTIFACT_SET_UNAVAILABLE`; if bytes, size, references, or accepted
semantics drift, it records `ARTIFACT_INTEGRITY_FAILED`. The process can
then answer health and other API requests only with the corresponding
`503` envelope. An unexpected loader error becomes a path-free
`500 INTERNAL_ERROR`; local paths and tracebacks are not returned.

## Response contract

Successful responses contain:

- `schema_version: 1`;
- `data`: the immutable P7-R1 projection; and
- `meta`: contract identity, `read_only: true`, and the accepted
  report-only source role.

Framework validation is normalized so an invalid enum, empty required
query, invalid integer, page outside the frozen range, or cross-filter
violation returns `400 INVALID_QUERY` rather than FastAPI's default
validation response. An unknown in-memory case ID returns
`404 CASE_NOT_FOUND`. Mutating HTTP methods return the frozen
`405 METHOD_NOT_ALLOWED` envelope.

All six success families and the error family are validated in tests
against `contracts/api/p7_readonly_api_v1.openapi.yml`.

## Dependencies and cost

FastAPI, Starlette, and Uvicorn are local open-source runtime
dependencies. HTTPX is test-only. No paid API, cloud service, database,
telemetry service, external asset host, React/Node build, or new dataset
is required.

## Verification

P7-R2 adds 32 tests covering:

- the exact six-route `GET` surface and disabled generated docs;
- all success envelopes and OpenAPI response schemas;
- the three accepted comparison scopes;
- deterministic filtering, pagination, and case joins;
- framework and projection query normalization;
- unknown and traversal-like case identifiers;
- rejection of `POST`, `PUT`, `PATCH`, and `DELETE`;
- missing, drifted, and unexpected startup failures;
- one catalog load for multiple requests;
- Uvicorn's fixed local bind and disabled reload; and
- a full API exercise with the estimator absent and all 15 source
  hashes unchanged.

Final verification:

- P7-R2 tests: 32/32;
- combined P7-R0, P7-R1, and P7-R2 tests: 65/65;
- targeted Phase 6 regression: 185/185; and
- complete regression suite: 493/493.

The API was exercised through FastAPI's ASGI test client. No persistent
server was left running, no Containerlab topology was started, and no
accepted runtime artifact was modified.

## Boundary and next step

P7-R2 does not implement the Dashboard. P7-R3 may add only static
same-origin HTML/CSS/JavaScript for the four frozen views: overview,
method comparison, case explorer, and provenance/limitations. It must
consume the six accepted routes without changing their semantics.
