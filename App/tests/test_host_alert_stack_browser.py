"""0969: repeated alert stacks stay compact, filing urgency stays fully visible.

Presentation only. Every deadline alert (its stay link, title and deadline text)
must be on every host page at every width; pages that are not about stays and
alerts of another property on a filtered Stays list show compact lines.
"""
from __future__ import annotations

import os
import secrets
import socket
import threading
import time
from datetime import timedelta
from pathlib import Path

import pytest

REQUIRE_BROWSER = os.environ.get("UBYHOST_REQUIRE_BROWSER") == "1"
if REQUIRE_BROWSER:
    import playwright.sync_api as sync_api
else:
    sync_api = pytest.importorskip("playwright.sync_api")

import uvicorn
from fastapi.testclient import TestClient

from app import alerts, auth, claim, db, onboarding
from app.main import app
from tests.browser_support import chromium_launch_kwargs
from tests.conftest import login_as, mark_security_prompt_seen

SHOTS = Path(os.environ.get("UBYHOST_SHOTS_DIR") or "/tmp/ubyhost-b11")
WIDTHS = (390, 768, 1280)

READ_JS = """() => {
  const rows = [...document.querySelectorAll('[data-host-alerts] article[data-notification]')].map(a => {
    const box = a.getBoundingClientRect();
    const link = a.querySelector('a.notification-link');
    const reasons = [...a.querySelectorAll('small')]
      .filter(s => !s.classList.contains('notification-action') && !s.hasAttribute('data-workspace-label'))
      .map(s => s.textContent.trim());
    const label = a.querySelector('[data-workspace-label]');
    return {
      id: a.dataset.alertId, scope: a.dataset.alertScope || '', compact: a.hasAttribute('data-alert-compact'),
      title: a.querySelector('strong').textContent.trim(), reasons: reasons,
      href: link ? link.getAttribute('href') : '', action: !!a.querySelector('.notification-action'),
      label: label ? label.textContent.trim() : '', dismiss: !!a.querySelector('form[data-notification-dismiss]'),
      h: box.height, right: box.right, left: box.left,
    };
  });
  const summary = document.querySelector('[data-host-alerts] [data-notification-summary]');
  return {rows: rows, summary: summary ? summary.textContent.trim() : '',
          summaryHref: summary ? summary.querySelector('a').getAttribute('href') : '',
          overflow: document.documentElement.scrollWidth - innerWidth, width: innerWidth,
          stack: !!document.querySelector('[data-host-alerts]')};
}"""


@pytest.fixture(scope="module")
def base():
    db.init_db()
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
        pytest.fail("the alert stack test server did not start")
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=5)


@pytest.fixture(scope="module")
def browser():
    with sync_api.sync_playwright() as playwright:
        try:
            instance = playwright.chromium.launch(**chromium_launch_kwargs())
        except Exception:
            if REQUIRE_BROWSER:
                raise
            pytest.skip("Chromium is required for alert stack coverage")
        yield instance
        instance.close()


@pytest.fixture
def workspace():
    """Factory: a host with two properties, overdue stays, deadline alerts and two foldable alerts."""
    made = []

    def build(tag, karlin=2, vinohrady=1, foldable=True):
        username = f"b11-{tag}-{secrets.token_hex(4)}"
        owner_id = mark_security_prompt_seen(auth.create_account(
            f"{username}@example.test", "B11 Alerts", role="host", username=username
        ))
        now = db.utcnow()
        entity_id = db.insert("legal_entity", {
            "name": "B11 Alerts s.r.o.", "seat": "Praha", "ico": "11223344",
            "contact_email": "b11@example.test", "owner_user_id": owner_id, "created_at": now,
        })

        def prop(name):
            return db.insert("apartment", {
                "legal_entity_id": entity_id, "owner_user_id": owner_id, "internal_name": name,
                "permalink_token": f"b11{secrets.token_hex(4)}", "permalink_pin": "123456",
                "automation_mode": "manual", "submit_after_hours": 24, "active": 1, "created_at": now,
            })

        karlin_id, vinohrady_id = prop("Karlin Flat"), prop("Vinohrady Flat")
        today = claim.prague_today()

        def overdue_stay(apartment_id, index):
            start = today - timedelta(days=10 + index)
            reservation_id = db.insert("reservation", {
                "apartment_id": apartment_id, "source": "manual",
                "uid": f"b11-{apartment_id}-{index}-{secrets.token_hex(3)}",
                "date_from": start.isoformat(), "date_to": (start + timedelta(days=2)).isoformat(),
                "expected_guests_override": 1, "status": "active", "created_at": now, "updated_at": now,
            })
            alerts.raise_alert(
                "critical", "deadline", f"Deadline {reservation_id}", apartment_id=apartment_id,
                reservation_id=reservation_id, owner_user_id=owner_id,
                dedupe_key=f"deadline:{reservation_id}",
            )
            return reservation_id

        stays = [overdue_stay(karlin_id, i) for i in range(karlin)]
        stays += [overdue_stay(vinohrady_id, 10 + i) for i in range(vinohrady)]
        if foldable:
            alerts.raise_alert(
                "critical", "guest_pin_abuse", "Guest link tried too often",
                apartment_id=vinohrady_id, owner_user_id=owner_id,
                dedupe_key=f"guest_pin_abuse:{vinohrady_id}",
            )
        onboarding.set_dismissed(owner_id, True)
        client = TestClient(app)
        response = login_as(client, username, url="/login?lang=en", follow_redirects=False)
        assert response.status_code == 303, response.text
        cards = [
            card for card in alerts.present_many(alerts.open_alerts(owner_id), "en")
            if card["kind"] == "deadline"
        ]
        made.append((owner_id, entity_id, [karlin_id, vinohrady_id]))
        return {
            "cookie": client.cookies.get(auth.SESSION_COOKIE), "owner": owner_id,
            "karlin": karlin_id, "vinohrady": vinohrady_id, "stays": stays,
            # Issue ids (the stay in the link) and deadline texts every page must keep showing.
            "expected": {
                (card["action_href"], card["display_title"], card["display_reason"]) for card in cards
            },
        }

    yield build
    for owner_id, entity_id, apartment_ids in made:
        db.execute("DELETE FROM settings WHERE key = ?", (f"onboarding_dismissed_{owner_id}",))
        db.execute("DELETE FROM alert WHERE owner_user_id = ?", (owner_id,))
        db.execute("DELETE FROM audit WHERE owner_user_id = ?", (owner_id,))
        for apartment_id in apartment_ids:
            db.execute("DELETE FROM reservation WHERE apartment_id = ?", (apartment_id,))
            db.execute("DELETE FROM apartment WHERE id = ?", (apartment_id,))
        db.execute("DELETE FROM legal_entity WHERE id = ?", (entity_id,))
        db.execute("DELETE FROM user_account WHERE id = ?", (owner_id,))


