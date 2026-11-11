"""1086/1100: the police letter flow in a real browser, with Turbo and with no script.

Filing HIGH RISK: a wrong value means filings under the wrong account. Every
value here is a fake ``SAMPLE_*`` one and the police client is always a fake.
Set UBYHOST_SHOTS_1097 (or UBYHOST_SHOTS_1086) to a folder to also write the review screenshots.
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
from app.ubyport_sample_pdf import (
    SAMPLE_FACILITY_LINE1,
    SAMPLE_FACILITY_LINE2,
    SAMPLE_IDUB,
    SAMPLE_WS_PASSWORD,
    SAMPLE_WS_USER,
    SAMPLE_ZKRATKA,
)
from tests.browser_support import chromium_launch_kwargs, settle_motion
from tests.test_police_letter_flow import LETTER, MARKER, fake_client, host, no_client  # noqa: F401

if os.environ.get("UBYHOST_REQUIRE_BROWSER") == "1":
    import playwright.sync_api as sync_api
else:
    sync_api = pytest.importorskip("playwright.sync_api")

WIDTHS = [390, 768, 1280]
FIELDS = ("uby_idub", "uby_ws_user", "uby_mark")
READ_ONLY = {"TestDostupnosti", "MaximalniDelkaSeznamu", "DejMiCiselnik"}
SHOTS = os.environ.get("UBYHOST_SHOTS_1097") or os.environ.get("UBYHOST_SHOTS_1086")
# 1100: the flow tests' letter plus the facility lines, so all five boxes fill.
FULL_LETTER = f"{LETTER}Ubytovací zařízení:\n{SAMPLE_FACILITY_LINE1}\n{SAMPLE_FACILITY_LINE2}\n"
READ_BUTTON = "[data-letter-read]"
TEST_BUTTON = 'button[formaction$="/test-connection"]'
SAVE_BUTTON = '.savebar button[form="property-settings-form"]'
SAVE_ROW = ".savebar[data-for='property-settings-form']"


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


def paste(page, js=True):
    """Paste the fake letter. With JS it fills in place; without, the button posts and the page comes back."""
    page.locator("details.police-letter-paste").evaluate("d => { d.open = true; }")  # 1099: may start open
    page.fill("#letter_text", FULL_LETTER)
    if js:
        with page.expect_response(lambda r: r.url.endswith("/police-letter")) as reply:
            page.dispatch_event("#letter_text", "paste")
        assert reply.value.status == 200
        assert reply.value.headers.get("content-type", "").startswith("application/json")
        page.wait_for_function(f"() => document.getElementById('uby_idub').value === '{SAMPLE_IDUB}'", timeout=2000)
    else:
        with page.expect_response(lambda r: r.url.endswith("/police-letter")) as reply:
            page.locator(READ_BUTTON).click()
        assert reply.value.status == 422
    assert reply.value.headers.get("cache-control") == "no-store"


def assert_filled(page):
    """1100: the five boxes hold the letter values, the password in plain sight; no check block, no tick."""
    assert page.input_value("#uby_idub") == SAMPLE_IDUB
    assert page.input_value("#uby_ws_user") == SAMPLE_WS_USER
    assert page.input_value("#uby_mark") == SAMPLE_ZKRATKA
    assert page.input_value("#uby_name") == SAMPLE_FACILITY_LINE1
    assert page.input_value("#uby_ws_password") == SAMPLE_WS_PASSWORD
    assert page.get_attribute("#uby_ws_password", "type") == "text"
    assert page.locator("#uby_ws_password").is_visible()
    assert page.locator("[data-letter-fields]").get_attribute("value") == ",".join(FIELDS)
    status = page.locator("#police-letter-status").inner_text()
    assert en("police_letter.filled", names="").split(":")[0] in status, status
    for name in ("setup.label.idub", "setup.label.login", "setup.label.password", "setup.label.facility"):
        assert en(name) in status, (name, status)
    assert page.locator("#police-letter-check").count() == 0
    assert page.locator("#letter_ok, [name=letter_ok]").count() == 0
    for name in FIELDS + ("uby_ws_password", "uby_name"):
        assert page.locator(f'[name="{name}"]').count() == 1, name
    assert MARKER not in page.content()


@pytest.mark.parametrize("width", WIDTHS)
def test_the_find_card_shows_the_drawn_letter(live, no_client, width):  # noqa: F811
    page = live.open(width)
    page.goto(live.url)
    page.locator("details.police-letter-find").evaluate("d => { d.open = true; }")  # 1099: may start open
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
def test_paste_fills_in_place_and_saves_with_turbo(live, fake_client, width):  # noqa: F811
    page = live.open(width)
    dialogs = []
    page.on("dialog", lambda d: (dialogs.append(d.type), d.accept()))
    before = saved_row()
    page.goto(live.url)
    assert page.evaluate("() => typeof window.Turbo === 'object'"), "Turbo is not loaded on the editor"
    assert not page.locator(READ_BUTTON).is_visible()
    page.evaluate("() => { window.__uby1100 = 1; }")
    paste(page)
    assert page.evaluate("() => window.__uby1100") == 1, "the paste must not load a page"
    assert_filled(page)
    assert page.locator(SAVE_ROW).is_visible()
    assert saved_row() == before
    assert fits(page)
    shot(page, "filled", width)

    # Save with no tick: saved, and tested once with read-only calls.
    page.locator(SAVE_BUTTON).click()
    page.get_by_text(en("flash.apartments.letter_test_ok")).first.wait_for()
    assert saved_row() == {"uby_idub": SAMPLE_IDUB, "uby_ws_user": SAMPLE_WS_USER, "uby_mark": SAMPLE_ZKRATKA}
    assert len(fake_client["made"]) == 1
    calls = fake_client["made"][0].calls
    assert calls and set(calls) <= READ_ONLY, calls
    assert SAMPLE_WS_PASSWORD not in page.content(), "the stored password is never rendered"

    # Pasted again, password cleared by hand: saved, and no client is built.
    page.goto(live.url)
    paste(page)
    page.fill("#uby_ws_password", "")
    page.locator(SAVE_BUTTON).click()
    page.get_by_text(en("flash.apartments.letter_saved_untested")).first.wait_for()
    assert len(fake_client["made"]) == 1
    assert dialogs == [], dialogs
    assert fits(page)


@pytest.mark.parametrize("width", WIDTHS)
def test_paste_without_javascript_fills_the_boxes_and_saves(live, fake_client, width):  # noqa: F811
    page = live.open(width, js=False)
    before = saved_row()
    page.goto(live.url)
    assert page.locator(READ_BUTTON).is_visible()
    paste(page, js=False)
    assert page.url.endswith("/police-letter")
    assert page.locator("#property-settings-form").get_attribute("data-dirty-start") == "1"
    assert page.locator("#sec-police[open]").count() == 1
    assert_filled(page)
    assert saved_row() == before

    # Back returns to the property page with nothing kept.
    page.go_back()
    assert page.url == live.url
    assert page.input_value("#uby_ws_password") == ""

    paste(page, js=False)
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
    page.locator("details.police-letter-paste").evaluate("d => { d.open = true; }")  # 1099: may start open
    page.locator("details.police-letter-find").evaluate("d => { d.open = false; }")  # 1099: starts open in first setup
    page.wait_for_timeout(400)
    settle_motion(page)
    if width == 390:
        shot(page, "paste-open", width)
    paste(page)
    page.wait_for_timeout(300)
    settle_motion(page)
    seen = page.evaluate(
        """() => {
          const r = (el) => el.getBoundingClientRect();
          const one = (sel) => document.querySelector(sel);
          const all = (sel) => [...document.querySelectorAll(sel)];
          const paste = one('details.police-letter-paste');
          const style = getComputedStyle(paste);
          const tall = (sel) => all(sel).filter(e => e.getClientRects().length).map(e => r(e).height);
          const card = one('#ubyport');
          return {
            pasteBottom: r(paste).bottom,
            findBottom: r(one('details.police-letter-find')).bottom,
            pasteTop: r(paste).top,
            statusTop: r(one('#police-letter-status')).top,
            statusBottom: r(one('#police-letter-status')).bottom,
            idubTop: r(one('label[for=uby_idub]')).top,
            textarea: r(one('#letter_text')).width,
            column: r(paste).width - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight),
            summaries: tall('#ubyport details.police-letter-find > summary, #ubyport details.police-letter-paste > summary'),
            buttons: tall('#ubyport button.ui-btn'),
            boxes: tall('#ubyport input[type=text]'),
            cut: all('#ubyport label, #ubyport summary, #police-letter-status')
              .filter(e => e.clientWidth > 0 && e.scrollWidth > e.clientWidth).map(e => e.textContent.trim()),
            card: card.scrollWidth <= card.clientWidth,
            focus: document.activeElement && document.activeElement.id,
          };
        }"""
    )
    assert abs(seen["pasteTop"] - seen["findBottom"]) < 1, seen
    assert seen["statusTop"] >= seen["pasteBottom"], seen
    assert seen["idubTop"] - seen["statusBottom"] >= 8, seen
    assert seen["cut"] == [], seen
    if width < 768:
        assert abs(seen["textarea"] - seen["column"]) <= 1, seen
        for name in ("summaries", "buttons", "boxes"):
            assert seen[name] and min(seen[name]) >= 44, (name, seen[name])
    assert seen["focus"] == "letter_text", seen
    assert seen["card"] and fits(page)
    assert no_client == []


@pytest.mark.parametrize("width", WIDTHS)
def test_a_box_changed_without_javascript_saves_the_typed_value(live, no_client, width):  # noqa: F811
    """1100: every value is its own box; a typed IDUB after the read is what Save stores, no tick."""
    page = live.open(width, js=False)
    page.goto(live.url)
    paste(page, js=False)
    assert page.locator("#uby_idub").is_visible()
    assert fits(page)
    new_idub = "987654321098"
    page.fill("#uby_idub", new_idub)
    page.fill("#uby_ws_password", "")
    page.locator(SAVE_BUTTON).click()
    page.get_by_text(en("flash.apartments.letter_saved_untested")).first.wait_for()
    assert saved_row() == {"uby_idub": new_idub, "uby_ws_user": SAMPLE_WS_USER, "uby_mark": SAMPLE_ZKRATKA}
    assert no_client == []


@pytest.mark.parametrize("width", WIDTHS)
def test_the_police_section_phone_fixes(live, no_client, width):  # noqa: F811
    """1097 F2 (Send timing text) and F3 (full-width test button). F1 is blocked, see docs/tasks/1097-report.md."""
    page = live.open(width)
    page.goto(live.url)
    settle_motion(page)
    if width == 390:
        shot(page, "plain", width)
    f3 = page.evaluate(
        """() => {
          const btn = document.querySelector('#ubyport button[formaction$="/test-connection"]');
          const box = btn.parentElement.getBoundingClientRect();
          const b = btn.getBoundingClientRect();
          const lh = parseFloat(getComputedStyle(btn).lineHeight) || 20;
          const range = document.createRange(); range.selectNodeContents(btn);
          return {w: b.width, h: b.height, parent: box.width, lines: range.getClientRects().length,
                  secondary: btn.classList.contains('ui-btn-secondary'), lh};
        }"""
    )
    assert f3["secondary"], f3
    if width < 768:
        assert abs(f3["w"] - f3["parent"]) <= 1 and f3["h"] >= 44 and f3["lines"] == 1, f3
    else:
        assert f3["w"] < f3["parent"] - 1, f3

    if width == 390:
        for lang in ("cs", "en"):
            page.goto(live.plain + f"?view=settings&section=reporting&lang={lang}#automation")
            for value in ("manual", "scheduled", "immediate"):
                page.select_option("#automation_mode", value)
                fit = page.evaluate(
                    """() => {
                      const sel = document.querySelector('#automation_mode');
                      const style = getComputedStyle(sel);
                      const ctx = document.createElement('canvas').getContext('2d');
                      ctx.font = style.font || `${style.fontWeight} ${style.fontSize} ${style.fontFamily}`;
                      const text = sel.options[sel.selectedIndex].text.trim();
                      const room = sel.clientWidth - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight);
                      return {text, width: ctx.measureText(text).width, room, overflow: style.textOverflow};
                    }"""
                )
                assert fit["width"] <= fit["room"], (lang, value, fit)
                assert fit["overflow"] != "ellipsis", fit
            assert fits(page)
