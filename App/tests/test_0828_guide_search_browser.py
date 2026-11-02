"""0828: /guide has a search field that filters topics as you type, and every topic is folded until opened."""
from __future__ import annotations

import pytest

from tests.test_0710_v2_mockup_match_browser import _launch, base, dashboard_host, dashboard_rich_host
from tests.test_0800_v2_remaining_pages_browser import _launch_ctx

__all__ = ["base", "dashboard_host", "dashboard_rich_host"]

WIDTHS = [390, 1280]

_TOPICS_JS = """() => [...document.querySelectorAll('.guide-topic')].map(d => ({
  id: d.id, open: d.open, hidden: d.hidden, text: d.textContent.toLowerCase(),
  summary: d.querySelector('summary') ? d.querySelector('summary').getBoundingClientRect().height : 0,
}))"""


def _go(browser, base_url, host, url, width):
    from app import auth

    cookie = host["client"].cookies.get(auth.SESSION_COOKIE)
    assert cookie
    context = browser.new_context(viewport={"width": width, "height": 1000}, reduced_motion="reduce")
    context.add_cookies([{"name": auth.SESSION_COOKIE, "value": cookie, "url": base_url + "/"}])
    page = context.new_page()
    page.goto(f"{base_url}{url}")
    page.wait_for_load_state("networkidle")
    return context, page


def _run(base_url, host, url, width, steps):
    with _launch_ctx() as playwright:
        browser = _launch(playwright)
        context, page = _go(browser, base_url, host, url, width)
        try:
            return steps(page)
        finally:
            context.close()
            browser.close()


@pytest.mark.parametrize("width", WIDTHS)
def test_topics_are_folded_on_load(width, base, dashboard_rich_host):
    topics = _run(base, dashboard_rich_host, "/guide?lang=en", width, lambda p: p.evaluate(_TOPICS_JS))
    assert len(topics) >= 20, f"expected about 24 topics at {width} px, found {len(topics)}"
    opened = [t["id"] for t in topics if t["open"]]
    assert not opened, f"topics open on load at {width} px: {opened}"
    short = [t["id"] for t in topics if t["summary"] < 44]
    assert not short, f"topic rows under 44 px high at {width} px: {short}"


@pytest.mark.parametrize("width", WIDTHS)
def test_typing_pin_keeps_only_matching_topics_open(width, base, dashboard_rich_host):
    def steps(page):
        page.wait_for_selector("#guide-search:not([hidden])")
        page.fill("#guide-search", "PIN")
        page.wait_for_timeout(300)
        return page.evaluate(_TOPICS_JS)

    topics = _run(base, dashboard_rich_host, "/guide?lang=en", width, steps)
    visible = [t for t in topics if not t["hidden"]]
    assert visible, f"no topic matched PIN at {width} px"
    assert len(visible) < len(topics), "every topic matched PIN, so nothing was filtered"
    for t in visible:
        assert t["open"], f"matching topic {t['id']} is not open"
        assert "pin" in t["text"], f"topic {t['id']} shown for PIN without the word"
    for t in topics:
        if t["hidden"]:
            assert not t["open"], f"hidden topic {t['id']} is still open"


@pytest.mark.parametrize("width", WIDTHS)
def test_nonsense_query_shows_no_results_and_escape_resets(width, base, dashboard_rich_host):
    def steps(page):
        page.wait_for_selector("#guide-search:not([hidden])")
        page.fill("#guide-search", "zqxjkwv")
        page.wait_for_timeout(300)
        empty_shown = page.is_visible(".guide-search-empty")
        visible_during = [t for t in page.evaluate(_TOPICS_JS) if not t["hidden"]]
        page.press("#guide-search", "Escape")
        page.wait_for_timeout(300)
        after = page.evaluate(_TOPICS_JS)
        value = page.input_value("#guide-search")
        return empty_shown, visible_during, after, value

    empty_shown, visible_during, after, value = _run(base, dashboard_rich_host, "/guide?lang=en", width, steps)
    assert empty_shown, "no-results line is not shown for a nonsense query"
    assert not visible_during, "topics still shown for a nonsense query"
    assert all(not t["hidden"] and not t["open"] for t in after), "Escape did not restore the closed list"
    assert value == ""


@pytest.mark.parametrize("width", WIDTHS)
def test_anchor_opens_its_topic(width, base, dashboard_rich_host):
    def steps(page):
        page.wait_for_timeout(300)
        return page.evaluate(
            """() => { const d = document.getElementById('door-codes');
              return {open: !!(d && d.open), top: d ? d.getBoundingClientRect().top : null, vh: window.innerHeight}; }"""
        )

    state = _run(base, dashboard_rich_host, "/guide?lang=en#door-codes", width, steps)
    assert state["open"], f"/guide#door-codes did not open its topic at {width} px"
    assert state["top"] is not None and -5 <= state["top"] < state["vh"], f"topic not in view: {state}"


def test_guide_page_height_under_3000_on_load_at_1280(base, dashboard_rich_host):
    height = _run(
        base, dashboard_rich_host, "/guide?lang=en", 1280,
        lambda p: p.evaluate("() => document.documentElement.scrollHeight"),
    )
    assert height < 3000, f"/guide is {height} px tall on load at 1280 px"
