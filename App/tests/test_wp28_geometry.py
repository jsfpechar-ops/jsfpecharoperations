"""WP28: computed geometry for the defects the UI sweep found in the demo.

Markup cannot show that a button hangs out of its card or that a table hides
its last column, so these load the seeded demo workspace in Chromium, in the
style of tests/test_host_geometry.py. Skipped without Playwright unless
UBYHOST_REQUIRE_BROWSER=1.
"""
import os
import secrets
import socket
import threading
import time

import pytest

REQUIRE_BROWSER = os.environ.get("UBYHOST_REQUIRE_BROWSER") == "1"
if REQUIRE_BROWSER:
    import playwright.sync_api as sync_api
else:
    sync_api = pytest.importorskip("playwright.sync_api")

import uvicorn
from fastapi.testclient import TestClient

from app import auth, db, demo, reporting
from app.main import app
from tests.browser_support import chromium_launch_kwargs
from tests.conftest import login_as


NO_SIDEWAYS_SCROLL = "() => document.documentElement.scrollWidth - document.documentElement.clientWidth"


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
    deadline = time.time() + 15
    while not server.started and time.time() < deadline:
        time.sleep(0.05)
    if not server.started:
        pytest.fail("the test server did not start")
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=5)


@pytest.fixture(scope="module")
def world():
    db.init_db()
    username = f"sweepgeo{secrets.token_hex(4)}"
    owner = auth.create_account(f"{username}@example.test", "Sweep Geometry", role="host", username=username)
    studio = demo.seed(owner)
    assert studio, "the demo seed needs UBYHOST_UBYPORT_ENV=mock"
    client = TestClient(app)
    response = login_as(client, username, url="/login?lang=en", follow_redirects=False)
    assert response.status_code == 303, response.text
    stay = None
    for row in db.query(
        "SELECT * FROM reservation WHERE apartment_id = ? AND status = 'active' ORDER BY date_from", (studio,)
    ):
        registered = db.query_one("SELECT COUNT(*) AS n FROM guest WHERE reservation_id = ?", (row["id"],))["n"]
        if registered and (reporting.expected_guest_count(row) or 0) > registered:
            stay = row
            break
    token = db.query_one("SELECT permalink_token FROM apartment WHERE id = ?", (studio,))["permalink_token"]
    return {
        "session": client.cookies.get(auth.SESSION_COOKIE),
        "studio": studio,
        "stay": stay["id"] if stay else None,
        "token": token,
    }


@pytest.fixture(scope="module")
def browser():
    with sync_api.sync_playwright() as playwright:
        try:
            chromium = playwright.chromium.launch(**chromium_launch_kwargs())
        except Exception as exc:
            if REQUIRE_BROWSER:
                raise
            pytest.skip(f"Chromium is not available: {exc}")
        yield chromium
        chromium.close()


def _page(browser, base, world, width, signed_in=True):
    context = browser.new_context(viewport={"width": width, "height": 900})
    if signed_in:
        context.add_cookies([{"name": auth.SESSION_COOKIE, "value": world["session"], "url": base + "/"}])
    return context, context.new_page()


@pytest.mark.parametrize("width", [390, 1280])
def test_guest_links_message_wraps_instead_of_widening_the_page(base, world, browser, width):
    context, page = _page(browser, base, world, width)
    try:
        page.goto(base + "/guest-links?lang=en")
        page.wait_for_selector(".message-template")
        assert page.evaluate(NO_SIDEWAYS_SCROLL) <= 1
    finally:
        context.close()


def test_calendar_remove_button_is_visible_without_scrolling(base, world, browser):
    context, page = _page(browser, base, world, 1280)
    try:
        page.goto(f"{base}/apartments/{world['studio']}?lang=en")
        page.wait_for_selector(".feed-table")
        box = page.evaluate(
            """() => {
              const wrap = document.querySelector('.feed-table').closest('.scroll-x');
              const button = wrap.querySelector('.row-actions .btn');
              const w = wrap.getBoundingClientRect(), b = button.getBoundingClientRect();
              const name = wrap.querySelector('td strong');
              const range = document.createRange(); range.selectNodeContents(name);
              const lines = new Set([...range.getClientRects()].map(r => Math.round(r.top))).size;
              return {inside: b.right <= w.right + 1 && b.left >= w.left - 1,
                      hidden: wrap.scrollWidth - wrap.clientWidth, nameLines: lines,
                      overflow: getComputedStyle(wrap).overflowX};
            }"""
        )
    finally:
        context.close()
    assert box["overflow"] == "auto"
    assert box["inside"], box
    assert box["hidden"] <= 1, box
    assert box["nameLines"] == 1, "the feed name broke mid-word"


