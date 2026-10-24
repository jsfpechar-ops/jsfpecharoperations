"""0227: Settings > Phone app > urgent alerts, in a real browser.

The browser's push service is not reachable from CI, so an init script stands
in for PushManager (it hands out the subscription of a test Browser from
tests/test_push.py); everything else (permission, pwa.js, the endpoints, the
database, the encrypted test push) runs for real.
"""
import json
import os
import secrets
import tempfile
from pathlib import Path

import pytest

REQUIRE_BROWSER = os.environ.get("UBYHOST_REQUIRE_BROWSER") == "1"
if REQUIRE_BROWSER:
    import playwright.sync_api as sync_api
else:
    sync_api = pytest.importorskip("playwright.sync_api")

from app import auth, config, push
from tests.browser_support import chromium_launch_kwargs
from tests.test_host_geometry import _browser_session_cookie, base  # noqa: F401
from tests.test_push import Browser, PushService

SHOT_DIR = os.path.join(os.environ.get("UBYHOST_SHOTS_DIR", tempfile.gettempdir()), "pwa-0227")
IPHONE = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1"
)

_FAKE_PUSH = """
(() => {
  const made = {
    endpoint: %s,
    options: { applicationServerKey: null },
    expirationTime: null,
    toJSON() { return { endpoint: this.endpoint, keys: %s }; },
    unsubscribe() { sessionStorage.removeItem('fake-push'); return Promise.resolve(true); },
  };
  PushManager.prototype.getSubscription = () =>
    Promise.resolve(sessionStorage.getItem('fake-push') ? made : null);
  PushManager.prototype.subscribe = () => {
    sessionStorage.setItem('fake-push', '1');
    return Promise.resolve(made);
  };
})();
"""


@pytest.fixture(autouse=True)
def push_on(monkeypatch):
    monkeypatch.setattr(config, "WEB_PUSH", True)


def _host():
    username = f"ps{secrets.token_hex(3)}"
    owner = auth.create_account(f"{username}@example.test", "Push", role="host", username=username)
    return username, owner


def _browser(playwright):
    # The old headless shell always reports Notification.permission "denied",
    # even after grant_permissions(); the full Chromium in new headless mode honours it.
    kwargs = chromium_launch_kwargs()
    if "executable_path" not in kwargs:
        kwargs["channel"] = "chromium"
    try:
        return playwright.chromium.launch(**kwargs)
    except Exception as exc:
        if REQUIRE_BROWSER:
            raise
        pytest.skip(f"Chromium is not available: {exc}")


def _page(browser, base, username, width, *, fake=None, user_agent=None, collapsed=False, grant=True):
    options = {"viewport": {"width": width, "height": 900}}
    if user_agent:
        options["user_agent"] = user_agent
    context = browser.new_context(**options)
    if grant:
        context.grant_permissions(["notifications"], origin=base)
    context.add_cookies([{"name": auth.SESSION_COOKIE, "value": _browser_session_cookie(username), "url": base + "/"}])
    if fake:
        context.add_init_script(_FAKE_PUSH % (json.dumps(fake.endpoint), json.dumps(fake.subscription()["keys"])))
    context.add_init_script(
        "try { localStorage.setItem('ubyhost-sidebar-collapsed', '%s'); } catch (e) {}" % ("1" if collapsed else "0")
    )
    return context.new_page()


def _shot(page, name):
    Path(SHOT_DIR).mkdir(parents=True, exist_ok=True)
    page.locator("#settings-group-phone").screenshot(path=os.path.join(SHOT_DIR, f"{name}.png"))


def _open_settings(page, base, lang):
    page.goto(f"{base}/settings?lang={lang}")
    page.wait_for_selector("#settings-group-phone", timeout=30000)
    page.wait_for_function("navigator.serviceWorker.controller !== null", timeout=30000)


