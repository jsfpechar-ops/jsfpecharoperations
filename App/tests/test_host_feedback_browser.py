"""Real Chromium checks for host copy results and transient feedback."""
import os
import secrets
import socket
import threading
from pathlib import Path

import pytest
import uvicorn
from fastapi.testclient import TestClient

from app import auth, db
from app.main import app
from tests.browser_support import chromium_launch_kwargs
from tests.conftest import login_as


REQUIRE_BROWSER = os.environ.get("UBYHOST_REQUIRE_BROWSER") == "1"
if REQUIRE_BROWSER:
    import playwright.sync_api as sync_api
else:
    sync_api = pytest.importorskip("playwright.sync_api")


def _free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture(scope="module")
def base():
    db.init_db()
    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = __import__("time").time() + 15
    while not server.started and __import__("time").time() < deadline:
        __import__("time").sleep(0.05)
    if not server.started:
        pytest.fail("the test server did not start")
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=5)


def _session_cookie(username):
    client = TestClient(app)
    response = login_as(client, username, url="/login?lang=en", follow_redirects=False)
    assert response.status_code == 303, response.text
    token = client.cookies.get(auth.SESSION_COOKIE)
    assert token
    return token


def test_host_copy_feedback_truth_and_geometry(base):
    username = f"feedback{secrets.token_hex(4)}"
    auth.create_account(f"{username}@example.test", "Feedback QA", role="host", username=username)
    session = _session_cookie(username)
    shots = Path("/tmp/0032-host-feedback")
    shots.mkdir(parents=True, exist_ok=True)
    fixture_script = """
      window.__copyMode = 'success';
      window.__clipboardWrites = [];
      Object.defineProperty(navigator, 'clipboard', { configurable: true, value: {
        writeText: (text) => {
          window.__clipboardWrites.push(text);
          return window.__copyMode === 'reject' ? Promise.reject(new Error('denied')) : Promise.resolve();
        }
      }});
      document.addEventListener('DOMContentLoaded', () => {
        const main = document.querySelector('main') || document.body;
        const rail = document.querySelector('[data-feedback-rail]');
        if (rail && sessionStorage.getItem('__fullFeedbackRail') === '1') {
          for (let i = 1; i <= 3; i += 1) {
            const toast = document.createElement('div');
            toast.className = 'toast'; toast.dataset.toast = ''; toast.dataset.toastKind = 'info'; toast.dataset.toastSticky = '';
            toast.innerHTML = `<span class="grow">Queued fixture ${i}</span><button type="button" data-toast-close aria-label="Dismiss">×</button>`;
            rail.appendChild(toast);
          }
        }
        const source = document.createElement('input');
        source.id = 'feedback-copy-source'; source.className = 'sr-only'; source.value = 'synthetic-copy-value'; source.readOnly = true;
        const button = document.createElement('button');
        button.id = 'feedback-copy'; button.type = 'button'; button.dataset.copy = source.id;
        button.dataset.copyLabel = 'Copy'; button.dataset.copiedLabel = document.documentElement.lang === 'cs' ? 'Zkopírováno' : 'Copied';
        button.textContent = 'Copy';
        main.append(source, button);
      });
    """
    with sync_api.sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(**chromium_launch_kwargs())
        except Exception as exc:
            if REQUIRE_BROWSER:
                raise
            pytest.skip(f"Chromium is not available: {exc}")
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        context.add_cookies([{"name": auth.SESSION_COOKIE, "value": session, "url": base + "/"}])
        context.add_init_script(fixture_script)
        page = context.new_page()
        for locale in ("en", "cs"):
            page.goto(f"{base}/?lang={locale}")
            page.wait_for_selector("[data-feedback-rail]", state="attached")
            button = page.locator("#feedback-copy")
            before = button.bounding_box()
            button.click()
            page.locator('.toast[data-toast-kind="success"]').wait_for()
            after = button.bounding_box()
            assert after["width"] == pytest.approx(before["width"], abs=0.5)
            assert after["height"] == pytest.approx(before["height"], abs=0.5)
            assert button.get_attribute("aria-label") == ("Copied" if locale == "en" else "Zkopírováno")
            assert "synthetic-copy-value" not in page.locator("[data-feedback-rail]").inner_text()
            assert page.evaluate("document.activeElement.id") == "feedback-copy"
            page.locator(".toast[data-toast-kind=success]").dispatch_event("mouseenter")
            for width in (360, 390, 471, 1280):
                page.set_viewport_size({"width": width, "height": 900})
                page.wait_for_timeout(60)
                overflow = page.evaluate("""() => ({
                  scrollWidth: document.documentElement.scrollWidth,
                  outside: [...document.body.querySelectorAll('*')].map(el => {
                    const r = el.getBoundingClientRect();
                    const path = [];
                    for (let node = el; node && path.length < 4; node = node.parentElement) path.push(node.tagName.toLowerCase() + (node.id ? '#' + node.id : '') + (typeof node.className === 'string' && node.className ? '.' + node.className.trim().replace(/\\s+/g, '.') : ''));
                    return { right: r.right, path };
                  }).filter(item => item.right > window.innerWidth + 1).slice(0, 5)
                })""")
                assert overflow["scrollWidth"] <= width, overflow
                geometry = page.locator(".toast-stack").evaluate("el => { const r=el.getBoundingClientRect(); const c=el.querySelector('[data-toast-close]').getBoundingClientRect(); return {left:r.left, right:r.right, width:el.clientWidth, scrollWidth:el.scrollWidth, closeWidth:c.width, closeHeight:c.height}; }")
                assert geometry["left"] >= -1 and geometry["right"] <= width + 1, geometry
                assert geometry["scrollWidth"] <= geometry["width"] + 1, geometry
                assert geometry["closeWidth"] >= 44 and geometry["closeHeight"] >= 44
                page.screenshot(path=str(shots / f"{locale}-{width}.png"), full_page=True)

        page.locator('.toast[data-toast-kind="success"] [data-toast-close]').click()
        page.evaluate("sessionStorage.setItem('__fullFeedbackRail', '1')")
        for locale in ("en", "cs"):
            for width in (360, 390):
                page.set_viewport_size({"width": width, "height": 900})
                page.goto(f"{base}/?lang={locale}")
                page.wait_for_selector("[data-feedback-rail] [data-toast]")
                page.evaluate("window.__copyMode = 'reject'")
                button = page.locator("#feedback-copy")
                button.click()
                assert page.locator('[data-feedback-rail] [data-toast]').count() == 3
                page.wait_for_timeout(100)
                failure_label = page.locator("[data-host-feedback]").get_attribute("data-copy-failure")
                assert failure_label in page.locator("[data-feedback-alert]").inner_text()
                assert not button.evaluate("el => el.classList.contains('copied')")
                manual_source = page.locator("#feedback-copy-source")
                assert manual_source.get_attribute("data-copy-manual-visible") == ""
                assert page.evaluate("getSelection().toString() || document.activeElement.value") == "synthetic-copy-value"
                manual_geometry = manual_source.evaluate("el => { const r=el.getBoundingClientRect(); return {left:r.left, top:r.top, right:r.right, bottom:r.bottom, width:innerWidth, height:innerHeight}; }")
                assert manual_geometry["left"] >= -1 and manual_geometry["top"] >= -1
                assert manual_geometry["right"] <= width + 1 and manual_geometry["bottom"] <= 901, manual_geometry
                page.screenshot(path=str(shots / f"failure-{locale}-{width}.png"), full_page=True)
                page.locator("[data-toast-close]").first.click()
                assert page.locator('.toast[data-toast-kind="error"]').count() == 1
                while page.locator("[data-toast-close]").count():
                    page.locator("[data-toast-close]").first.click()

        page.evaluate("""() => {
          Object.defineProperty(navigator, 'clipboard', { configurable: true, value: undefined });
          document.execCommand = () => false;
        }""")
        page.set_viewport_size({"width": 1280, "height": 900})
        button.click()
        page.wait_for_timeout(100)
        assert not button.evaluate("el => el.classList.contains('copied')")
        assert page.locator('.toast[data-toast-kind="error"]').count() == 1
        assert page.locator("#feedback-copy-source").get_attribute("data-copy-manual-visible") == ""
        page.locator("[data-toast-close]").first.click()
        assert page.locator("#feedback-copy-source").get_attribute("data-copy-manual-visible") is None
        page.evaluate("sessionStorage.removeItem('__fullFeedbackRail')")
        page.reload()

        page.route("**/api/command-palette", lambda route: route.fulfill(json={"items": [{"label": "Copy guest link", "copy": "https://example.test/guest-secret", "group": "Actions"}]}))
        page.evaluate("window.__copyMode = 'reject'")
        page.keyboard.press("Control+k")
        command = page.locator("#command-dialog")
        command.wait_for(state="visible")
        option = page.get_by_role("option", name="Copy guest link")
        option.wait_for()
        option.click()
        failure = command.get_by_role("alert")
        failure.wait_for()
        manual_source = failure.locator("textarea")
        assert manual_source.is_visible()
        assert manual_source.input_value() == "https://example.test/guest-secret"
        assert page.locator("[data-feedback-rail] [data-toast-kind=error]").count() == 0
        assert command.get_attribute("open") is not None
        assert command.locator("[data-command-results]").get_attribute("role") == "listbox"
        page.keyboard.press("Control+a")
        assert page.evaluate("document.activeElement === document.querySelector('#command-dialog textarea')")
        assert page.evaluate("getSelection().toString() || document.activeElement.value") == "https://example.test/guest-secret"
        page.locator("[data-command-input]").fill("no matching command")
        assert command.locator("[role=alert]").count() == 0
        assert command.locator("[data-command-results]").get_attribute("role") == "listbox"
        page.locator("[data-command-close]").click()
        assert command.get_attribute("open") is None
        assert command.locator("[role=alert]").count() == 0

        # Hover and keyboard focus both pause an automatic card's seven-second lifetime.
        page.evaluate("window.__copyMode = 'success'")
        button.click()
        success = page.locator('.toast[data-toast-kind="success"]')
        success.wait_for()
        success.hover()
        page.wait_for_timeout(7100)
        assert success.count() == 1
        page.mouse.move(10, 10)
        close = success.locator("[data-toast-close]")
        close.focus()
        page.wait_for_timeout(7100)
        assert success.count() == 1
        close.click()
        assert page.evaluate("document.activeElement.id") == "feedback-copy"
        no_js = browser.new_context(java_script_enabled=False, viewport={"width": 390, "height": 844})
        no_js.add_cookies([{"name": auth.SESSION_COOKIE, "value": session, "url": base + "/"}])
        no_js_page = no_js.new_page()
        no_js_page.goto(f"{base}/?lang=en&undo_stay=123")
        assert no_js_page.locator(".toast-undo").inner_text() == "Undo"
        form = no_js_page.locator(".toast-undo").locator("xpath=..")
        assert form.get_attribute("method") == "post"
        assert "/reservations/123/unarchive" in form.get_attribute("action")
        assert no_js_page.locator("[data-feedback-rail]").get_attribute("aria-live") == "off"
        no_js.close()
        browser.close()
