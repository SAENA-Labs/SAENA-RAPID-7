"""Local signed identity + real offline report producer; no external content."""

import hashlib
import json
import os
from dataclasses import FrozenInstanceError

import pytest
from fastapi.testclient import TestClient
from saena_forge_console.app import create_app
from saena_forge_console.report_store import ReportCatalog, ReportEntry
from saena_pilot.page_audit_report import build_page_audit_report
from saena_site_discovery.page_audit import audit_supplied_html

from svc_forge_console.test_verified_auth import key, token, verifier  # noqa: F401


def digest(data):
    return "sha256:" + hashlib.sha256(data).hexdigest()


def documents():
    audit = audit_supplied_html(
        tenant_id="acme-corp",
        page_url="https://example.invalid/one",
        html=b"<html><head><title>Demo</title></head></html>",
        evidence_ref="local-html://demo",
    )
    report = json.loads(
        build_page_audit_report(
            tenant_id="acme-corp",
            expected_pages=["https://example.invalid/one", "https://example.invalid/missing"],
            audits=[audit],
        ).json_text
    )
    receipt = {
        "tenant_id": "acme-corp",
        "scope": "offline_supplied_html",
        "raw_html_stored": False,
        "manifest_sha256": "sha256:" + "1" * 64,
    }
    return report, receipt


@pytest.fixture
def setup(tmp_path, key, monkeypatch):  # noqa: F811
    monkeypatch.setenv("SAENA_TENANT_ID", "acme-corp")
    root = tmp_path.resolve()
    directory = root / "run-one"
    directory.mkdir(mode=0o700)
    report, receipt = documents()

    class Harness:
        def __init__(self):
            self.report = report
            self.receipt = receipt
            self.root = root
            self.directory = directory
            self.auth = {"Authorization": "Bearer " + token(key)}

        def client(self, report_bytes=None, receipt_bytes=None, readers=None):
            r = report_bytes if report_bytes is not None else json.dumps(self.report).encode()
            c = receipt_bytes if receipt_bytes is not None else json.dumps(self.receipt).encode()
            (directory / "report.json").write_bytes(r)
            (directory / "receipt.json").write_bytes(c)
            self.entry = ReportEntry("acme-corp", "run-one", digest(r), digest(c))
            self.catalog = ReportCatalog(
                root=str(root),
                entries={
                    "known": self.entry,
                    "foreign": ReportEntry("other-corp", "does-not-exist", digest(r), digest(c)),
                },
                readers=readers if readers is not None else {("acme-corp", "actor-0001")},
            )
            return TestClient(create_app(token_verifier=verifier(key), report_catalog=self.catalog))

    return Harness()


def test_real_offline_producer_and_uncertainty_preserved(setup):
    client = setup.client()
    before = (setup.directory / "report.json").read_bytes()
    result = client.get("/v1/html-audit-reports/known", headers=setup.auth)
    assert result.status_code == 200
    assert result.json() == setup.report
    assert result.json()["unmeasured_pages"] == ["https://example.invalid/missing"]
    assert len(result.json()["measured_pages"][0]["unknown"]) >= 5
    assert result.headers["cache-control"] == "no-store"
    assert result.headers["x-content-type-options"] == "nosniff"
    assert before == (setup.directory / "report.json").read_bytes()


def test_unknown_and_foreign_identical(setup):
    client = setup.client()
    results = [
        client.get("/v1/html-audit-reports/" + v, headers=setup.auth)
        for v in ["unknown", "foreign"]
    ]
    assert [r.status_code for r in results] == [404, 404]
    assert results[0].json()["detail"] == results[1].json()["detail"]
    assert all(r.headers["cache-control"] == "no-store" for r in results)


def test_reader_grants_and_authentication(setup):
    client = setup.client(readers=set())
    assert client.get("/v1/html-audit-reports/known", headers=setup.auth).status_code == 403
    assert client.get("/v1/html-audit-reports/known").status_code == 401
    assert (
        client.get(
            "/v1/html-audit-reports/known", headers={**setup.auth, "X-Saena-Roles": "auditor"}
        ).status_code
        == 401
    )


def test_testmode_cannot_expose_api(setup):
    setup.client()
    with pytest.raises(ValueError):
        create_app(auth_mode="test_headers", report_catalog=setup.catalog)


