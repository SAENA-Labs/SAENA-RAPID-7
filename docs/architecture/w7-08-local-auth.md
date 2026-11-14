# W7-08 local verified authentication boundary

Owner approval 2026-11-14 relayed verbatim: "아까 물어본거 승인할게".
Approved: production signed tokens only; server subject-to-tenant/role mapping;
signature/issuer/audience/time validation, header spoof resistance, synthetic
local tests, service dependencies. No real IdP, accounts, deployment or shared
schemas. Dev-repo approval record, NOT a fabricated signed tenant Action Contract.

Ponytail: necessary because current header stub is not authentication; reuse
RequestActor, domain ActorContext and RBAC. Stdlib cannot safely implement JWT
cryptography. Approved maintained PyJWT[crypto] dependency, pinned by uv.lock;
no custom crypto. Small service-local verifier and explicit test-only legacy
mode, no new network API. No customer content or Hanes touched. Rollback is
revert this isolated unit; never expose old header mode publicly.

Plan: fixed RS256 public key >=2048 bits, exact issuer/audience, required
sub/jti/iat/nbf/exp with bounded TTL; immutable server membership map supplies
actor, tenant and roles. Reject identity headers in production (tenant header
may only match authenticated tenant); bind tenant to configured pod even when
header absent. Default app refuses missing verifier. Explicit test_headers
mode for old unit fixtures only. No network key lookup, token issuance,
refresh, browser login, key rotation, session revocation or durable membership.
Independent review and local forged/expired/cross-tenant regressions required.

## Verification and exact remaining boundary

103 console unit cases passed (59 retained legacy-mode tests + 44 new synthetic
cases), 0.50s. One targeted approval-flow cross-tenant test file: 5 passed,
0.16s. The existing in-process approval harness now opts into test_headers
explicitly at both construction sites; parent Integrator assigned exclusive
ownership of that fixture. Ruff and diff whitespace checks pass. Full regression
is deferred while Hanes runs its priority model test. No real provider/session,
concurrent production, network identity or full-stack deployment validation.

New default is intentionally fail-closed: callers constructing create_app()
without a verifier must update startup composition, not silently get header auth.
Test mode is a developer capability, not a remotely switchable HTTP parameter.
This unit secures only the console edge; audit-ledger and other internal stub
transports are NOT independently production-secure or exposed by this change.

RS256 only; one trusted public key, one exact issuer/audience, server membership
map keyed by subject under that issuer, one deployment tenant via SAENA_TENANT_ID.
Required integer iat/nbf/exp with maximum one-hour life; jti becomes the validated
ActorContext session reference, not a bearer credential in logs. No replay cache,
revocation, token issuance or live key rotation. Token typ is not an IdP access-
token discriminator yet; a dedicated API audience/access-token contract must be
confirmed before connecting any real issuer. Existing unverified role/tenant
claims inside a signed token cannot grant roles: only server mapping does.

Dependencies: PyJWT 2.15.1 with cryptography 50.0.2 locked using uv offline cache.
Test dependencies were installed in /private/tmp/saena-w7-auth-py312, never into
the original checkout venv. No shared contracts, schema, deploy changes or push.
Sources: https://pyjwt.readthedocs.io/en/latest/usage.html and /api.html.

Independent reviewer final PASS: 44 new authentication cases independently
passed in 0.29s against this worktree; static review and diff check passed.
Reviewer could not apply nice(15) in its environment; only the short new suite
ran. Full regression remains deferred, not silently considered complete.

## Post-Hanes integration verification

After Hanes finished its priority model run, parent authorized integration and
full regression. Applied unit 739f2c1 onto clean integration/rapid7-local-readiness
27bbb57 as 7d2ccf6 without conflicts. No original checkout or remote changes.
Integration console + in-process approval-flow suite: 146 passed, 1 warning,
1.02s. Full non-integration regression on code 7d2ccf6: 6273 passed, 45 skipped,
453 integration cases deselected, 2 warnings, 115.27s. Skips: 43 missing prior
contract tags and 2 unavailable Helm/kubeconform tools. This does not validate
live providers/deployment. Original baseline 6070 -> current 6273 (203 added
regressions across approved units). Dependency injection source paths explicitly
selected this checkout and the isolated PyJWT/crypto install, not original code.
Single nice15 test process, memory free observed 72% before and 71% during run;
no Hanes model started, no parallel workload added. Ruff/diff checks pass.
Follow-up trust-config hardening: PyJWT accepts issuer/audience collections,
so type annotations alone did not enforce our single exact issuer/audience
configuration contract. Reject non-string or blank issuer/audience at startup.
Six regression cases added; console suite 109 passed in 0.77s; independent static
review PASS. Normal values are not normalized, preserving exact comparison.