def _visit(browser, base, ws, path, width):
    context = browser.new_context(viewport={"width": width, "height": 900})
    context.add_cookies([{"name": auth.SESSION_COOKIE, "value": ws["cookie"], "url": base + "/"}])
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    joiner = "&" if "?" in path else "?"
    page.goto(f"{base}{path}{joiner}lang=en")
    page.wait_for_load_state("networkidle")
    later = page.locator("#security-prompt [data-security-prompt-later]")
    if later.is_visible():
        later.click()
    page.evaluate("window.scrollTo(0, 0)")
    return context, page, errors


def _read(browser, base, ws, path, width, shot=None):
    context, page, errors = _visit(browser, base, ws, path, width)
    try:
        data = page.evaluate(READ_JS)
        if shot:
            SHOTS.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(SHOTS / f"{shot}-{width}.png"))
        assert not errors, errors
        return data
    finally:
        context.close()


def _filing(data, ws):
    """The deadline alerts on a page as (stay link, title, deadline text) keys."""
    wanted = {key[0] for key in ws["expected"]}
    return [
        (row["href"], row["title"], row["reasons"][0] if row["reasons"] else "")
        for row in data["rows"] if row["href"] in wanted
    ]


def _pages(ws):
    return [
        "/reservations", f"/reservations?apartment={ws['karlin']}",
        f"/reservations?apartment={ws['vinohrady']}", "/settings", "/settings/archived", "/entities",
    ]


# --- baseline: must pass before and after the template change -------------------------------

def test_same_filing_issues_and_deadlines_on_every_page(browser, base, workspace):
    ws = workspace("same")
    assert len(ws["expected"]) == 3
    for width in WIDTHS:
        for path in _pages(ws):
            data = _read(browser, base, ws, path, width)
            found = _filing(data, ws)
            assert len(found) == 3, (path, width, found)
            assert set(found) == ws["expected"], (path, width, found, ws["expected"])
            assert data["overflow"] <= 1, (path, width, data["overflow"])
            for row in data["rows"]:
                if row["href"] in {key[0] for key in ws["expected"]}:
                    assert row["dismiss"], (path, width, row["href"])
                    assert row["right"] <= width + 1 and row["left"] >= -1, (path, width, row)


def test_zero_alerts_render_no_stack(browser, base, workspace):
    ws = workspace("zero", karlin=0, vinohrady=0, foldable=False)
    for path in ("/reservations", "/settings"):
        data = _read(browser, base, ws, path, 390, shot="zero-stays" if path == "/reservations" else None)
        assert data["stack"] is False and data["rows"] == [], (path, data)


# --- 0969 behaviour ---------------------------------------------------------------------------

