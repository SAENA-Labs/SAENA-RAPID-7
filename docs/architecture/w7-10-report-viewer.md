# W7-10 approved local read-only customer viewer

Owner voice approval relayed: "어, 실행해, 같이". Base 95570a5. Parent Integrator
reassigned completed W7-09 app.py ownership. Scope: same-origin read-only viewer,
existing API/auth/schema unchanged; synthetic local browser tests only. No real
IdP/customer files/external deployment. Hanes priority, one lightweight test.

Ponytail: single screen needs no framework/build/dependency. Existing FastAPI
serves only three named package assets; native DOM/fetch/AbortController handles
rendering. Existing Chromium and Node native CDP can test without installing new
product dependencies. Never turn diagnostic or unmeasured state into performance.

Opt-in enable_report_viewer=True requires configured production TokenVerifier
and ReportCatalog. Public empty shell only, no report/token injection into HTML.
GET /report-viewer and two named assets. Token/password field used only in memory
and Authorization header; no URL/cookies/storage/console. Clear on reset/pagehide/
pageshow; cancel in-flight and reject stale responses on newer request/input.
No login/issuance/refresh implemented. Same-origin fetch with credentials omit,
no redirects/cache; URL content rendered as text, not followed. CSP self scripts/
styles/connect, no inline/eval/frame/object/base/form, no-store/nosniff/no-referrer.

## Running and trust boundary

Construct the existing app with token_verifier=<configured TokenVerifier>,
report_catalog=<approved ReportCatalog>, enable_report_viewer=True. Without the
flag the viewer routes do not exist; without production auth/catalog enabling
fails closed. Browse /report-viewer on the same origin. This unit does not add
login/account/token issuance; the UI explicitly asks for a temporary access
token, NOT an account password. Every request clears the input field; it must
be supplied again for another query. Authorization exists only in the pending
browser request, never in app storage/history/cookies. This does not defeat
malicious browser extensions or user password-manager behavior outside the app.

The data API/schema/grants are unchanged. Only index.html, viewer.css, viewer.js
are named routes; no directory listing or arbitrary static file path exists.
HTML/CSS/JS are included in the built saena_forge_console wheel (offline uv build
verified). No external CDN/font/analytics, no service-worker/local persistence.

Input changes/reset/pagehide/pageshow abort old requests and clear displayed
reports. A generation counter prevents stale responses replacing a new report;
in-flight submit disabled to avoid double-click cancellation, input/reset still
usable. Keyboard Enter triggers the same button path. Focus styles/labels/status
live region provided. Network/type/HTTP errors leave no old report displayed.
Maximum response body read is 8 MiB; server still owns full structural validation.
URLs and diagnostic strings are textContent only and never followed/rendered as
HTML. Info/review labels shown without altering supplied evidence or findings.

## Verification

11 new static route/configuration tests pass; console+approval-flow total 217
passed in 1.53s. Ruff/diff/Node syntax checks pass. Native Node/CDP with existing
Chromium verified 20 scenarios against a temporary 127.0.0.1 server and synthetic
RSA tokens/report bytes: valid, unmeasured, XSS text-only, memory-only token,
401/403/404/503, stale response, repeated click, review level, cancel, Enter,
severity label, mobile, 100-page report, network error, invalid response, reload,
and browser back. Test fixture/browser processes exit after completion. No
non-loopback page requests or browser runtime exceptions were observed; this
statement covers test-page requests, not an audit of Chromium background traffic.

Direct visual inspection: 1280px desktop and 390px mobile; no horizontal overflow,
readable evidence/missing-page/limitation sections. QA images remain local only,
not uploaded as user deliverables. UI English diagnostic detail is original
source text, retained rather than translated into unsupported conclusions.
No automated WCAG certification or production load/security certification is
claimed. Full regression and independent final review follow below.

Final full non-integration regression: 6344 passed, 45 skipped, 453 deselected,
2 warnings in 127.34s. Skips remain 43 missing prior contract tags and 2 unavailable
Helm/kubeconform tools; excluded provider/integration cases are not claimed run.
One nice 15 process; observed free memory 72–74%; Hanes files/services untouched.
Independent first review found no blocking security defect and separately
validated static shell/assets CSP/no-store/DENY, allowlist traversal404,
report401 and default opt-out404 with memory-only TestClient. Its nonblocking
severity-label recommendation was implemented and browser-verified. Final
changed-JS static confirmation is awaited before integration.

Final independent static re-review PASS: info/review whitelist and textContent
labels; disabled submit with input/reset/cancel re-enable; generation-guarded
finally cannot unlock a newer request; Enter routes through disabled-aware
native button.click(). Reviewer also ran Node syntax and small forbidden-sink/
button-lifecycle assertions. Reviewer did not rerun the 20 browser scenarios;
those are implementer actual-Chromium results, distinguished above. No remaining
blocking finding. Integrate only this tested code and evidence document.
