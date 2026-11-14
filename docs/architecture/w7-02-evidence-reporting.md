# W7-02: evidence and reporting integrity

Internal development authorized by owner on 2026-11-14 via the parent-relayed
“진행해” approval of the development/evidence/reporting plan. Same no-push,
no-merge, no-deploy, no external observation scope and Hanes-first priority.
Not a customer signed Action Contract or a production policy signature.
Base: 61e555ea9fbdb5c29c5534787e97f53a7d1018c7.

Read: pipeline inputs, orchestrator, outcome, measurement evidence/DiD/B-gate,
and existing pipeline factories/tests. Reproduced missing baseline provenance
returning PASS with an incomplete bundle; a production B-gate label together
with fixture GRS/DiD policies returning is_production=True.

Plan: bind each signal to its available per-kind evidence; prevent PASS with
incomplete sealed evidence; report production provenance only when every
relevant policy is production-valid; hash full DiD input values rather than
only identifying labels. No schema, thresholds, score, or policy changes.
Regressions must reproduce old behavior before fixes. Independent review,
full relevant tests, local commit only. Revert/discard this unit for rollback.

Ponytail ladder PASS: concrete false-positive reporting defects; reuse existing
evidence flags, enums and model serialization; no dependency/abstraction/new
service. Preserve all guards. Exclusive paths are the pipeline orchestrator,
new reporting-integrity test and this document. No protected paths changed.

## Reproducible experiments and results

All observations below are synthetic offline fixtures. No customer data,
provider calls, real deployment or elapsed seven-day observation is involved.

| Scenario | Original | Patched |
|---|---|---|
| Remove all baseline, treatment or control metadata (3 cases) | PASS | UNDETERMINED + missing_raw_evidence_ref |
| Remove metadata for one of two signal bases (3 cases) | PASS despite gap | UNDETERMINED |
| Production gate label with fixture GRS/DiD | is_production=True | False |
| Change numeric repeats, keep same mean | same evidence hash | different evidence hash |
| Change timestamps only or observation IDs only | not explicitly bound in DID_INPUTS | different evidence hash |
| All 8 production/fixture policy flag combinations | only gate flag considered | production iff all 3 are production |

Initial 8 added regressions failed against original source, then passed with
fixes. Relevant pipeline/boundary/persistence suite: 135 passed. Full
non-integration tree at that revision: 6,078 passed, 45 skipped (43 previous
contract tags absent + 2 Helm/kubeconform absent), 453 integration deselected,
2 warnings, 117.06 seconds. Following independent review, 10 additional tests
cover all policy combinations plus timestamps/IDs: all 18 new regressions
passed in 0.14 seconds. Independent non-author review PASS; independently ran
18 selected regression/idempotency/GRS tests and a NaN input probe, which
remained UNDETERMINED. Ruff and diff checks passed.

`is_production` is policy-provenance metadata, not a claim of real data,
cryptographic approval, external visibility lift or causal success. The
production-positive test injects synthetic policy decisions solely to check
boolean propagation; it does not invent production approval/signatures.

## Remaining commercial gates

Real source evidence must still be verified by the authorized intake/observer
and trusted policy loader. A hash commits to supplied inputs, not their truth.
No live 7-day data, provider authorization, real control-group validity or
customer sales uplift was established. The downstream report-publisher trust
boundary is a separate patch unit; this unit fixes pipeline assembly only.

No remote push/merge/deploy. Original checkout remains unchanged. Rollback:
discard/revert this unit's local commit; original full baseline was independently
verified before modification (6,070 passed, same exclusions).

## W7-03 integration follow-up

The downstream publisher now verifies the actual DiD output and complete
BGateDecision hashes. This generator therefore hashes the whole decision JSON,
not only verdict/reasons/qualifying layers, binding confidence and raw/control
views as well. W7-02 and W7-03 must be reviewed/integrated together. Legacy
subset-hashed bundles are not silently upgraded: new publication rejects
mismatches. Preserve old records; a new authorized evaluation/run is needed,
not an in-place overwrite under an old idempotency key. No existing stored
records were modified during this task.
