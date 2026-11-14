# W7-01: observer reliability (internal development)

Base: `61e555ea9fbdb5c29c5534787e97f53a7d1018c7`.
Owner: Arthur AEO worker. Branch: `unit/w7-01-observer-reliability`.

## Approval and boundary

The owner approved the internal development proposal on 2026-11-14 with
“진행해” and directed completion by 21:00 KST, rather than an actual seven-day
observation. Parent relayed the approval and retained the Hanes-first resource
priority. This records chat approval for INTERNAL development only. It is not
an invented cryptographic signature, signed production policy, or authorization
to run a customer's FORGE Action Contract. ADR-0019 distinguishes dev-repo
safety hooks from the customer execution gate. No gate or protected path is
changed. No install, push, merge, deployment, external observation or customer
contact is authorized by this unit.

## Read/understanding record

Read `playwright_driver.py`, `pool.py`, `pool_capture.py`, the service manifest,
existing observer tests, ADR-0019/0023, CLAUDE.md and AGENTS.md. The adapter
interpolates raw query text into a URL and retains no context handle. A query
`C++ & B2B #가격? 지역=대전` decodes as `C   `, invalidating observation cells.
Factory-created contexts outlive `page.close()` until whole-browser shutdown.

## Scoped plan / minimality ladder

1. Correct query encoding to preserve the exact registered query.
2. Close the context owned by each leased session; clean up on page creation
   failure. Preserve the existing page-only test/adapter construction path.
3. Add offline regression tests using fake browser/page/context objects.
4. Report evidence, remaining live integration limitations, and rollback.

Ladder PASS: both fixes prevent concrete reliability defects; no reusable URL
builder exists here; Python urllib.parse and native context.close suffice;
no new dependency, new service, schema change, scoring change or abstraction.
Delete candidates: none; no safety/evidence/tests removed.

Exclusive changes: this document, `playwright_driver.py`, and
`tests/unit/svc_chatgpt_observer/test_playwright_driver.py`. Existing schemas,
contracts, protected policy, deploy and provider scope remain unchanged.

## Verification / rollback

Run the targeted regression suite against the original code first, then the
patched module, and observer/pilot/measurement regressions. Reuse installed
Python environment without installation; ensure the worktree module is first
on PYTHONPATH. External resources are fixture-only. Request independent
non-author review. Rollback is discarding this isolated unit or reverting its
local commit; do not merge or reset the original checkout.

## Limitations

Unit tests demonstrate mechanism correctness, not real ChatGPT observations,
indexing, citations, leads or sales. Production observation methodology,
authorization, dependency packaging and end-to-end live validation remain
separate gates. No seven-day performance or production-readiness claim.

## Verified results (2026-11-14)

- Original full non-integration baseline: **6,070 passed / 45 skipped /
  453 integration tests deselected**, 109.52 seconds, single process at
  lowered scheduling priority. 43 skips: absent previous contract release
  tags; 2 skips: unavailable Helm/kubeconform. Not full integration validation.
- Original-code regression reproduction: **7 failed / 5 passed**.
- Patched observer, scheduling and discovery unit suites: **168 passed**.
- Independent read-only reviewer: **PASS**, independently reran 12 new tests,
  Ruff and diff whitespace validation. Live browser/ChatGPT not exercised.
- No changes to original checkout or Hanes code/services. No dependencies
  installed and no external observations or uploads performed.

## Commercial readiness assessment (source-derived, not market evidence)

The 1,795-file repository implements substantial infrastructure: tenant-scoped
intake, isolated patch workspaces, approval/policy machinery, immutable
artifact references, experiment binding and treatment/control difference in
differences. This is more than a scoring demo. But code and fixture tests do
not establish successful customer use or real ChatGPT visibility lift.

### Sellable pilot scope, subject to customer authorization

1. Read-only technical/source audit and factual source-of-truth collection.
2. A proposed, human-approved patch package, reproducible QA and rollback.
3. A preregistered measurement plan with fixed prompts, locale, repeats,
   baseline, control, evidence and observation failure labels.
