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


def test_dashboard_geometry_locales_and_screenshots(dashboard_host, base):
    shots = os.environ.get("UBYHOST_SHOTS_DIR")
    cookie = dashboard_host["client"].cookies.get(auth.SESSION_COOKIE)
    assert cookie

    with sync_api.sync_playwright() as playwright:
        browser = _launch(playwright)
        for locale in ("en", "cs"):
            for width in (360, 390, 1280):
                context = browser.new_context(viewport={"width": width, "height": 1000})
                context.add_cookies([{"name": auth.SESSION_COOKIE, "value": cookie, "url": base + "/"}])
                context.add_init_script("""window.__copyWrites = []; Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText: value => { window.__copyWrites.push(value); return Promise.resolve(); } } });""")
                page = context.new_page()
                page_errors = []
                page.on("pageerror", lambda error: page_errors.append(str(error)))
                page.goto(f"{base}/?lang={locale}")
                page.wait_for_load_state("networkidle")
                security_later = page.locator("#security-prompt [data-security-prompt-later]")
                if security_later.is_visible():
                    security_later.click()
                page.evaluate("window.scrollTo(0, 0)")
                assert "has-js" in (page.locator("html").get_attribute("class") or "")
                assert not page_errors, f"browser script errors: {page_errors}"

                assert page.locator(".dashboard-stats .dashboard-stat").count() == 4
                rows = page.locator(".dashboard-row")
                assert 1 <= rows.count() <= 5
                assert page.locator("#current").count() == 1
                assert page.locator(".dashboard-stat.waiting").get_attribute("href") == "#current"
                own_row = page.locator(f'.dashboard-row[data-stay-id="{dashboard_host["reservation"]}"]')
                assert own_row.count() == 1
                assert page.evaluate("() => document.documentElement.scrollWidth - innerWidth") <= 1

                open_action = own_row.get_by_role("link", name="Open" if locale == "en" else "Otevřít", exact=True)
                more_action = own_row.locator(".row-menu-trigger")
                assert more_action.get_attribute("aria-label") == ("More actions" if locale == "en" else "Další akce")
                assert more_action.inner_text() == ""
                open_box, more_box = open_action.bounding_box(), more_action.bounding_box()
                assert abs(open_box["y"] - more_box["y"]) <= 2
                assert open_box["x"] + open_box["width"] <= more_box["x"] + 1
                more_action.click()
                panel = page.locator(".row-menu-panel.is-open")
                assert panel.is_visible(), (
                    f"menu did not open: expanded={more_action.get_attribute('aria-expanded')}, "
                    f"scrollY={page.evaluate('window.scrollY')}, menu={own_row.locator('.row-menu').inner_html()}"
                )
                assert panel.get_by_role("menuitem", name="Add a guest" if locale == "en" else "Přidat hosta").is_visible()
                assert panel.get_by_role("menuitem", name="Open guest form" if locale == "en" else "Otevřít formulář hosta").is_visible()
                assert panel.locator('button[data-copy][role="menuitem"]').count() == 1
                copy_source_id = panel.locator('button[data-copy][role="menuitem"]').get_attribute("data-copy")
                copy_source = page.locator(f"#{copy_source_id}")
                assert copy_source.count() == 1 and copy_source.get_attribute("tabindex") == "-1"
                if width <= 390:
                    touch_targets = [open_action, more_action]
                    touch_targets.extend(panel.locator('[role="menuitem"]').all())
                    assert len(touch_targets) >= 6
                    for target in touch_targets:
                        target_box = target.bounding_box()
                        assert target_box["height"] >= 44, (
                            f"touch target is only {target_box['height']}px high in {locale}/{width}"
                        )
                else:
                    assert abs(open_box["height"] - 42) <= 1
                    assert abs(more_box["height"] - 42) <= 1

                page.keyboard.press("Escape")
                assert not panel.is_visible()
                assert more_action.evaluate("el => el === document.activeElement")
                more_action.focus()
                page.keyboard.press("Enter")
                assert panel.is_visible()
                assert panel.get_by_role("menuitem").first.evaluate("el => el === document.activeElement")
                page.keyboard.press("ArrowDown")
                assert panel.get_by_role("menuitem").nth(1).evaluate("el => el === document.activeElement")
                page.keyboard.press("Home")
                assert panel.get_by_role("menuitem").first.evaluate("el => el === document.activeElement")
                page.keyboard.press("End")
                assert panel.get_by_role("menuitem").last.evaluate("el => el === document.activeElement")
                page.keyboard.press("Tab")
                assert not panel.is_visible()
                assert page.evaluate("document.activeElement !== document.body")
                page.mouse.click(10, 10)
                if shots:
                    os.makedirs(shots, exist_ok=True)
                    page.evaluate("window.scrollTo(0, 0)")
                    page.screenshot(path=os.path.join(shots, f"dashboard-single-{locale}-{width}.png"), full_page=True)
                context.close()
        browser.close()


