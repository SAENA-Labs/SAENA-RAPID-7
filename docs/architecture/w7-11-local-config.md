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
