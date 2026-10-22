"""Browser geometry and localization coverage for the Quiet host overview."""
from __future__ import annotations

import os
import secrets
import socket
import threading
import time
from datetime import timedelta

import pytest

REQUIRE_BROWSER = os.environ.get("UBYHOST_REQUIRE_BROWSER") == "1"
if REQUIRE_BROWSER:
    import playwright.sync_api as sync_api
else:
    sync_api = pytest.importorskip("playwright.sync_api")

import uvicorn
from fastapi.testclient import TestClient

from app import auth, claim, db, demo, onboarding
from app.main import app
from tests.browser_support import chromium_launch_kwargs
from tests.conftest import login_as


@pytest.fixture(scope="module")
def dashboard_host():
    db.init_db()
    username = f"quiet-dashboard-{secrets.token_hex(4)}"
    owner_id = auth.create_account(
        f"{username}@example.test", "Quiet Dashboard", role="host", username=username
    )
    entity_id = db.insert("legal_entity", {
        "name": "Quiet Dashboard s.r.o.", "seat": "Praha", "ico": "12345678",
        "contact_email": "quiet@example.test", "owner_user_id": owner_id,
        "created_at": db.utcnow(),
    })
    apartment_id = db.insert("apartment", {
        "legal_entity_id": entity_id, "owner_user_id": owner_id,
        "internal_name": "Quiet Flat", "permalink_token": f"quiet{secrets.token_hex(4)}",
        "permalink_pin": "123456", "automation_mode": "manual",
        "submit_after_hours": 24, "active": 1, "created_at": db.utcnow(),
    })
    today = claim.prague_today()
    reservation_id = db.insert("reservation", {
        "apartment_id": apartment_id, "source": "manual", "uid": f"quiet-{secrets.token_hex(4)}",
        "date_from": today.isoformat(), "date_to": (today + timedelta(days=2)).isoformat(),
        "expected_guests_override": 1,
        "status": "active", "created_at": db.utcnow(), "updated_at": db.utcnow(),
    })
    client = TestClient(app)
    response = login_as(client, username, url="/login?lang=en", follow_redirects=False)
    assert response.status_code == 303, response.text
    onboarding.set_dismissed(owner_id, True)
    yield {"client": client, "reservation": reservation_id}
    db.execute("DELETE FROM settings WHERE key = ?", (f"onboarding_dismissed_{owner_id}",))
    db.execute("DELETE FROM alert WHERE owner_user_id = ?", (owner_id,))
    db.execute("DELETE FROM audit WHERE owner_user_id = ?", (owner_id,))
    db.execute("DELETE FROM reservation WHERE apartment_id = ?", (apartment_id,))
    db.execute("DELETE FROM apartment WHERE id = ?", (apartment_id,))
    db.execute("DELETE FROM legal_entity WHERE id = ?", (entity_id,))
    db.execute("DELETE FROM user_account WHERE id = ?", (owner_id,))