def test_catalog_is_frozen(setup):
    setup.client()
    with pytest.raises(FrozenInstanceError):
        setup.catalog.root = "/"
    with pytest.raises(TypeError):
        setup.catalog.entries["evil"] = setup.entry


@pytest.mark.parametrize("which", ["report.json", "receipt.json"])
def test_changed_bytes_rejected(setup, which):
    client = setup.client()
    (setup.directory / which).write_bytes(b"{}")
    response = client.get("/v1/html-audit-reports/known", headers=setup.auth)
    assert response.status_code == 503
    assert str(setup.root) not in response.text


@pytest.mark.parametrize(
    "mode", ["symlink", "hardlink", "fifo", "writable", "directory", "missing"]
)
def test_unsafe_file_refused(setup, mode):
    client = setup.client()
    p = setup.directory / "report.json"
    if mode == "writable":
        p.chmod(0o666)
    else:
        data = p.read_bytes()
        p.unlink()
        if mode in {"symlink", "hardlink"}:
            other = setup.root / "target"
            other.write_bytes(data)
            if mode == "symlink":
                p.symlink_to(other)
            else:
                os.link(other, p)
        elif mode == "fifo":
            os.mkfifo(p)
        elif mode == "directory":
            p.mkdir()
    assert client.get("/v1/html-audit-reports/known", headers=setup.auth).status_code == 503


def test_directory_symlink_refused(setup):
    client = setup.client()
    moved = setup.root / "moved"
    setup.directory.rename(moved)
    setup.directory.symlink_to(moved)
    assert client.get("/v1/html-audit-reports/known", headers=setup.auth).status_code == 503


@pytest.mark.parametrize(
    "relative", ["../escape", "/etc", "one/../two", "one//two", "one\\two", ".hidden"]
)
def test_bad_catalog_paths(relative):
    with pytest.raises(ValueError):
        ReportEntry("acme-corp", relative, "sha256:" + "1" * 64, "sha256:" + "2" * 64)


@pytest.mark.parametrize(
    "mutation",
    [
        "tenant",
        "scope",
        "count",
        "unknown",
        "lines",
        "digest",
        "limitations",
        "secret",
        "page_secret",
        "extra",
        "duplicatepage",
    ],
)
def test_invalid_semantic_report(setup, mutation):
    report = setup.report
    page = report["measured_pages"][0]
    if mutation == "tenant":
        report["tenant_id"] = "other-corp"
    elif mutation == "scope":
        report["scope"] = "live_citation_success"
    elif mutation == "count":
        report["expected_page_count"] = 3
    elif mutation == "unknown":
        page["unknown"] = []
    elif mutation == "lines":
        page["findings"][0]["lines"] = [-1]
    elif mutation == "digest":
        page["html_sha256"] = "sha256:invalid"
    elif mutation == "limitations":
        report["limitations"] = []
    elif mutation == "secret":
        report["warnings"] = ["sk-proj-" + "x" * 30]
    elif mutation == "page_secret":
        page["page_url"] = "https://example.invalid/?key=sk-proj-" + "x" * 30
    elif mutation == "extra":
        report["unexpected"] = "value"
    elif mutation == "duplicatepage":
        report["unmeasured_pages"] = [page["page_url"]]
    client = setup.client()
    response = client.get("/v1/html-audit-reports/known", headers=setup.auth)
    assert response.status_code == 503
    assert "sk-proj" not in response.text


@pytest.mark.parametrize("mutation", ["tenant", "scope", "raw", "hash"])
def test_receipt_mismatch(setup, mutation):
    if mutation == "tenant":
        setup.receipt["tenant_id"] = "other-corp"
    elif mutation == "scope":
        setup.receipt["scope"] = "live"
    elif mutation == "raw":
        setup.receipt["raw_html_stored"] = True
    else:
        setup.receipt["manifest_sha256"] = "invalid"
    assert setup.client().get("/v1/html-audit-reports/known", headers=setup.auth).status_code == 503


@pytest.mark.parametrize(
    "data",
    [
        b'{"tenant_id":"a","tenant_id":"b"}',
        b'{"x": NaN}',
        b"not JSON",
        b"\xff",
        b"[" * 1000 + b"]" * 1000,
    ],
)
def test_malformed_json(setup, data):
    assert (
        setup.client(report_bytes=data)
        .get("/v1/html-audit-reports/known", headers=setup.auth)
        .status_code
        == 503
    )