4. A transparent report separating technical defects fixed from external
   discovery/citation/absorption/prominence/referral outcomes.

Do NOT sell a guaranteed seven-day citation, ranking, lead or revenue result.
The existing measurement clock starts from accepted customer deployment,
not this development task or code delivery, and incomplete windows remain
UNDETERMINED. The code explicitly excludes conversion as a seven-day B-layer
success metric. Short offline fixture tests are not seven days of evidence.

### Remaining release gates

- Resolve the approved ChatGPT observation methodology, account/ToS/rate-limit
  ownership and packaging of the optional Playwright dependency. The URL
  `/search?q=...` is code configuration, not verified evidence that this is a
  supported public production observation API.
- Test real rendered-result discrimination. An HTTP response alone does not
  prove an actual answer was captured; challenges/login/error pages require
  explicit missing/invalid evidence rather than a zero-citation observation.
- Wire and validate the real citation extractor. `pool_capture.py` currently
  permits a default extractor returning an empty tuple; this is safe in
  fixtures but does not distinguish extraction-not-configured from true zero.
- Complete live end-to-end persistence/browser/authorization/rollback tests.
  Docker, production DB, cluster and provider accounts were not exercised.
- Decide production GRS thresholds, effect-size/repeat policy, SLA and privacy
  controls through human review. No production values were fabricated.
- Reconcile outdated root/service README claims (some say NOT IMPLEMENTED
  despite existing source). Protect original specifications; publish a dated
  capability matrix instead of claiming universal readiness.
- DiD/leave-one-out sign stability is a useful diagnostic, not proof of causal
  lift without valid controls, sample sufficiency and stable query cells.

### One-day acceptance vs later outcome evidence

Today: reproducible defects removed, offline regressions green, operator
handoff and limitations clear. Later: approved live observations, baseline and
control, deployed patch, sufficient completed window and real evidence bundle.
Keep those acceptance gates separate in all sales materials.

## Additional same-boundary remediation

Independent read-only review reproduced HTTP 403/429/500 bodies returned as
successful captures. The same scoped driver now refuses missing/non-success
HTTP responses before reading content and retains only the HTTP status in the
error context. Added regression checks for 301/403/429/500/503/None and no body
read. Also added page-close fallback on context teardown failure and explicit
idempotent-close assertions. This does NOT classify HTTP-200 login/challenge
pages as real answers: that remains a separate live-validation gate.

### Final targeted validation

After HTTP and teardown hardening: **175 observer/scheduling/discovery tests
passed**, including 19 new driver regressions. Independent non-author review
reran all 19 driver tests in 0.08 seconds and returned PASS with the same live
HTTP-200 challenge/result-discrimination limitation. Ruff and diff checks
passed. No self-evaluation-only completion claim.

### Operator review commands

From this unit worktree, reuse the already installed base-repo environment:

```sh
PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH="$PWD/services/acquisition/chatgpt-observer-service/src" \
../../SAENA-RAPID-7/.venv/bin/python -m pytest -p no:cacheprovider -q \
  tests/unit/svc_chatgpt_observer \
  tests/unit/svc_observer_discovery \
  tests/unit/svc_chatgpt_observer_scheduling
```

This command injects only the patched observer source ahead of the installed
base tree. Other dependencies are unchanged. It neither installs packages
nor starts external browsers or containers. Review the local unit branch;
original branch/checkout has not been switched, reset or merged.

### Complete non-integration rerun

Patched worktree: **6,089 passed / 45 skipped / 453 integration tests
deselected / 2 warnings**, 114.16 seconds. The 19 added tests account exactly
for the increase from the original 6,070. Skip categories are unchanged.
Run used one nice-10 process; observed Python memory approximately 200 MB.
Runtime import-path check confirmed the patched worktree driver was loaded.

Remote read-only comparison: GitHub `wave6-operationalization` remains
`61e555ea9fbdb5c29c5534787e97f53a7d1018c7`; `main` is
`68b63a2d6eb662ee7fcc51432e5eb9b5a14e6ea1`. No remote changes. Original checkout
still has only its pre-existing untracked `.devcontainer/devcontainer-lock.json`.
