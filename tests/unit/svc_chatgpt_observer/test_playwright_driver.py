"""Offline driver regressions: no browser, network, account or extra dependency."""

from urllib.parse import parse_qs, urlsplit

import pytest
from saena_chatgpt_observer.errors import BrowserSessionRenderError
from saena_chatgpt_observer.playwright_driver import (
    PlaywrightBrowserSessionFactory,
    _PlaywrightBrowserSession,
)


class Response:
    def __init__(self, status):
        self.status = status
        self.ok = 200 <= status < 300


class Page:
    def __init__(self):
        self.url = None
        self.closed = False
        self.response = Response(200)
        self.content_calls = 0

    def goto(self, url, **kwargs):
        self.url = url
        return self.response

    def content(self):
        self.content_calls += 1
        return "<html>fixture only</html>"

    def close(self):
        self.closed = True


class Context:
    def __init__(self, fail=False):
        self.page = Page()
        self.closed = False
        self.fail = fail
        self.close_calls = 0

    def new_page(self):
        if self.fail:
            raise RuntimeError("fixture page failure")
        return self.page

    def close(self):
        self.close_calls += 1
        self.closed = True


class Browser:
    def __init__(self, fail=False):
        self.contexts = []
        self.fail = fail

    def new_context(self):
        context = Context(self.fail)
        self.contexts.append(context)
        return context

    def is_connected(self):
        return True


def factory(browser):
    # Exercise allocation without starting real Playwright or Chromium.
    instance = object.__new__(PlaywrightBrowserSessionFactory)
    instance._browser = browser
    instance._next_id = 0
    return instance


@pytest.mark.parametrize(
    "query",
    [
        "C++ & B2B #가격? 지역=대전",
        "100% SaaS",
        "a+b",
        "a&b=c",
        "서울 가격",
        'quote " and / path',
        "a#fragment",
        "literal %2F %26",
        "ordinary query",
    ],
)
def test_query_round_trip(query):
    page = Page()
    session = _PlaywrightBrowserSession(Browser(), page, "fixture")
    assert session.render_search_result(query_text=query) == b"<html>fixture only</html>"
    url = urlsplit(page.url)
    assert url.scheme == "https"
    assert url.netloc == "chatgpt.com"
    assert url.path == "/search"
    assert not url.fragment
    assert parse_qs(url.query) == {"q": [query]}


def test_session_close_releases_owned_context():
    browser = Browser()
    session = factory(browser)()
    session.close()
    session.close()
    assert browser.contexts[0].closed
    assert browser.contexts[0].close_calls == 1
    assert not session.is_healthy()


def test_page_creation_failure_releases_context():
    browser = Browser(fail=True)
    with pytest.raises(RuntimeError, match="fixture page failure"):
        factory(browser)()
    assert browser.contexts[0].closed


def test_legacy_page_only_session_still_closes_page():
    page = Page()
    _PlaywrightBrowserSession(Browser(), page, "legacy").close()
    assert page.closed


@pytest.mark.parametrize("status", [None, 301, 403, 429, 500, 503])
def test_unsuccessful_navigation_never_becomes_observation(status):
    page = Page()
    page.response = None if status is None else Response(status)
    session = _PlaywrightBrowserSession(Browser(), page, "fixture")
    with pytest.raises(BrowserSessionRenderError) as caught:
        session.render_search_result(query_text="query")
    assert caught.value.context["http_status"] == status
    assert page.content_calls == 0
    assert "fixture only" not in str(caught.value)


def test_context_close_failure_attempts_page_cleanup():
    class FailingContext:
        def close(self):
            raise RuntimeError("fixture context close failure")

    page = Page()
    session = _PlaywrightBrowserSession(Browser(), page, "fixture", _context=FailingContext())
    session.close()
    assert page.closed
    assert not session.is_healthy()
