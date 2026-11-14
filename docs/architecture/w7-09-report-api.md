# W7-09 approved local read-only report API

Owner approval relayed 2026-11-14: "진행해" for the exact read-only report API
plan. Parent Integrator reassigned app.py and new report modules/tests from
completed W7-08 ownership. Base 05d7469 includes all prior approved units.
No protected schema, deployment, customer data or remote operations allowed.

Ponytail: reuse TokenVerifier/RequestActor and existing service error model;
existing CLI report/receipt bytes stay unchanged. Local boundary secret guard
copies existing pilot patterns by explicit repo convention (no cross-package
security guard dependency). Stdlib descriptors/hash/JSON suffice; no install.
No new UI, writer, discovery/listing, signing or network feature.

GET /v1/html-audit-reports/{report_id}. Server startup injects immutable catalog
(id -> tenant, relative directory, report and receipt SHA256) and explicit
(tenant, actor) read grants. Never select files from request paths/tenants.
Verified production auth required; reject enabling this route in header-test
mode. Authenticate -> grant -> catalog tenant match -> bounded secure read ->
hashes/schema/secret guard -> JSON with no-store/nosniff. Unknown/other tenant
IDs same404; no grant403; auth401; damaged artifacts503 without detail.
Only report.json <=8MiB and receipt.json <=64KiB, regular/single link, no
symlink path components, private/trusted owner dirs. Expected cohort <=1000,
findings <=4096, evidence/page/line/unknown/unmeasured retained. Known-secret
patterns applied to decoded keys/values. No file changes, URL fetch or raw HTML.

Trust: startup config and same-UID process trusted; catalog hashes establish
binding, not source truth, signing authority or actual citation measurement.
No hot reload, persistent account control, IdP, rate-limiting deployment or
customer-facing production validation in this unit. Synthetic TestClient only.

## Startup and data registration contract

The route is absent unless create_app(token_verifier=..., report_catalog=...)
is explicitly constructed. Header-test mode cannot enable it. Construct a
ReportCatalog(root=<canonical absolute approved runstore>, entries={report_id:
ReportEntry(tenant_id, relative_directory, report_sha256, receipt_sha256)},
readers={(tenant_id, actor_id)}). Values originate from trusted server startup,
not HTTP requests. Catalog/grants and entries are immutable defensive copies.
Choose SHA256 of exact approved report.json and receipt.json bytes; this is an
operator attestation of the selected local artifact, not a digital signature.
The report ID is an opaque 1..128 character alphanumeric/underscore/hyphen key.
It is not a path; no list endpoint or automatic registration is provided.

Reconstruct app configuration for changes; no writable registration API. The
route returns the report JSON structure unchanged after validation. Expected
pages include unmeasured pages; an all-unmeasured report is valid and never
converted to a successful observation. Existing report scope and limitations
must be retained. Receipt is validation input only, not separately exposed.

Trust/root constraints: walk root and relative directory with dirfds and
O_NOFOLLOW, trusted owner (root/current UID), no shared-writable ancestors
except root-owned sticky temporary ancestors; file owner trusted, no group/other
write, regular single-link files only. Parent path races by a malicious same-UID
process remain outside this local trust model. No protection against a trusted
operator registering fabricated source evidence is claimed.

JSON byte caps are 8 MiB report/64 KiB receipt; structural caps 1000 pages,
4096 total findings (1024 per page), 256 line references per finding, depth16,
100000 total key/value/container nodes. Hashes are checked before JSON parsing.
UTF-8 decode and decoded string re-encode reject escaped lone surrogates before
HTTP serialization. Secret pattern checking covers decoded keys and values,
not every possible password or unknown credential format. No raw HTML response.
All report-path responses including tenant middleware denials have no-store and
nosniff headers. There is no multiuser load, abuse/rate-limit or live deployment
validation; these are mandatory future production considerations.

## Review and tests

Reviewer found escaped lone-surrogate JSON could reach response serialization
outside the protected read error boundary, yielding500 instead of503. Fixed by
strict decoded string UTF-8 validation and moving serialization inside the error
boundary. Surrogate keys/values now produce generic503 with no-store/nosniff.
54 new cases passed in 0.44s, including real local HTML diagnostic/report producer
composition, two verified tenant identities and read grants, actor spoof denial,
unsafe files/paths, hash/schema/receipt/secret failures, node/depth exact limits,
0 measured pages preserved, and no mutation. Console+approval-flow 206 passed
in 1.41s; Ruff/diff checks passed. Full regression and independent final review
results are recorded below when finished. No signing key/customer input persisted.

Final independent review PASS: reviewer rechecked source and ran separate
memory-only surrogate-key/value, forced response-serialization failure503,
no-store/nosniff and depth/node boundary checks. Reviewer did not rerun the full
file/HTTP suite; those results above are implementer execution, not mislabeled
independent execution. Final full non-integration regression on this unit code:
6333 passed, 45 skipped, 453 deselected, 2 warnings in 115.32s. Skips remain 43 missing
prior contract tags and 2 missing Helm/kubeconform; excluded live/integration
coverage is NOT claimed complete. This is local functional/security regression,
not a production security certification. No external requests, remote push,
customer files or deployment, and no Hanes workspace/service changes.
