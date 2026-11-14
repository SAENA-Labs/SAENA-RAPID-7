# W7-12 approved local SQLite run metadata
Owner approval relayed: affirmative approval of local SQLite persistence plan.
Base02c47ab. Integrator reassigned local_config.py W7-11 -> W7-12.
Scope: service-private SQLite adapter, optional version2 local config, synthetic
restart/concurrency/corruption/tenant tests. Existing HTTP/shared schemas fixed.
No real customer/network/IdP/deployment. Hanes resource priority.

Ponytail before execute: stdlib sqlite3, existing generated RuncontextLifecycle,
existing store interface; no dependency. Directory must already exist0700 and
owned by user, DB0600 regular singlelink; canonical nofollow parents. Same-UID
malicious races excluded. Fixed filename runs.sqlite3; DELETE journal+FULL sync,
BEGIN IMMEDIATE/busy timeout2s; no WAL. v1 remains memory-backed. v2 adds exactly
run_store={kind:sqlite,directory:canonical-absolute}. --check does not create DB;
ASGI factory initializes only after all report/config validation.
Bound payload256KiB,total JSON16MiB,rows10000,DB64MiB. No retention/delete API.
Schema/app/version/tenant binding/quick_check/payload validation fail closed.
Existing corruption never silently reset. Repeated initialization is idempotent.

## Verification and operating limits
37 dedicated synthetic tests pass; console+in-process approval flow301 passed,
1 existing warning,4.57s. Tests include new OS process reading saved metadata,
2 concurrent writer threads with separate connections, transaction process exit
before commit preserving prior row,2s lock refusal without overwrite, bound
single tenant, parameterized query injection, permission/path/link/FIFO/sidecar
rejection, version2 check-no-create and factory/API restart, schema/payload
corruption rejection. These are not power-loss/hardware durability certification.

Independent review found a schema-name collision: dict(name,sql) could hide an
extra trigger named meta when sqlite_master rows were reordered. Fixed validation
compares ALL type/name/tbl_name/sql rows, allowing exactly two tables and their
known implicit primary-key indexes, no triggers/views/extra indexes. Regression
reorders meta table/index to rowids10/11; a new connection with trusted_schema=OFF
still passes old dict comparison, but fixed check/put reject. Also reject orphan
journal even before DB creation. No corruption auto-reset or repair path exists.

Storage holds latest run metadata, not an immutable audit ledger. No cross-tenant
DB reuse, backups, retention/deletion, encryption, replication or credential
management implemented. Directory creation is operator-owned and must be0700;
DB0600. --check uses SQLite read-only mode and rejects recovery-required states;
factory may initialize/recover permitted DELETE journal within trusted directory.
Existing malformed/empty databases fail closed rather than being repurposed.
Database first-start races may fail closed and require retry; simultaneous writes
after initialization are tested. Same OS-user malicious file races are excluded.
Every operation validates the bounded store, trading throughput for simple safety;
large-customer performance has NOT been established. File/schema checks cannot
prove truth of structurally valid edits by a trusted OS user. No shared schema
or HTTP route behavior changes, no new deployment or external network access.

## Current gate: BLOCKED, not integrated
Final author-run non-integration regression:6428 passed,45 skipped,
453 deselected,2 warnings,127.19s. Prior exclusions unchanged:43 missing release
tags plus2 unavailable Helm/kubeconform tools; external integrations not tested.
Memory free66-68%,single low-priority runner; Hanes untouched.

Independent re-review of the correction did NOT complete: parent reported the
reviewer turn was rejected with "This content was flagged for possible
cybersecurity risk" and no further details or approval card. Do not rephrase,
reroute or repeat that same rejected review. No independent acceptance of the
correction is claimed. Keep this unit out of integration until the required
review can be completed through an authorized path. Current accepted integration
remains02c47ab. This branch checkpoint is implementation/test evidence only,
not release acceptance, external deployment or completed security review.
