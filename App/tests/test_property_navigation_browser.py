"""0094: property Overview / Bookings & calendars / Settings with one editor."""
from __future__ import annotations

import json
import os
import re
import secrets
import socket
import threading
import time
from html.parser import HTMLParser
from pathlib import Path

import pytest
import uvicorn
from fastapi.testclient import TestClient

REQUIRE_BROWSER = os.environ.get("UBYHOST_REQUIRE_BROWSER") == "1"
if REQUIRE_BROWSER:
    import playwright.sync_api as sync_api
else:
    sync_api = pytest.importorskip("playwright.sync_api")

from app import auth, config, db, property_setup
from app.main import app
from tests.browser_support import chromium_launch_kwargs
from tests.conftest import login_as

EVIDENCE = Path(__file__).resolve().parents[2] / "docs" / "tasks" / "0094-evidence"
LOCK = {"lock_id": "70940001", "alias": "Synthetic Door", "battery": 90, "tz_offset_ms": 3600000}
# 0101: every link carries ?view=&section=; the hash only scrolls to the section.
HASHES = {
    "basics": ("settings", "property"), "address": ("settings", "property"),
    "communication": ("settings", "guests"), "door-code": ("settings", "lock"),
    "ubyport": ("settings", "reporting"),
    "stay-fee-settings": ("settings", "reporting"), "automation": ("settings", "automation"),
    "calendars": ("bookings", None), "calendar-connect": ("bookings", None),
}


def _canonical_query(view, group):
    return f"view={view}" + (f"&section={group}" if group else "")
# The successful controls of the one property form, by name.
SETTINGS_NAMES = {
    "signature_drawn", "signature_name", "fee_signature_section", "signature_file", "return_to", "_csrf", "internal_name", "city_en", "legal_entity_id", "data_controller_entity_id",
    "addr_okres", "addr_obec", "addr_obec_cast", "addr_street", "addr_house_no", "addr_orient_no", "addr_zip",
    "notes", "permalink_pin", "guest_message", "permalink_window_days",
    "permalink_reachback_days", "passport_photo_policy", "door_code_section", "door_codes_fields", "door_codes",
    "lock_id", "checkin_hour", "checkout_hour", "uby_idub", "uby_ws_user", "uby_ws_password", "uby_mark",
    "uby_name", "uby_contact", "stay_fee_rate_czk", "stay_fee_cadence", "stay_fee_vs", "stay_fee_council_account",
    "_stay_fee_account_existing", "stay_fee_authority_name",
    "stay_fee_authority_address", "stay_fee_authority_contact", "stay_fee_authority_databox",
    "automation_mode", "submit_after_hours", "default_purpose",
}


class _Forms(HTMLParser):
    """Forms, their successful controls and any nesting, as the browser sees them."""

    def __init__(self):
        super().__init__()
        self.forms, self.stack, self.nested, self.ids = [], [], False, []
        self._select = self._textarea = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if "id" in a:
            self.ids.append(a["id"])
        if tag == "form":
            if self.stack:
                self.nested = True
            form = {"action": a.get("action"), "method": (a.get("method") or "get").lower(), "fields": []}
            self.forms.append(form)
            self.stack.append(form)
            return
        if not self.stack:
            return
        form = self.stack[-1]
        if tag == "input" and a.get("name") and "disabled" not in a:
            kind = a.get("type", "text")
            if kind in ("checkbox", "radio") and "checked" not in a:
                return
            if kind in ("submit", "button"):
                return
            form["fields"].append((a["name"], a.get("value", "")))
        elif tag == "select" and a.get("name"):
            self._select = [a["name"], None, None]
            form["fields"].append(self._select)
        elif tag == "option" and self._select is not None:
            value = a.get("value", "")
            if self._select[2] is None:
                self._select[2] = value
            if "selected" in a and "disabled" not in a:
                self._select[1] = value
        elif tag == "textarea" and a.get("name"):
            self._textarea = [a["name"], ""]
            form["fields"].append(self._textarea)

    def handle_data(self, data):
        if self._textarea is not None:
            self._textarea[1] += data

    def handle_endtag(self, tag):
        if tag == "form" and self.stack:
            self.stack.pop()
        elif tag == "select" and self._select is not None:
            if self._select[1] is None:
                self._select[1] = self._select[2] or ""
            self._select = None
        elif tag == "textarea":
            self._textarea = None