@pytest.fixture(scope="module")
def dashboard_rich_host():
    """A real queue with every positive count and more actions than fit."""
    db.init_db()
    username = f"quiet-dashboard-rich-{secrets.token_hex(4)}"
    owner_id = auth.create_account(
        f"{username}@example.test", "Quiet Dashboard Review", role="host", username=username
    )
    now = db.utcnow()
    entity_id = db.insert("legal_entity", {
        "name": "Quiet Dashboard Review s.r.o.", "seat": "Praha", "ico": "87654321",
        "contact_email": "quiet-review@example.test", "owner_user_id": owner_id,
        "created_at": now,
    })
    apartment_id = db.insert("apartment", {
        "legal_entity_id": entity_id, "owner_user_id": owner_id,
        "internal_name": "Review Flat", "permalink_token": f"review{secrets.token_hex(4)}",
        "permalink_pin": "123456", "automation_mode": "manual",
        "submit_after_hours": 24, "active": 1, "created_at": now,
    })
    # Exercise the dashboard's real calendar-sync and clear-demo actions in
    # screenshots without calling either action or using a live feed.
    demo_apartment_id = db.insert("apartment", {
        "legal_entity_id": entity_id, "owner_user_id": owner_id,
        "internal_name": demo.DEMO_APARTMENT, "permalink_token": f"demo{secrets.token_hex(4)}",
        "permalink_pin": "123456", "automation_mode": "manual",
        "submit_after_hours": 24, "active": 1, "created_at": now,
    })
    db.insert("ical_feed", {
        "apartment_id": demo_apartment_id, "url": "https://example.test/synthetic.ics",
        "label": "Synthetic calendar", "active": 1, "created_at": now,
    })
    today = claim.prague_today()

    def stay(label, arrival, departure, expected=1):
        return db.insert("reservation", {
            "apartment_id": apartment_id, "source": "manual",
            "uid": f"quiet-review-{label}-{secrets.token_hex(3)}",
            "date_from": arrival.isoformat(), "date_to": departure.isoformat(),
            "status": "active", "expected_guests_override": expected,
            "created_at": now, "updated_at": now,
        })

    # One old unresolved stay must remain visible and count as overdue.
    overdue_id = stay("old-overdue", today - timedelta(days=62), today - timedelta(days=60))
    # Five additional actionable stays, including one complete reportable guest
    # that is ready to send. Their order makes the ready stay part of the cap.
    ready_id = stay("ready", today + timedelta(days=1), today + timedelta(days=3))
    incomplete_ids = [
        stay(f"incomplete-{offset}", today + timedelta(days=offset), today + timedelta(days=offset + 2))
        for offset in (2, 3, 4, 5)
    ]
    waiting_id = stay("waiting", today, today + timedelta(days=2), expected=None)
    db.insert("guest", {
        "reservation_id": ready_id, "surname": "NOVAK", "first_name": "TOMAS",
        "birth_date": "01011990", "nationality": "GBR", "doc_number": "P1234567",
        "res_street": "Street 1", "res_city": "London", "res_country": "GBR",
        "purpose": "10", "is_lead": 1, "entered_by": "host",
        "signature_png": "imported", "signed_at": now, "identity_verified_at": now,
        "submit_state": "pending", "created_at": now, "updated_at": now,
    })
    client = TestClient(app)
    response = login_as(client, username, url="/login?lang=en", follow_redirects=False)
    assert response.status_code == 303, response.text
    onboarding.set_dismissed(owner_id, True)
    yield {
        "client": client, "overdue": overdue_id, "ready": ready_id,
        "incomplete": incomplete_ids, "waiting": waiting_id,
        "all_actionable": {overdue_id, ready_id, *incomplete_ids},
    }
    db.execute("DELETE FROM settings WHERE key = ?", (f"onboarding_dismissed_{owner_id}",))
    db.execute("DELETE FROM alert WHERE owner_user_id = ?", (owner_id,))
    db.execute("DELETE FROM audit WHERE owner_user_id = ?", (owner_id,))
    db.execute("DELETE FROM guest WHERE reservation_id IN (SELECT id FROM reservation WHERE apartment_id = ?)", (apartment_id,))
    db.execute("DELETE FROM reservation WHERE apartment_id = ?", (apartment_id,))
    db.execute("DELETE FROM apartment WHERE id = ?", (demo_apartment_id,))
    db.execute("DELETE FROM apartment WHERE id = ?", (apartment_id,))
    db.execute("DELETE FROM legal_entity WHERE id = ?", (entity_id,))
    db.execute("DELETE FROM user_account WHERE id = ?", (owner_id,))


@pytest.fixture(scope="module")
def base(dashboard_host):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 15
    while not server.started and time.time() < deadline:
        time.sleep(0.05)
    if not server.started:
        pytest.fail("the dashboard test server did not start")
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=5)


def _launch(playwright):
    try:
        return playwright.chromium.launch(**chromium_launch_kwargs())
    except Exception:
        if REQUIRE_BROWSER:
            raise
        pytest.skip("Chromium is required for dashboard geometry coverage")


