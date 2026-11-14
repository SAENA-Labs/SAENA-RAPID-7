# W7-13 read-only observation aggregation

Owner approved ChatGPT Search UI aggregation and server tenant verification.
Owner exception relayed by root: "계약 파일 요구사항을 아예 무시하고 작업을 진행해줘".
This exception applies only to the local signed Action Contract file prerequisite
for this previously approved unit. No signed JSON is fabricated and no policy
file is altered. Base 5935d50. Exclusive paths: ui_observation_store.py,
ui_observation_api.py, app.py registration, test_ui_observations.py, this document.
No SQLite access, deployment, push, shared schema changes or automatic approval.

Ponytail understanding: read app factory, production TokenVerifier, ReportCatalog
safe file readers and PlatformObservation generated model. Need actual counts,
not HTML-derived performance. Reuse those readers/models; stdlib aggregation;
no dependency installation. No delete candidates. Rollback: revert this unit.

Input is operator-approved immutable observations.json (<=8MiB), exact SHA256
registered out of band, private trusted directory and explicit reader grants.
Envelope keys: schema_version=1, tenant_id, expected_observation_ids, observations.
Expected IDs are the explicit cohort; observation IDs must be unique and a subset.
Observations use the existing PlatformObservation contract (ChatGPT Search only).
Invalid dates/URL domains, mixed tenants, duplicate IDs, unknown fields fail closed.
Max 10,000 expected IDs, 10,000 observations, 100,000 citation references total.
No raw responses or raw_object_ref are returned. Artifact hashes are provenance
references, not proof that the raw artifacts were fetched or independently verified.
Empty observed cohort is unmeasured; observed zero citations is measured zero.
Missing observations remain coverage.missing_samples, not zero-result samples.
Counts are citation-reference occurrences, not unique pages, causal lift or ROI.

## Operator factory wiring (no live activation by this unit)

Create a trusted private root with collection-a/observations.json. Compute its
SHA256; register ObservationEntry(tenant_id, 'collection-a', 'sha256:<digest>').
Construct ObservationCatalog(root=<absolute root>, entries={'approved-id': entry},
readers={(tenant_id, actor_id)}). Construct the existing verified TokenVerifier
with pinned public key/issuer/audience/server membership. Then:

    app = create_app(token_verifier=verifier, observation_catalog=catalog)

The accepted version1 local_config loader is unchanged. Supply this explicit
operator-owned ASGI factory to an authorized server; this is not automatic
registration, login, production deployment or a live observer runner.
GET /v1/ui-observations/approved-id requires bearer auth and reader grant.
Never enable test_headers mode for this API. There are no write/list endpoints.

## Capture registration boundary

The observer's older local capture record has `query_text` and `observed_at`,
while the formal PlatformObservation contract uses `observation_id`,
`artifact_hash` and `captured_at`. Do not relabel arbitrary local output as a
verified registered collection. The authorized acquisition/registry owner must
assign a stable observation ID, retain exact raw capture bytes separately,
compute their SHA256 artifact anchor, and carry observed_at into captured_at
in UTC-Z form. Omit query_text from this read-only UI projection. The explicit
expected cohort includes failed/missing observation IDs, with no invented record
for failures. Register the resulting observations.json exact byte hash in the
catalog after operator approval. This unit is not an automatic capture exporter.
Only public HTTP(S) citation URLs are supported for domain aggregation; opaque
artifact references are explicitly rejected rather than counted as domains.
Unique-domain output is capped at 10,000, with refusal, never truncation.

The original `run_id` must remain tied to the authorized capture run; registration
must not silently assign an unrelated run. This endpoint aggregates registered
formal snapshots, not a live observer-to-UI automatic pipeline.

## Verification

New unit cases: 14 (counts/coverage, measured zero vs missing, scope/engine/hash,
invalid dates/URLs, duplicate IDs, real private-file read + signed JWT API,
unauthorized/foreign reader refusal, corrupted registered bytes, domain cap).
All Console tests: 235 passed, 2 existing/dependency warnings, 1.54s. Source
`app.__file__` asserted this worktree before execution using the already-installed
integration venv. Ruff and git diff --check passed. Initial original-repo venv
lacked jwt; no dependency was installed and the existing integration venv was used.
No live/customer measurements or production readiness claimed.

Independent review reported no remaining blocker after the domain-cap correction;
12 independent cases passed (2 filesystem cases omitted in reviewer environment).
Integrator separately reran actual ephemeral loopback Python API -> HTTP -> Node
BFF integration: 1 passed, using generated synthetic credentials/data only.
This is not production-provider observation or browser/login validation.