def _forms(html):
    parser = _Forms()
    parser.feed(html)
    return parser


def _fields(form):
    return [(item[0], item[1]) for item in form["fields"]]


@pytest.fixture
def host(monkeypatch):
    db.init_db()
    monkeypatch.setattr(config, "DOOR_CODES_ENABLED", True)
    monkeypatch.setattr(config, "TTLOCK_CLIENT_ID", "cid")
    monkeypatch.setattr(config, "TTLOCK_CLIENT_SECRET", "csecret")
    username = f"nav-{secrets.token_hex(4)}"
    owner = auth.create_account(f"{username}@example.test", "Nav Host", role="host", username=username)
    now = db.utcnow()
    entities = [
        db.insert("legal_entity", {"name": name, "seat": "Praha", "ico": "12345678",
                                   "contact_email": "nav@example.test", "owner_user_id": owner, "created_at": now})
        for name in ("Synthetic Operator s.r.o.", "Synthetic Controller s.r.o.")
    ]
    apartment = db.insert("apartment", {
        "internal_name": "Synthetic Garden Flat", "city_en": "Brno", "owner_user_id": owner,
        "legal_entity_id": entities[0], "data_controller_entity_id": entities[1],
        "addr_obec": "Brno", "addr_house_no": "12", "addr_zip": "60200", "addr_street": "Synthetic",
        "uby_idub": "123456789012", "uby_mark": "SYNTH", "uby_name": "Synthetic Garden",
        "uby_ws_user": "UBY-WSsynth", "uby_contact": "host@example.test", "uby_ws_password_enc": db.encrypt_secret("synthetic-secret"),
        "automation_mode": "scheduled", "submit_after_hours": 6, "default_purpose": "10",
        "permalink_token": f"navtok{secrets.token_hex(4)}", "permalink_pin": "246810",
        "permalink_window_days": 3, "permalink_reachback_days": 90, "passport_photo_policy": "required_foreign",
        "guest_message": "Synthetic welcome.", "notes": "Synthetic note.",
        "stay_fee_rate_czk": 30, "stay_fee_cadence": "quarterly", "stay_fee_authority_name": "Synthetic Council",
        "lock_provider": "ttlock", "lock_id": LOCK["lock_id"], "checkin_hour": 15, "checkout_hour": 10,
        "active": 1, "created_at": now,
    })
    property_setup.start(apartment)
    property_setup.finish(apartment)
    db.insert("lock_account", {"owner_user_id": owner, "provider": "ttlock", "username": "synthetic_nav",
                               "status": "ok", "locks_json": json.dumps([LOCK]), "created_at": now, "updated_at": now})
    client = TestClient(app)
    assert login_as(client, username, url="/login?lang=en", follow_redirects=False).status_code == 303
    yield {"client": client, "owner": owner, "apartment": apartment, "entities": entities, "username": username}
    db.execute("DELETE FROM ical_feed WHERE apartment_id IN (SELECT id FROM apartment WHERE owner_user_id = ?)", (owner,))
    db.execute("DELETE FROM lock_account WHERE owner_user_id = ?", (owner,))


def _page(host, query=""):
    return host["client"].get(f"/apartments/{host['apartment']}{query}").text


def _active(html, attr):
    return re.findall(rf'class="[^"]*\bis-active\b[^"]*" {attr}="([a-z]+)"', html)


# --- markup and server state -------------------------------------------------


