"""Immutable operator-approved observation cohorts; no network or raw content."""

import os
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType
from urllib.parse import urlsplit

from saena_schemas.domain.platform_observation_v1 import PlatformObservation

from saena_forge_console.report_store import _digest, _json, _open_directory, _parts, _read

LIMITATIONS = [
    "Counts are supplied ChatGPT Search citation occurrences, not causal lift or revenue.",
    "Missing observations are unmeasured, not zero-citation observations.",
    "File hashes bind approved bytes; raw artifact provenance is not independently verified.",
]


def opaque(value):
    if not isinstance(value, str) or not 1 <= len(value) <= 128:
        raise ValueError("invalid identifier")
    return value


@dataclass(frozen=True, slots=True)
class ObservationEntry:
    tenant_id: str
    relative_directory: str
    sha256: str

    def __post_init__(self):
        if not re.fullmatch(r"[a-z0-9]([a-z0-9-]{1,30}[a-z0-9])", self.tenant_id):
            raise ValueError("invalid tenant")
        _parts(self.relative_directory)
        _digest(self.sha256)


@dataclass(frozen=True, slots=True, init=False)
class ObservationCatalog:
    root: str
    entries: object
    readers: frozenset

    def __init__(self, *, root, entries, readers):
        if not isinstance(root, str) or not os.path.isabs(root) or len(entries) > 10000:
            raise ValueError("invalid catalog")
        for name, entry in entries.items():
            if (
                not isinstance(name, str)
                or not re.fullmatch(r"[a-zA-Z0-9_-]{1,128}", name)
                or not isinstance(entry, ObservationEntry)
            ):
                raise ValueError("invalid catalog entry")
        grants = frozenset(readers)
        if len(grants) > 10000 or any(
            not isinstance(g, tuple)
            or len(g) != 2
            or any(not isinstance(s, str) or not s for s in g)
            for g in grants
        ):
            raise ValueError("invalid grants")
        object.__setattr__(self, "root", root)
        object.__setattr__(self, "entries", MappingProxyType(dict(entries)))
        object.__setattr__(self, "readers", grants)

    def read(self, collection_id):
        entry = self.entries[collection_id]
        fd = _open_directory(self.root, entry.relative_directory)
        try:
            data = _json(_read(fd, "observations.json", 8 * 1024 * 1024, entry.sha256))
        finally:
            os.close(fd)
        return aggregate(data, collection_id, entry.tenant_id)


def aggregate(data, collection_id, tenant_id):
    if (
        not isinstance(data, dict)
        or set(data) != {"schema_version", "tenant_id", "expected_observation_ids", "observations"}
        or type(data["schema_version"]) is not int
        or data["schema_version"] != 1
        or data["tenant_id"] != tenant_id
    ):
        raise ValueError("invalid collection")
    expected, rows = data["expected_observation_ids"], data["observations"]
    if (
        not isinstance(expected, list)
        or len(expected) > 10000
        or not isinstance(rows, list)
        or len(rows) > 10000
    ):
        raise ValueError("invalid cohort")
    wanted = {opaque(v) for v in expected}
    if len(wanted) != len(expected):
        raise ValueError("duplicate cohort")
    seen, domains, days, day_citations, provenance = set(), Counter(), Counter(), Counter(), []
    total = 0
    for row in rows:
        # Existing generated closed contract; additional strict checks below do
        # not relax its engine/tenant/provenance conventions.
        PlatformObservation.model_validate(row)
        oid = opaque(row["observation_id"])
        if (
            row["tenant_id"] != tenant_id
            or row["engine_id"] != "chatgpt-search"
            or oid in seen
            or oid not in wanted
        ):
            raise ValueError("observation scope mismatch")
        captured = row["captured_at"]
        datetime.fromisoformat(captured.replace("Z", "+00:00"))
        refs = row["citation_refs"]
        total += len(refs)
        if total > 100000:
            raise ValueError("citation limit")
        for ref in refs:
            url = urlsplit(ref)
            host = url.hostname
            if (
                url.scheme not in {"https", "http"}
                or url.username
                or url.password
                or url.query
                or url.fragment
                or not host
                or len(host) > 253
                or not re.fullmatch(r"[a-z0-9.-]+", host)
                or host.startswith(".")
                or host.endswith(".")
                or ".." in host
            ):
                raise ValueError("invalid citation domain")
            _ = url.port
            domains[host] += 1
            if len(domains) > 10000:
                raise ValueError("domain limit")
        seen.add(oid)
        day = captured[:10]
        days[day] += 1
        day_citations[day] += len(refs)
        provenance.append(
            {"observation_id": oid, "artifact_hash": row["artifact_hash"], "captured_at": captured}
        )
    return {
        "schema_version": 1,
        "collection_id": collection_id,
        "tenant_id": tenant_id,
        "engine_id": "chatgpt-search",
        "status": "measured" if seen else "unmeasured",
        "sample_count": len(seen),
        "total_citations": total,
        "unique_domains": len(domains),
        "by_day": [
            {"date": day, "sample_count": days[day], "citation_count": day_citations[day]}
            for day in sorted(days)
        ],
        "domain_counts": [
            {"domain": domain, "count": domains[domain]} for domain in sorted(domains)
        ],
        "evidence_ids": sorted(seen),
        "coverage": {
            "expected_samples": len(wanted),
            "measured_samples": len(seen),
            "missing_samples": len(wanted - seen),
        },
        "provenance": sorted(provenance, key=lambda p: p["observation_id"]),
        "limitations": LIMITATIONS.copy(),
    }
