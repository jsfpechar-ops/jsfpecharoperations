"""Saved pricing review fits signup and onboarding, including without JavaScript."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from app import auth, config, db
from tests.test_onboarding_wizard_browser import (  # noqa: F401 (shared fixtures)
    base_url, host, sync_api,
)
from tests.test_host_stay_actions_browser import _browser

SELECTION = {"plan": "standard", "interval": "year", "apartments": "7", "ttlock": "1"}


def screenshot(page, name):
    root = Path(os.environ.get("UBYHOST_SHOTS_DIR", ".pytest_cache/signup-pricing-shots"))
    root.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(root / name), full_page=True)


@pytest.mark.parametrize("lang", ["en", "cs"])
@pytest.mark.parametrize("width", [360, 390, 1024, 1280])
@pytest.mark.parametrize("javascript", [False, True])
def test_signup_and_onboarding_review_fit_without_js(
    host, base_url, monkeypatch, lang, width, javascript,
):
    monkeypatch.setattr(config, "SIGNUP_ENABLED", True)
    monkeypatch.setattr(config, "BILLING_ENABLED", True)
    db.update("user_account", host["owner"], {
        "signup_selection_json": json.dumps(SELECTION),
    })
    with sync_api.sync_playwright() as playwright:
        browser = _browser(playwright)
        context = browser.new_context(viewport={"width": width, "height": 900},
                                      java_script_enabled=javascript)
        page = context.new_page()
        page.goto(f"{base_url}/signup?plan=standard&interval=year&apts=7&ttlock=1&lang={lang}")
        assert page.locator('input[name="apartments"]').input_value() == "7"
        assert page.locator('input[name="plan"]').input_value() == "standard"
        assert page.locator('form[action="/signup"] button[type="submit"]').is_visible()
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
        screenshot(page, f"signup-pricing-{lang}-{width}-js{int(javascript)}.png")

        context.add_cookies([{"name": auth.SESSION_COOKIE,
                             "value": host["client"].cookies.get(auth.SESSION_COOKIE),
                             "url": base_url + "/"}])
        page.goto(f"{base_url}/onboarding?lang={lang}")
        later = page.locator("#security-prompt [data-security-prompt-later]")
        if later.is_visible():
            later.click()
        review = page.locator('.ui-section').filter(
            has=page.locator('a[href="/predplatne"]'),
        )
        assert review.is_visible()
        assert "7" in review.inner_text()
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
        screenshot(page, f"onboarding-pricing-{lang}-{width}-js{int(javascript)}.png")
        # Billing review remains a regular link, usable with scripting disabled.
        review.locator('a[href="/predplatne"]').click()
        page.wait_for_url("**/predplatne")
        assert page.locator("main").is_visible()
        browser.close()