WIDTHS = (360, 390, 760, 1280, 1440, 2000)
LOCALES = ("en", "cs", "vi")
TONE_RANK = {"red": 0, "amber": 1, "grey": 2}

# 0243: every visible line of "What needs you", measured in one pass.
CARD_JS = """() => {
  const card = document.querySelector('.needs-you');
  if (!card) return null;
  const rect = el => { const b = el.getBoundingClientRect(); return {l: b.left, r: b.right, t: b.top, b: b.bottom, w: b.width, h: b.height}; };
  const style = el => getComputedStyle(el);
  const shown = el => el.offsetParent !== null;
  const items = [...card.querySelectorAll('.needs-you-item')].filter(shown).map(li => {
    const copy = li.querySelector('.needs-you-copy');
    const buttons = [...li.querySelectorAll('.needs-you-actions a, .needs-you-actions button')].filter(shown);
    return {
      kind: li.dataset.needsYou, tone: li.dataset.tone, text: copy.textContent.trim().slice(0, 80), box: rect(li),
      border: [style(li).borderTopStyle, parseFloat(style(li).borderTopWidth), parseFloat(style(li).borderLeftWidth), style(li).borderLeftColor],
      copy: rect(copy), copyOverflow: copy.scrollWidth > copy.clientWidth + 1,
      buttons: buttons.map(b => Object.assign(rect(b), {text: b.innerText.trim(), clipped: b.scrollWidth > b.clientWidth + 1})),
    };
  });
  return {card: rect(card), cardBorder: [style(card).borderTopStyle, parseFloat(style(card).borderTopWidth)], items,
          header: rect(document.querySelector('.ui-ph')),
          calendar: document.querySelector('#calendar') ? rect(document.querySelector('#calendar')) : null,
          scroll: document.documentElement.scrollWidth - innerWidth,
          stack: !!document.querySelector('.notification-stack')};
}"""


def _open(browser, base, cookie, locale, width, collapsed=False):
    context = browser.new_context(viewport={"width": width, "height": 1000})
    context.add_cookies([{"name": auth.SESSION_COOKIE, "value": cookie, "url": base + "/"}])
    flag = "1" if collapsed else "0"
    context.add_init_script(f"try {{ localStorage.setItem('ubyhost-sidebar-collapsed', '{flag}'); }} catch (e) {{}}")
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(f"{base}/?lang={locale}")
    page.wait_for_load_state("networkidle")
    later = page.locator("#security-prompt [data-security-prompt-later]")
    if later.is_visible():
        later.click()
    page.evaluate("window.scrollTo(0, 0)")
    return context, page, errors


