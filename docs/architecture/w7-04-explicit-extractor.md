# W7-04: explicit citation extraction configuration

Internal owner-approved observer reliability scope, 2026-11-14. No external
accounts, customer access, deployment, dependency or schema changes. Hanes first.

Problem: omitted extractor silently becomes valid zero citations. Plan: refuse
missing/noncallable extractor before browser or artifact activity, preserving
engine-first rejection and explicit legitimate zero-citation extraction. Only
registered paths change. Existing fixtures explicitly declare their synthetic
empty extraction; no real parser or live effects are fabricated. Test old-source
failure, unit/security tests, independent review, then isolated local commit.

Rollback: revert/discard this unit; no customer state changed. Intentional API
compatibility tightening: callers must explicitly inject an extractor. Production
parser integration and HTTP200 login/challenge validity remain separate work.

## Validation

Original-source reproductions: 3 failed (omitted/None/noncallable), explicit
zero fixture passed. Updated observer/security suite: 72 passed, Ruff and diff
checks passed. Five new regressions include parser-exception propagation.
Independent non-author review PASS. Existing composite end-to-end engine test
also exercises disallowed engine with extractor omitted. Parser runtime failure
still preserves the raw artifact captured before failure (existing behavior),
but returns no successful observation. This is not automatic cleanup/rollback.

## Commercial-readiness assessment after W7-01 through W7-04

A credible initial offer is a bounded technical AEO audit and implementation
pilot, NOT a guarantee of mentions, rankings, leads or sales within seven days.
The repository has substantial reusable control, evidence and measurement
logic, but no demonstrated production acquisition-to-report deployment. Tests
use fixtures and some always-trust authorization doubles, not real policies.

What can be demonstrated internally today:
- Exact search-query preservation; HTTP navigation failures rejected.
- Tenant-scoped observations and deliberate rather than accidental zero refs.
- Synthetic treatment/control measurements and complete evidence binding.
- Fail-closed success reports and replay/idempotency behavior.
- Local repository discovery/audit workflow with explicit customer boundaries.

Before a paid external pilot requiring measured search outcomes:
1. Agree a narrow authorized customer repository/site scope and signed Action
   Contract, owner approver, allowed edits, rollback and deployment evidence.
2. Establish a supported/permitted observation method, provider access and
   real parser with sanitized captured fixtures. Distinguish blocked/login/
   challenge/no-answer from a valid answer with zero citations.
3. Wire production adapters and dependency packaging, not fixture mappings or
   accepted_stub gateways; verify the real runtime and secret/tenant boundaries.
4. Load authenticated production policies; preserve reproducible query cohort,
   engine/model/context, timestamp, treatment/control and raw evidence refs.
5. Record baseline before change and anchor post-period to actual confirmed
   deployment. Wait for actual observation availability; report inconclusive
   results as such. Recrawl/indexing and provider output are not controlled.
6. Migrate the report gate only alongside the full-decision evidence generator.
   Preserve old records and use new evaluation identities where needed.

Acceptance wording: deliver an evidence-linked audit, approved change diff,
rollback and verification report, plus a baseline/measurement plan. Report
separately (a) local correctness, (b) real deployment, (c) observed visibility,
(d) attributed business effect. Today only (a) was tested here. No external
customer access, publication, merge, push or deployment was performed.

## Final combined regression result

All four patches combined in an isolated temporary clone, original repository
and Hanes untouched: **6129 passed, 45 skipped, 453 integration deselected,
2 warnings in 125.42 seconds**. Baseline was 6070 passed, so 59 regressions
were added across four units. Python imports were directed to the combined
clone; existing environment reused; single nice-10 process. No live outcome
claim follows from these numbers. The 45 skips include missing historical
release tags and absent Helm/kubeconform. Original working tree still has only
its pre-existing untracked devcontainer lock file; all four unit trees clean.

## Follow-up: malformed empty results are not measured zero (2026-11-14)

Continued owner-authorized reliability work after initial report. A callable
extractor returning empty string, bytes, mapping, set or iterator was silently
coerced by the downstream list() conversion to a successful zero-citation
observation. Five actual false-success shapes reproduced. None and malformed
individual refs already errored differently; do not count these as additional
false-success defects.

Require an explicit list/tuple of nonblank string refs before record creation;
then normalize to the builder's tuple contract. List support is explicit in the
type alias. Existing URL schema validation remains unchanged. Legitimate empty
list/tuple stays valid zero, while unknown/malformed results raise rather than
becoming a metric. Added 9 negative and 4 positive regressions; relevant observer
and security tests: 85 passed. Independent critic PASS; type/tuple consistency
follow-up targeted suite: 24 passed. No parser accuracy/recall claim: a callable
returning an incorrect but well-formed empty tuple is still undetectable without
a trustworthy parser/source. Invalid extraction still leaves its previously
stored raw artifact, but returns no successful observation (existing ordering).

Final exact-code combined verification including type normalization: **6142
passed, 45 skipped, 453 deselected, 2 warnings in 112.04 seconds**. Added tests
now total 72 above the 6070 baseline. No new dependency or external observations.
