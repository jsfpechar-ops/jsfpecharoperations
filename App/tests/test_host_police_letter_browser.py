"""1086: the police letter flow in a real browser, with Turbo and with no script.

Filing HIGH RISK: a wrong value means filings under the wrong account. Every
value here is a fake ``SAMPLE_*`` one and the police client is always a fake.
Set UBYHOST_SHOTS_1086 to a folder to also write the review screenshots.
"""
from __future__ import annotations

import os
import socket
import threading
import time
from pathlib import Path

import pytest

from app import auth, db, host_i18n
from app.main import app
from app.ubyport_sample_pdf import SAMPLE_IDUB, SAMPLE_WS_PASSWORD, SAMPLE_WS_USER, SAMPLE_ZKRATKA
from tests.browser_support import chromium_launch_kwargs, settle_motion
from tests.test_police_letter_flow import LETTER, MARKER, fake_client, host, no_client  # noqa: F401

if os.environ.get("UBYHOST_REQUIRE_BROWSER") == "1":
    import playwright.sync_api as sync_api
else:
    sync_api = pytest.importorskip("playwright.sync_api")

WIDTHS = [390, 768, 1280]
FIELDS = ("uby_idub", "uby_ws_user", "uby_mark")
READ_ONLY = {"TestDostupnosti", "MaximalniDelkaSeznamu", "DejMiCiselnik"}
SHOTS = os.environ.get("UBYHOST_SHOTS_1086")
TYPED_PASSWORD = "typed-by-hand-1086"
READ_BUTTON = "details.police-letter-paste .actions button"
TEST_BUTTON = 'button[formaction$="/test-connection"]'
SAVE_BUTTON = '.savebar button[form="property-settings-form"]'


def en(key: str, **params) -> str:
    text = host_i18n.translate("en", key, **params)
    assert text and text != key, key
    return str(text)


def saved_row() -> dict:
    row = db.query(
        "SELECT * FROM apartment WHERE owner_user_id = "
        "(SELECT id FROM user_account WHERE username = ?) ORDER BY id",
        ("police-letter-host",),
    )[0]
    return {name: row[name] for name in FIELDS}


def apartment_id() -> int:
    return db.query(
        "SELECT id FROM apartment WHERE owner_user_id = "
        "(SELECT id FROM user_account WHERE username = ?) ORDER BY id",
        ("police-letter-host",),
    )[0]["id"]


@pytest.fixture
def live(host):  # noqa: F811
    """The app on a local port, plus a browser. ``open(width, js)`` gives a signed-in page."""
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    import uvicorn

    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 15
    while not server.started and time.time() < deadline:
        time.sleep(0.05)
    assert server.started, "the test server did not start"
    base = f"http://127.0.0.1:{port}"
    page_path = f"/apartments/{apartment_id()}"

    class Live:
        plain = base + page_path
        url = f"{base}{page_path}?view=settings&section=reporting#ubyport"

        def open(self, width, js=True):
            context = browser.new_context(viewport={"width": width, "height": 1000}, java_script_enabled=js)
            context.add_cookies(
                [{"name": auth.SESSION_COOKIE, "value": host.cookies.get(auth.SESSION_COOKIE), "url": base + "/"}]
            )
            return context.new_page()

    try:
        with sync_api.sync_playwright() as playwright:
            browser = playwright.chromium.launch(**chromium_launch_kwargs())
            yield Live()
            browser.close()
    finally:
        server.should_exit = True
        thread.join(timeout=5)


def shot(page, name, width, full_page=False):
    if not SHOTS:
        return
    page.wait_for_timeout(700)
    Path(SHOTS).mkdir(parents=True, exist_ok=True)
    path = str(Path(SHOTS) / f"{name}-{width}.png")
    if full_page:
        page.screenshot(path=path, full_page=True)
    else:
        page.locator("#ubyport").screenshot(path=path)


def fits(page) -> bool:
    return page.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth")


def paste(page, expect_status=422):
    """Open the paste row, paste the fake letter and read it."""
    page.locator("details.police-letter-paste > summary").click()
    page.fill("#letter_text", LETTER)
    with page.expect_response(lambda r: r.url.endswith("/police-letter")) as reply:
        page.locator(READ_BUTTON).click()
    assert reply.value.status == expect_status
    assert reply.value.headers.get("cache-control") == "no-store"
    page.wait_for_selector("#police-letter-check")


def tick_all(page):
    for name in FIELDS:
        page.check(f"#letter_ok_{name}")