def _check_card(geo, width, label):
    """Borders, lane, touch targets, no overflow and no overlap for every visible line."""
    assert geo, f"{label}: no What needs you card"
    assert geo["scroll"] <= 1, (label, "horizontal scroll", geo["scroll"])
    assert not geo["stack"], f"{label}: the alert stack is shown next to the card"
    card = geo["card"]
    assert geo["cardBorder"][0] == "solid" and geo["cardBorder"][1] >= 1, (label, geo["cardBorder"])
    for edge in ("l", "r"):
        assert abs(card[edge] - geo["header"][edge]) <= 2, (label, "lane", card, geo["header"])
        if geo["calendar"]:
            assert abs(card[edge] - geo["calendar"][edge]) <= 2, (label, "calendar lane", card, geo["calendar"])
    if geo["calendar"]:
        assert geo["calendar"]["t"] >= card["b"] - 0.5, (label, "card overlaps calendar")
    tone_colours = {}
    for item in geo["items"]:
        where = (label, item["kind"], item["text"])
        box, copy = item["box"], item["copy"]
        assert box["l"] >= card["l"] - 0.5 and box["r"] <= card["r"] + 0.5, where
        assert item["border"][0] == "solid" and item["border"][1] >= 1, where + (item["border"],)
        assert item["border"][2] >= 3.5, where + (item["border"],)
        tone_colours.setdefault(item["tone"], set()).add(item["border"][3])
        assert not item["copyOverflow"], where
        assert copy["l"] >= box["l"] - 0.5 and copy["r"] <= box["r"] + 0.5, where
        assert 1 <= len(item["buttons"]) <= 2, where + (item["buttons"],)
        for button in item["buttons"]:
            assert button["h"] >= 43.5, where + (button,)
            assert button["w"] >= (43.5 if width <= 767 else 39.5), where + (button,)
            assert not button["clipped"], where + (button,)
            assert button["l"] >= box["l"] - 0.5 and button["r"] <= box["r"] + 0.5, where + (button,)
            assert button["t"] >= box["t"] - 0.5 and button["b"] <= box["b"] + 0.5, where + (button,)
            overlap_x = min(button["r"], copy["r"]) - max(button["l"], copy["l"])
            overlap_y = min(button["b"], copy["b"]) - max(button["t"], copy["t"])
            assert overlap_x <= 0.5 or overlap_y <= 0.5, where + ("button overlaps text", button, copy)
    for tone, colours in tone_colours.items():
        assert len(colours) == 1, (label, tone, colours)
    if "red" in tone_colours and "amber" in tone_colours:
        assert tone_colours["red"] != tone_colours["amber"], (label, tone_colours)


def _check_focus(page, label):
    page.keyboard.press("Tab")
    button = page.locator(".needs-you > .needs-you-list .needs-you-actions .ui-btn").first
    button.focus()
    ring = button.evaluate("el => [getComputedStyle(el).outlineStyle, parseFloat(getComputedStyle(el).outlineWidth)]")
    assert ring[0] != "none" and ring[1] >= 2, (label, ring)


def test_dashboard_single_stay_needs_you_card(dashboard_host, base):
    shots = os.environ.get("UBYHOST_SHOTS_DIR")
    cookie = dashboard_host["client"].cookies.get(auth.SESSION_COOKIE)
    assert cookie
    stay_id = dashboard_host["reservation"]
    with sync_api.sync_playwright() as playwright:
        browser = _launch(playwright)
        for locale in LOCALES:
            for width in (360, 390, 1280):
                label = f"single/{locale}/{width}"
                context, page, errors = _open(browser, base, cookie, locale, width)
                assert "has-js" in (page.locator("html").get_attribute("class") or "")
                assert not errors, (label, errors)
                assert page.locator("[data-calendar]").count() == 1
                assert page.locator(".dashboard-stats, .dashboard-row, .ui-banner-attention").count() == 0, label
                line = page.locator(f'.needs-you-item[data-needs-you-stay="{stay_id}"]')
                assert line.count() == 1, label
                assert line.get_attribute("data-tone") == "amber", label
                link = line.locator(".needs-you-actions .ui-btn")
                assert link.count() == 1, label
                assert link.get_attribute("href") == f"/reservations/{stay_id}?return_to=/#now", label
                _check_card(page.evaluate(CARD_JS), width, label)
                _check_focus(page, label)
                if shots:
                    os.makedirs(shots, exist_ok=True)
                    page.mouse.click(1, 1)
                    page.evaluate("window.scrollTo(0, 0)")
                    page.screenshot(path=os.path.join(shots, f"dashboard-single-{locale}-{width}.png"), full_page=True)
                if locale == "en" and width == 390:
                    with page.expect_navigation():
                        link.click()
                    assert page.url.endswith(f"/reservations/{stay_id}?return_to=/#now")
                    assert page.locator("#now").is_visible()
                    assert page.evaluate("document.querySelector('#now').getBoundingClientRect().top") < 1000
                context.close()
        browser.close()