@pytest.mark.parametrize("lang", ["en", "cs", "vi"])
def test_turning_alerts_on_sends_one_test_and_lists_this_device(base, lang, monkeypatch):
    service = PushService(monkeypatch)
    username, owner = _host()
    fake = Browser()
    with sync_api.sync_playwright() as playwright:
        browser = _browser(playwright)
        try:
            page = _page(browser, base, username, 390, fake=fake)
            _open_settings(page, base, lang)
            assert page.is_visible("[data-push-on]")
            assert not page.is_visible("[data-push-unsupported]")
            _shot(page, f"alerts-off-390-{lang}")
            page.click("[data-push-on]")
            page.wait_for_selector("[data-push-state-on]:not([hidden])", timeout=30000)
            assert push.count_for(owner) == 1
            assert len(service.sent) == 1
            assert fake.read(service.sent[0]["data"])["title"] == push.message("test", lang, {})["title"]
            assert page.is_visible("[data-push-controls]")
            assert page.locator("#settings-alerts form[action^='/account/push/devices/']").count() == 1
            _shot(page, f"alerts-on-390-{lang}")
        finally:
            browser.close()


@pytest.mark.parametrize("width,collapsed", [(1280, False), (1280, True), (2000, False), (2000, True)])
def test_the_alerts_row_fits_wide_layouts(base, width, collapsed):
    username, owner = _host()
    fake = Browser()
    push.save_subscription(owner, fake.subscription(), lang="en", device="iPhone")
    with sync_api.sync_playwright() as playwright:
        browser = _browser(playwright)
        try:
            page = _page(browser, base, username, width, fake=fake, collapsed=collapsed)
            page.add_init_script("sessionStorage.setItem('fake-push', '1')")
            _open_settings(page, base, "en")
            page.wait_for_selector("[data-push-state-on]:not([hidden])", timeout=30000)
            overflow = page.evaluate(
                "[...document.querySelectorAll('#settings-group-phone *')]"
                ".filter(e => e.scrollWidth > e.clientWidth + 1 && getComputedStyle(e).overflowX === 'visible').length"
            )
            assert overflow == 0
            assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
            badge = page.locator("[data-push-state-on]").bounding_box()
            test_button = page.locator("[data-push-test]").bounding_box()
            assert abs((badge["y"] + badge["height"] / 2) - (test_button["y"] + test_button["height"] / 2)) < 8
            assert test_button["x"] > badge["x"]
            _shot(page, f"alerts-on-{width}{'-collapsed' if collapsed else ''}-en")
        finally:
            browser.close()


@pytest.mark.parametrize("lang", ["en", "cs", "vi"])
def test_an_iphone_outside_the_home_screen_app_is_told_to_add_it_first(base, lang):
    username, _owner = _host()
    with sync_api.sync_playwright() as playwright:
        browser = _browser(playwright)
        try:
            page = _page(browser, base, username, 390, user_agent=IPHONE, grant=False)
            page.goto(f"{base}/settings?lang={lang}")
            page.wait_for_selector("#settings-group-phone", timeout=30000)
            page.wait_for_selector("[data-push-ios-first]:not([hidden])", timeout=30000)
            assert not page.is_visible("[data-push-on]")
            assert page.is_visible("[data-pwa-ios]")
            _shot(page, f"iphone-390-{lang}")
        finally:
            browser.close()


def test_logging_out_turns_alerts_off_on_this_device(base):
    username, owner = _host()
    fake = Browser()
    push.save_subscription(owner, fake.subscription(), lang="en", device="Mac")
    with sync_api.sync_playwright() as playwright:
        browser = _browser(playwright)
        try:
            page = _page(browser, base, username, 1280, fake=fake)
            page.add_init_script("sessionStorage.setItem('fake-push', '1')")
            _open_settings(page, base, "en")
            page.wait_for_selector("[data-push-state-on]:not([hidden])", timeout=30000)
            with page.expect_navigation(timeout=30000):
                page.evaluate("document.querySelector('form[action=\"/logout\"]').requestSubmit()")
            assert "/login" in page.url
            assert push.count_for(owner) == 0
        finally:
            browser.close()
