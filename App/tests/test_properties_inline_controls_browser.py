"""Task 0098: inline guest link, PIN and reporting timing on Properties.

The "Guest links and reporting timing" section shows each property's full
guest URL and PIN with icon-only Copy / Preview / New PIN, and an inline
"When to send to UbyPort" control. The control saves through the scoped
automation-timing route, which uses the Automation save's own normaliser:
the stored row is identical to a save from Settings -> Automation. New PIN
posts to the existing regenerate-pin route. Everything works without JS.

Screenshots: ``UBYHOST_CAPTURE_0098=1`` writes docs/tasks/0098-evidence/.
"""
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
from fastapi.testclient import TestClient

from app import auth, config, db, guest_slug
from app.main import app
from tests.conftest import login_as

EVIDENCE = Path(__file__).resolve().parents[2] / "docs" / "tasks" / "0098-evidence"
TIMING_COLUMNS = ("automation_mode", "submit_after_hours", "default_purpose")


def _cleanup(username: str) -> None:
    row = db.query_one("SELECT id FROM user_account WHERE username = ?", (username,))
    if not row:
        return
    user_id = row["id"]
    for table in ("apartment_slug", "ical_feed", "reservation"):
        db.execute(f"DELETE FROM {table} WHERE apartment_id IN "
                   "(SELECT id FROM apartment WHERE owner_user_id = ?)", (user_id,))
    db.execute("DELETE FROM alert WHERE apartment_id IN "
               "(SELECT id FROM apartment WHERE owner_user_id = ?)", (user_id,))
    db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (user_id,))
    db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (user_id,))
    db.execute("DELETE FROM audit WHERE owner_user_id = ?", (user_id,))
    db.execute("DELETE FROM alert WHERE owner_user_id = ?", (user_id,))
    db.execute("DELETE FROM user_account WHERE id = ?", (user_id,))


def _account(prefix: str):
    username = f"{prefix}-{secrets.token_hex(3)}"
    owner_id = auth.create_account(f"{username}@example.test", "Inline Host", username=username)
    entity_id = db.insert("legal_entity", {
        "name": "Ukázka Pole s.r.o.", "seat": "Praha 1", "ico": "04656679",
        "contact_email": "pole@example.test", "owner_user_id": owner_id, "created_at": db.utcnow(),
    })
    return username, owner_id, entity_id


def _property(name, entity_id, owner_id, **over) -> int:
    values = {
        "internal_name": name, "owner_user_id": owner_id, "legal_entity_id": entity_id,
        "automation_mode": "manual", "submit_after_hours": 24, "default_purpose": "10",
        "permalink_token": auth.new_permalink_token(), "permalink_pin": auth.new_permalink_pin(),
        "addr_obec": "Praha", "addr_house_no": "12", "addr_zip": "11000",
        "active": 1, "created_at": db.utcnow(),
    }
    values.update(over)
    return db.insert("apartment", values)


def _link_key(apartment_id: int) -> str:
    return guest_slug.current(apartment_id) or _row(apartment_id)["permalink_token"]


