"""0789b: the two e-mail choices on Settings are switches that submit on change.

With JavaScript off the Save button sits in a <noscript> block, so the form
still posts from its own button.
"""
from __future__ import annotations

from app import auth
from tests.browser_support import chromium_launch_kwargs
from tests.test_0786_settings_geometry_browser import base, host  # noqa: F401 (module fixtures)

sync_api = __import__("pytest").importorskip("playwright.sync_api")


def test_the_email_choices_are_switches_with_a_noscript_save(host):  # noqa: F811
    page = host["client"].get("/settings/account?lang=en").text
    assert 'id="settings-onboarding-emails"' in page
    assert page.count("data-toggle-submit") >= 1
    assert page.count("<noscript><button") >= 1


def test_the_switch_submits_on_change_and_the_form_posts_without_js(host, base):  # noqa: F811
    cookie = host["client"].cookies.get(auth.SESSION_COOKIE)
    assert cookie
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        # JavaScript off: the Save button is visible inside the noscript block.
        context = browser.new_context(viewport={"width": 390, "height": 900}, java_script_enabled=False)
        context.add_cookies([{"name": auth.SESSION_COOKIE, "value": cookie, "url": base + "/"}])
        page = context.new_page()
        page.goto(f"{base}/settings/account?lang=en")
        assert page.locator("#settings-onboarding-emails button[type=submit]").is_visible()
        context.close()
        # JavaScript on: changing the switch submits the form, no Save press needed.
        context = browser.new_context(viewport={"width": 390, "height": 900})
        context.add_cookies([{"name": auth.SESSION_COOKIE, "value": cookie, "url": base + "/"}])
        page = context.new_page()
        page.goto(f"{base}/settings/account?lang=en")
        switch = page.locator("#settings-onboarding-emails input[type=checkbox]")
        before = switch.is_checked()
        with page.expect_navigation():
            switch.click()
        assert page.locator("#settings-onboarding-emails input[type=checkbox]").is_checked() != before
        context.close()
        browser.close()
