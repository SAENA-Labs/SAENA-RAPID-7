"""Synthetic stored cohort -> signed-token API, never real provider calls."""

import hashlib
import json

import pytest
from fastapi.testclient import TestClient
from saena_forge_console.app import create_app
from saena_forge_console.ui_observation_store import ObservationCatalog, ObservationEntry, aggregate

from svc_forge_console.test_verified_auth import key, token, verifier  # noqa: F401


def observation(refs=None):
    return {
        "tenant_id": "acme-corp",
        "run_id": "run-1",
        "engine_id": "chatgpt-search",
        "observation_id": "obs-1",
        "raw_object_ref": "local-capture://one",
        "artifact_hash": "sha256:" + "1" * 64,
        "citation_refs": refs
        if refs is not None
        else ["https://example.invalid/a", "https://example.invalid/b"],
        "captured_at": "2026-11-14T03:00:00Z",
    }


def source(rows=None):
    return {
        "schema_version": 1,
        "tenant_id": "acme-corp",
        "expected_observation_ids": ["obs-1", "obs-missing"],
        "observations": rows if rows is not None else [observation()],
    }


def test_counts_and_missing():
    result = aggregate(source(), "known", "acme-corp")
    assert result["total_citations"] == 2
    assert result["unique_domains"] == 1
    assert result["coverage"] == {
        "expected_samples": 2,
        "measured_samples": 1,
        "missing_samples": 1,
    }
    assert result["domain_counts"] == [{"domain": "example.invalid", "count": 2}]
    assert result["by_day"] == [{"date": "2026-11-14", "sample_count": 1, "citation_count": 2}]
    assert "raw_object_ref" not in json.dumps(result)


def test_zero_vs_unmeasured():
    assert aggregate(source([]), "known", "acme-corp")["status"] == "unmeasured"
    r = aggregate(source([observation([])]), "known", "acme-corp")
    assert r["status"] == "measured" and r["total_citations"] == 0


@pytest.mark.parametrize(
    "field,value",
    [
        ("tenant_id", "other-corp"),
        ("engine_id", "gemini"),
        ("artifact_hash", "bad"),
        ("captured_at", "2026-02-31T00:00:00Z"),
        ("citation_refs", ["artifact://opaque"]),
        ("citation_refs", ["https://user:pass@example.invalid/a"]),
        ("citation_refs", ["https://example.invalid/a?secret=yes"]),
    ],
)
def test_invalid_observation(field, value):
    row = observation()
    row[field] = value
    with pytest.raises(ValueError):
        aggregate(source([row]), "known", "acme-corp")


def test_duplicates_and_unknown():
    with pytest.raises(ValueError):
        aggregate(source([observation(), observation()]), "known", "acme-corp")
    data = source()
    data["expected_observation_ids"] = ["other"]
    with pytest.raises(ValueError):
        aggregate(data, "known", "acme-corp")
    data = source()
    data["expected_observation_ids"] = ["obs-1", "obs-1"]
    with pytest.raises(ValueError):
        aggregate(data, "known", "acme-corp")


@pytest.fixture
def setup(tmp_path, key, monkeypatch):  # noqa: F811
    monkeypatch.setenv("SAENA_TENANT_ID", "acme-corp")
    directory = tmp_path.resolve() / "collection-a"
    directory.mkdir(mode=0o700)
    data = json.dumps(source()).encode()
    path = directory / "observations.json"
    path.write_bytes(data)
    entry = ObservationEntry(
        "acme-corp", "collection-a", "sha256:" + hashlib.sha256(data).hexdigest()
    )

    def client(readers=None):
        catalog = ObservationCatalog(
            root=str(tmp_path.resolve()),
            entries={
                "known": entry,
                "foreign": ObservationEntry("other-corp", "collection-a", entry.sha256),
            },
            readers=readers if readers is not None else {("acme-corp", "actor-0001")},
        )
        return TestClient(create_app(token_verifier=verifier(key), observation_catalog=catalog))

    return client, path, {"Authorization": "Bearer " + token(key)}


def test_real_file_signed_token_api(setup):
    client, path, headers = setup
    before = path.read_bytes()
    r = client().get("/v1/ui-observations/known", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["sample_count"] == 1
    assert r.headers["cache-control"] == "no-store"
    assert path.read_bytes() == before


def test_auth_scope_and_hash(setup):
    client, path, headers = setup
    assert client().get("/v1/ui-observations/known").status_code == 401
    assert client(set()).get("/v1/ui-observations/known", headers=headers).status_code == 403
    for name in ["foreign", "missing"]:
        assert client().get("/v1/ui-observations/" + name, headers=headers).status_code == 404
    path.write_text("{}")
    r = client().get("/v1/ui-observations/known", headers=headers)
    assert r.status_code == 503 and r.json()["detail"] == "observations unavailable"


def test_header_mode_refused():
    catalog = ObservationCatalog(root="/tmp", entries={}, readers=set())
    with pytest.raises(ValueError):
        create_app(auth_mode="test_headers", observation_catalog=catalog)


def test_domain_output_bound():
    refs = [f"https://host-{n}.invalid/a" for n in range(10001)]
    with pytest.raises(ValueError, match="domain limit"):
        aggregate(source([observation(refs)]), "known", "acme-corp")