def assert_check_block(page):
    """The three rows, each with its source and its required tick; never the password."""
    rows = page.locator("#police-letter-check [data-letter-row]")
    assert rows.evaluate_all("els => els.map(e => e.dataset.letterRow)") == list(FIELDS)
    assert page.input_value("#uby_idub") == SAMPLE_IDUB
    assert page.input_value("#uby_ws_user") == SAMPLE_WS_USER
    assert page.input_value("#uby_mark") == SAMPLE_ZKRATKA
    assert page.input_value("#uby_ws_password") == ""
    assert page.input_value("#letter_text") == ""
    for name in FIELDS:
        row = page.locator(f'[data-letter-row="{name}"]')
        assert row.locator(".police-letter-src code").count() >= 1, name
        assert row.locator(".police-letter-src code").first.inner_text().strip(), name
        assert row.locator(f"#letter_ok_{name}[required]").count() == 1, name
        label = row.locator(f'label[for="letter_ok_{name}"]')
        assert en("police_letter.confirm") in label.inner_text(), name
        assert label.locator(".req-star").count() == 1, name
    mark = page.locator('[data-letter-row="uby_mark"]')
    assert mark.locator(".police-letter-value").inner_text().strip() == SAMPLE_ZKRATKA
    line = mark.locator('input[name="letter_line_uby_mark"]').get_attribute("value")
    assert en("police_letter.source_login", line=line) in mark.locator(".police-letter-src").inner_text()
    content = page.content()
    assert SAMPLE_WS_PASSWORD not in content
    assert MARKER not in content


@pytest.mark.parametrize("width", WIDTHS)
def test_the_find_card_shows_the_drawn_letter(live, no_client, width):  # noqa: F811
    page = live.open(width)
    page.goto(live.url)
    page.locator("details.police-letter-find > summary").click()
    page.wait_for_timeout(400)
    settle_motion(page)
    assert page.locator(".police-letter-svg").is_visible()
    seen = page.evaluate(
        """() => {
          const panel = document.querySelector('details.police-letter-find').getBoundingClientRect();
          const svg = document.querySelector('.police-letter-svg');
          const box = svg.getBoundingClientRect();
          const scale = box.width / 320;
          const labels = [...svg.querySelectorAll('.pl-label')].map(t => t.getBBox());
          const values = [...svg.querySelectorAll('.pl-value')].map(t => t.getBBox());
          const narrow = [...document.querySelectorAll('.police-letter-legend li, .police-letter-legend p')]
            .filter(e => e.scrollWidth > e.clientWidth).map(e => e.textContent.trim());
          return {
            inside: box.left >= panel.left - 0.5 && box.right <= panel.right + 0.5
              && box.top >= panel.top && box.bottom <= panel.bottom + 0.5,
            lines: [...svg.querySelectorAll('.pl-num-text')].map(t => t.textContent),
            labelEnds: labels.map(b => b.x + b.width),
            valueStarts: values.map(b => b.x),
            valueEnds: values.map(b => b.x + b.width),
            valuePx: parseFloat(getComputedStyle(svg.querySelector('.pl-value')).fontSize) * scale,
            legend: document.querySelectorAll('.police-letter-legend li').length,
            narrow,
          };
        }"""
    )
    assert seen["inside"], seen
    assert seen["lines"] == ["1", "2", "3"] and seen["legend"] == 3
    for end, start in zip(seen["labelEnds"], seen["valueStarts"]):
        assert end < start, seen
    assert max(seen["valueEnds"]) <= 316, seen
    assert seen["valuePx"] >= 7.5, seen
    assert seen["narrow"] == [], seen
    assert fits(page)
    shot(page, "find", width)
    assert no_client == []


