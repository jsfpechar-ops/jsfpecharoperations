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
        const sourceForm = document.createElement('form'); sourceForm.dataset.feedbackSourceForm = 'true'; sourceForm.append(source);
        const button = document.createElement('button');
        button.id = 'feedback-copy'; button.type = 'button'; button.dataset.copy = source.id;
        button.dataset.copyLabel = 'Copy'; button.dataset.copiedLabel = document.documentElement.lang === 'cs' ? 'Zkopírováno' : 'Copied';
        button.textContent = 'Copy';
        main.append(sourceForm, button);
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
            page.evaluate("window.scrollTo(0, 0)")
            before = button.bounding_box()
            before_scroll = page.evaluate("window.scrollY")
            before_document_y = before["y"] + before_scroll
            button.click()
            page.wait_for_function("document.querySelector('#feedback-copy').getAttribute('aria-label') === (document.documentElement.lang === 'cs' ? 'Zkopírováno' : 'Copied')")
            after = button.bounding_box()
            after_scroll = page.evaluate("window.scrollY")
            feedback_layout = page.evaluate("""() => {
              const region = document.querySelector('[data-host-feedback]');
              const rail = document.querySelector('[data-feedback-rail]');
              const action = document.querySelector('#feedback-copy');
              const r = rail.getBoundingClientRect(), a = action.getBoundingClientRect();
              return { position: getComputedStyle(rail).position, insideMain: document.querySelector('main').contains(region),
                top: r.top, bottom: r.bottom, actionTop: a.top, actionBottom: a.bottom,
                overlapsAction: r.left < a.right && r.right > a.left && r.top < a.bottom && r.bottom > a.top };
            }""")
            assert feedback_layout["insideMain"]
            assert feedback_layout["position"] != "fixed", feedback_layout
            assert not feedback_layout["overlapsAction"], feedback_layout
            assert after["width"] == pytest.approx(before["width"], abs=0.5)
            assert after["height"] == pytest.approx(before["height"], abs=0.5)
            assert after["y"] + after_scroll == pytest.approx(before_document_y, abs=1), {"before": before, "after": after, "scroll": (before_scroll, after_scroll)}
            assert button.get_attribute("aria-label") == ("Copied" if locale == "en" else "Zkopírováno")
            assert page.locator("[data-feedback-rail] [data-toast]").count() == 0
            assert page.locator("[data-feedback-live]").inner_text() == ("Copied" if locale == "en" else "Zkopírováno")
            assert page.evaluate("document.activeElement.id") == "feedback-copy"
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
                geometry = page.locator(".toast-stack").evaluate("el => { const r=el.getBoundingClientRect(); return {left:r.left, right:r.right, width:el.clientWidth, scrollWidth:el.scrollWidth}; }")
                assert geometry["left"] >= -1 and geometry["right"] <= width + 1, geometry
                assert geometry["scrollWidth"] <= geometry["width"] + 1, geometry
                assert page.locator("[data-feedback-rail] [data-toast]").count() == 0
                page.screenshot(path=str(shots / f"{locale}-{width}.png"), full_page=True)
            page.wait_for_timeout(1700)
            after_reset = button.bounding_box()
            reset_scroll = page.evaluate("window.scrollY")
            assert after_reset["y"] + reset_scroll == pytest.approx(before_document_y, abs=1)
            assert not button.evaluate("el => el.classList.contains('copied')")
            assert button.get_attribute("aria-label") is None

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
                assert manual_source.evaluate("el => el.form && el.getAttribute('form') === el.form.id && el.form.id.startsWith('ubyhost-manual-copy-form-')")
                recovery = page.locator("[data-copy-recovery]")
                assert recovery.is_visible()
                assert manual_source.locator("xpath=ancestor::*[@data-copy-recovery-source]").count() == 1
                assert page.evaluate("getSelection().toString() || document.activeElement.value") == "synthetic-copy-value"
                manual_geometry = manual_source.evaluate("el => { const r=el.getBoundingClientRect(); return {left:r.left, top:r.top, right:r.right, bottom:r.bottom, width:innerWidth, height:innerHeight}; }")
                assert manual_geometry["left"] >= -1 and manual_geometry["top"] >= -1
                assert manual_geometry["right"] <= width + 1 and manual_geometry["bottom"] <= 901, manual_geometry
                recovery_geometry = recovery.evaluate("el => { const r=el.getBoundingClientRect(); return {top:r.top,bottom:r.bottom,close:el.querySelector('[data-copy-recovery-close]').getBoundingClientRect().toJSON()}; }")
                rail_geometry = page.locator("[data-feedback-rail]").evaluate("el => el.getBoundingClientRect().toJSON()")
                assert recovery_geometry["top"] >= rail_geometry["bottom"] - 1, (rail_geometry, recovery_geometry)
                assert not (manual_geometry["left"] < recovery_geometry["close"]["right"] and manual_geometry["right"] > recovery_geometry["close"]["left"] and manual_geometry["top"] < recovery_geometry["close"]["bottom"] and manual_geometry["bottom"] > recovery_geometry["close"]["top"]), (manual_geometry, recovery_geometry)
                page.screenshot(path=str(shots / f"failure-{locale}-{width}.png"), full_page=True)
                if locale == "en" and width == 360:
                    recovery.locator("[data-copy-recovery-close]").click()
                    assert not recovery.is_visible()
                    assert manual_source.get_attribute("data-copy-manual-visible") is None
                    assert manual_source.evaluate("el => el.parentElement.dataset.feedbackSourceForm === 'true' && el.classList.contains('sr-only') && el.hidden === false && !el.hasAttribute('form') && el.form === el.parentElement && el.form.id === ''")
                    assert page.evaluate("document.activeElement.id") == "feedback-copy"
                    page.locator("[data-toast-close]").first.click()
                    assert page.locator('.toast[data-toast-kind="error"]').count() == 0
                else:
                    page.locator("[data-toast-close]").first.click()
                    assert page.locator('.toast[data-toast-kind="error"]').count() == 1
                    assert manual_source.locator("xpath=ancestor::*[@data-toast-kind='error']").count() == 1
                while page.locator("[data-toast-close]").count():
                    page.locator("[data-toast-close]").first.click()
                assert manual_source.get_attribute("data-copy-manual-visible") is None
                assert manual_source.evaluate("el => el.parentElement.dataset.feedbackSourceForm === 'true' && el.classList.contains('sr-only') && el.hidden === false && !el.hasAttribute('form') && el.form === el.parentElement && el.form.id === ''")

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
        page.screenshot(path=str(shots / "failure-en-1280.png"), full_page=True)
        page.locator("[data-toast-close]").first.click()
        assert page.locator("#feedback-copy-source").get_attribute("data-copy-manual-visible") is None
        page.evaluate("sessionStorage.removeItem('__fullFeedbackRail')")
        page.reload()

        page.route("**/api/command-palette", lambda route: route.fulfill(json={"items": [{"label": "Copy guest link", "copy": "https://example.test/guest-secret", "group": "Actions"}]}))
        page.evaluate("window.__copyMode = 'reject'")
        for command_width in (360, 1280):
            page.set_viewport_size({"width": command_width, "height": 900})
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
            geometry = page.evaluate("""() => {
              const d = document.querySelector('#command-dialog').getBoundingClientRect();
              const f = document.querySelector('.command-copy-error').getBoundingClientRect();
              const t = document.querySelector('.command-copy-error textarea').getBoundingClientRect();
              return { width: innerWidth, height: innerHeight, dialog: d.toJSON(), failure: f.toJSON(), source: t.toJSON() };
            }""")
            assert geometry["dialog"]["left"] >= -1 and geometry["dialog"]["right"] <= command_width + 1, geometry
            assert geometry["dialog"]["top"] >= -1 and geometry["dialog"]["bottom"] <= 901, geometry
            assert geometry["failure"]["left"] >= geometry["dialog"]["left"] - 1 and geometry["failure"]["right"] <= geometry["dialog"]["right"] + 1, geometry
            assert geometry["source"]["left"] >= geometry["failure"]["left"] - 1 and geometry["source"]["right"] <= geometry["failure"]["right"] + 1, geometry
            page.screenshot(path=str(shots / f"command-copy-failure-en-{command_width}.png"), full_page=True)
            page.keyboard.press("Control+a")
            assert page.evaluate("document.activeElement === document.querySelector('#command-dialog textarea')")
            assert page.evaluate("getSelection().toString() || document.activeElement.value") == "https://example.test/guest-secret"
            page.locator("[data-command-input]").fill("no matching command")
            assert command.locator("[role=alert]").count() == 0
            assert command.locator("[data-command-results]").get_attribute("role") == "listbox"
            page.locator("[data-command-close]").click()
            assert command.get_attribute("open") is None
            assert command.locator("[role=alert]").count() == 0

        # Command-palette success keeps the shared seven-second notification behavior.
        page.evaluate("window.__copyMode = 'success'")
        opener = page.locator(".command-trigger")
        opener.click()
        page.locator("#command-dialog").wait_for(state="visible")
        page.get_by_role("option", name="Copy guest link").click()
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
        assert success.count() == 0
        assert opener.evaluate("el => document.activeElement === el")

        # A copy receipt must stay in place at both a top and a scrolled action.
        for action_position in ("top", "scrolled"):
            page.goto(f"{base}/?lang=en")
            page.wait_for_selector("[data-feedback-rail]", state="attached")
            page.evaluate("""position => {
              const main = document.querySelector('main');
              const region = document.querySelector('[data-host-feedback]');
              const form = document.querySelector('[data-feedback-source-form]');
              const button = document.querySelector('#feedback-copy');
              if (position === 'top') region.after(form, button);
              else main.append(form, button);
              const documentY = button.getBoundingClientRect().top + window.scrollY;
              window.scrollTo(0, position === 'top' ? 0 : Math.max(0, documentY - 400));
            }""", action_position)
            button = page.locator("#feedback-copy")
            baseline = button.evaluate("el => el.getBoundingClientRect().top + window.scrollY")
            scroll_before = page.evaluate("window.scrollY")
            button.click()
            page.wait_for_function("document.querySelector('#feedback-copy').classList.contains('copied')")
            after_insert = button.evaluate("el => el.getBoundingClientRect().top + window.scrollY")
            scroll_after = page.evaluate("window.scrollY")
            assert after_insert == pytest.approx(baseline, abs=1), {"position": action_position, "scroll": (scroll_before, scroll_after), "baseline": baseline, "after": after_insert}
            assert page.locator("[data-feedback-rail] [data-toast]").count() == 0
            page.wait_for_timeout(7100)
            after_receipt = button.evaluate("el => el.getBoundingClientRect().top + window.scrollY")
            assert after_receipt == pytest.approx(baseline, abs=1), {"position": action_position, "baseline": baseline, "after": after_receipt}

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