def _wait(page, fn: str, arg=None, timeout=5.0):
    """Poll a JS function (the CSP forbids wait_for_function's eval)."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if page.evaluate(fn, arg):
            return
        page.wait_for_timeout(50)
    raise AssertionError(f"timed out waiting for {fn} {arg}")


_STATUS_IS = """([id, text]) => {
  const s = document.querySelector(`tr[data-summary-row="${id}"] [data-timing-status]`);
  return text === 'error' ? s.classList.contains('is-error') : s.textContent === text;
}"""


def _row(apartment_id: int):
    return dict(db.query_one("SELECT * FROM apartment WHERE id = ?", (apartment_id,)))


def _login(username: str) -> TestClient:
    client = TestClient(app)
    response = login_as(client, username, url="/login?lang=en", follow_redirects=False)
    assert response.status_code == 303, response.text
    return client


@pytest.fixture
def host():
    db.init_db()
    username, owner_id, entity_id = _account("inline0098")
    client = _login(username)
    try:
        yield {"client": client, "owner": owner_id, "entity": entity_id}
    finally:
        _cleanup(username)


def _summary(page: str) -> str:
    start = page.index('id="property-summaries"')
    return page[start:page.index("</section>", start)]


class _FormFields(HTMLParser):
    """The fields a browser would submit from one form (no JS)."""

    def __init__(self, form_id: str):
        super().__init__()
        self.form_id, self.inside, self.fields = form_id, False, []
        self._select = None
        self._select_first = None
        self._select_chosen = None
        self._textarea = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "form" and a.get("id") == self.form_id:
            self.inside = True
        if not self.inside:
            return
        if tag == "input" and a.get("name") and "disabled" not in a:
            kind = a.get("type", "text")
            if kind in ("checkbox", "radio") and "checked" not in a:
                return
            if kind in ("submit", "button", "file"):
                return
            self.fields.append((a["name"], a.get("value", "on" if kind == "checkbox" else "")))
        elif tag == "select" and a.get("name"):
            self._select, self._select_first, self._select_chosen = a["name"], None, None
        elif tag == "option" and self._select:
            if self._select_first is None:
                self._select_first = a.get("value", "")
            if "selected" in a:
                self._select_chosen = a.get("value", "")
        elif tag == "textarea" and a.get("name"):
            self._textarea = [a["name"], ""]

    def handle_data(self, data):
        if self._textarea is not None:
            self._textarea[1] += data

    def handle_endtag(self, tag):
        if not self.inside:
            return
        if tag == "select" and self._select:
            chosen = self._select_chosen if self._select_chosen is not None else self._select_first
            self.fields.append((self._select, chosen or ""))
            self._select = None
        elif tag == "textarea" and self._textarea is not None:
            self.fields.append(tuple(self._textarea))
            self._textarea = None
        elif tag == "form":
            self.inside = False


def _automation_page_save(client, apartment_id, mode, hours):
    """Save exactly what the Settings -> Automation form submits (no JS)."""
    page = client.get(f"/apartments/{apartment_id}?view=settings&section=automation&lang=en").text
    parser = _FormFields("property-settings-form")
    parser.feed(page)
    fields = dict(parser.fields)
    assert {"automation_mode", "submit_after_hours", "default_purpose"} <= set(fields)
    fields["automation_mode"], fields["submit_after_hours"] = mode, str(hours)
    response = client.post(f"/apartments/{apartment_id}", data=fields, follow_redirects=False)
    assert response.status_code == 303, response.text[:400]


# --- server: markup, identical storage, refusals, ownership ---------------------

def test_full_url_pin_and_icon_actions_render(host):
    client = host["client"]
    first = _property("Byt Alfa", host["entity"], host["owner"])
    row = _row(first)
    summary = _summary(client.get("/apartments?lang=en").text)
    url = f"{config.PUBLIC_BASE_URL}/l/{_link_key(first)}"
    assert f'id="guest-url-{first}">{url}</code>' in summary
    assert f'id="guest-pin-{first}">{row["permalink_pin"]}</code>' in summary
    for label in ("Copy link", "Preview as a guest", "Copy PIN", "Generate a new PIN"):
        assert f'aria-label="{label}"' in summary and f'<span class="sr-only">{label}</span>' in summary
    assert f'href="/l/{_link_key(first)}" target="_blank" rel="noopener"' in summary
    assert "regenerate-link" not in summary
    pin_form = re.search(r'<form[^>]*action="/apartments/%d/regenerate-pin"[^>]*>' % first, summary).group(0)
    assert "data-confirm" in pin_form and "The old PIN stops working for guests" in pin_form
    assert 'name="return_to" value="/apartments#property-summaries"' in summary
    # Header: a plain section heading with its "?", same table design as above.
    assert 'class="heading-with-tip property-summaries-head"' in summary
    assert 'class="panel tight scroll-x list-cards lc-properties property-summary-panel"' in summary
    assert re.search(r'<a class="row-primary-link" href="/apartments/%d">\s*<span class="property-identity">' % first, summary)
    cs = _summary(client.get("/apartments?lang=cs").text)
    assert "Kdy odesílat do UbyPortu" in cs and 'aria-label="Kopírovat PIN"' in cs
    assert "Starý PIN hostům okamžitě přestane fungovat" in cs
    assert not re.search(r">\s*properties\.[a-z_.]+\s*<", cs)


@pytest.mark.parametrize("mode,hours", [("scheduled", 7), ("immediate", 9), ("manual", 30), ("scheduled", 48)])
def test_inline_save_stores_the_same_row_as_the_automation_page(host, mode, hours):
    client = host["client"]
    via_settings = _property("Byt Alfa", host["entity"], host["owner"], default_purpose="99")
    via_inline = _property("Byt Beta", host["entity"], host["owner"], default_purpose="99")
    before = _row(via_inline)
    _automation_page_save(client, via_settings, mode, hours)
    response = client.post(f"/apartments/{via_inline}/automation-timing",
                           data={"automation_mode": mode, "submit_after_hours": str(hours),
                                 "return_to": "/apartments#property-summaries"},
                           follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"].startswith("/apartments?msg=")
    assert response.headers["location"].endswith("#property-summaries")
    settings_row, inline_row = _row(via_settings), _row(via_inline)
    assert {c: settings_row[c] for c in TIMING_COLUMNS} == {c: inline_row[c] for c in TIMING_COLUMNS}
    assert inline_row["default_purpose"] == "99"
    # The inline save writes nothing but the two timing columns.
    changed = {k for k in before if before[k] != inline_row[k]}
    assert changed <= {"automation_mode", "submit_after_hours", "updated_at"}, changed


def test_json_save_and_refusals_store_nothing(host):
    client = host["client"]
    apartment_id = _property("Byt Alfa", host["entity"], host["owner"],
                             automation_mode="scheduled", submit_after_hours=6)
    ok = client.post(f"/apartments/{apartment_id}/automation-timing",
                     data={"automation_mode": "scheduled", "submit_after_hours": "12"},
                     headers={"Accept": "application/json"})
    assert ok.status_code == 200 and ok.json()["ok"] is True
    assert ok.json()["submit_after_hours"] == 12
    before = _row(apartment_id)
    for data in ({"automation_mode": "scheduled", "submit_after_hours": ""},
                 {"automation_mode": "scheduled", "submit_after_hours": "0"},
                 {"automation_mode": "scheduled", "submit_after_hours": "49"},
                 {"automation_mode": "scheduled", "submit_after_hours": "abc"},
                 {"automation_mode": "sometimes", "submit_after_hours": "5"}):
        refused = client.post(f"/apartments/{apartment_id}/automation-timing", data=data,
                              headers={"Accept": "application/json"})
        assert refused.status_code == 400 and refused.json()["ok"] is False, data
        assert "Nothing was saved" in refused.json()["error"]
        no_js = client.post(f"/apartments/{apartment_id}/automation-timing", data=data,
                            follow_redirects=False)
        assert no_js.status_code == 303 and "err=" in no_js.headers["location"], data
        assert no_js.headers["location"].endswith("#property-summaries")
    assert _row(apartment_id) == before


def test_a_foreign_property_is_refused(host):
    other_user, other_owner, other_entity = _account("inline0098-other")
    try:
        foreign = _property("Cizí byt", other_entity, other_owner)
        before = _row(foreign)
        client = host["client"]
        refused = client.post(f"/apartments/{foreign}/automation-timing",
                              data={"automation_mode": "immediate", "submit_after_hours": "5"},
                              headers={"Accept": "application/json"})
        assert refused.status_code == 404 and refused.json()["ok"] is False
        no_js = client.post(f"/apartments/{foreign}/automation-timing",
                            data={"automation_mode": "immediate"}, follow_redirects=False)
        assert no_js.status_code == 303 and "err=" in no_js.headers["location"]
        pin = client.post(f"/apartments/{foreign}/regenerate-pin",
                          data={"return_to": "/apartments#property-summaries"}, follow_redirects=False)
        assert pin.status_code == 303 and "err=" in pin.headers["location"]
        assert _row(foreign) == before
        # Logged out: the login guard, nothing stored.
        anonymous = TestClient(app).post(f"/apartments/{foreign}/automation-timing",
                                         data={"automation_mode": "immediate"}, follow_redirects=False)
        assert anonymous.status_code in (303, 401, 403)
        assert _row(foreign) == before
    finally:
        _cleanup(other_user)


def test_no_js_new_pin_returns_to_the_summary(host):
    client = host["client"]
    apartment_id = _property("Byt Alfa", host["entity"], host["owner"])
    old = _row(apartment_id)["permalink_pin"]
    response = client.post(f"/apartments/{apartment_id}/regenerate-pin",
                           data={"return_to": "/apartments#property-summaries"}, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"].startswith("/apartments?msg=")
    assert response.headers["location"].endswith("#property-summaries")
    assert _row(apartment_id)["permalink_pin"] != old


# --- browser ------------------------------------------------------------------

@pytest.fixture(scope="module")
def browser_host():
    db.init_db()
    username, owner_id, entity_id = _account("inline0098b")
    ids = [
        _property("Byt Alfa", entity_id, owner_id),
        _property("Chata Beta u lesa s dlouhým názvem", entity_id, owner_id, addr_obec="Horní Planá",
                  automation_mode="scheduled", submit_after_hours=6),
        _property("Studio Gama", entity_id, owner_id, addr_obec="Brno", automation_mode="immediate"),
    ]
    client = _login(username)
    yield {"client": client, "owner": owner_id, "ids": ids}
    _cleanup(username)


@pytest.fixture(scope="module")
def live_base(browser_host):
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
        pytest.fail("the test server did not start")
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=5)


_CLIPBOARD = """window.__copyWrites = []; Object.defineProperty(navigator, 'clipboard', {
  configurable: true, value: { writeText: v => { window.__copyWrites.push(v); return Promise.resolve(); } } });"""


def _context(browser, live_base, browser_host, *, width=1280, js=True):
    context = browser.new_context(viewport={"width": width, "height": 900}, java_script_enabled=js)
    cookie = browser_host["client"].cookies.get(auth.SESSION_COOKIE)
    context.add_cookies([{"name": auth.SESSION_COOKIE, "value": cookie, "url": live_base + "/"}])
    if js:
        context.add_init_script(_CLIPBOARD)
    return context


@pytest.fixture(scope="module")
def browser():
    sync_api = pytest.importorskip("playwright.sync_api")
    from tests.browser_support import chromium_launch_kwargs

    with sync_api.sync_playwright() as playwright:
        instance = playwright.chromium.launch(**chromium_launch_kwargs())
        try:
            yield instance
        finally:
            instance.close()


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
    page.wait_for_timeout(250)


def test_copy_link_and_pin_and_new_pin_with_confirmation(browser, live_base, browser_host, monkeypatch):
    first = browser_host["ids"][0]
    row = _row(first)
    context = _context(browser, live_base, browser_host)
    page = context.new_page()
    page.goto(f"{live_base}/apartments?lang=en#property-summaries")
    tr = page.locator(f'tr[data-summary-row="{first}"]')
    tr.get_by_role("button", name="Copy link").click()
    tr.get_by_role("button", name="Copy PIN").click()
    _wait(page, "() => window.__copyWrites.length >= 2")
    writes = page.evaluate("window.__copyWrites")
    key = _link_key(first)
    assert writes[0] == f"{config.PUBLIC_BASE_URL}/l/{key}"
    assert writes[1] == row["permalink_pin"]
    preview = tr.get_by_role("link", name="Preview as a guest")
    assert preview.get_attribute("target") == "_blank"
    assert preview.get_attribute("href") == f"/l/{key}"
    # New PIN asks first, and the question says the old PIN stops working.
    tr.get_by_role("button", name="Generate a new PIN").click()
    dialog = page.locator("#confirm-dialog")
    dialog.wait_for(state="visible")
    assert "old PIN stops working for guests" in dialog.inner_text()
    dialog.locator("[data-confirm-proceed]").click()
    page.wait_for_url(re.compile(r"/apartments\?msg=.*#property-summaries$"))
    new_pin = _row(first)["permalink_pin"]
    assert new_pin != row["permalink_pin"]
    assert page.locator(f"#guest-pin-{first}").inner_text() == new_pin
    context.close()
    # The guest page refuses the old PIN and accepts the new one.
    monkeypatch.setattr("app.config.GUEST_PIN_REQUIRED", True)
    guest = TestClient(app)
    old = guest.post(f"/l/{key}/pin", data={"pin": row["permalink_pin"], "return_to": f"/l/{key}"},
                     follow_redirects=False)
    assert old.status_code != 303
    fresh = guest.post(f"/l/{key}/pin", data={"pin": new_pin, "return_to": f"/l/{key}"},
                       follow_redirects=False)
    assert fresh.status_code == 303


def test_timing_saves_on_change_and_hours_box_follows_the_mode(browser, live_base, browser_host):
    target = browser_host["ids"][2]
    db.update("apartment", target, {"automation_mode": "immediate", "submit_after_hours": 24})
    context = _context(browser, live_base, browser_host)
    page = context.new_page()
    page.goto(f"{live_base}/apartments?lang=en#property-summaries")
    tr = page.locator(f'tr[data-summary-row="{target}"]')
    hours = tr.locator("[data-timing-hours-input]")
    status = tr.locator("[data-timing-status]")
    assert tr.locator("[data-timing-save]").is_hidden()          # JS saves on change
    assert hours.is_hidden()
    tr.locator("select[data-timing-mode]").select_option("scheduled")
    assert hours.is_visible()
    _wait(page, _STATUS_IS, [target, "Saved"])
    assert status.get_attribute("aria-live") == "polite"
    assert _row(target)["automation_mode"] == "scheduled"
    hours.fill("5")
    deadline = time.time() + 5                                 # debounced, then sent
    while _row(target)["submit_after_hours"] != 5 and time.time() < deadline:
        page.wait_for_timeout(50)
    assert _row(target)["submit_after_hours"] == 5
    _wait(page, _STATUS_IS, [target, "Saved"])
    # Invalid hours: the real error, and nothing stored.
    before = _row(target)
    hours.fill("60")
    _wait(page, _STATUS_IS, [target, "error"])
    assert "1 to 48" in status.inner_text()
    assert _row(target) == before
    tr.locator("select[data-timing-mode]").select_option("manual")
    assert hours.is_hidden()
    _wait(page, _STATUS_IS, [target, "Saved"])
    assert _row(target)["automation_mode"] == "manual"
    # Reload: the page shows what is stored.
    page.reload()
    assert page.locator(f"#timing-mode-{target}").input_value() == "manual"
    context.close()


def test_no_js_save_button_works(browser, live_base, browser_host):
    target = browser_host["ids"][0]
    db.update("apartment", target, {"automation_mode": "manual", "submit_after_hours": 24})
    context = _context(browser, live_base, browser_host, js=False)
    page = context.new_page()
    page.goto(f"{live_base}/apartments?lang=cs")
    tr = page.locator(f'tr[data-summary-row="{target}"]')
    save = tr.locator("[data-timing-save]")
    assert save.is_visible() and save.inner_text().strip() == "Uložit"
    tr.locator("select[data-timing-mode]").select_option("scheduled")
    hours = tr.locator("[data-timing-hours-input]")
    assert hours.is_visible()                                    # CSS :has(), no JS needed
    hours.fill("8")
    save.click()
    page.wait_for_url(re.compile(r"/apartments\?msg=.*#property-summaries$"))
    stored = _row(target)
    assert (stored["automation_mode"], stored["submit_after_hours"]) == ("scheduled", 8)
    context.close()


_FIT_JS = """() => {
  const vw = document.documentElement.clientWidth;
  const panel = document.querySelector('.property-summary-panel');
  const list = document.querySelector('.properties-table').closest('.panel');
  const pr = panel.getBoundingClientRect(), lr = list.getBoundingClientRect();
  const bad = [], small = [];
  const sel = 'a, button, select, input:not([type=hidden]), code, h2, .help-tip-btn';
  for (const el of document.querySelectorAll('#property-summaries ' + sel.split(', ').join(', #property-summaries '))) {
    const r = el.getBoundingClientRect();
    if (!r.width || !r.height) continue;
    if (el.closest('.sr-only') || el.classList.contains('sr-only')) continue;
    if (r.right > pr.right + 1 || r.left < pr.left - 1 || r.right > vw + 1)
      bad.push((el.getAttribute('aria-label') || el.textContent || el.tagName).trim().slice(0, 30));
    if (el.matches('.btn-icon, select, input, [data-timing-save]') && (r.height < 43.5 || r.width < 43.5))
      small.push((el.getAttribute('aria-label') || el.tagName) + ' ' + Math.round(r.width) + 'x' + Math.round(r.height));
  }
  const title = document.querySelector('.property-summaries-title');
  const ts = getComputedStyle(title);
  return {scroll: document.documentElement.scrollWidth, vw, bad, small,
          panelScroll: panel.scrollWidth - panel.clientWidth,
          cards: getComputedStyle(panel.querySelector('thead')).display === 'none',
          listCards: getComputedStyle(list.querySelector('thead')).display === 'none',
          aligned: Math.abs(pr.left - lr.left) <= 2 && Math.abs(pr.right - lr.right) <= 2,
          band: ts.backgroundColor !== 'rgba(0, 0, 0, 0)' && ts.backgroundColor !== 'transparent',
          details: document.querySelectorAll('#property-summaries details').length};
}"""


def test_summary_fits_every_width_both_languages_rail_states(browser, live_base, browser_host):
    capture = os.environ.get("UBYHOST_CAPTURE_0098") == "1"
    for width in (360, 390, 760, 1024, 1280, 1440):
        context = _context(browser, live_base, browser_host, width=width)
        page = context.new_page()
        for lang in ("en", "cs"):
            page.goto(f"{live_base}/apartments?lang={lang}")
            # Show the hours box on one row so the widest state is measured.
            for collapsed in ((False, True) if width >= 1024 else (False,)):
                _sidebar(page, collapsed)
                fit = page.evaluate(_FIT_JS)
                key = (width, lang, collapsed)
                assert fit["scroll"] <= fit["vw"], (key, fit)
                assert fit["panelScroll"] <= 1, (key, fit)
                assert not fit["bad"], (key, fit)
                assert not fit["small"], (key, fit)
                assert fit["aligned"] and fit["details"] == 0 and not fit["band"], (key, fit)
                # Same narrow-lane behaviour as the Properties table above.
                assert fit["cards"] == fit["listCards"], (key, fit)
                if width <= 760:
                    assert fit["cards"], (key, fit)
                if width >= 1280:
                    assert not fit["cards"], (key, fit)
            _sidebar(page, False)
            if capture and width in (360, 1280):
                EVIDENCE.mkdir(parents=True, exist_ok=True)
                page.locator("#property-summaries").scroll_into_view_if_needed()
                page.screenshot(path=str(EVIDENCE / f"properties-inline-{width}-{lang}.png"), full_page=True)
        context.close()