def test_three_views_four_groups_one_editor_and_unique_ids(host):
    html = _page(host, "?lang=en")
    for label in ("Overview", "Bookings &amp; calendars", "Settings"):
        assert f">{label}</a>" in html
    for label in ("Property information", "Guest experience", "Reporting &amp; fees", "Door lock", "Automation"):
        assert f'<h2 class="property-group-title">{label}</h2>' in html
    parsed = _forms(html)
    assert not parsed.nested, "a form is nested inside another"
    dupes = {i for i in parsed.ids if parsed.ids.count(i) > 1}
    assert not dupes, dupes
    property_forms = [f for f in parsed.forms if f["action"] == f"/apartments/{host['apartment']}" and f["method"] == "post"]
    assert len(property_forms) == 1
    names = [name for name, _ in _fields(property_forms[0])]
    assert set(names) == SETTINGS_NAMES, set(names) ^ SETTINGS_NAMES
    assert len(names) == len(set(names)), "a setting is submitted twice"
    calendar = [f for f in parsed.forms if f["action"] == f"/apartments/{host['apartment']}/feeds"]
    assert len(calendar) == 1
    assert _active(html, "data-property-view") == ["overview"]
    assert _active(html, "data-settings-group") == ["property"]
    # No folded essentials, no suggested portal message, no shadow form on Overview.
    content = html[html.index('<nav class="ui-tabs property-tabs"'):]
    # The shared fee partial's council fold belongs to 0077 (outside this task).
    assert "<details" not in content.replace('<details class="fee-setup-section">', "").replace('<details class="setup-readiness-help">', "").replace('<details class="ui-section" id="smart-locks-add-more">', "")
    assert "message-template" not in content and "copy_message" not in content
    overview = content[content.index('data-property-view="overview"'):content.index('data-property-view="bookings"')]
    assert "property-settings-form" not in overview and 'id="calendar-add"' not in overview


def test_view_and_section_are_sanitized_presentation_choices(host):
    assert _active(_page(host, "?view=bookings"), "data-property-view") == ["bookings"]
    reporting = _page(host, "?section=reporting")
    assert _active(reporting, "data-property-view") == ["settings"]
    assert _active(reporting, "data-settings-group") == ["reporting"]
    bogus = _page(host, "?view=%3Cscript%3E&section=../../x")
    assert _active(bogus, "data-property-view") == ["overview"]
    assert _active(bogus, "data-settings-group") == ["property"]
    assert "<script>" not in bogus.split("</head>", 1)[1].split("<script", 1)[0]
    settings = _page(host, "?view=settings&section=automation")
    assert f'name="return_to" value="/apartments/{host["apartment"]}?view=settings&amp;section=automation"' in settings


def test_placement_of_guest_link_actions_archive_and_switch(host):
    html = _page(host, "?lang=en")
    guests = html[html.index('id="settings-guests"'):html.index('id="settings-lock"')]
    communication = guests[guests.index('id="communication"'):]
    assert communication.index("/regenerate-pin") < communication.index('name="guest_message"')
    assert communication.index("/regenerate-link") < communication.index('name="guest_message"')
    assert communication.index('id="permalink_pin"') < communication.index("/regenerate-pin")
    prop = html[html.index('id="settings-property"'):html.index('id="settings-guests"')]
    assert "/archive" in prop and "/archive" not in guests
    assert html.index('id="archive"') < html.index('class="actions host-property-save"')
    door = html[html.index('id="settings-lock"'):html.index('id="settings-reporting"')]
    assert 'id="door-code"' in door and 'id="door-code"' not in guests
    assert 'role="switch"' in door and "Automatic door codes" in door
    assert ">Enabled</span>" in door
    assert door.count('href="/guide#door-codes"') == 1
    assert "Create a door code for each stay" not in html