def test_dashboard_rich_queue_colors_cap_and_interaction_screenshots(dashboard_rich_host, base):
    """Exercise actual queue data, positive count colors, cap, hover and focus."""
    shots = os.environ.get("UBYHOST_SHOTS_DIR")
    cookie = dashboard_rich_host["client"].cookies.get(auth.SESSION_COOKIE)
    assert cookie
    with sync_api.sync_playwright() as playwright:
        browser = _launch(playwright)
        for locale in ("en", "cs"):
            for width in (360, 390, 1280, 1440, 1680, 1920, 2048):
                context = browser.new_context(viewport={"width": width, "height": 1000})
                context.add_cookies([{"name": auth.SESSION_COOKIE, "value": cookie, "url": base + "/"}])
                context.add_init_script("""window.__copyWrites = []; Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText: value => { window.__copyWrites.push(value); return Promise.resolve(); } } });""")
                page = context.new_page()
                page_errors = []
                page.on("pageerror", lambda error: page_errors.append(str(error)))
                page.goto(f"{base}/?lang={locale}")
                page.wait_for_load_state("networkidle")
                security_later = page.locator("#security-prompt [data-security-prompt-later]")
                if security_later.is_visible():
                    security_later.click()
                page.evaluate("window.scrollTo(0, 0)")
                assert not page_errors, f"browser script errors: {page_errors}"

                cards = page.locator(".dashboard-stats .dashboard-stat")
                assert cards.count() == 4
                for kind, count in (("action", 6), ("waiting", 1), ("ready", 1), ("overdue", 1)):
                    card = page.locator(f".dashboard-stat.{kind}")
                    assert card.locator("strong").inner_text() == str(count)
                    assert "is-positive" in (card.get_attribute("class") or "")
                    assert card.evaluate("el => getComputedStyle(el).boxShadow") != "none"
                rows = page.locator(".dashboard-row")
                assert rows.count() == 5
                shown_ids = [int(value) for value in rows.evaluate_all("nodes => nodes.map(node => node.dataset.stayId)")]
                assert len(set(shown_ids)) == 5
                assert set(shown_ids) <= dashboard_rich_host["all_actionable"]
                assert dashboard_rich_host["overdue"] in shown_ids
                assert dashboard_rich_host["ready"] in shown_ids
                assert page.locator(".dashboard-row-task .pill.amber").count() >= 1
                ready_row = page.locator(f'.dashboard-row[data-stay-id="{dashboard_rich_host["ready"]}"]')
                assert ready_row.locator(".dashboard-row-task .pill.blue").count() == 1
                overdue_row = page.locator(f'.dashboard-row[data-stay-id="{dashboard_rich_host["overdue"]}"]')
                assert "is-overdue" in (overdue_row.get_attribute("class") or "")
                overflow = page.locator("#needs-action > p a")
                assert overflow.count() == 1
                assert "1" in overflow.inner_text()
                # The waiting stay is counted but hidden because the five-row
                # cap is consumed by actionable work. Do not claim the current
                # queue is empty or link the count to a nonexistent section.
                assert page.locator("#current").count() == 0
                assert page.locator(".dashboard-stat.waiting").get_attribute("href") == "/reservations"
                assert page.get_by_text("No guest forms are currently outstanding.", exact=True).count() == 0
                assert page.evaluate("() => document.documentElement.scrollWidth - innerWidth") <= 1

                header_actions = page.locator(".dashboard-actions")
                assert header_actions.locator('a[href="/reservations?new=1"]').is_visible()
                assert header_actions.locator('form[action="/sync"]').is_visible()
                assert header_actions.locator('form[action="/demo/reset"]').is_visible()
                header_buttons = header_actions.locator(
                    ".action-group > .btn, .action-group > form > .btn, .action-group .sync-cta .btn"
                )
                assert header_buttons.count() == 3
                header_boxes = [button.bounding_box() for button in header_buttons.all()]
                assert all(abs(box["height"] - (44 if width <= 390 else 42)) <= 1 for box in header_boxes)
                if width > 390:
                    assert max(box["y"] for box in header_boxes) - min(box["y"] for box in header_boxes) <= 2

                if width >= 1440:
                    # On ultrawide screens the dashboard title/actions, count
                    # cards, and queue should share the same centered lane.
                    lane_boxes = page.evaluate("""() => [
                      '.host-today-head', '.dashboard-stats', '#needs-action'
                    ].map(selector => {
                      const rect = document.querySelector(selector).getBoundingClientRect();
                      return {selector, left: rect.left, right: rect.right};
                    })""")
                    for box in lane_boxes[1:]:
                        assert abs(box["left"] - lane_boxes[0]["left"]) <= 2, lane_boxes
                        assert abs(box["right"] - lane_boxes[0]["right"]) <= 2, lane_boxes

                # Save the base view before interaction, with real statuses and
                # all four positive counters visible.
                if shots:
                    os.makedirs(shots, exist_ok=True)
                    page.screenshot(path=os.path.join(shots, f"dashboard-{locale}-{width}.png"), full_page=True)

                row = page.locator(f'.dashboard-row[data-stay-id="{dashboard_rich_host["ready"]}"]')
                open_action = row.get_by_role("link", name="Open" if locale == "en" else "Otevřít", exact=True)
                more_action = row.locator(".row-menu-trigger")
                open_box, more_box = open_action.bounding_box(), more_action.bounding_box()
                assert abs(open_box["y"] - more_box["y"]) <= 2
                assert open_box["x"] + open_box["width"] <= more_box["x"] + 1
                assert more_action.inner_text() == ""
                assert abs(open_box["height"] - (44 if width <= 760 else 42)) <= 1
                assert abs(more_box["height"] - (44 if width <= 760 else 42)) <= 1

                before_hover = open_action.evaluate("el => getComputedStyle(el).backgroundColor")
                open_action.hover()
                page.wait_for_timeout(350)
                after_hover = open_action.evaluate("el => getComputedStyle(el).backgroundColor")
                assert before_hover != after_hover, f"Open link hover did not change in {locale}/{width}"
                if shots:
                    page.screenshot(path=os.path.join(shots, f"dashboard-hover-{locale}-{width}.png"), full_page=True)

                more_action.focus()
                page.keyboard.press("Shift+Tab")
                assert open_action.evaluate("el => el === document.activeElement")
                assert open_action.evaluate("el => getComputedStyle(el).outlineStyle") != "none"
                if shots:
                    page.screenshot(path=os.path.join(shots, f"dashboard-focus-{locale}-{width}.png"), full_page=True)

                if locale == "en" and width == 360:
                    more_action.click()
                    panel = page.locator(".row-menu-panel.is-open")
                    assert panel.is_visible()
                    copy = panel.locator('button[data-copy][role="menuitem"]')
                    assert copy.count() == 1
                    source_id = copy.get_attribute("data-copy")
                    source = page.locator(f"#{source_id}")
                    assert source.get_attribute("tabindex") == "-1"
                    link = panel.locator('a[href^="/l/"][target="_blank"]').get_attribute("href")
                    assert source.input_value().endswith(link)
                    copy.click()
                    page.wait_for_function("window.__copyWrites.length === 1")
                    assert page.evaluate("window.__copyWrites[0]") == source.input_value()
                    assert page.evaluate("window.__copyWrites[0]").endswith(link)
                    page.keyboard.press("Escape")
                    assert not panel.is_visible()
                    assert more_action.evaluate("el => el === document.activeElement")
                    more_action.click()
                    panel = page.locator(".row-menu-panel.is-open")
                    page.keyboard.press("End")
                    delete = panel.get_by_role("menuitem", name="Delete")
                    assert delete.evaluate("el => el === document.activeElement")
                    delete.click()
                    confirm = page.locator("#confirm-dialog")
                    assert confirm.get_attribute("open") is not None
                    confirm.locator("[data-confirm-cancel]").click()
                    assert confirm.get_attribute("open") is None
                    assert page.locator(f'.dashboard-row[data-stay-id="{dashboard_rich_host["ready"]}"]').count() == 1

                if width in (360, 390, 1280, 1920):
                    evidence_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "generated_images", "0041-evidence")
                    os.makedirs(evidence_dir, exist_ok=True)
                    row.locator(".dashboard-row-actions").screenshot(path=os.path.join(evidence_dir, f"dashboard-actions-{locale}-{width}.png"))
                context.close()
        browser.close()
