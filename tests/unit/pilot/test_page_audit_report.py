"""Offline adapter fixtures; no customer or provider data."""

import json
from dataclasses import dataclass, replace

import pytest
from saena_pilot.errors import SecretShapedValueError
from saena_pilot.page_audit_report import build_page_audit_report


@dataclass(frozen=True)
class Finding:
    code: str = "title_not_observed"
    level: str = "review"
    lines: tuple[int, ...] = (3,)
    detail: str = "Verify rendered title."


@dataclass(frozen=True)
class Audit:
    tenant_id: str = "tenant-a"
    page_url: str = "https://example.com/a"
    evidence_ref: str = "artifact://a"
    html_sha256: str = "sha256:" + "a" * 64
    supplied_http_status: int | None = 200
    findings: tuple = (Finding(),)
    unknown: tuple = ("actual_index_state",)


def build(audits=(), expected=("https://example.com/a",)):
    return build_page_audit_report(tenant_id="tenant-a", expected_pages=expected, audits=audits)


def test_missing_not_clean_and_evidence_preserved():
    report = build([Audit()], ("https://example.com/a", "https://example.com/b"))
    data = json.loads(report.json_text)
    assert data["measured_page_count"] == 1 and data["expected_page_count"] == 2
    assert data["unmeasured_pages"] == ["https://example.com/b"]
    page = data["measured_pages"][0]
    assert page["html_sha256"] == Audit().html_sha256
    assert page["evidence_ref"] == "artifact://a"
    assert page["findings"][0]["lines"] == [3]
    assert {"robots_txt", "http_headers", "cdn_access", "render_completeness"} <= set(
        page["unknown"]
    )
    assert "not live search performance" in report.human_text


def test_all_missing_is_reported_without_success():
    data = json.loads(build().json_text)
    assert data["measured_page_count"] == 0 and data["unmeasured_pages"]
    assert "success" not in data


def test_mixed_tenant_refused():
    with pytest.raises(ValueError, match="mixed tenant"):
        build([Audit(), replace(Audit(), tenant_id="b")])


def test_unexpected_page_refused():
    with pytest.raises(ValueError, match="outside"):
        build([replace(Audit(), page_url="https://other.example/")])


def test_identical_duplicate_collapses():
    data = json.loads(build([Audit(), Audit()]).json_text)
    assert data["measured_page_count"] == 1
    assert "duplicate_snapshot_collapsed" in data["warnings"]


def test_conflicting_snapshot_refused():
    with pytest.raises(ValueError, match="conflicting snapshots"):
        build([Audit(), replace(Audit(), findings=())])


def test_evidence_ref_conflict_refused():
    with pytest.raises(ValueError, match="conflicting hashes"):
        build([Audit(), replace(Audit(), html_sha256="sha256:" + "b" * 64)])


def test_identical_bytes_different_pages_not_independent():
    data = json.loads(
        build(
            [Audit(), replace(Audit(), page_url="https://example.com/b")],
            ("https://example.com/a", "https://example.com/b"),
        ).json_text
    )
    assert "identical_html_across_pages_not_independent_observation" in data["warnings"]


@pytest.mark.parametrize("field", ["evidence_ref", "page_url", "tenant_id"])
def test_secret_shapes_never_render(field):
    secret = "sk-proj-" + "a" * 30
    a = replace(
        Audit(), **{field: ("https://example.com/" + secret if field == "page_url" else secret)}
    )
    with pytest.raises((SecretShapedValueError, ValueError)) as error:
        build([a], (a.page_url,))
    assert secret not in str(error.value)


def test_secret_finding_refused():
    with pytest.raises(SecretShapedValueError):
        build([replace(Audit(), findings=(replace(Finding(), detail="ghp_" + "a" * 36),))])


def test_text_control_characters_do_not_spoof_rows():
    report = build(
        [replace(Audit(), findings=(replace(Finding(), detail="hello\nMeasured: 999"),))]
    )
    assert "\nMeasured: 999" not in report.human_text
    assert "\\nMeasured: 999" in report.human_text


def test_deterministic_sorting():
    a = Audit()
    b = replace(a, page_url="https://example.com/b", evidence_ref="artifact://b")
    assert build([a, b], (b.page_url, a.page_url)) == build([b, a], (a.page_url, b.page_url))


@pytest.mark.parametrize(
    "change",
    [
        {"html_sha256": "fake"},
        {"supplied_http_status": True},
        {"findings": (replace(Finding(), lines=(-1,)),)},
        {"findings": (replace(Finding(), level="success"),)},
    ],
)
def test_invalid_measurement_input_refused(change):
    with pytest.raises(ValueError):
        build([replace(Audit(), **change)])


def test_empty_and_unbounded_cohorts_refused():
    for pages in [(), ("https://example.com",) * 1001]:
        with pytest.raises(ValueError):
            build(expected=pages)


@pytest.mark.parametrize("url", ["https://@example.com", "https://:@example.com"])
def test_even_empty_userinfo_is_refused(url):
    with pytest.raises(ValueError, match="credential-free"):
        build(expected=(url,))


def test_total_text_budget_is_enforced(monkeypatch):
    import saena_pilot.page_audit_report as module

    monkeypatch.setattr(module, "MAX_REPORT_CHARS", 50)
    with pytest.raises(ValueError, match="total report text"):
        build([Audit()])


def test_total_finding_budget_is_enforced(monkeypatch):
    import saena_pilot.page_audit_report as module

    monkeypatch.setattr(module, "MAX_TOTAL_FINDINGS", 1)
    with pytest.raises(ValueError, match="total findings"):
        build([replace(Audit(), findings=(Finding(), Finding()))])
