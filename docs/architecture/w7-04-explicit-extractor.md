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