def test_one_alert_is_large_on_stays_and_compact_elsewhere(browser, base, workspace):
    ws = workspace("one", karlin=1, vinohrady=0, foldable=False)
    stays = _read(browser, base, ws, "/reservations", 390, shot="one-stays")
    settings = _read(browser, base, ws, "/settings", 390, shot="one-settings")
    assert len(stays["rows"]) == 1 and len(settings["rows"]) == 1
    large, small = stays["rows"][0], settings["rows"][0]
    assert large["action"] and not large["compact"] and large["scope"] == ""
    assert small["compact"] and not small["action"]
    assert (large["href"], large["title"], large["reasons"]) == (small["href"], small["title"], small["reasons"])
    assert small["h"] < large["h"], (small["h"], large["h"])


def test_many_alerts_keep_every_deadline_and_fold_only_non_filing(browser, base, workspace):
    ws = workspace("many")
    for width in WIDTHS:
        stays = _read(browser, base, ws, "/reservations", width, shot="many-stays")
        settings = _read(browser, base, ws, "/settings", width, shot="many-settings")
        # Stays page: the guest link alert is a line of its own, nothing is folded.
        assert any("Guest link" in row["title"] for row in stays["rows"]), stays["rows"]
        # Settings: the guest link alert folds into the one dashboard line; the 3 deadlines stay.
        assert not any("Guest link" in row["title"] for row in settings["rows"]), settings["rows"]
        assert settings["summary"] and settings["summaryHref"] == "/#needs-action", settings
        assert set(_filing(settings, ws)) == ws["expected"]
        assert all(row["compact"] and not row["action"] for row in settings["rows"])
        stays_h = {row["href"]: row["h"] for row in stays["rows"]}
        for row in settings["rows"]:
            assert row["h"] < stays_h[row["href"]], (width, row["href"], row["h"], stays_h[row["href"]])
        assert settings["overflow"] <= 1 and stays["overflow"] <= 1


def test_filtered_property_labels_alerts_of_other_properties(browser, base, workspace):
    ws = workspace("filter")
    for width in WIDTHS:
        data = _read(
            browser, base, ws, f"/reservations?apartment={ws['karlin']}", width, shot="filtered-karlin"
        )
        mine = [r for r in data["rows"] if "Karlin" in r["title"]]
        other = [r for r in data["rows"] if "Vinohrady" in r["title"]]
        assert len(mine) == 2 and len(other) == 1, data["rows"]
        for row in mine:
            assert row["scope"] == "" and not row["compact"] and row["action"] and row["label"] == ""
        for row in other:
            assert row["scope"] == "workspace" and row["compact"] and not row["action"]
            assert "Workspace alert" in row["label"], row
            assert row["reasons"] and row["href"].startswith("/reservations/") and row["dismiss"]
        # The other property's non-filing alert folds into the dashboard line; its deadline does not.
        assert not any("Guest link" in r["title"] for r in data["rows"])
        assert data["summary"] and data["summaryHref"] == "/#needs-action"
        assert set(_filing(data, ws)) == ws["expected"]
        assert data["overflow"] <= 1
    unfiltered = _read(browser, base, ws, "/reservations", 1280)
    assert all(row["scope"] == "" for row in unfiltered["rows"])
    # Filtered by the other property, the first property's alerts are the workspace ones.
    elsewhere = _read(browser, base, ws, f"/reservations?apartment={ws['vinohrady']}", 1280, shot="filtered-vinohrady")
    assert len([r for r in elsewhere["rows"] if r["scope"] == "workspace"]) == 2
    assert set(_filing(elsewhere, ws)) == ws["expected"]


def test_dismissal_and_return_navigation_keep_the_filter_and_the_rest(browser, base, workspace):
    ws = workspace("dismiss")
    path = f"/reservations?apartment={ws['karlin']}"
    context, page, errors = _visit(browser, base, ws, path, 390)
    try:
        before = page.evaluate(READ_JS)
        mine = [r for r in before["rows"] if "Karlin" in r["title"] and r["dismiss"]]
        assert mine, before["rows"]
        gone = mine[0]
        page.locator(f'[data-alert-id="{gone["id"]}"] [data-notification-dismiss] button').click()
        page.wait_for_selector(f'[data-alert-id="{gone["id"]}"]', state="detached")
        page.reload()
        page.wait_for_load_state("networkidle")
        assert f"apartment={ws['karlin']}" in page.url
        after = page.evaluate(READ_JS)
        left = {r["id"] for r in after["rows"]}
        assert gone["id"] not in left
        assert left == {r["id"] for r in before["rows"]} - {gone["id"]}
        assert db.query_one("SELECT user_dismissed FROM alert WHERE id = ?", (int(gone["id"]),))["user_dismissed"] == 1
        # Leave for Settings and come back: same filter, same remaining alerts, label still there.
        page.goto(f"{base}/settings?lang=en")
        page.wait_for_load_state("networkidle")
        page.go_back()
        page.wait_for_load_state("networkidle")
        assert f"apartment={ws['karlin']}" in page.url
        back = page.evaluate(READ_JS)
        assert {r["id"] for r in back["rows"]} == left
        assert any(r["scope"] == "workspace" and "Workspace alert" in r["label"] for r in back["rows"])
        assert not errors, errors
    finally:
        context.close()
