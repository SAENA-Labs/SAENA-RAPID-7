"""Synthetic supplied-document checks; no indexing or ranking experiment."""

from dataclasses import FrozenInstanceError

import pytest
from saena_site_discovery.page_audit import MAX_HTML_BYTES, audit_supplied_html


def audit(source, **kwargs):
    return audit_supplied_html(
        tenant_id="tenant-a",
        page_url="https://example.com/p",
        evidence_ref="artifact://test/page",
        html=source.encode(),
        **kwargs,
    )


def codes(result):
    return {f.code for f in result.findings}


def test_normal_page_has_evidence_and_unknown_external_facts():
    result = audit(
        """<html><head>
<title>Example</title>
<link rel="canonical" href="/p">
<script type="application/ld+json">{"@type":"Product"}</script>
</head><body>Text</body></html>""",
        http_status=200,
    )
    assert codes(result) == {"title_present", "canonical_present", "jsonld_syntax_valid"}
    assert next(f for f in result.findings if f.code == "title_present").lines == (2,)
    assert result.evidence_ref == "artifact://test/page"
    assert result.tenant_id == "tenant-a"
    assert {
        "robots_txt",
        "http_headers",
        "cdn_access",
        "actual_index_state",
        "render_completeness",
    } == set(result.unknown)
    with pytest.raises(FrozenInstanceError):
        result.tenant_id = "tenant-b"


@pytest.mark.parametrize("directive", ["noindex", "NOINDEX, follow", "none"])
def test_noindex_observed_not_automatically_removed(directive):
    result = audit(f'<head><meta name="robots" content="{directive}"></head>')
    assert "meta_noindex" in codes(result)
    assert "actual_index_state" in result.unknown


@pytest.mark.parametrize("directive", ["nosnippet", "max-snippet:0"])
def test_snippet_restrictions(directive):
    assert "meta_snippet_restriction" in codes(
        audit(f'<head><meta name="googlebot" content="{directive}"></head>')
    )


def test_no_metadata_is_not_declared_ineligible():
    result = audit("<html><body>hello</body></html>")
    assert codes(result) == {"title_not_observed", "canonical_not_observed", "jsonld_not_observed"}
    assert all(f.level == "info" for f in result.findings if f.code != "title_not_observed")


@pytest.mark.parametrize("raw", ["{", "NaN", "null", "42", '"string"'])
def test_invalid_jsonld(raw):
    assert "jsonld_invalid" in codes(audit(f'<script type="application/ld+json">{raw}</script>'))


@pytest.mark.parametrize("raw", ["{}", "[]", '{"@context":"https://never-fetch.example/context"}'])
def test_valid_json_syntax_does_not_validate_semantics_or_fetch_context(raw):
    result = audit(f'<script type="application/ld+json">{raw}</script>')
    finding = next(f for f in result.findings if f.code == "jsonld_syntax_valid")
    assert "unverified" in finding.detail


@pytest.mark.parametrize(
    "href", ["", "javascript:alert(1)", "https://user:secret@example.com", "https://"]
)
def test_invalid_canonical(href):
    assert "invalid_canonical" in codes(audit(f'<head><link rel="canonical" href="{href}"></head>'))


def test_duplicates_empty_title_and_ambiguous_attributes():
    result = audit(
        '<head><title></title><title>B</title><link rel="canonical" href="/a">'
        '<link rel="canonical" href="/b">'
        '<meta name="robots" name="googlebot" content="noindex"></head>'
    )
    assert {"empty_title", "multiple_titles", "multiple_canonicals", "ambiguous_markup"} <= codes(
        result
    )


def test_comment_script_body_and_template_do_not_supply_head_metadata():
    result = audit("""<head><!-- <title>fake</title> --><template><title>fake</title></template>
<script>const x='<meta name="robots" content="noindex">';</script></head>
<body><title>not head</title><link rel="canonical" href="/fake"></body>""")
    assert {"title_not_observed", "canonical_not_observed"} <= codes(result)
    assert "meta_noindex" not in codes(result)


def test_unclosed_json_is_not_valid_jsonld():
    result = audit('<script type="application/ld+json">{"x":1}')
    assert "ambiguous_markup" in codes(result)
    assert "jsonld_syntax_valid" not in codes(result)


def test_input_hash_changes_and_is_repeatable():
    a = audit("<head><title>A</title></head>")
    assert a == audit("<head><title>A</title></head>")
    assert a.html_sha256 != audit("<head><title>B</title></head>").html_sha256


@pytest.mark.parametrize("status", [404, 302, 500])
def test_supplied_non_success_status_is_only_supplied_fact(status):
    assert "non_success_status" in codes(audit("<html></html>", http_status=status))


@pytest.mark.parametrize("status", [True, 99, 600, "200"])
def test_bad_status_rejected(status):
    with pytest.raises(ValueError):
        audit("<html></html>", http_status=status)


@pytest.mark.parametrize("source", [b"", b" ", b"\xff", b"x" * (MAX_HTML_BYTES + 1)])
def test_invalid_or_unbounded_input(source):
    with pytest.raises(ValueError):
        audit_supplied_html(
            tenant_id="a", page_url="https://example.com", evidence_ref="artifact://x", html=source
        )


def test_metadata_count_is_bounded():
    with pytest.raises(ValueError, match="too many"):
        audit("<head>" + "<title>a</title>" * 257 + "</head>")


@pytest.mark.parametrize(
    "url", ["file:///etc/passwd", "https://a:b@example.com", "https://", "relative"]
)
def test_invalid_page_identity(url):
    with pytest.raises(ValueError):
        audit_supplied_html(
            tenant_id="a", page_url=url, evidence_ref="artifact://x", html=b"<html>"
        )


def test_context_urls_are_never_fetched(monkeypatch):
    import socket

    def forbidden(*args, **kwargs):
        raise AssertionError("offline audit attempted network")

    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    result = audit(
        '<script type="application/ld+json">{"@context":"https://example.com/context"}</script>'
    )
    assert "jsonld_syntax_valid" in codes(result)


def test_tenant_binding_is_not_shared_state():
    values = dict(
        page_url="https://example.com",
        evidence_ref="artifact://input",
        html=b"<head><title>A</title></head>",
    )
    a = audit_supplied_html(tenant_id="a", **values)
    b = audit_supplied_html(tenant_id="b", **values)
    assert a.tenant_id == "a" and b.tenant_id == "b"
    assert a.html_sha256 == b.html_sha256
    assert a != b


def test_duplicate_attribute_does_not_choose_one_directive():
    result = audit('<head><meta name="robots" content="index" content="noindex"></head>')
    assert "ambiguous_markup" in codes(result)
    assert "meta_noindex" not in codes(result)


def test_snippet_zero_with_whitespace_is_observed():
    assert "meta_snippet_restriction" in codes(
        audit('<head><meta name="robots" content="max-snippet: 0"></head>')
    )
