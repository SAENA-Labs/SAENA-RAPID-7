# W7-03: customer-report publication gate

Internal evidence/reporting hardening under the owner's 2026-11-14 approval.
Same Hanes-first and no external observation/push/merge/deploy rules.
Base 61e555e. Independent unit, no schema or production policy changes.

Reproduction: existing boundary positive fixture has a manifest containing
only B_GATE_DECISION and two entirely insufficient DiD signals. Nonetheless
publisher returns b_verdict=pass. Hash self-consistency is not completeness or
proof that the reported decision is supported by supplied measurements.

Plan: require complete manifest, matching identity/hash, and sufficient positive
support for claimed layers; reject mixed fixture/production policy provenance.
Update positive test fixtures to actually satisfy these existing invariants,
retain negative tests, add reproductions. No new provider/account or effects
claims. Pure offline synthetic input tests only.

Ponytail: existing validate_completeness + verify_manifest and existing result
fields suffice. No new dependency, weighting, threshold or schema. Modify only
registered publisher and its tests, plus this document. Independent review and
local commit; rollback by discarding/reverting this isolated unit.

## What is now checked before returning a PASS report payload

- At least two unique declared qualifying layers.
- A resolved, self-hash-verified AND complete evidence manifest.
- Manifest tenant, experiment and requested hash match the report request.
- DID_OUTPUTS matches the exact canonical supplied measurement output.
- B_GATE_DECISION matches the full canonical decision, including confidence,
  raw/control views and policy metadata, not just a verdict label.
- Claimed layers have sufficient finite positive-net-effect measurements and
  nonempty four-cell sample counts; insufficient inputs are not accepted.
- Existing domain maximum bipartite matching verifies each declared layer can
  be assigned a distinct evidence basis. Unclaimed extra layers cannot supply
  independence on their behalf. No new scoring algorithm was introduced.
- GRS, DiD and B-gate policy provenance agree; fixture results cannot borrow a
  production label from one policy.

Initial two reproductions both failed on the original implementation. Current
boundary suite: 60 passed, including existing tests and 17 new adversarial
regressions. Positive fixtures were strengthened, not tests removed/relaxed:
actual synthetic four-cell measurements, complete kinds and payload hashes.
All are offline fixtures. No live provider, customer, bus or publication is
involved; the function returns a dictionary for downstream handling.

Independent critic identified and reproduced (1) same-basis duplicated layers,
(2) different-measurement bundle reuse, and (3) an unclaimed third layer masking
shared bases. All received fixes and explicit regressions. No tests or
security gates were removed to obtain green results.

## Compatibility and remaining limits

Apply together with W7-02's full B_GATE_DECISION hash generator. Old partial-
decision hashes will be refused, intentionally. Preserve old records; do not
rewrite signed or idempotent history. New authorized evaluation records need
new run identity. This is a local, unshipped migration requirement, not a claim
that existing customer production history has been migrated.

Hashes prove binding/integrity of supplied objects, not their truth. Intake,
authenticated policy loading, observation authenticity, signed decisions and
real elapsed measurements are still upstream requirements. This boundary is
not a replacement for those trust roots, and a fixture PASS is not empirical
AEO visibility or revenue evidence. Legacy FAIL/UNDETERMINED payload paths are
unchanged. No external API/event schema was edited.

Final independent non-author review: PASS; reviewer reran all 60 boundary
unit tests in 0.13 seconds and diff whitespace checks. No further blocking
finding. Combined W7-02/W7-03 integration verification follows separately.
