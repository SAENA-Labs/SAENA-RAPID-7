# W7-07: approved local integration and HTML snapshot CLI

Owner 2026-11-14 approval relayed: "rapid7 제안한 대로 진행해" to six-patch
local integration + explicit-tenant local HTML CLI plan. Separate integration
branch integration/rapid7-local-readiness starts at 61e555e and contains the six
approved patch units in order. W7-02/03 travel together; old persisted hashes
are never rewritten. Original working branch preserved, no remote push/deploy.

Plan: separate python -m saena_pilot.html_audit_cli entry, mandatory existing
skill-bundle validation before input processing. --tenant-id + --input-root
absolute directory + --manifest relative JSON path. Manifest tenant must match,
expected_pages explicit, snapshots carry page_url/file/sha256 and optional status.
Only bounded regular .html/.htm files inside input root, no symlink/path escape,
FIFO/device/hardlink input; verify exact bytes against supplied SHA256 before
calling W7-05 then W7-06. No scripts/network/agents/customer writes. Known-secret
guard on manifest and reports. Fresh private report directory under existing
pilot-runs, outside code and input roots. Do not create regular pilot run.json
or impersonate signed action/deployment/measurement records. Return JSON/text
plus receipt with input hashes; no raw HTML stored. Test guards + independent
review + actual local CLI fixture + full combined regression. Stdlib filesystem
logic, no dependency install; service import lazy, source checkout paths explicit.

## Input contract and invocation

This is a separate local-only entry point, not a new network service:

    python -m saena_pilot.html_audit_cli --tenant-id demo \
      --input-root /absolute/canonical/path/to/approved-snapshots \
      --manifest manifest.json

In a source checkout use the existing Python environment and explicitly put the
integration checkout's `tools/saena-pilot/src` and the site-discovery service's
`src` on PYTHONPATH. No hidden install or copying into the original checkout.
Input paths must be canonical/no-symlink (on macOS `/private/tmp`, not `/tmp`).
Manifest is relative to input root, all listed file paths are relative too:

    {"tenant_id":"demo", "expected_pages":["https://example.com/product"],
     "snapshots":[{"page_url":"https://example.com/product",
       "file":"product.html", "sha256":"sha256:<64 lowercase hex of exact bytes>",
       "http_status":200}]}

Use `SAENA_PILOT_HOME` to select an approved local runstore outside all Git
working trees AND outside input_root. This invocation does not grant customer
write permissions or imply signed action/deployment approval. Expected URLs
not represented by a file remain UNMEASURED. Only supplied HTML is read;
no URL/JSON-LD context is fetched, and customer scripts are never executed.
Existing trusted bundle validators still run; missing/invalid bundle refuses.

## Validation and limitations

20 new local fixture tests pass. Real CLI end-to-end also passed against the
actual repository bundle using synthetic HTML only, not the test bundle:
report.json/report.txt/receipt.json created in a fresh private run directory,
measured=1/expected=2 and missing page retained. Input bytes remained unchanged.
No run.json is fabricated, so legacy run listing/resume does not mistake this
report for a regular signed workflow. No raw HTML is copied into the store.

Tests cover manifest tenant/schema/duplicate keys, changed hash, traversal and
non-HTML paths, input symlink components, hardlinks, FIFO nonblocking refusal,
raw HTML known-secret pattern, output under input/repo, output symlink,
customer-repo sibling output, shared-writable output ancestor, mandatory bundle
validation, and CLI generic error non-disclosure. Full source paths/decoder input
are not printed on failures. Known-secret guard is not universal PII detection.

Independent static review found that input_root could be a customer repo's
snapshots subdirectory while output was a sibling inside that repo. Fixed by
refusing outputs in ANY detected Git working tree, with regression. Output path
components must be root/current-user owned and not group/other writable, except
root-owned sticky temp directories; new run folders/files are 0700/0600 with
O_EXCL/O_NOFOLLOW. This does not defend against a malicious concurrent process
with the SAME OS user identity renaming trusted directories. User-owned output
paths and no hostile same-user concurrent filesystem changes are prerequisites.

Filesystem failures can leave a partial newly-created report directory; CLI then
fails and makes no success claim. No old report is overwritten. Receipt binds the
manifest bytes, report binds HTML bytes; neither proves external source truth.
No provider observations, real index/citation improvement, API/authentication,
remote push, deployment, schema migration or historical evidence rewrite.

Independent reviewer executed 20 fixture tests successfully, then identified
Git helper errors being treated as non-repository. Added explicit lstat of .git
markers from nearest existing output ancestor to filesystem root: any marker
is refused; only FileNotFoundError is ignored; permission errors fail closed.
Git probing remains supplemental, not sole authority. Added helper-failure
regression: final local CLI suite 21 passed. No global Git helper/policy changed.