def test_unrelated_save_keeps_every_stored_value(host):
    before = dict(db.query_one("SELECT * FROM apartment WHERE id = ?", (host["apartment"],)))
    html = _page(host, "?view=settings&section=reporting")
    form = next(f for f in _forms(html).forms if f["action"] == f"/apartments/{host['apartment']}" and f["method"] == "post")
    data = [(k, v) for k, v in _fields(form) if k != "_csrf"]
    data = [(k, "Synthetic note, edited.") if k == "notes" else (k, v) for k, v in data]
    response = host["client"].post(f"/apartments/{host['apartment']}", data=dict(data), follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"].startswith(f"/apartments/{host['apartment']}?view=settings&section=reporting")
    after = dict(db.query_one("SELECT * FROM apartment WHERE id = ?", (host["apartment"],)))
    # The form has always stored an untouched blank text field as "" (not NULL).
    changed = {k for k in before if (before[k] if before[k] is not None else "") != (after[k] if after[k] is not None else "")} - {"updated_at"}
    assert changed == {"notes"}, {k: (before[k], after[k]) for k in changed}


def test_refused_save_and_refused_calendar_render_their_own_view(host, monkeypatch):
    other = auth.create_account(f"nav-other-{secrets.token_hex(3)}@example.test", "Other", role="host")
    foreign = db.insert("legal_entity", {"name": "Foreign Op", "owner_user_id": other, "created_at": db.utcnow()})
    refused = host["client"].post(
        f"/apartments/{host['apartment']}",
        data={"internal_name": "Typed Name", "legal_entity_id": str(foreign)},
        follow_redirects=False,
    )
    assert refused.status_code == 400
    assert _active(refused.text, "data-property-view") == ["settings"]
    assert _active(refused.text, "data-settings-group") == ["property"]
    assert 'value="Typed Name"' in refused.text
    feed = host["client"].post(
        f"/apartments/{host['apartment']}/feeds",
        data={"label": "", "url": "https://example.invalid/x.ics", "own_name": "Garden"},
        follow_redirects=False,
    )
    assert feed.status_code == 400
    assert _active(feed.text, "data-property-view") == ["bookings"]
    assert 'id="calendar-connect" data-calendar-connect' in feed.text  # open, not collapsed
    assert 'value="Garden"' in feed.text


def test_bookings_view_with_no_one_and_many_feeds(host):
    empty = _page(host, "?view=bookings")
    assert 'class="calendar-connect" id="calendar-connect"' in empty
    assert "data-calendar-add" not in empty
    db.insert("ical_feed", {"apartment_id": host["apartment"], "url": "https://example.invalid/a.ics",
                            "label": "Airbnb", "own_name": "Airbnb", "active": 1, "last_status": "error",
                            "last_error": "Synthetic failure", "created_at": db.utcnow()})
    one = _page(host, "?view=bookings&lang=en")
    assert 'class="calendar-connect is-collapsed" id="calendar-connect"' in one
    assert "data-calendar-add" in one and "Synthetic failure" in one
    assert 'data-tone="red"' in one
    opened = _page(host, "?view=bookings&add_calendar=1")
    assert 'class="calendar-connect" id="calendar-connect"' in opened
    db.insert("ical_feed", {"apartment_id": host["apartment"], "url": "https://example.invalid/b.ics",
                            "label": "Booking.com", "own_name": "Main", "active": 1, "created_at": db.utcnow()})
    many = _page(host, "?view=bookings&lang=en")
    assert many.count('/delete"') >= 2
    overview = _page(host, "?lang=en")
    assert "2 calendars" in overview
    # A calendar removal returns to the Bookings tab.
    feed_id = db.query_one("SELECT id FROM ical_feed WHERE apartment_id = ? ORDER BY id LIMIT 1", (host["apartment"],))["id"]
    removed = host["client"].post(f"/feeds/{feed_id}/delete", follow_redirects=False)
    assert removed.headers["location"].startswith(f"/apartments/{host['apartment']}?view=bookings")


def test_the_kept_e_mail_link_opens_its_settings_group(host):
    # 0101: /guest-links stays only for lifecycle e-mails already sent; /automation is gone.
    links = host["client"].get("/guest-links", follow_redirects=False)
    assert links.headers["location"] == f"/apartments/{host['apartment']}?view=settings&section=guests#communication"
    assert host["client"].get("/automation", follow_redirects=False).status_code == 404


def test_overview_cards_point_at_the_canonical_editors(host):
    html = _page(host, "?lang=en")
    overview = html[html.index('data-property-view="overview"'):html.index('data-property-view="bookings"')]
    base = f"/apartments/{host['apartment']}"
    for href in (f"{base}?view=bookings#calendars",
                 f"{base}?view=settings&amp;section=reporting#ubyport", f"/entities?edit={host['entities'][0]}&amp;next={base}",  # 0076: returns here
                 f"{base}?view=settings&amp;section=reporting#stay-fee-settings",
                 f"{base}?view=settings&amp;section=property#address", f"{base}?view=settings&amp;section=lock#door-code"):
        assert f'href="{href}"' in overview, href
    assert "Ready to report" in overview


# --- browser ----------------------------------------------------------------


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


def _shot(page, name):
    if os.environ.get("UBYHOST_CAPTURE_0094") == "1":
        EVIDENCE.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(EVIDENCE / f"{name}.png"), full_page=True)


