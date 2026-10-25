"""0322: "Ask Havel (AI)" in the command palette and on the Help page."""
from __future__ import annotations

from pathlib import Path

from app import config

from tests.test_havel_browser import _context, origin  # noqa: F401
from tests.test_submission_retry_cap import host  # noqa: F401

try:
    from playwright import sync_api
except ImportError:  # pragma: no cover - the browser test is skipped without Playwright
    sync_api = None

SHOTS = Path(__file__).resolve().parents[2] / "docs" / "tasks" / "screenshots-0322"


def _actions(html):
    """The page-header actions of /guide (the sidebar and top-bar launchers are left out)."""
    head = html.split('class="guide-layout"')[0]
    return head.split("ui-ph-acts", 1)[1] if "ui-ph-acts" in head else ""


def test_palette_carries_the_havel_row_only_when_on(host, monkeypatch):
    monkeypatch.setattr(config, "AI_FEATURES", frozenset())
    assert not [i for i in host.get("/api/command-palette?lang=en").json()["items"] if i.get("havel")]
    assert "data-havel-launcher" not in _actions(host.get("/guide?lang=en").text)
    monkeypatch.setattr(config, "AI_FEATURES", frozenset({"havel"}))
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "k")
    rows = [i for i in host.get("/api/command-palette?lang=en").json()["items"] if i.get("havel")]
    assert rows == [{"label": "Ask Havel (AI)", "group": "Havel (AI)", "url": "/havel", "havel": True}]
    assert 'data-sheet-open="havel-sheet"' in _actions(host.get("/guide?lang=en").text)


def test_no_match_opens_havel_with_the_query(origin):
    SHOTS.mkdir(parents=True, exist_ok=True)
    with sync_api.sync_playwright() as pw:
        for width in (390, 1280):
            browser, context = _context(pw, origin, width)
            page = context.new_page()
            page.goto(f"{origin[0]}/guide?lang=en")
            if width == 390:
                # host2.css hides header secondary actions below phone width (as on every host page);
                # the phone entry point is the top-bar launcher, so the Help button is only attached here.
                assert page.locator(".ui-ph-acts [data-havel-launcher]").count() == 1
                page.screenshot(path=str(SHOTS / "guide-ask-390.png"))
            else:
                assert page.locator(".ui-ph-acts [data-havel-launcher]").is_visible()
            page.locator("[data-command-open]:visible").first.click()
            page.fill("[data-command-input]", "how do i zzqx")
            option = page.locator(".command-option").first
            option.wait_for()
            assert "Ask Havel (AI): how do i zzqx" in option.inner_text()
            if width == 390:
                page.screenshot(path=str(SHOTS / "palette-ask-390.png"))
            option.click()
            # A locator check, not wait_for_function: a string predicate is eval'd and CSP blocks it.
            sync_api.expect(page.locator("#havel-sheet textarea[name=message]")).to_have_value("how do i zzqx")
            assert page.evaluate("document.documentElement.scrollWidth") <= width
            browser.close()
