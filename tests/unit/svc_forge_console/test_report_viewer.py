"""Opt-in static routes do not change the authenticated report API."""

import pytest
from fastapi.testclient import TestClient
from saena_forge_console.app import create_app
from saena_forge_console.report_store import ReportCatalog

from svc_forge_console.test_verified_auth import key, verifier  # noqa: F401


@pytest.fixture
def viewer(key, tmp_path):  # noqa: F811
    return TestClient(
        create_app(
            token_verifier=verifier(key),
            report_catalog=ReportCatalog(root=str(tmp_path.resolve()), entries={}, readers=set()),
            enable_report_viewer=True,
        )
    )


@pytest.mark.parametrize(
    "path,media",
    [
        ("/report-viewer", "text/html"),
        ("/report-viewer-assets/viewer.css", "text/css"),
        ("/report-viewer-assets/viewer.js", "text/javascript"),
    ],
)
def test_static_allowlist(viewer, path, media):
    response = viewer.get(path)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith(media)
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert "default-src 'none'" in response.headers["content-security-policy"]
    assert "unsafe-inline" not in response.headers["content-security-policy"]


def test_report_still_needs_authentication(viewer):
    assert viewer.get("/v1/html-audit-reports/anything").status_code == 401


@pytest.mark.parametrize(
    "path",
    [
        "/report-viewer-assets/",
        "/report-viewer-assets/app.py",
        "/report-viewer-assets/other.js",
        "/report-viewer-assets/%2e%2e%2fapp.py",
    ],
)
def test_no_directory_exposure(viewer, path):
    assert viewer.get(path).status_code == 404


def test_viewer_is_opt_in(key):  # noqa: F811
    assert (
        TestClient(create_app(token_verifier=verifier(key))).get("/report-viewer").status_code
        == 404
    )


def test_invalid_enable_configuration(key):  # noqa: F811
    with pytest.raises(ValueError):
        create_app(auth_mode="test_headers", enable_report_viewer=True)
    with pytest.raises(ValueError):
        create_app(token_verifier=verifier(key), enable_report_viewer=True)
    with pytest.raises(ValueError):
        create_app(token_verifier=verifier(key), enable_report_viewer="true")


def test_no_storage_or_raw_html_sinks(viewer):
    script = viewer.get("/report-viewer-assets/viewer.js").text
    for forbidden in [
        "localStorage",
        "sessionStorage",
        "innerHTML",
        "document.cookie",
        "console.log",
    ]:
        assert forbidden not in script
    assert 'credentials:"omit"' in script
    assert "pagehide" in script and "pageshow" in script
    html = viewer.get("/report-viewer").text
    assert 'type="password"' in html and 'role="status"' in html
