"""Approved catalog of immutable local HTML diagnostic reports, never a fetcher."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from urllib.parse import urlsplit

REPORT_LIMIT = 8 * 1024 * 1024
RECEIPT_LIMIT = 64 * 1024
UNKNOWN = {"robots_txt", "http_headers", "cdn_access", "actual_index_state", "render_completeness"}
LIMITATIONS = {
    "Not a live fetch, index, citation, traffic or revenue measurement.",
    "No findings on supplied HTML is not proof of eligibility or success.",
    "Tenant label and input hash are not authentication or source truth.",
}
# Boundary-owned copy per saena_pilot.secretguard convention. No weakening by
# cross-package refactors; guard decoded JSON keys as well as values.
_SECRET = tuple(
    re.compile(p)
    for p in (
        r"sk-[A-Za-z0-9]{20,}",
        r"AKIA[0-9A-Z]{16}",
        r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}",
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
        r"gh[opsu]_[A-Za-z0-9]{36}",
        r"xox[baprs]-[A-Za-z0-9-]{10,}",
        r"AIza[0-9A-Za-z_-]{35}",
        r"\b[sr]k_(live|test)_[A-Za-z0-9]{10,}",
        r"\b[sr]k-(live|test)-[A-Za-z0-9]{10,}",
        r"sk-(proj|svcacct|admin)-[A-Za-z0-9_-]{20,}",
        r"github_pat_[A-Za-z0-9_]{22,}",
        r"\bglpat-[A-Za-z0-9_-]{20,}",
    )
)


def _text(value: object) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 4096:
        raise ValueError("invalid text")
    return value


def _digest(value: object) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", value):
        raise ValueError("invalid digest")
    return value


def _parts(value: str) -> tuple[str, ...]:
    if not isinstance(value, str) or not value or "\\" in value or value.startswith("/"):
        raise ValueError("invalid relative directory")
    parts = tuple(value.split("/"))
    if any(not p or p.startswith(".") or "\x00" in p for p in parts):
        raise ValueError("invalid relative directory")
    return parts


def _trusted_dir(fd: int) -> None:
    info = os.fstat(fd)
    if info.st_uid not in {0, os.getuid()}:
        raise ValueError("untrusted directory owner")
    if info.st_mode & 0o022 and not (info.st_uid == 0 and info.st_mode & stat.S_ISVTX):
        raise ValueError("writable directory")


def _open_directory(root: str, relative: str) -> int:
    path = Path(root)
    if not path.is_absolute() or str(path) != root or any(p in {".", ".."} for p in path.parts):
        raise ValueError("canonical absolute root required")
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in (*path.parts[1:], *_parts(relative)):
            nxt = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = nxt
            _trusted_dir(fd)
        return fd
    except BaseException:
        os.close(fd)
        raise


def _read(fd: int, name: str, limit: int, digest: str) -> bytes:
    target = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
    with os.fdopen(target, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > limit:
            raise ValueError("unsafe report file")
        if info.st_uid not in {0, os.getuid()} or info.st_mode & 0o022:
            raise ValueError("untrusted report file")
        data = stream.read(limit + 1)
    if len(data) > limit or "sha256:" + hashlib.sha256(data).hexdigest() != digest:
        raise ValueError("report byte binding failed")
    return data


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _json(data: bytes):
    obj = json.loads(
        data.decode("utf-8"),
        object_pairs_hook=_pairs,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite JSON")),
    )
    pending = [(obj, 0)]
    nodes = 0
    while pending:
        value, depth = pending.pop()
        nodes += 1
        if depth > 16 or nodes > 100000:
            raise ValueError("JSON complexity limit")
        if isinstance(value, str):
            # JSON permits escaped lone surrogates; HTTP UTF-8 does not.
            value.encode("utf-8", errors="strict")
            if any(p.search(value) for p in _SECRET):
                raise ValueError("secret-shaped value")
        if isinstance(value, dict):
            pending.extend((v, depth + 1) for pair in value.items() for v in pair)
        elif isinstance(value, list):
            pending.extend((v, depth + 1) for v in value)
    return obj


def _url(value):
    text = _text(value)
    parsed = urlsplit(text)
    _ = parsed.port
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or any(c.isspace() or ord(c) < 32 for c in text)
    ):
        raise ValueError("invalid page URL")
    return text


def _string_list(value, limit):
    if not isinstance(value, list) or len(value) > limit:
        raise ValueError("invalid list")
    return [_text(item) for item in value]


def _validate(report, receipt, tenant):
    if not isinstance(receipt, dict) or set(receipt) != {
        "tenant_id",
        "manifest_sha256",
        "scope",
        "raw_html_stored",
    }:
        raise ValueError("invalid receipt")
    if (
        receipt["tenant_id"] != tenant
        or receipt["scope"] != "offline_supplied_html"
        or receipt["raw_html_stored"] is not False
    ):
        raise ValueError("receipt scope mismatch")
    _digest(receipt["manifest_sha256"])
    fields = {
        "tenant_id",
        "scope",
        "expected_page_count",
        "measured_page_count",
        "unmeasured_pages",
        "measured_pages",
        "warnings",
        "limitations",
    }
    if (
        not isinstance(report, dict)
        or set(report) != fields
        or report["tenant_id"] != tenant
        or report["scope"] != "offline_supplied_html"
    ):
        raise ValueError("report scope mismatch")
    expected, measured = report["expected_page_count"], report["measured_page_count"]
    if (
        type(expected) is not int
        or type(measured) is not int
        or not 0 <= measured <= expected <= 1000
        or expected == 0
    ):
        raise ValueError("invalid cohort")
    missing = [_url(v) for v in _string_list(report["unmeasured_pages"], 1000)]
    pages = report["measured_pages"]
    if not isinstance(pages, list) or len(pages) != measured or measured + len(missing) != expected:
        raise ValueError("incomplete cohort")
    _string_list(report["warnings"], 1000)
    if not set(_string_list(report["limitations"], 32)) >= LIMITATIONS:
        raise ValueError("missing limitations")
    urls, evidence, findings_count = list(missing), {}, 0
    for page in pages:
        if not isinstance(page, dict) or set(page) != {
            "page_url",
            "measurement",
            "evidence_ref",
            "html_sha256",
            "supplied_http_status",
            "findings",
            "unknown",
        }:
            raise ValueError("invalid page")
        urls.append(_url(page["page_url"]))
        if (
            page["measurement"] != "supplied_html_only"
            or not set(_string_list(page["unknown"], 64)) >= UNKNOWN
        ):
            raise ValueError("missing uncertainty")
        ref, digest = _text(page["evidence_ref"]), _digest(page["html_sha256"])
        if ref in evidence and evidence[ref] != digest:
            raise ValueError("conflicting evidence")
        evidence[ref] = digest
        status = page["supplied_http_status"]
        if status is not None and (type(status) is not int or not 100 <= status <= 599):
            raise ValueError("invalid asserted status")
        findings = page["findings"]
        if not isinstance(findings, list) or len(findings) > 1024:
            raise ValueError("invalid findings")
        findings_count += len(findings)
        for finding in findings:
            if not isinstance(finding, dict) or set(finding) != {
                "code",
                "level",
                "lines",
                "detail",
            }:
                raise ValueError("invalid finding")
            _text(finding["code"])
            _text(finding["detail"])
            lines = finding["lines"]
            if (
                finding["level"] not in {"info", "review"}
                or not isinstance(lines, list)
                or len(lines) > 256
                or any(type(n) is not int or not 1 <= n <= 2147483647 for n in lines)
            ):
                raise ValueError("invalid evidence lines")
    if len(set(urls)) != expected or findings_count > 4096:
        raise ValueError("duplicate cohort or excessive findings")


@dataclass(frozen=True, slots=True)
class ReportEntry:
    tenant_id: str
    relative_directory: str
    report_sha256: str
    receipt_sha256: str

    def __post_init__(self):
        _text(self.tenant_id)
        _parts(self.relative_directory)
        _digest(self.report_sha256)
        _digest(self.receipt_sha256)


@dataclass(frozen=True, slots=True, init=False)
class ReportCatalog:
    root: str
    entries: Mapping[str, ReportEntry]
    readers: frozenset[tuple[str, str]]

    def __init__(self, *, root: str, entries: Mapping[str, ReportEntry], readers):
        object.__setattr__(self, "root", root)
        if len(entries) > 10000:
            raise ValueError("catalog limit")
        for key, value in entries.items():
            if (
                not isinstance(key, str)
                or not re.fullmatch(r"[a-zA-Z0-9_-]{1,128}", key)
                or not isinstance(value, ReportEntry)
            ):
                raise ValueError("invalid catalog")
        object.__setattr__(self, "entries", MappingProxyType(dict(entries)))
        object.__setattr__(self, "readers", frozenset(readers))
        if len(self.readers) > 10000 or any(
            not isinstance(v, tuple)
            or len(v) != 2
            or any(not isinstance(s, str) or not s.strip() for s in v)
            for v in self.readers
        ):
            raise ValueError("invalid reader grants")

    def read(self, entry: ReportEntry):
        fd = _open_directory(self.root, entry.relative_directory)
        try:
            report = _json(_read(fd, "report.json", REPORT_LIMIT, entry.report_sha256))
            receipt = _json(_read(fd, "receipt.json", RECEIPT_LIMIT, entry.receipt_sha256))
        finally:
            os.close(fd)
        _validate(report, receipt, entry.tenant_id)
        return report
