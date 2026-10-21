"""0203: the service worker installs, and a lost connection shows the offline page."""
import os
import secrets
from pathlib import Path

import pytest

REQUIRE_BROWSER = os.environ.get("UBYHOST_REQUIRE_BROWSER") == "1"
if REQUIRE_BROWSER:
    import playwright.sync_api as sync_api
else:
    sync_api = pytest.importorskip("playwright.sync_api")

from app import auth
from tests.browser_support import chromium_launch_kwargs
from tests.test_host_geometry import _browser_session_cookie, base  # noqa: F401

SHOT_DIR = "/mnt/project-files/pwa/0203/"

_OFFLINE_CACHED = """async (lang) => {
  for (const key of await caches.keys()) {
    const stored = await (await caches.open(key)).match('/offline');
    if (stored && stored.headers.get('Content-Language') === lang) return true;
  }
  return false;
}"""


def _open(playwright, base, width, height, target):
    username = f"pwa{secrets.token_hex(3)}"
    auth.create_account(f"{username}@example.test", "Pwa", role="host", username=username)
    try:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
    except Exception as exc:
        if REQUIRE_BROWSER:
            raise
        pytest.skip(f"Chromium is not available: {exc}")
    context = browser.new_context(viewport={"width": width, "height": height})
    context.add_cookies([{"name": auth.SESSION_COOKIE, "value": _browser_session_cookie(username), "url": base + "/"}])
    page = context.new_page()
    page.goto(base + target)
    page.wait_for_selector("#main-content", timeout=30000)
    return browser, context, page


def _shot(page, name):
    Path(SHOT_DIR).mkdir(parents=True, exist_ok=True)
    page.screenshot(path=f"{SHOT_DIR}{name}.png", full_page=True)


@pytest.mark.parametrize(
    "lang,title", [("en", "You are offline"), ("cs", "Jste offline"), ("vi", "Bạn đang ngoại tuyến")]
)
def test_a_failed_page_load_shows_the_offline_page_in_the_hosts_language(base, lang, title):
    with sync_api.sync_playwright() as playwright:
        browser, context, page = _open(playwright, base, 390, 844, f"/settings?lang={lang}")
        try:
            page.wait_for_function("navigator.serviceWorker.controller !== null", timeout=30000)
            page.wait_for_function(_OFFLINE_CACHED, arg=lang, timeout=30000)
            # Settings > Phone app: on desktop Chromium the generic how-to shows.
            assert page.is_visible("#settings-group-phone [data-pwa-other]")
            assert not page.is_visible("#settings-group-phone [data-pwa-ios]")
            page.locator("#settings-group-phone").scroll_into_view_if_needed()
            _shot(page, f"settings-phone-390-{lang}")
            context.set_offline(True)
            page.goto(base + "/stays")
            assert page.locator("h1").inner_text() == title
            _shot(page, f"offline-390-{lang}")
            context.set_offline(False)
        finally:
            browser.close()


def test_guest_links_are_never_answered_by_the_worker(base):
    with sync_api.sync_playwright() as playwright:
        browser, context, page = _open(playwright, base, 390, 844, "/settings?lang=en")
        try:
            page.wait_for_function("navigator.serviceWorker.controller !== null", timeout=30000)
            context.set_offline(True)
            with pytest.raises(Exception):
                page.goto(base + "/l/not-a-real-link")
            context.set_offline(False)
        finally:
            browser.close()
