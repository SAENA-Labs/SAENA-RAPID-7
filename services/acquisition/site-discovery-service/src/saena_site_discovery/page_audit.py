"""Offline metadata diagnostics, never a crawler, ranking score or index check."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

MAX_HTML_BYTES = 2 * 1024 * 1024
MAX_METADATA_ITEMS = 256
UNKNOWN_EXTERNAL_FACTS = (
    "robots_txt",
    "http_headers",
    "cdn_access",
    "actual_index_state",
    "render_completeness",
)


@dataclass(frozen=True)
class Finding:
    code: str
    level: str
    lines: tuple[int, ...]
    detail: str


@dataclass(frozen=True)
class PageAudit:
    tenant_id: str
    page_url: str
    evidence_ref: str
    html_sha256: str
    supplied_http_status: int | None
    findings: tuple[Finding, ...]
    unknown: tuple[str, ...] = UNKNOWN_EXTERNAL_FACTS


class _MetadataParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.in_head = False
        self.ignored = 0
        self.title: tuple[int, list[str]] | None = None
        self.ld: tuple[int, list[str]] | None = None
        self.titles: list[tuple[int, str]] = []
        self.canonicals: list[tuple[int, str]] = []
        self.robots: list[tuple[int, str, str]] = []
        self.jsonld: list[tuple[int, str]] = []
        self.items = 0
        self.ambiguous: list[int] = []

    def _item(self) -> None:
        self.items += 1
        if self.items > MAX_METADATA_ITEMS:
            raise ValueError("too many metadata items")

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"template", "noscript"}:
            self.ignored += 1
        if self.ignored:
            return
        if tag == "head":
            self.in_head = True
        if tag == "body":
            self.in_head = False
        values = dict(attrs)
        line = self.getpos()[0]
        relevant = (self.in_head and tag in {"title", "link", "meta"}) or tag == "script"
        if relevant and len(values) != len(attrs):
            self.ambiguous.append(line)
            return  # Duplicate attributes have no reliable selected value here.
        if self.in_head and tag == "title":
            self._item()
            self.title = (line, [])
        elif (
            self.in_head
            and tag == "link"
            and "canonical" in (values.get("rel") or "").lower().split()
        ):
            self._item()
            self.canonicals.append((line, values.get("href") or ""))
        elif (
            self.in_head
            and tag == "meta"
            and (values.get("name") or "").lower() in {"robots", "googlebot"}
        ):
            self._item()
            self.robots.append((line, (values["name"] or "").lower(), values.get("content") or ""))
        elif (
            tag == "script" and (values.get("type") or "").strip().lower() == "application/ld+json"
        ):
            self._item()
            self.ld = (line, [])

    def handle_data(self, data: str) -> None:
        if self.ignored:
            return
        if self.title is not None:
            self.title[1].append(data)
        if self.ld is not None:
            self.ld[1].append(data)

    def handle_endtag(self, tag: str) -> None:
        if self.ignored:
            if tag in {"template", "noscript"}:
                self.ignored -= 1
            return
        if tag == "title" and self.title is not None:
            self.titles.append((self.title[0], "".join(self.title[1]).strip()))
            self.title = None
        if tag == "script" and self.ld is not None:
            self.jsonld.append((self.ld[0], "".join(self.ld[1])))
            self.ld = None
        if tag in {"head", "body"}:
            self.in_head = False


def _web_url(value: str) -> bool:
    try:
        parsed = urlsplit(value)
        _ = parsed.port
        return (
            parsed.scheme in {"http", "https"}
            and bool(parsed.hostname)
            and parsed.username is None
            and parsed.password is None
            and not any(char.isspace() or ord(char) < 32 for char in value)
        )
    except ValueError:
        return False


def _reject_constant(value: str) -> None:
    raise ValueError(f"nonstandard JSON constant: {value}")


def audit_supplied_html(
    *, tenant_id: str, page_url: str, html: bytes, evidence_ref: str, http_status: int | None = None
) -> PageAudit:
    """Inspect exact UTF-8 input. External permissions/indexing remain unknown.

    A caller must preserve tenant authorization before supplying bytes. A tenant
    label here binds output, but is not itself authentication or access control.
    Caller-supplied status is not a verified fetch; no network operation occurs.
    """
    if not tenant_id.strip() or not evidence_ref.strip():
        raise ValueError("tenant_id and evidence_ref are required")
    if not _web_url(page_url):
        raise ValueError("page_url must be an absolute credential-free HTTP(S) URL")
    if not isinstance(html, bytes) or not html.strip() or len(html) > MAX_HTML_BYTES:
        raise ValueError("html must be nonempty bounded bytes")
    if http_status is not None and (type(http_status) is not int or not 100 <= http_status <= 599):
        raise ValueError("http_status must be an HTTP status integer")
    parser = _MetadataParser()
    parser.feed(html.decode("utf-8-sig", errors="strict"))
    parser.close()
    findings: list[Finding] = []

    def add(code: str, level: str, lines: tuple[int, ...], detail: str) -> None:
        findings.append(Finding(code, level, lines, detail))

    if http_status is not None and not 200 <= http_status < 300:
        add(
            "non_success_status",
            "review",
            (),
            "Supplied HTTP status is not 2xx; verify actual response.",
        )
    if parser.ambiguous or parser.title is not None or parser.ld is not None:
        add(
            "ambiguous_markup",
            "review",
            tuple(parser.ambiguous),
            "Duplicate attributes or unclosed metadata; do not treat this as a browser DOM audit.",
        )
    if not parser.titles:
        add(
            "title_not_observed",
            "review",
            (),
            "No closed title found in an explicit head; verify rendered document.",
        )
    else:
        add(
            "title_present",
            "info",
            tuple(x[0] for x in parser.titles),
            "Title markup observed; relevance and quality not scored.",
        )
        if any(not value for _, value in parser.titles):
            add(
                "empty_title",
                "review",
                tuple(line for line, value in parser.titles if not value),
                "Empty title observed.",
            )
        if len(parser.titles) > 1:
            add(
                "multiple_titles",
                "review",
                tuple(x[0] for x in parser.titles),
                "Multiple titles; review rendered head.",
            )
    if not parser.canonicals:
        add(
            "canonical_not_observed",
            "info",
            (),
            "No canonical in supplied head; absence alone is not an indexing failure.",
        )
    for line, href in parser.canonicals:
        try:
            parsed_href = urlsplit(href)
            target = href if parsed_href.scheme else urljoin(page_url, href)
            valid = bool(href.strip()) and _web_url(target)
        except ValueError:
            valid = False
        add(
            "canonical_present" if valid else "invalid_canonical",
            "info" if valid else "review",
            (line,),
            "Canonical markup observed; chosen canonical and target existence remain unknown."
            if valid
            else "Canonical target is missing or invalid.",
        )
    if len(parser.canonicals) > 1:
        add(
            "multiple_canonicals",
            "review",
            tuple(x[0] for x in parser.canonicals),
            "Multiple canonical declarations require review; no target selected automatically.",
        )
    for line, agent, content in parser.robots:
        tokens = set(re.split(r"[\s,]+", content.lower()))
        if tokens & {"noindex", "none"}:
            add(
                "meta_noindex",
                "review",
                (line,),
                f"{agent} meta contains noindex/none; verify whether exclusion is intentional.",
            )
        if "nosnippet" in tokens or re.search(
            r"(?:^|[\s,])max-snippet\s*:\s*0(?:$|[\s,])", content.lower()
        ):
            add(
                "meta_snippet_restriction",
                "review",
                (line,),
                f"{agent} meta restricts snippets; verify intended policy.",
            )
    if not parser.jsonld:
        add(
            "jsonld_not_observed",
            "info",
            (),
            "No closed JSON-LD block found; not a prerequisite for AI search inclusion.",
        )
    for line, raw in parser.jsonld:
        try:
            payload = json.loads(raw, parse_constant=_reject_constant)
            valid = isinstance(payload, (dict, list))
        except (ValueError, RecursionError):
            valid = False
        add(
            "jsonld_syntax_valid" if valid else "jsonld_invalid",
            "info" if valid else "review",
            (line,),
            "JSON syntax/object-array shape only; schema semantics and truth unverified."
            if valid
            else "Invalid JSON or non-object/array JSON-LD root.",
        )
    return PageAudit(
        tenant_id,
        page_url,
        evidence_ref,
        "sha256:" + hashlib.sha256(html).hexdigest(),
        http_status,
        tuple(findings),
    )
