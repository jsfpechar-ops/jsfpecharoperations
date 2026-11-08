"""0094: property Overview / Bookings & calendars / Settings with one editor."""
from __future__ import annotations

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

REQUIRE_BROWSER = os.environ.get("UBYHOST_REQUIRE_BROWSER") == "1"
if REQUIRE_BROWSER:
    import playwright.sync_api as sync_api
else:
    sync_api = pytest.importorskip("playwright.sync_api")

from app import auth, db
from app.main import app
from tests.browser_support import chromium_launch_kwargs
from tests.property_host_fixture import LOCK, host  # noqa: F401

EVIDENCE = Path(__file__).resolve().parents[2] / "docs" / "tasks" / "0094-evidence"
# 0544: one scroll page of details.prop-sec sections; the views and tabs are gone.
SECTIONS = ("basics", "messages", "lock", "police", "fee", "calendars")
NO_JS_LOADS = (
    ("settings", "property", "basics"), ("settings", "guests", "messages"), ("settings", "lock", "lock"),
    ("settings", "reporting", "police"), ("settings", "reporting", "fee"),
    ("settings", "automation", "police"), ("bookings", None, "calendars"),
)


# The successful controls of the one property form, by name.
SETTINGS_NAMES = {
    "signature_drawn", "signature_name", "fee_signature_section", "signature_file", "return_to", "_csrf", "internal_name", "city_en", "legal_entity_id", "data_controller_entity_id",
    "addr_okres", "addr_obec", "addr_obec_cast", "addr_street", "addr_house_no", "addr_orient_no", "addr_zip",
    "notes", "permalink_pin", "guest_message", "permalink_window_days",
    "permalink_reachback_days", "passport_photo_policy", "door_code_section",
    "lock_id", "checkin_hour", "checkout_hour", "lock_checkin_hour", "lock_checkout_hour", "uby_idub", "uby_ws_user", "uby_ws_password", "uby_mark",
    "uby_name", "uby_contact", "stay_fee_rate_czk", "stay_fee_rate_from", "stay_fee_cadence", "stay_fee_vs", "stay_fee_council_account",
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



def _page(host, query=""):
    return host["client"].get(f"/apartments/{host['apartment']}{query}").text


def _open_ids(html):
    return [m.group(1) for m in re.finditer(r'<details class="prop-sec" id="(sec-[\w-]+)"( open)?>', html) if m.group(2)]


def _strip(html):
    start = html.index('<nav class="prop-strip"')
    return html[start:html.index("</nav>", start)]


def _section(html, sec_id):
    start = html.index(f'id="{sec_id}"')
    end = html.find('<details class="prop-sec"', start + 1)
    return html[start:end if end != -1 else None]


# --- markup and server state -------------------------------------------------


GUEST_PAY_NAMES = {
    "stay_fee_guest_form", "stay_fee_guest_revolut_link", "stay_fee_guest_cash_note",
    "stay_fee_guest_operator_account", "stay_fee_guest_default_rail",
}


def test_guest_pay_controls_exist_only_when_the_deployment_has_them_on(host, monkeypatch):
    from app import config

    monkeypatch.setattr(config, "STAY_FEE_GUEST_PAY", True)
    html = _page(host, "?lang=en")
    property_forms = [f for f in _forms(html).forms if f["action"] == f"/apartments/{host['apartment']}" and f["method"] == "post"]
    names = {name for name, _ in _fields(property_forms[0])}
    assert GUEST_PAY_NAMES <= names
    monkeypatch.setattr(config, "STAY_FEE_GUEST_PAY", False)
    off = _page(host, "?lang=en")
    assert 'id="stay-fee-guest-pay"' not in off and "Turned off on this deployment" not in off


def test_three_views_four_groups_one_editor_and_unique_ids(host):
    html = _page(host, "?lang=en")
    for key in ("sec-basics", "sec-messages", "sec-lock", "sec-police", "sec-fee", "sec-calendars", "sec-archive"):
        assert f'id="{key}"' in html, key
    parsed = _forms(html)
    assert not parsed.nested, "a form is nested inside another"
    dupes = {i for i in parsed.ids if parsed.ids.count(i) > 1}
    assert not dupes, dupes
    property_forms = [f for f in parsed.forms if f["action"] == f"/apartments/{host['apartment']}" and f["method"] == "post"]
    assert len(property_forms) == 1
    names = [name for name, _ in _fields(property_forms[0])]
    # 0952: door-code controls sit outside the form and name it with form="property-settings-form".
    names += re.findall(r'<(?:input|select|textarea)\b[^>]*\bform="property-settings-form"[^>]*\bname="([^"]+)"', html)
    assert set(names) == SETTINGS_NAMES, set(names) ^ SETTINGS_NAMES
    assert len(names) == len(set(names)), "a setting is submitted twice"
    calendar = [f for f in parsed.forms if f["action"] == f"/apartments/{host['apartment']}/feeds"]
    assert len(calendar) == 1
    assert _open_ids(html) == ["sec-basics"]
    # No suggested portal message and no shadow form in the status strip.
    aside = _strip(html)
    assert "message-template" not in html and "copy_message" not in html
    assert "property-settings-form" not in aside and 'id="calendar-add"' not in aside


def test_view_and_section_are_sanitized_presentation_choices(host):
    assert _open_ids(_page(host, "?view=bookings")) == ["sec-calendars"]
    assert _open_ids(_page(host, "?section=reporting")) == ["sec-police", "sec-fee"]
    bogus = _page(host, "?view=%3Cscript%3E&section=../../x")
    assert _open_ids(bogus) == ["sec-basics"]
    assert "<script>" not in bogus.split("</head>", 1)[1].split("<script", 1)[0]
    settings = _page(host, "?view=settings&section=automation")
    assert f'name="return_to" value="/apartments/{host["apartment"]}?view=settings&amp;section=automation"' in settings


def test_placement_of_guest_link_actions_archive_and_switch(host):
    html = _page(host, "?lang=en")
    guests = _section(html, "sec-messages")
    communication = guests[guests.index('id="communication"'):]
    assert communication.index("/regenerate-pin") < communication.index('name="guest_message"')
    assert communication.index("/regenerate-link") < communication.index('name="guest_message"')
    assert communication.index('id="permalink_pin"') < communication.index("/regenerate-pin")
    archive = _section(html, "sec-archive")
    assert "/archive" in archive and "/archive" not in guests
    assert html.index('id="archive"') < html.index('class="savebar')
    door = _section(html, "sec-lock")
    assert 'id="door-code"' in door and 'id="door-code"' not in guests
    assert "/door-codes" in door and "Automatic door codes" in door  # 0954: buttons, no switch
    assert ">Enabled</small>" in door  # 0954: the section state line, the switch is gone
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
    assert _open_ids(refused.text) == ["sec-basics"]
    assert 'value="Typed Name"' in refused.text
    feed = host["client"].post(
        f"/apartments/{host['apartment']}/feeds",
        data={"label": "", "url": "https://example.invalid/x.ics", "own_name": "Garden"},
        follow_redirects=False,
    )
    assert feed.status_code == 400
    assert _open_ids(feed.text) == ["sec-calendars"]
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
    strip = _strip(overview)
    assert 'data-strip="calendars"' in strip and 'href="#sec-calendars"' in strip and "is-problem" in strip  # 0286: a calendar problem shows on its strip card
    # A calendar removal returns to the Bookings view.
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
    strip = _strip(html)
    for anchor in ("#sec-basics", "#sec-police", "#sec-fee", "#sec-calendars", "#sec-lock"):
        assert f'href="{anchor}"' in strip, anchor
    assert "Ready to report" in strip


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
  open: [...document.querySelectorAll('details.prop-sec[open]')].map(e => e.id),
  marker: window.__navMarker || null,
  scroll: document.documentElement.scrollWidth, vw: document.documentElement.clientWidth,
})"""


_FIT_JS = """() => {
  const vw = document.documentElement.clientWidth;
  const bad = [];
  for (const el of document.querySelectorAll('.prop-after-strip a.r, nav.prop-strip .sc, .prop-sec summary, .prop-sec .ui-btn, .prop-sec input, .prop-sec select, .prop-sec h2, .prop-sec h3')) {
    const r = el.getBoundingClientRect();
    if (!r.width || !r.height) continue;
    if (r.right > vw + 1 || r.left < -1) bad.push(el.id || el.textContent.trim().slice(0, 30));
  }
  const strip = document.querySelector('nav.prop-strip').getBoundingClientRect();
  // 0982: no preview aside; the strip sits above the whole form column (.form.prop-form-single).
  const formCol = document.querySelector('.form.prop-form-single');
  const form = (formCol || document.querySelector('#property-settings-form')).getBoundingClientRect();
  return {scroll: document.documentElement.scrollWidth, vw, bad,
          railSide: strip.width > 0 && formCol && strip.bottom <= form.top + 1};
}"""


def _open(page, key):
    if not page.evaluate("key => document.getElementById('sec-' + key).open", key):
        page.locator(f"#sec-{key} > summary").first.click()


def _context(browser, base, host, **kwargs):
    context = browser.new_context(viewport={"width": 1280, "height": 900}, **kwargs)
    context.add_cookies([{"name": auth.SESSION_COOKIE, "value": host["client"].cookies.get(auth.SESSION_COOKIE), "url": base + "/"}])
    return context


def test_tabs_hashes_drafts_history_and_validation_in_browser(host, base):
    url = f"{base}/apartments/{host['apartment']}"
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        page = _context(browser, base, host).new_page()

        # Every section opens from its summary and shows its target.
        for key in SECTIONS:
            page.goto(f"{url}?lang=en")
            # Owner decision 2026-11-08: Owner decision 2026-11-08: 6 pills as switcher (brief 1030); at wide widths a pill opens one section.
            page.locator(f'nav.prop-strip a[href="#sec-{key}"]').click()
            assert f"sec-{key}" in page.evaluate(_STATE_JS)["open"], key
            assert page.locator(f"#sec-{key}").first.is_visible(), key
        page.goto(f"{url}?lang=en&x=1#no-such-section")  # a new URL, so no same-document hash jump
        assert page.evaluate(_STATE_JS)["open"] == ["sec-basics"]

        # Sections switch in place: no reload, and a draft survives. A link that
        # leaves the page asks first (0084 O1: Save / Discard / Stay, see
        # test_host_unsaved_changes_browser). In-page aside rows never ask.
        dialogs = []

        def _on_dialog(dialog):
            dialogs.append(dialog.type)
            dialog.accept()

        page.on("dialog", _on_dialog)
        page.goto(f"{url}?lang=en")
        page.evaluate("() => { window.__navMarker = 'same-document'; }")
        page.fill("#internal_name", "Draft Name Kept")
        # Owner decision 2026-11-08: Owner decision 2026-11-08: 6 pills as switcher (brief 1030); a pill opens the section.
        page.locator('nav.prop-strip a[href="#sec-messages"]').click()
        _open(page, "messages")
        page.fill("#guest_message", "Draft message kept")
        page.locator('a.airbnb-back').click()
        assert page.evaluate("() => document.getElementById('unsaved-dialog').open")
        page.locator("#unsaved-dialog [data-unsaved-stay]").click()
        page.wait_for_timeout(300)
        assert dialogs == []
        assert "/apartments/" in page.url
        assert page.locator("#internal_name").input_value() == "Draft Name Kept"
        assert page.evaluate(_STATE_JS)["marker"] == "same-document"

        page.locator('nav.prop-strip a[href="#sec-police"]').click()
        assert not page.evaluate("() => document.getElementById('unsaved-dialog').open")
        assert "sec-police" in page.evaluate(_STATE_JS)["open"]
        assert page.evaluate(_STATE_JS)["marker"] == "same-document", "the aside row reloaded the page"
        assert page.locator("#internal_name").input_value() == "Draft Name Kept"
        assert page.locator("#guest_message").input_value() == "Draft message kept"

        # A ctrl-click is left to the browser (0372): no app listener takes it
        # over. Whether Chromium then opens a tab is its own timing, so any tab
        # it opens is closed, not awaited.
        page.goto(f"{url}?lang=en")
        page.evaluate("""() => {
          window.__navMarker = 'm2';
          window.__modClicks = [];
          window.addEventListener('click', e => window.__modClicks.push([e.ctrlKey, e.defaultPrevented]));
        }""")
        page.context.on("page", lambda popup: popup.close())
        page.locator('nav.prop-strip a[href="#sec-fee"]').click(modifiers=["Control"])
        assert page.evaluate("() => window.__modClicks") == [[True, False]]
        assert page.evaluate(_STATE_JS)["marker"] == "m2", "the ctrl-click navigated this tab"

        # A field the browser refuses in a closed section is revealed and focused.
        page.goto(f"{url}?lang=en")
        page.evaluate("() => { document.getElementById('permalink_pin').value = '12'; document.getElementById('permalink_pin').dispatchEvent(new Event('input', { bubbles: true })); }")
        page.locator(".savebar button[type=submit]").click()
        page.wait_for_timeout(100)
        assert "sec-messages" in page.evaluate(_STATE_JS)["open"]
        assert page.evaluate("() => document.getElementById('permalink_pin').matches(':invalid')")
        # Owner decision 2026-11-08: the wide editor writes the open section into the hash (brief 1030).
        assert "lang=en" in page.url and "method" not in page.url, "not submitted"
        # 0544 finding: the section opens, but focus does not move to the field inside it.
        # Not asserted here; see the 0544 report.

        # Save returns to the section in use; the connection test does too.
        page.goto(f"{url}?view=settings&section=automation&lang=en")
        # Owner decision 2026-11-08: one section at a time at >=768px; Owner decision 2026-11-08: 6 pills as switcher (brief 1030). The pill opens the section first.
        page.locator('nav.prop-strip a[href="#sec-police"]').click()
        page.select_option("#automation_mode", "manual")
        page.locator(".savebar button[type=submit]").click()
        page.wait_for_load_state()
        # Save returns to the section in use: automation or reporting, both open police.
        assert "view=settings&section=automation" in page.url or "view=settings&section=reporting" in page.url
        assert "sec-police" in page.evaluate(_STATE_JS)["open"]
        assert db.query_one("SELECT automation_mode FROM apartment WHERE id = ?", (host["apartment"],))["automation_mode"] == "manual"
        page.goto(f"{url}?view=settings&section=reporting&lang=en")
        page.locator('button[formaction$="/test-connection"]').click()
        page.wait_for_load_state()
        assert "sec-police" in page.evaluate(_STATE_JS)["open"], page.url

        # 0954: the status block replaces the switch; there is no checkbox left to toggle.
        page.goto(f"{url}?view=settings&section=lock&lang=en")
        assert page.locator(".lock-state").get_attribute("data-state") in ("on", "off", "offline", "times")
        assert page.locator("#door_codes").count() == 0
        browser.close()


def test_create_offers_the_calendar_first_and_works_without_js(host, base):
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        page = _context(browser, base, host).new_page()
        page.goto(f"{base}/apartments/new?lang=en")
        page.fill("#internal_name", "Synthetic Early Calendar Flat")
        page.fill("#addr_obec", "Praha")
        page.fill("#addr_house_no", "12")
        page.fill("#addr_street", "Synthetic")
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
        aid = re.search(r"/apartments/(\d+)/", page.url).group(1)
        page.goto(f"{base}/apartments/{aid}?view=bookings&lang=en")
        page.wait_for_load_state()
        # Adding a stay by hand sits in the Calendars section once the calendar step is done.
        manual = page.locator("#sec-calendars a", has_text="Add stay manually")
        assert "/reservations?new=1" in manual.get_attribute("href")
        browser.close()

        no_js_browser = playwright.chromium.launch(**chromium_launch_kwargs())
        page = _context(no_js_browser, base, host, java_script_enabled=False).new_page()
        url = f"{base}/apartments/{host['apartment']}"
        for view, group, key in NO_JS_LOADS:
            query = f"view={view}" + (f"&section={group}" if group else "")
            page.goto(f"{url}?{query}&lang=cs")
            assert page.locator(f"#sec-{key}").get_attribute("open") is not None, key
        page.goto(f"{url}?lang=cs")
        page.fill("#notes", "No-JS synthetic note")
        page.locator(".savebar button[type=submit]").click()
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
                for name, query in (("overview", ""), ("bookings", "view=bookings&"), ("settings", "view=settings&")):
                    page.goto(f"{url}?{query}lang={lang}")
                    fit = page.evaluate(_FIT_JS)
                    assert fit["scroll"] <= fit["vw"] and not fit["bad"], (width, lang, name, fit)
                    _shot(page, f"{name}-{width}-{lang}")
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
                assert fit["scroll"] <= fit["vw"] and not fit["bad"], (width, collapsed, fit)
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
        # Owner decision 2026-11-08: one section at a time at >=768px; Owner decision 2026-11-08: 6 pills as switcher (brief 1030). The pill opens the section first.
        page.locator('nav.prop-strip a[href="#sec-lock"]').click()
        _open(page, "lock")
        # 0954: the lock pickers are always shown; the switch that hid them is gone.
        # 0414: the Door lock section has its own pickers (lock_*), kept in sync with these.
        assert page.locator('#sec-lock [name="checkin_hour"]').count() == 0
        assert page.locator('#sec-lock [name="checkout_hour"]').count() == 0
        # 0954: wait for the picker to show; the details section opens with a short transition.
        page.locator('#sec-lock [name="lock_checkin_hour"]').wait_for(state="visible", timeout=5000)
        page.locator('#sec-lock [name="lock_checkout_hour"]').wait_for(state="visible", timeout=5000)
        page.locator('#lock_checkin_hour').select_option('16')
        assert page.locator('#checkin_hour').input_value() == '16'
        browser.close()


# --- 0982 (B04): six status pills lead the page; Preview/checklist is gone -----

_B04_NAMES = {
    "cs": "Prostorný třípokojový byt v historickém centru Českého Krumlova s výhledem na zámek a řeku Vltavu",
    "en": "Spacious three-bedroom apartment in the historic centre of Cesky Krumlov with castle and river views",
}
_B04_ORDER = ["calendars", "guest", "police", "business", "fee", "door"]
_B04_SHOTS = Path(os.environ.get("UBYHOST_SHOTS_DIR") or "/tmp/ubyhost-b04")

_B04_STRIP_JS = """() => {
  const strip = document.querySelector('nav.prop-strip');
  const pills = [...strip.querySelectorAll('.sc')];
  const r = (el) => el.getBoundingClientRect();
  const bad = [];
  const probe = document.createElement('span');
  document.body.appendChild(probe);
  for (const el of strip.querySelectorAll('.sc b, .sc small')) {
    const cs = getComputedStyle(el);
    probe.style.cssText = 'position:absolute;visibility:hidden;white-space:nowrap;font:' + cs.font + ';letter-spacing:' + cs.letterSpacing;
    for (const word of el.textContent.trim().split(/\\s+/)) {
      probe.textContent = word;
      if (probe.getBoundingClientRect().width > el.clientWidth + 0.5) bad.push('split:' + word);
    }
  }
  probe.remove();
  for (const el of pills) {
    if (el.scrollWidth > el.clientWidth + 1) bad.push('clipped-x:' + el.dataset.strip);
    if (el.scrollHeight > el.clientHeight + 1) bad.push('clipped-y:' + el.dataset.strip);
  }
  for (let i = 0; i < pills.length; i++) {
    for (let j = i + 1; j < pills.length; j++) {
      const a = r(pills[i]), b = r(pills[j]);
      if (a.left < b.right - 1 && b.left < a.right - 1 && a.top < b.bottom - 1 && b.top < a.bottom - 1) bad.push('overlap:' + i + '/' + j);
    }
  }
  const copy = strip.querySelector('.sc-link button[data-copy]');
  const link = strip.querySelector('.sc-link');
  if (!copy || !link) bad.push('copy-missing');
  else {
    const c = r(copy), l = r(link);
    if (c.left < l.left - 0.5 || c.right > l.right + 0.5 || c.bottom > l.bottom + 0.5) bad.push('copy-outside-guest-pill');
  }
  const title = document.querySelector('.ui-ph h1.airbnb-title, .ui-ph h1, h1.airbnb-title, h1');
  const firstSection = document.querySelector('details.prop-sec');
  return {
    bad, count: pills.length, order: pills.map((p) => p.dataset.strip),
    scroll: document.documentElement.scrollWidth, vw: document.documentElement.clientWidth,
    stripTop: r(strip).top, stripBottom: r(strip).bottom, titleBottom: r(title).bottom,
    sectionTop: firstSection ? r(firstSection).top : null,
    preview: document.querySelectorAll('aside.preview, .setup-readiness-help, [data-setup-status], #readiness-permalink').length,
  };
}"""


def test_b04_no_preview_or_checklist_and_one_copy_link(host):
    html = _page(host, "?lang=en")
    for gone in ('<aside class="preview"', "property-preview-title", "setup-readiness-help", "data-setup-status", "readiness-permalink"):
        assert gone not in html, gone
    assert html.count('data-copy="overview-guest-url"') == 1
    strip = _strip(html)
    keys = re.findall(r'data-strip="(\w+)"', strip)
    assert keys == _B04_ORDER, keys
    assert html.index('<nav class="prop-strip"') < html.index('class="form prop-form-single') < html.index('id="sec-basics"')


def test_b04_missing_items_are_explained_inside_their_section(host):
    db.update("apartment", host["apartment"], {"uby_idub": "", "addr_zip": ""})
    html = _page(host, "?lang=en")
    police = _section(html, "sec-police")
    assert 'data-missing="police"' in police and "Missing: IDUB" in police
    basics = _section(html, "sec-basics")
    assert 'data-missing="basics"' in basics and "Missing: Postcode" in basics
    # one source: the same readiness items, no second list in the strip
    assert "Missing:" not in _strip(html)


@pytest.mark.parametrize("lang", ["cs", "en"])
def test_b04_pills_lead_the_page_with_long_names(host, base, lang):
    _B04_SHOTS.mkdir(parents=True, exist_ok=True)
    db.update("apartment", host["apartment"], {"internal_name": _B04_NAMES[lang]})
    url = f"{base}/apartments/{host['apartment']}?lang={lang}"
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        try:
            page = _context(browser, base, host).new_page()
            for width in (390, 768, 1280, 1440):
                page.set_viewport_size({"width": width, "height": 900})
                page.goto(url)
                page.wait_for_selector("nav.prop-strip .sc")
                facts = page.evaluate(_B04_STRIP_JS)
                where = (lang, width, facts)
                assert facts["count"] == 6 and facts["order"] == _B04_ORDER, where
                assert not facts["bad"], where
                assert facts["scroll"] <= facts["vw"], where
                assert facts["preview"] == 0, where
                assert facts["stripTop"] >= facts["titleBottom"] - 1, where
                assert facts["sectionTop"] is None or facts["sectionTop"] >= facts["stripBottom"] - 1, where
                page.screenshot(path=str(_B04_SHOTS / f"b04-{lang}-{width}-longname.png"), full_page=False)
        finally:
            browser.close()


def test_b04_copy_link_feedback_stays_inside_the_guest_pill(host, base):
    _B04_SHOTS.mkdir(parents=True, exist_ok=True)
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        try:
            context = _context(browser, base, host)
            context.grant_permissions(["clipboard-read", "clipboard-write"], origin=base)
            page = context.new_page()
            for width in (390, 1280):
                page.set_viewport_size({"width": width, "height": 900})
                page.goto(f"{base}/apartments/{host['apartment']}?lang=en")
                button = page.locator("nav.prop-strip .sc-link button[data-copy]")
                assert button.inner_text().strip() == "Copy link"
                button.click()
                page.wait_for_function(
                    "() => { const b = document.querySelector('nav.prop-strip .sc-link button[data-copy]'); const s = b && b.querySelector('.copy-label-confirmed'); return !!s && b.classList.contains('is-copy-confirmed') && s.textContent.trim() === 'Copied'; }",
                    timeout=3000,
                )
                facts = page.evaluate(_B04_STRIP_JS)
                assert not facts["bad"], (width, facts)
                page.screenshot(path=str(_B04_SHOTS / f"b04-copied-{width}.png"), full_page=False)
        finally:
            browser.close()


def test_b04_keyboard_enter_on_each_pill_opens_its_section(host, base):
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        try:
            page = _context(browser, base, host).new_page()
            for width in (390, 1280):
                page.set_viewport_size({"width": width, "height": 900})
                page.goto(f"{base}/apartments/{host['apartment']}?lang=en")
                links = page.locator("nav.prop-strip a")
                assert links.count() == 6
                for index in range(6):
                    href = links.nth(index).get_attribute("href")
                    assert href and href.startswith("#")
                    page.evaluate(
                        "() => { document.querySelectorAll('details.prop-sec').forEach((d) => { d.open = false; }); history.replaceState(null, '', location.pathname + location.search); }"
                    )
                    link = links.nth(index)
                    page.wait_for_function(
                        """(i) => {
                      const n = document.querySelectorAll('nav.prop-strip a');
                      const el = n[i];
                      if (!el) return false;
                      el.focus();
                      const cs = getComputedStyle(el);
                      const ow = parseFloat(cs.outlineWidth);
                      const hasOutline = cs.outlineStyle !== 'none' && !Number.isNaN(ow) && ow > 0;
                      const hasRing = !!(cs.boxShadow && cs.boxShadow !== 'none');
                      return hasOutline || hasRing;
                    }""",
                        arg=index,
                        timeout=8000,
                    )
                    link.press("Enter")
                    page.locator(f"details#{href[1:]}[open]").wait_for(state="visible", timeout=15000)
                # Tab walk: start from the strip (close sections first so focus is not inside a panel).
                page.evaluate(
                    "() => { document.querySelectorAll('details.prop-sec').forEach((d) => { d.open = false; }); history.replaceState(null, '', location.pathname + location.search); }"
                )
                page.locator("nav.prop-strip .sc-actions button[data-copy]").wait_for(state="visible", timeout=8000)
                cal_link = page.locator('nav.prop-strip a[data-strip="calendars"]')
                cal_link.wait_for(state="visible", timeout=8000)
                cal_link.evaluate("el => el.focus()")
                sync_api.expect(cal_link).to_be_focused(timeout=8000)
                seen = []
                for _ in range(7):
                    page.keyboard.press("Tab")
                    seen.append(page.evaluate("() => document.activeElement.dataset.strip || document.activeElement.closest('[data-strip]')?.dataset.strip || document.activeElement.tagName"))
                assert seen[0] == "guest" and seen[1] == "guest", seen
                assert seen[2] in ("police", "BODY"), seen
        finally:
            browser.close()


def test_b04_pill_opens_incomplete_section_with_its_missing_note(host, base):
    db.update("apartment", host["apartment"], {"uby_idub": ""})
    _B04_SHOTS.mkdir(parents=True, exist_ok=True)
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        try:
            page = _context(browser, base, host).new_page()
            page.set_viewport_size({"width": 390, "height": 900})
            page.goto(f"{base}/apartments/{host['apartment']}?lang=en")
            page.evaluate("() => document.querySelectorAll('details.prop-sec').forEach((d) => { d.open = false; })")
            page.locator('nav.prop-strip a[data-strip="police"]').click()
            note = page.locator('#sec-police [data-missing="police"]')
            note.wait_for(state="visible", timeout=3000)
            assert "Missing: IDUB" in note.inner_text()
            page.screenshot(path=str(_B04_SHOTS / "b04-incomplete-police-390.png"), full_page=False)
        finally:
            browser.close()