@pytest.mark.parametrize("width", WIDTHS)
def test_paste_check_and_confirm_with_turbo(live, fake_client, width):  # noqa: F811
    page = live.open(width)
    dialogs, posts = [], []
    page.on("dialog", lambda d: (dialogs.append(d.type), d.accept()))
    page.on("request", lambda r: posts.append(r.url) if r.method == "POST" else None)
    before = saved_row()
    page.goto(live.plain)
    page.goto(live.url)
    assert page.evaluate("() => typeof window.Turbo === 'object'"), "Turbo is not loaded on the editor"
    paste(page)
    page.wait_for_timeout(300)
    # With Turbo loaded the 422 reply still shows the block, and it is in view.
    assert page.evaluate("() => typeof window.Turbo === 'object'")
    assert page.locator("#police-letter-check").is_visible()
    top = page.evaluate("() => document.querySelector('#police-letter-check').getBoundingClientRect().top")
    assert 0 <= top < 1000, top
    assert_check_block(page)
    assert fits(page)
    shot(page, "check", width)
    shot(page, "lint-check", width, full_page=True)

    # Back returns to the property page, with nothing kept from the paste.
    page.go_back()
    page.wait_for_load_state()
    assert page.url.split("?")[0].split("#")[0] == live.plain
    assert page.locator("#police-letter-check").count() == 0
    assert saved_row() == before

    page.goto(live.url)
    paste(page)
    # Save with no tick: the browser refuses it, so nothing is posted.
    # (The Save row appears with the first tick.)
    page.check("#letter_ok_uby_idub")
    sent = len(posts)
    page.locator(SAVE_BUTTON).click()
    page.wait_for_timeout(300)
    assert len(posts) == sent
    assert page.evaluate("() => document.querySelector('#letter_ok_uby_ws_user').validity.valueMissing")
    page.uncheck("#letter_ok_uby_idub")
    # "Save and test connection" skips the browser check: the server refuses it.
    with page.expect_response(lambda r: r.url.endswith("/test-connection")) as refused:
        page.locator(TEST_BUTTON).click()
    assert refused.value.status == 400
    page.wait_for_selector("#letter_ok_uby_idub-error")
    assert page.locator("#police-letter-check").is_visible()
    for name in FIELDS:
        assert page.locator(f"#letter_ok_{name}-error").count() == 1, name
    assert page.locator("#police-letter-check [data-field-error]").count() == 3
    assert saved_row() == before
    assert fake_client["made"] == []
    assert fits(page)

    # Ticked, with a typed password: saved, and tested once with read-only calls.
    tick_all(page)
    page.fill("#uby_ws_password", TYPED_PASSWORD)
    page.locator(SAVE_BUTTON).click()
    page.get_by_text(en("flash.apartments.letter_test_ok")).first.wait_for()
    assert en("flash.apartments.letter_test_ok") == "Saved. The login and password work."
    assert saved_row() == {"uby_idub": SAMPLE_IDUB, "uby_ws_user": SAMPLE_WS_USER, "uby_mark": SAMPLE_ZKRATKA}
    assert len(fake_client["made"]) == 1
    calls = fake_client["made"][0].calls
    assert calls and set(calls) <= READ_ONLY, calls
    assert TYPED_PASSWORD not in page.content()

    # Pasted again, ticked, no password: saved, and no client is built.
    page.goto(live.url)
    paste(page)
    tick_all(page)
    page.locator(SAVE_BUTTON).click()
    page.get_by_text(en("flash.apartments.letter_saved_untested")).first.wait_for()
    assert len(fake_client["made"]) == 1
    assert dialogs == ["beforeunload"], dialogs
    assert fits(page)


@pytest.mark.parametrize("width", WIDTHS)
def test_paste_check_and_confirm_without_javascript(live, fake_client, width):  # noqa: F811
    page = live.open(width, js=False)
    before = saved_row()
    page.goto(live.url)
    paste(page)
    assert page.url.endswith("/police-letter")
    assert page.locator("#police-letter-check").is_visible()
    assert page.locator("#letter_ok_uby_idub:focus").count() == 1, "the first unticked box has no focus"
    assert page.locator("#property-settings-form").get_attribute("data-dirty-start") == "1"
    assert_check_block(page)

    # Back returns to the property page.
    page.go_back()
    assert page.url == live.url
    assert page.locator("#police-letter-check").count() == 0

    paste(page)
    with page.expect_response(lambda r: r.url.endswith("/test-connection")) as refused:
        page.locator(TEST_BUTTON).click()
    assert refused.value.status == 400
    for name in FIELDS:
        assert page.locator(f"#letter_ok_{name}-error").count() == 1, name
    assert page.locator("#police-letter-check").is_visible()
    assert saved_row() == before
    assert fake_client["made"] == []

    tick_all(page)
    page.fill("#uby_ws_password", TYPED_PASSWORD)
    page.locator(SAVE_BUTTON).click()
    page.get_by_text(en("flash.apartments.letter_test_ok")).first.wait_for()
    assert saved_row() == {"uby_idub": SAMPLE_IDUB, "uby_ws_user": SAMPLE_WS_USER, "uby_mark": SAMPLE_ZKRATKA}
    assert len(fake_client["made"]) == 1
    assert set(fake_client["made"][0].calls) <= READ_ONLY
    assert SAMPLE_WS_PASSWORD not in page.content()