def _sidebar(page, collapsed):
    page.evaluate(
        """(want) => {
          const now = document.body.classList.contains('sidebar-collapsed');
          if (want === now) return;
          const btn = document.querySelector('button[data-sidebar-collapse]');
          if (btn && btn.offsetParent !== null) { btn.click(); return; }
          document.body.classList.toggle('sidebar-collapsed', want);
        }""",
        collapsed,
    )


_STATE_JS = """() => ({
  view: [...document.querySelectorAll('[data-property-view].is-active')].map(e => e.dataset.propertyView),
  visibleViews: [...document.querySelectorAll('[data-property-view]')].filter(e => getComputedStyle(e).display !== 'none').map(e => e.dataset.propertyView),
  visibleGroups: [...new Set([...document.querySelectorAll('[data-settings-group]')].filter(e => getComputedStyle(e).display !== 'none').map(e => e.dataset.settingsGroup))],
  marker: window.__navMarker || null,
  scroll: document.documentElement.scrollWidth, vw: document.documentElement.clientWidth,
})"""

_FIT_JS = """() => {
  const vw = document.documentElement.clientWidth;
  const bad = [];
  for (const el of document.querySelectorAll('.property-tabs a, .property-settings-nav a, .property-view.is-active .ui-btn, .property-view.is-active input, .property-view.is-active select, .property-view.is-active h2, .property-view.is-active h3')) {
    const r = el.getBoundingClientRect();
    if (!r.width || !r.height) continue;
    if (r.right > vw + 1 || r.left < -1) bad.push(el.id || el.textContent.trim().slice(0, 30));
  }
  const tabs = document.querySelector('.property-tabs');
  return {scroll: document.documentElement.scrollWidth, vw, bad,
          tabsScroll: tabs.scrollWidth <= tabs.clientWidth + 1,
          railSide: (() => { const n = document.querySelector('.property-settings-nav').getBoundingClientRect();
                             const f = document.querySelector('.property-settings-form').getBoundingClientRect();
                             return n.width > 0 && n.right <= f.left + 1; })()};
}"""


def _context(browser, base, host, **kwargs):
    context = browser.new_context(viewport={"width": 1280, "height": 900}, **kwargs)
    context.add_cookies([{"name": auth.SESSION_COOKIE, "value": host["client"].cookies.get(auth.SESSION_COOKIE), "url": base + "/"}])
    return context


