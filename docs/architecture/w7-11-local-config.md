# W7-11 approved local configuration
Owner approval relayed by Integrator: "승인". Base 790402d.
Scope: local version1 config, single tenant, pinned public RSA key, server
membership/read grants/catalog, check-only command and existing ASGI factory.
No external IdP/network/issuance/new HTTP API/shared schema/deploy. Hanes priority.
Assigned paths local_config.py, test_local_config.py, this document only.

Ponytail before implementation: reuse TokenVerifier, ReportCatalog and their
bounded parser/file safety primitives; stdlib config/CLI, no new dependency.
Public key only, no secrets or implicit defaults. Existing authorization unchanged.
Configuration is trusted operator input, not a customer upload. Same-UID malicious
filesystem replacement is outside the threat model. All values validated;
unknown/duplicate keys, unsafe files, mixed tenants and unsupported versions fail.

Exact version1 keys: version, tenant_id, issuer, audience, public_key_file,
memberships, readers, report_root, reports, enable_viewer.
memberships maps subject to actor_id/tenant_id/roles; readers is actor ID list;
reports maps opaque report ID to relative_directory/report_sha256/receipt_sha256.
Config 1MiB, public key16KiB, memberships/readers/reports1000 each.
Tenant must match SAENA_TENANT_ID; no environment override. Key is relative to
config directory, report_root canonical absolute. No-follow paths, trusted owner,
no group/world writable files/directories (root sticky tmp exception), regular
single-link files only. Checks all report byte hashes and validation before app.
No token/password/private key in JSON; bounded parser secret-pattern defense.

Run with source/install environment configured:
python -m saena_forge_console.local_config --config /absolute/config.json --check
ASGI callable: saena_forge_console.local_config:create_local_app
Set SAENA_LOCAL_CONFIG and SAENA_TENANT_ID explicitly. Factory does not listen;
operator chooses server process only under separate execution authorization.
No login or token issuance. --check outputs only static counts/status, not
identities, source paths or secrets, and is not a health/availability guarantee.

## Verification
47 dedicated tests pass, including actual --check subprocess, generated offline
W5/W6 report -> loader -> signed-token API -> viewer shell, missing measurement,
configuration count caps, unknown/duplicate fields, malformed roles/grants,
wrong tenant/environment, symlink/hardlink/FIFO/permissions/size/private-key
rejection, corrupt artifact sanitized failure, and explicit viewer disabled.
Console + in-process approval-flow regression: 264 passed, 1 existing warning,
4.30s. Initial one test assertion used a nonexistent report key; corrected to
existing expected_page_count/measured_page_count, no production contract change.
Ruff and git diff --check pass. No real provider/customer/login/key issuance.

Independent critic PASS: source review plus separate memory-only normal-loader
check with network socket creation prohibited, seven invalid contracts and
duplicate JSON rejected. Critic's filesystem boundaries were mocked; actual
filesystem and subprocess tests are implementer results, not independent reruns.
No new blocking finding. Full regression recorded below when completed.

Final full non-integration regression: 6391 passed, 45 skipped, 453 deselected,
2 existing warnings in125.28s. Prior skips unchanged:43 missing contract release
tags,2 missing Helm/kubeconform. No excluded integration/provider claims.
One low-priority process, observed memory free67-68%; Hanes untouched.

## Final wheel smoke
Built final saena-forge-console wheel with uv build --offline (no dependency
installation). Explicit wheel-first PYTHONPATH, console source excluded; asserted
local_config.__file__ resolves inside the wheel before execution. Auth, report
API, viewer and local-config suites:162 passed,2 warnings,1.30s. This includes
actual --check subprocess and named static asset serving through importlib
resources from the wheel. Dependencies/shared packages remain the existing test
environment/source; this is NOT a clean-machine installation or deployment test.
No persistent server/network provider/account/token issuance. Full regression
6391 remains same unchanged code; this addendum records artifact verification.

## Operator handoff checklist (accepted v1 path only)

This is a local technical-diagnostic pilot, not live AEO measurement or a
self-service SaaS login. Do not select the unintegrated SQLite version2 unit.

1. Obtain explicit authorization for the exact supplied HTML pages. Use synthetic
   data for demos; do not fetch sites or copy customer accounts automatically.
2. Create a canonical, non-symlink input directory outside the Git checkout.
   Write the existing CLI manifest with explicit tenant, expected cohort, relative
   HTML files and SHA256 of exact supplied bytes. Missing pages stay unmeasured.
3. Set SAENA_PILOT_HOME to a separate private directory outside both input and
   every Git repository. Run the existing html_audit_cli with mandatory real
   skill-bundle validation from the accepted integration checkout.
4. Inspect report.json, report.txt and receipt.json. The operator must confirm
   page/tenant provenance, not merely accept a filename or hash as truth.
5. Build the existing version1 operator config: pinned PUBLIC key only,
   issuer/audience, server membership, explicit read grants, report_root and
   opaque report IDs with exact report/receipt byte hashes. For report-only
   users, roles can be empty; readers grants do not require proposer powers.
   Never put a token, account password or private signing key into config.
6. Run local_config --check. Refusal means stop and inspect the source locally;
   never disable validation to load the report. Check does not fetch/observe.
7. Only an authorized operator may start the existing ASGI factory. Bind to
   loopback for a local demonstration; do not expose it externally. Startup
   does not create an IdP, login, refresh, token issuance or TLS deployment.
8. Open /report-viewer, use only an authorized temporary access token, and enter
   the approved opaque report ID. Token is cleared on each request. A normal
   viewer session cannot discover report IDs or manage accounts.
9. Confirm missing pages and unknown robots/header/CDN/index/render status are
   visible. Title/canonical/JSON-LD syntax findings are not citation outcomes.
10. End the temporary local process/session. Record validated inputs, artifact
    hashes, known limitations and actual operator acceptance separately.
    There is no built-in retention/deletion workflow or production backup yet.

Troubleshooting without bypass:
- configuration invalid: exact version1 keys, tenant env, public-key format,
  trusted canonical file permissions and registered artifact hashes.
- 401: temporary token signature/issuer/audience/time/server membership, not
  role headers; never log or paste the token into an error report.
- 403: explicit server reader grant missing; do not grant wider proposer roles.
- 404: wrong/unknown report ID or another tenant; do not reveal its existence.
- 503: unsafe/corrupt/mismatched report; preserve it and investigate, not reset.
- unmeasured: no supplied page bytes, not a performance score of zero.

## Actual accepted-path synthetic pilot demonstration

Executed from accepted02c47ab, not SQLite worktree, with real CLI bundle validation
and two explicitly synthetic HTML snapshots for example.invalid/product:
before: canonical_not_observed, jsonld_invalid, meta_noindex, title_not_observed.
after: canonical_present, jsonld_syntax_valid, title_present.
Both reports retained expected2/measured1 and the same unmeasured missing page.
This demonstrates local diagnostic response to supplied markup changes, NOT
search-engine eligibility, actual indexing, citations, traffic or revenue lift.

Actual CLI created two fresh reports/receipts without changing input bytes.
Version1 --check accepted two report bindings and returned
live_observation_verified=false. In-process TestClient returned401 without token,
200 with in-memory synthetic signed token for both reports, and200 for viewer
shell/asset. No network server, real IdP, customer material or token/private-key
file was created. Public fixture key and output reports remain local QA inputs.
The browser interaction suite remains the earlier20 actual-Chromium scenarios;
this demonstration did not repeat that browser suite or claim it did.