def test_limits_before_read(setup, monkeypatch):
    client = setup.client()
    monkeypatch.setattr("saena_forge_console.report_store.REPORT_LIMIT", 32)
    assert client.get("/v1/html-audit-reports/known", headers=setup.auth).status_code == 503


def test_no_other_http_methods(setup):
    client = setup.client()
    assert client.post("/v1/html-audit-reports/known", headers=setup.auth).status_code == 405


def test_tenant_header_mismatch_still_no_store(setup):
    client = setup.client()
    response = client.get(
        "/v1/html-audit-reports/known", headers={**setup.auth, "X-Saena-Tenant-Id": "other-corp"}
    )
    assert response.status_code == 403
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"


def test_zero_measurement_is_preserved(setup):
    setup.report = json.loads(
        build_page_audit_report(
            tenant_id="acme-corp", expected_pages=["https://example.invalid/missing"], audits=[]
        ).json_text
    )
    response = setup.client().get("/v1/html-audit-reports/known", headers=setup.auth)
    assert response.status_code == 200
    assert response.json()["measured_page_count"] == 0
    assert response.json()["unmeasured_pages"] == ["https://example.invalid/missing"]


def test_query_and_role_do_not_select_other_report(setup):
    client = setup.client()
    response = client.get(
        "/v1/html-audit-reports/known?tenant_id=other-corp&path=/etc/passwd", headers=setup.auth
    )
    assert response.status_code == 200
    assert response.json()["tenant_id"] == "acme-corp"


@pytest.mark.parametrize("where", ["value", "key"])
def test_lone_surrogate_sanitized_503(setup, where):
    if where == "value":
        setup.report["warnings"] = [chr(0xD800)]
    else:
        setup.report[chr(0xD800)] = "bad"
    response = setup.client().get("/v1/html-audit-reports/known", headers=setup.auth)
    assert response.status_code == 503
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "d800" not in response.text


def test_other_verified_tenant_and_grant_cannot_read(setup, key, monkeypatch):  # noqa: F811
    from saena_forge_console.verified_auth import Membership

    setup.client()
    catalog = ReportCatalog(
        root=str(setup.root),
        entries={"known": setup.entry},
        readers={("acme-corp", "actor-0001"), ("other-corp", "actor-0002")},
    )
    client = TestClient(
        create_app(
            report_catalog=catalog,
            token_verifier=verifier(
                key, {"subject-2": Membership("actor-0002", "other-corp", frozenset())}
            ),
        )
    )
    monkeypatch.setenv("SAENA_TENANT_ID", "other-corp")
    auth = {"Authorization": "Bearer " + token(key, sub="subject-2")}
    assert client.get("/v1/html-audit-reports/known", headers=auth).status_code == 404
    assert client.get("/v1/html-audit-reports/unknown", headers=auth).status_code == 404


def test_actor_spoof_cannot_gain_read_grant(setup, key):  # noqa: F811
    client = setup.client(readers={("acme-corp", "actor-9999")})
    assert client.get("/v1/html-audit-reports/known", headers=setup.auth).status_code == 403
    assert (
        client.get(
            "/v1/html-audit-reports/known", headers={**setup.auth, "X-Saena-Actor-Id": "actor-9999"}
        ).status_code
        == 401
    )


def test_receipt_limit_before_parsing(setup, monkeypatch):
    client = setup.client()
    monkeypatch.setattr("saena_forge_console.report_store.RECEIPT_LIMIT", 32)
    assert client.get("/v1/html-audit-reports/known", headers=setup.auth).status_code == 503


@pytest.mark.parametrize("depth,allowed", [(16, True), (17, False)])
def test_json_depth_limit(depth, allowed):
    from saena_forge_console.report_store import _json

    data = b"[" * depth + b'"value"' + b"]" * depth
    if allowed:
        _json(data)
    else:
        with pytest.raises(ValueError, match="complexity"):
            _json(data)


@pytest.mark.parametrize("items,allowed", [(99999, True), (100000, False)])
def test_json_node_limit(items, allowed):
    from saena_forge_console.report_store import _json

    data = json.dumps([None] * items).encode()
    if allowed:
        _json(data)
    else:
        with pytest.raises(ValueError, match="complexity"):
            _json(data)