def test_tabs_hashes_drafts_history_and_validation_in_browser(host, base):
    url = f"{base}/apartments/{host['apartment']}"
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        page = _context(browser, base, host).new_page()

        # Every canonical link opens its view and group, then shows the target.
        for anchor, (view, group) in HASHES.items():
            page.goto(f"{url}?{_canonical_query(view, group)}&lang=en#{anchor}")
            page.wait_for_timeout(30)
            state = page.evaluate(_STATE_JS)
            assert state["visibleViews"] == [view], (anchor, state)
            if group:
                assert state["visibleGroups"] == [group], (anchor, state)
            assert page.locator(f"#{anchor}").is_visible(), anchor
        page.goto(f"{url}?lang=en#no-such-section")
        assert page.evaluate(_STATE_JS)["visibleViews"] == ["overview"]

        # Tabs switch in place: no reload, history follows. A Settings draft
        # survives group switches and Back/Forward; a tab out of Settings asks
        # first (0084 O1: Save / Discard / Stay, see test_host_unsaved_changes_browser).
        dialogs = []

        def _on_dialog(dialog):
            dialogs.append(dialog.type)
            dialog.accept()

        page.on("dialog", _on_dialog)
        page.goto(f"{url}?lang=en")
        page.evaluate("() => { window.__navMarker = 'same-document'; }")
        page.locator('.property-tabs a[data-property-tab="settings"]').click()
        assert page.evaluate(_STATE_JS)["visibleViews"] == ["settings"]
        page.locator('.property-tabs a[data-property-tab="bookings"]').click()
        assert "view=bookings" in page.url  # clean: no question
        page.locator('.property-tabs a[data-property-tab="settings"]').click()
        page.fill("#internal_name", "Draft Name Kept")
        page.locator('[data-property-section-link="guests"]').click()
        page.fill("#guest_message", "Draft message kept")
        page.locator('.property-tabs a[data-property-tab="bookings"]').click()
        assert page.evaluate("() => document.getElementById('unsaved-dialog').open")
        page.locator("#unsaved-dialog [data-unsaved-stay]").click()
        state = page.evaluate(_STATE_JS)
        assert state["visibleViews"] == ["settings"] and state["visibleGroups"] == ["guests"], state
        page.go_back()
        assert page.evaluate(_STATE_JS)["visibleViews"] == ["settings"]
        page.go_back()
        assert page.evaluate(_STATE_JS)["visibleViews"] == ["bookings"]
        page.go_forward()
        state = page.evaluate(_STATE_JS)
        assert state["visibleViews"] == ["settings"] and state["visibleGroups"] == ["guests"], state
        assert page.evaluate(_STATE_JS)["marker"] == "same-document"
        assert page.locator("#internal_name").input_value() == "Draft Name Kept"
        assert page.locator("#guest_message").input_value() == "Draft message kept"
        # Overview card opens its exact editor in place, draft kept.
        for _ in range(3):
            page.go_back()
        assert page.evaluate(_STATE_JS)["visibleViews"] == ["overview"]
        page.locator(".host-property-card", has_text="Police reporting").click()
        page.locator("#ubyport").wait_for(state="visible")
        state = page.evaluate(_STATE_JS)
        assert state["visibleGroups"] == ["reporting"], state
        assert state["marker"] == "same-document", "the card reloaded the page"
        assert page.evaluate("() => document.querySelector('[data-property-return]').value").endswith("section=reporting")
        assert page.locator("#internal_name").input_value() == "Draft Name Kept"

        # Leaving with unsaved settings by an in-app link asks first, in the page.
        page.locator('.sidebar-nav a[href="/reservations"]').first.click()
        assert page.evaluate("() => document.getElementById('unsaved-dialog').open")
        page.locator("#unsaved-dialog [data-unsaved-stay]").click()
        page.wait_for_timeout(300)
        assert dialogs == []
        assert "/apartments/" in page.url
        assert page.locator("#internal_name").input_value() == "Draft Name Kept"

        # A ctrl-click is left to the browser.
        page.goto(f"{url}?lang=en")
        page.evaluate("() => { window.__navMarker = 'm2'; }")
        with page.context.expect_page() as popup:
            page.locator('.property-tabs a[data-property-tab="settings"]').click(modifiers=["Control"])
        popup.value.close()
        assert page.evaluate(_STATE_JS)["visibleViews"] == ["overview"]

        # A field the browser refuses in a hidden group is revealed and focused.
        page.goto(f"{url}?view=settings&section=property&lang=en")
        page.evaluate("() => { document.getElementById('permalink_pin').value = '12'; }")
        page.locator(".host-property-save .ui-btn-primary").click()
        page.wait_for_timeout(100)
        state = page.evaluate(_STATE_JS)
        assert state["visibleGroups"] == ["guests"], state
        assert page.evaluate("() => document.activeElement.id") == "permalink_pin"
        assert "section=property" in page.url  # not submitted

        # Save returns to the group in use; the credentials test does too.
        page.goto(f"{url}?view=settings&section=automation&lang=en")
        page.select_option("#automation_mode", "manual")
        page.locator(".host-property-save .ui-btn-primary").click()
        page.wait_for_load_state()
        assert "view=settings&section=automation" in page.url
        assert page.evaluate(_STATE_JS)["visibleGroups"] == ["automation"]
        assert db.query_one("SELECT automation_mode FROM apartment WHERE id = ?", (host["apartment"],))["automation_mode"] == "manual"
        page.goto(f"{url}?view=settings&section=reporting&lang=en")
        page.locator('button[formaction$="/test-connection"]').click()
        page.wait_for_load_state()
        assert page.evaluate(_STATE_JS)["visibleGroups"] == ["reporting"], page.url

        # The door-code switch says "Not saved yet" until it is saved.
        page.goto(f"{url}?view=settings&section=lock&lang=en")
        status = page.locator("#door_codes-status")
        assert status.inner_text() == "Enabled"
        page.locator("#door_codes").click()
        assert status.inner_text() == "Not saved yet"
        page.locator("#door_codes").click()
        assert status.inner_text() == "Enabled"
        browser.close()