def test_dashboard_rich_needs_you_order_cap_and_geometry(dashboard_rich_host, base):
    shots = os.environ.get("UBYHOST_SHOTS_DIR")
    cookie = dashboard_rich_host["client"].cookies.get(auth.SESSION_COOKIE)
    assert cookie
    overdue, ready = dashboard_rich_host["overdue"], dashboard_rich_host["ready"]
    with sync_api.sync_playwright() as playwright:
        browser = _launch(playwright)
        for locale in LOCALES:
            for width in WIDTHS:
                for collapsed in ((False, True) if width >= 1280 else (False,)):
                    label = f"rich/{locale}/{width}/{'collapsed' if collapsed else 'open'}"
                    context, page, errors = _open(browser, base, cookie, locale, width, collapsed)
                    assert not errors, (label, errors)

                    # Order: red first, then amber, then grey, across every line (shown or behind "Show more").
                    tones = page.locator(".needs-you-item").evaluate_all("nodes => nodes.map(node => node.dataset.tone)")
                    assert tones, label
                    ranks = [TONE_RANK[tone] for tone in tones]
                    assert ranks == sorted(ranks), (label, tones)
                    first = page.locator(".needs-you > .needs-you-list > .needs-you-item").first
                    assert first.get_attribute("data-needs-you-stay") == str(overdue), label
                    assert first.get_attribute("data-tone") == "red", label
                    ready_line = page.locator(f'.needs-you-item[data-needs-you-stay="{ready}"]')
                    assert ready_line.count() == 1 and ready_line.get_attribute("data-tone") == "amber", label
                    assert ready_line.locator(".ui-btn").get_attribute("href") == f"/reservations/{ready}?return_to=/#now"
                    for later in dashboard_rich_host["incomplete"]:
                        assert page.locator(f'.needs-you-item[data-needs-you-stay="{later}"]').count() == 0, label

                    # At most five lines open; the rest behind one "Show N more".
                    shown = page.locator(".needs-you > .needs-you-list > .needs-you-item").count()
                    total = len(tones)
                    assert shown == min(total, 5), (label, shown, total)
                    more = page.locator(".needs-you-more:not([data-paste-check]) > summary")
                    assert more.count() == (1 if total > 5 else 0), label
                    if total > 5:
                        assert str(total - 5) in more.inner_text(), (label, more.inner_text())
                    paste_line = page.locator('.needs-you-item[data-needs-you="paste"]')
                    if paste_line.count() and paste_line.first.is_visible():
                        how = paste_line.first.locator("[data-paste-check] > summary")
                        assert how.is_visible(), label
                        how_box, copy_box = how.bounding_box(), paste_line.first.locator(".needs-you-copy").bounding_box()
                        assert how_box["y"] >= copy_box["y"] + copy_box["height"] - 1, (label, how_box, copy_box)
                    assert page.locator('.needs-you-item[data-needs-you="setup"]', has_text="(demo)").count() == 0, label

                    # Header: one primary action; below 1024 px the rest sit in the overflow menu.
                    header_buttons = page.locator(".ui-ph-acts .ui-btn:not(.ui-ph-menu)")
                    visible_buttons = [button for button in header_buttons.all() if button.is_visible()]
                    if width < 1024:
                        assert len(visible_buttons) == 1, label
                        assert page.locator(".ui-ph-menu").is_visible(), label
                    header_boxes = [button.bounding_box() for button in visible_buttons]
                    assert all(abs(box["height"] - (44 if width <= 767 else 40)) <= 1 for box in header_boxes), label

                    _check_card(page.evaluate(CARD_JS), width, label)
                    _check_focus(page, label)
                    if shots:
                        os.makedirs(shots, exist_ok=True)
                        page.mouse.click(1, 1)
                        page.evaluate("window.scrollTo(0, 0)")
                        state = "collapsed" if collapsed else "open"
                        page.screenshot(path=os.path.join(shots, f"dashboard-{locale}-{width}-{state}.png"), full_page=True)
                    if total > 5:
                        more.click()
                        _check_card(page.evaluate(CARD_JS), width, label + "/more")
                        hidden_lines = page.locator(".needs-you-more .needs-you-item")
                        assert all(line.is_visible() for line in hidden_lines.all()), label
                    context.close()
        browser.close()
