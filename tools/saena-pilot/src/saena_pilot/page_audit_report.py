"""Pure, bounded single-tenant reporting for supplied-HTML diagnostics.

No network or writes. This binds an asserted tenant, not authentication. The
caller must authorize input first. No visibility/lift or index eligibility score.
"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlsplit

from saena_pilot.secretguard import guard_tree

MAX_PAGES = 1000
MAX_REPORT_CHARS = 1024 * 1024
MAX_TOTAL_FINDINGS = 4096
REQUIRED_UNKNOWNS = (
    "robots_txt",
    "http_headers",
    "cdn_access",
    "actual_index_state",
    "render_completeness",
)


class FindingLike(Protocol):
    code: str
    level: str
    lines: tuple[int, ...]
    detail: str


class AuditLike(Protocol):
    tenant_id: str
    page_url: str
    evidence_ref: str
    html_sha256: str
    supplied_http_status: int | None
    findings: tuple[FindingLike, ...]
    unknown: tuple[str, ...]


@dataclass(frozen=True)
class AuditReport:
    json_text: str
    human_text: str


def _text(value: object) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 4096:
        raise ValueError("report input requires bounded nonempty strings")
    return value


def _url(value: object) -> str:
    value = _text(value)
    try:
        parsed = urlsplit(value)
        _ = parsed.port
        valid = (
            parsed.scheme in {"https", "http"}
            and parsed.hostname
            and parsed.username is None
            and parsed.password is None
            and not any(c.isspace() or ord(c) < 32 for c in value)
        )
    except ValueError:
        valid = False
    if not valid:
        raise ValueError("invalid credential-free page URL")
    return value


def build_page_audit_report(
    *, tenant_id: str, expected_pages: Sequence[str], audits: Sequence[AuditLike]
) -> AuditReport:
    """Return guarded JSON/text. Missing snapshots never count as clean pages.

    Exact page identities, not URL normalization, define this report cohort.
    Multiple snapshots for one URL require explicit caller selection, not an
    arbitrary merge. Identical duplicate inputs are collapsed with a warning.
    """
    tenant_id = _text(tenant_id)
    if isinstance(expected_pages, (str, bytes)) or isinstance(audits, (str, bytes)):
        raise ValueError("expected_pages and audits must be bounded sequences")
    if not 0 < len(expected_pages) <= MAX_PAGES or len(audits) > MAX_PAGES:
        raise ValueError("report cohort exceeds bounds or is empty")
    expected = sorted(set(_url(page) for page in expected_pages))
    characters = len(tenant_id) + sum(len(p) for p in expected)
    total_findings = 0

    def consume(*values: str) -> None:
        nonlocal characters
        characters += sum(len(value) for value in values)
        if characters > MAX_REPORT_CHARS:
            raise ValueError("total report text exceeds bounds")

    consume()
    pages: dict[str, dict[str, object]] = {}
    warnings: set[str] = set()
    evidence_hashes: dict[str, str] = {}
    hash_pages: dict[str, set[str]] = {}
    for audit in audits:
        if audit.tenant_id != tenant_id:
            raise ValueError("mixed tenant audit input refused")
        page = _url(audit.page_url)
        if page not in expected:
            raise ValueError("audit page outside requested cohort")
        evidence = _text(audit.evidence_ref)
        digest = _text(audit.html_sha256)
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
            raise ValueError("invalid HTML evidence hash")
        if evidence in evidence_hashes and evidence_hashes[evidence] != digest:
            raise ValueError("evidence reference binds conflicting hashes")
        evidence_hashes[evidence] = digest
        hash_pages.setdefault(digest, set()).add(page)
        if audit.supplied_http_status is not None and (
            type(audit.supplied_http_status) is not int
            or not 100 <= audit.supplied_http_status <= 599
        ):
            raise ValueError("invalid supplied status")
        consume(page, evidence, digest)
        total_findings += len(audit.findings)
        if total_findings > MAX_TOTAL_FINDINGS:
            raise ValueError("total findings exceed bounds")
        if len(audit.findings) > 1024 or len(audit.unknown) > 64:
            raise ValueError("audit metadata exceeds report bounds")
        findings = []
        for finding in audit.findings:
            if finding.level not in {"info", "review"}:
                raise ValueError("unsupported diagnostic level")
            if len(finding.lines) > 256 or any(
                type(n) is not int or not 1 <= n <= 2147483647 for n in finding.lines
            ):
                raise ValueError("invalid evidence line references")
            consume(_text(finding.code), _text(finding.detail))
            findings.append(
                dict(
                    code=_text(finding.code),
                    level=finding.level,
                    lines=sorted(set(finding.lines)),
                    detail=_text(finding.detail),
                )
            )
        findings.sort(key=lambda f: (f["code"], f["level"], f["lines"], f["detail"]))
        unknown = sorted(set(REQUIRED_UNKNOWNS) | {_text(v) for v in audit.unknown})
        consume(*unknown)
        record = dict(
            page_url=page,
            measurement="supplied_html_only",
            evidence_ref=evidence,
            html_sha256=digest,
            supplied_http_status=audit.supplied_http_status,
            findings=findings,
            unknown=unknown,
        )
        if page in pages:
            if pages[page] != record:
                raise ValueError("multiple conflicting snapshots for one page")
            warnings.add("duplicate_snapshot_collapsed")
        pages[page] = record
    if any(len(items) > 1 for items in hash_pages.values()):
        warnings.add("identical_html_across_pages_not_independent_observation")
    missing = [p for p in expected if p not in pages]
    ordered = [pages[p] for p in sorted(pages)]
    report = dict(
        tenant_id=tenant_id,
        scope="offline_supplied_html",
        expected_page_count=len(expected),
        measured_page_count=len(pages),
        unmeasured_pages=missing,
        measured_pages=ordered,
        warnings=sorted(warnings),
        limitations=[
            "Not a live fetch, index, citation, traffic or revenue measurement.",
            "No findings on supplied HTML is not proof of eligibility or success.",
            "Tenant label and input hash are not authentication or source truth.",
        ],
    )
    guard_tree(report, path="html_audit_report")
    json_text = json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n"

    # JSON quoting keeps untrusted newlines/control characters from spoofing rows.
    def quote(value: object) -> str:
        return json.dumps(value, ensure_ascii=False)

    lines = [
        "Supplied-HTML audit (not live search performance)",
        f"Tenant: {quote(tenant_id)}",
        f"Measured: {len(pages)} / expected: {len(expected)}",
        f"Unmeasured: {quote(missing)}",
    ]
    for record in ordered:
        lines.extend(
            [
                f"Page: {quote(record['page_url'])}",
                f"Evidence: {quote(record['evidence_ref'])} {record['html_sha256']}",
                f"Supplied HTTP status: {record['supplied_http_status']}",
                f"Unknown: {quote(record['unknown'])}",
            ]
        )
        for finding in record["findings"]:
            lines.append(
                f"  {finding['level']} {quote(finding['code'])} lines={finding['lines']}: "
                f"{quote(finding['detail'])}"
            )
    lines.extend(["Warnings: " + quote(sorted(warnings)), *report["limitations"]])
    return AuditReport(json_text, "\n".join(lines) + "\n")