def test_create_offers_the_calendar_first_and_works_without_js(host, base):
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        page = _context(browser, base, host).new_page()
        page.goto(f"{base}/apartments/new?lang=en")
        page.fill("#internal_name", "Synthetic Early Calendar Flat")
        page.fill("#addr_obec", "Praha")
        page.fill("#addr_house_no", "12")
        page.fill("#addr_zip", "11000")
        page.select_option("#legal_entity_id", str(host["entities"][0]))
        for field, value in (("addr_obec", "Brno"), ("addr_house_no", "12"), ("addr_zip", "602 00")):
            page.fill(f"#{field}", value)
        page.locator(".property-create-actions .ui-btn-primary").click()
        page.wait_for_load_state()
        assert "/setup/calendar" in page.url
        assert not page.locator(".property-first-use").count()
        assert page.locator("[data-setup-wizard]").is_visible()
        assert page.locator("#calendar-add #label").is_visible()
        assert page.locator("#calendar-add #url").is_visible()
        _shot(page, "created-wizard-calendar-1280-en")
        page.locator(".setup-wizard-skip button[value='skip']").click()
        # 0270: story order, police comes after the calendar.
        page.wait_for_url("**/setup/police**")
        import re

        aid = re.search(r"/apartments/(\d+)/", page.url).group(1)
        page.goto(f"{base}/apartments/{aid}?view=bookings&lang=en")
        page.wait_for_load_state()
        # Adding a stay by hand stays one tab away once the calendar step is done.
        page.locator('.property-tabs a[data-property-tab="bookings"]').click()
        manual = page.locator(".property-view.is-active a", has_text="Add stay manually")
        assert "/reservations?new=1" in manual.get_attribute("href")
        browser.close()

        no_js_browser = playwright.chromium.launch(**chromium_launch_kwargs())
        page = _context(no_js_browser, base, host, java_script_enabled=False).new_page()
        url = f"{base}/apartments/{host['apartment']}"
        for anchor, (view, group) in HASHES.items():
            page.goto(f"{url}?{_canonical_query(view, group)}&lang=cs#{anchor}")
            assert page.locator(f"#{anchor}").is_visible(), anchor
            assert page.locator(f'[data-property-view="{view}"]').is_visible()
            if group:
                assert page.locator(f'[data-settings-group="{group}"]').first.is_visible()
        page.goto(f"{url}?lang=cs")
        page.locator('.property-tabs a[data-property-tab="settings"]').click()
        page.locator('[data-property-section-link="property"]').click()
        page.fill("#notes", "No-JS synthetic note")
        page.locator(".host-property-save .ui-btn-primary").click()
        page.wait_for_load_state()
        assert "view=settings" in page.url
        assert db.query_one("SELECT notes FROM apartment WHERE id = ?", (host["apartment"],))["notes"] == "No-JS synthetic note"
        _shot(page, "settings-nojs-1280-cs")
        no_js_browser.close()