@pytest.mark.parametrize("width", WIDTHS)
def test_the_letter_helper_geometry(live, no_client, width):  # noqa: F811
    page = live.open(width)
    page.goto(live.url)
    page.locator("details.police-letter-paste > summary").click()
    page.wait_for_timeout(400)
    settle_motion(page)
    closed = page.evaluate(
        """() => {
          const r = (sel) => document.querySelector(sel).getBoundingClientRect();
          const paste = document.querySelector('details.police-letter-paste');
          const style = getComputedStyle(paste);
          const inner = r('details.police-letter-paste').width
            - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight);
          return {
            buttonBottom: r('details.police-letter-paste .actions button').bottom,
            nextTop: r('label[for=uby_idub]').top,
            textarea: r('#letter_text').width,
            column: inner,
            findBottom: r('details.police-letter-find').bottom,
            pasteTop: r('details.police-letter-paste').top,
            parent: getComputedStyle(paste.parentElement).display + ' ' + getComputedStyle(paste.parentElement).rowGap
              + ' ' + paste.parentElement.tagName + '.' + paste.parentElement.className,
            findStyle: getComputedStyle(document.querySelector('details.police-letter-find')).marginBottom,
            pasteStyle: style.marginTop,
          };
        }"""
    )
    assert closed["nextTop"] - closed["buttonBottom"] >= 12, closed
    assert abs(closed["pasteTop"] - closed["findBottom"]) < 1, (closed["parent"], closed["findStyle"], closed["pasteStyle"])
    if width < 768:
        assert abs(closed["textarea"] - closed["column"]) <= 1, closed

    page.fill("#letter_text", LETTER)
    with page.expect_response(lambda r: r.url.endswith("/police-letter")):
        page.locator(READ_BUTTON).click()
    page.wait_for_selector("#police-letter-check")
    page.locator("details.police-letter-paste > summary").click()
    page.wait_for_timeout(400)
    settle_motion(page)
    seen = page.evaluate(
        """() => {
          const r = (el) => el.getBoundingClientRect();
          const one = (sel) => document.querySelector(sel);
          const all = (sel) => [...document.querySelectorAll(sel)];
          const block = r(one('#police-letter-check'));
          const card = one('#ubyport');
          const tall = (sel) => all(sel).filter(e => e.getClientRects().length).map(e => r(e).height);
          return {
            buttonBottom: r(one('details.police-letter-paste .actions button')).bottom,
            pasteBottom: r(one('details.police-letter-paste')).bottom,
            blockTop: block.top,
            blockBottom: block.bottom,
            fieldTop: r(one('label[for=uby_idub]')).top,
            ticks: tall('#police-letter-check .checkline label'),
            summaries: tall('#ubyport details.police-letter-find > summary, #ubyport details.police-letter-paste > summary'),
            buttons: tall('#ubyport button.ui-btn'),
            cut: all('#ubyport label, #ubyport .police-letter-name, #ubyport summary')
              .filter(e => e.clientWidth > 0 && e.scrollWidth > e.clientWidth).map(e => e.textContent.trim()),
            codes: all('#police-letter-check .police-letter-src code').map(c => ({
              inside: r(c).left >= block.left - 0.5 && r(c).right <= block.right + 0.5,
              scroll: c.scrollWidth <= c.clientWidth,
            })),
            card: card.scrollWidth <= card.clientWidth,
          };
        }"""
    )
    assert seen["blockTop"] - seen["buttonBottom"] >= 12, seen
    assert seen["blockTop"] >= seen["pasteBottom"], seen
    assert seen["fieldTop"] - seen["blockBottom"] >= 12, seen
    assert len(seen["ticks"]) == 3 and seen["cut"] == [], seen
    if width < 768:
        for name in ("ticks", "summaries", "buttons"):
            assert seen[name] and min(seen[name]) >= 44, (name, seen[name])
    assert seen["codes"] and all(c["inside"] and c["scroll"] for c in seen["codes"]), seen
    assert seen["card"] and fits(page)

    # The focus ring shows on a tick box reached with Tab.
    page.locator(READ_BUTTON).focus()
    page.keyboard.press("Tab")
    ring = page.evaluate(
        """() => {
          const el = document.activeElement;
          const style = getComputedStyle(el);
          return {
            id: el.id,
            visible: el.matches(':focus-visible'),
            outline: style.outlineStyle !== 'none' && parseFloat(style.outlineWidth) > 0,
            shadow: style.boxShadow !== 'none',
          };
        }"""
    )
    assert ring["id"] == "letter_ok_uby_idub" and ring["visible"], ring
    assert ring["outline"] or ring["shadow"], ring
    assert no_client == []
