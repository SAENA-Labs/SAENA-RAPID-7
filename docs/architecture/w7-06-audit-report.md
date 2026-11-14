# W7-06: single-tenant offline HTML audit report

Owner approval 2026-11-14 relayed by coordinator: "웅 진행해줘" to the
specific customer HTML report-adapter plan. No network/customer writes,
external API/schema/security-policy/deployment changes. Hanes first.

Plan: consume W7-05 PageAudit-shaped immutable values with explicit expected
page list. Reject mixed tenants and contradictory snapshot identities. Preserve
hash/ref/page/line evidence. Missing expected pages are UNMEASURED, external
unknowns remain unknown, never converted to zero issues. Stable JSON/text return
only; no filesystem writes. Apply existing secretguard before rendering. Pilot
is stdlib-only: structural Protocol typing, no runtime service import or new
package dependency. Add synthetic isolation/missingness/secret/determinism tests,
independent review, local commit. W7-05 must be combined for actual producer use.

## Verification

23 new synthetic tests pass and final independent critic review is PASS. The
critic reproduced empty URL userinfo acceptance; fixed to reject even empty
username/password markers, matching W7-05. Added cumulative 1 Mi-character input
text budget, 4096 total findings, 1000-page cap and bounded line references. The
character cap is not the serialized output byte count (JSON overhead exists).
Existing pilot/security suite at initial adapter revision: 406 passed.

Real producer handoff in the combined temporary checkout: W7-05 audited supplied
synthetic HTML, W7-06 returned JSON/text with measured=1/expected=2, missing page
retained as UNMEASURED, exact input hash preserved, and all external unknowns
preserved. No customer fetch/changes or actual visibility measurements occurred.
Reports contain diagnostic facts, not a ranking score or an assurance that an
issue-free supplied page is indexed. Unknown defaults are restored even if a
caller omits them. Same bytes across URLs are flagged as non-independent;
conflicting evidence refs or snapshots are rejected rather than silently merged.

No files are written by this adapter. Both outputs are returned after the existing
secret-shape guard; all user-supplied text is JSON-quoted in human output to avoid
newline row spoofing. Guard coverage is known secret patterns, not a universal
privacy detector. Tenant assertion is not authentication, and hashes are preserved
rather than reverified against missing original HTML. Future caller must enforce
authorization/source provenance. Pilot remains stdlib-only with no new runtime
service dependency. W7-05 and this adapter are not deployed/wired into an endpoint.
