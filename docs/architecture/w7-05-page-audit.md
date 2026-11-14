# W7-05: offline supplied-HTML audit

Owner approval 2026-11-14 relayed by coordinator: "개발하도록 해", in response
to the proposed internal HTML audit module/input-output plan. Scope: supplied
HTML only, no network/customer edits/API/schema/deployment changes. Hanes first.

Plan: immutable tenant-scoped findings for title, canonical, robots noindex,
and JSON-LD presence/syntax. Bind findings to SHA-256 of exact input and an
explicit evidence reference; cite HTML line numbers. Missing external facts
remain unknown: robots.txt, HTTP headers, CDN policy, actual index state,
render completeness. No visibility score, special AI schema requirement or
citation uplift claim. Bounded bytes/metadata, no external dependencies, no
execution of HTML/scripts/JSON-LD context URLs. Synthetic tests and independent
review before local commit. Rollback by discarding this isolated unit.

## Verification and boundaries

43 new synthetic tests pass; independent reviewer final PASS. Cases cover
normal head, noindex/none, snippet restrictions, malformed JSON, absent metadata,
invalid credential-bearing/non-HTTP canonical, ambiguous duplicate attributes,
ignored comments/templates/body metadata, unclosed script, byte/count limits,
tenant result binding and forbidden socket access. The parser never executes
scripts or resolves JSON-LD contexts. Initial absolute `https://` canonical
resolution bug and independent review findings (duplicate attribute last-value
selection, whitespace around max-snippet colon) were fixed with regressions.

Static before/after experiment: synthetic input produced review findings
empty_title, invalid_canonical, meta_noindex, jsonld_invalid; intentionally
corrected synthetic markup produced none of these. Both retained all five
external unknowns. This demonstrates diagnostic sensitivity, not crawling,
indexing, ranking, citation, causal or commercial uplift. No customer source was
modified; noindex can be intentional and requires owner review, not automatic
removal. JSON-LD absence is informational, never treated as an AI requirement.

This is a pure internal function, not a deployed endpoint/UI/complete crawler.
Tenant IDs bind output but are not authentication; caller authorization still
must be enforced in the future composition root. HTMLParser is not a browser's
HTML5 rendering engine, and evidence lines refer to supplied bytes, not live DOM.
UTF-8 input only, 2 MiB and 256 metadata-item caps. Non-2xx status is only a
caller-supplied fact. Hash binds input bytes, not source authenticity. Existing
external event/API/schema/policy/deployment contracts unchanged.

Primary rationale:
https://developers.google.com/search/docs/fundamentals/ai-optimization-guide
https://developers.google.com/search/docs/appearance/ai-features
https://help.openai.com/en/articles/12627856-publishers-and-developers-faq