def test_property_views_fit_every_width_and_sidebar(host, base):
    db.insert("ical_feed", {"apartment_id": host["apartment"], "url": "https://example.invalid/fit.ics",
                            "label": "Airbnb", "own_name": "Synthetic Airbnb calendar", "active": 1,
                            "last_status": "ok", "created_at": db.utcnow()})
    url = f"{base}/apartments/{host['apartment']}"
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        page = _context(browser, base, host).new_page()
        for width in (360, 390, 1280):
            page.set_viewport_size({"width": width, "height": 900})
            for lang in ("en", "cs"):
                for view in ("overview", "bookings", "settings"):
                    page.goto(f"{url}?view={view}&lang={lang}")
                    fit = page.evaluate(_FIT_JS)
                    assert fit["scroll"] <= fit["vw"] and not fit["bad"] and fit["tabsScroll"], (width, lang, view, fit)
                    _shot(page, f"{view}-{width}-{lang}")
                for section in ("guests", "reporting"):
                    page.goto(f"{url}?view=settings&section={section}&lang={lang}")
                    fit = page.evaluate(_FIT_JS)
                    assert fit["scroll"] <= fit["vw"] and not fit["bad"], (width, lang, section, fit)
                    if width == 1280:
                        _shot(page, f"settings-{section}-{width}-{lang}")
        for collapsed in (False, True):
            for width in (760, 1024, 1440, 1680, 1920, 2048):
                page.set_viewport_size({"width": width, "height": 900})
                page.goto(f"{url}?view=settings&section=guests&lang=cs")
                _sidebar(page, collapsed)
                page.wait_for_timeout(50)
                fit = page.evaluate(_FIT_JS)
                assert fit["scroll"] <= fit["vw"] and not fit["bad"] and fit["tabsScroll"], (width, collapsed, fit)
                if width >= 1440:
                    assert fit["railSide"], (width, collapsed, fit)
                if width in (760, 1024, 1440, 1920):
                    _shot(page, f"settings-{width}-cs-{'collapsed' if collapsed else 'expanded'}")
                page.goto(f"{url}?view=bookings&lang=cs")
                fit = page.evaluate(_FIT_JS)
                assert fit["scroll"] <= fit["vw"] and not fit["bad"], (width, collapsed, "bookings", fit)
        _sidebar(page, False)
        browser.close()



def test_shared_timing_pair_is_owned_by_properties(host, base):
    url = f"{base}/apartments/{host['apartment']}?view=settings&section=property&lang=en"
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        page = _context(browser, base, host).new_page()
        page.goto(url)
        assert page.locator('#property-settings-form [name="checkin_hour"]').count() == 1
        assert page.locator('#property-settings-form [name="checkout_hour"]').count() == 1
        assert page.locator('#arrival-departure').is_visible()
        page.locator('[data-property-section-link="lock"]').click()
        assert page.locator('#settings-lock [name="checkin_hour"]').count() == 0
        assert page.locator('#settings-lock [name="checkout_hour"]').count() == 0
        assert page.locator('#settings-lock a[href*="section=property#arrival-departure"]').is_visible()
        browser.close()