def test_stay_page_cards_hold_their_buttons(base, world, browser):
    if not world["stay"]:
        pytest.skip("the demo seed has no partly registered stay")
    context, page = _page(browser, base, world, 1280)
    try:
        page.goto(f"{base}/reservations/{world['stay']}?lang=en")
        page.wait_for_selector(".guest-card.placeholder")
        measured = page.evaluate(
            """() => {
              const R = el => el.getBoundingClientRect();
              const out = {placeholders: [], verify: null, filing: null};
              document.querySelectorAll('.guest-card.placeholder').forEach(card => {
                const c = R(card);
                const worst = Math.max(...[...card.querySelectorAll('.btn')].map(b => R(b).bottom));
                out.placeholders.push(Math.round(c.bottom - worst));
              });
              const verify = document.querySelector('.guest-card .verify-form .btn');
              if (verify) {
                const card = verify.closest('.guest-card');
                out.verify = Math.round(R(card).bottom - R(verify).bottom);
              }
              const filing = document.querySelector('#file-by-hand');
              if (filing) out.filing = parseFloat(getComputedStyle(filing).paddingLeft);
              return out;
            }"""
        )
    finally:
        context.close()
    assert measured["placeholders"], measured
    assert min(measured["placeholders"]) >= 8, f"a button sits on the card edge: {measured}"
    if measured["verify"] is not None:
        assert measured["verify"] >= 8, f"Mark ID checked touches the card edge: {measured}"
    if measured["filing"] is not None:
        assert measured["filing"] >= 12, "the hand-filing panel lost its padding"


def test_overdue_deadline_is_a_pill_not_a_bar(base, world, browser):
    overdue = db.query_one(
        "SELECT r.id FROM reservation r WHERE r.apartment_id = ? AND r.status = 'active' "
        "AND r.date_from < date('now', '-5 day') ORDER BY r.date_from LIMIT 1",
        (world["studio"],),
    )
    if not overdue:
        pytest.skip("the demo seed has no overdue stay")
    context, page = _page(browser, base, world, 1280)
    try:
        page.goto(f"{base}/reservations/{overdue['id']}?lang=en")
        widths = page.evaluate(
            """() => { const pill = document.querySelector('.metric-value.deadline.overdue');
              if (!pill) return null;
              return [pill.getBoundingClientRect().width, pill.parentElement.getBoundingClientRect().width]; }"""
        )
    finally:
        context.close()
    if widths is None:
        pytest.skip("the stay is not overdue on this date")
    assert widths[0] < widths[1] * 0.8, widths


def test_operator_signature_block_is_styled(base, world, browser):
    context, page = _page(browser, base, world, 1280)
    try:
        page.goto(base + "/entities?lang=en")
        page.wait_for_selector(".signature-block")
        style = page.evaluate(
            """() => { const f = document.querySelector('.signature-block'); const cs = getComputedStyle(f);
              const b = [...f.querySelectorAll('.action-group .btn')].map(e => Math.round(e.getBoundingClientRect().top));
              return {border: cs.borderTopStyle, radius: parseFloat(cs.borderTopLeftRadius), tops: b}; }"""
        )
    finally:
        context.close()
    assert style["border"] == "solid"
    assert style["radius"] > 0
    assert len(set(style["tops"])) == 1, f"Clear and Upload image are not level: {style}"


def test_guest_privacy_notice_fits_a_phone(base, world, browser):
    context, page = _page(browser, base, world, 390, signed_in=False)
    try:
        page.goto(f"{base}/l/{world['token']}/privacy?lang=en")
        page.wait_for_selector("table")
        assert page.evaluate(NO_SIDEWAYS_SCROLL) <= 1
    finally:
        context.close()
