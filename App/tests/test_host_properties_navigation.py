"""Task 0078: Properties list, shared-record links and read-only summaries.

The list shows name/location, setup state, calendar count and an aligned
Open. Business & legal details and a connected door-lock account are linked
once. The guest-link and reporting-timing summary is a visible, read-only
section whose rows open each property's own editor. Old hub URLs and Search
land on the same canonical places.
"""
from __future__ import annotations

import os
import re
import secrets
import socket
import threading
import time
from pathlib import Path
from unittest.mock import patch

import pytest
import uvicorn
from fastapi.testclient import TestClient

from app import auth, db
from app.main import app
from tests.conftest import login_as

USERNAME = "properties-nav-0078-host"
EVIDENCE = Path(__file__).resolve().parents[2] / "docs" / "tasks" / "0078-evidence"


def _owner() -> int:
    return db.query_one("SELECT id FROM user_account WHERE username = ?", (USERNAME,))["id"]


def _cleanup(username=USERNAME):
    row = db.query_one("SELECT id FROM user_account WHERE username = ?", (username,))
    if not row:
        return
    user_id = row["id"]
    db.execute("DELETE FROM apartment_slug WHERE apartment_id IN "
               "(SELECT id FROM apartment WHERE owner_user_id = ?)", (user_id,))
    db.execute("DELETE FROM ical_feed WHERE apartment_id IN "
               "(SELECT id FROM apartment WHERE owner_user_id = ?)", (user_id,))
    db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (user_id,))
    db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (user_id,))
    db.execute("DELETE FROM audit WHERE owner_user_id = ?", (user_id,))
    db.execute("DELETE FROM alert WHERE owner_user_id = ?", (user_id,))
    db.execute("DELETE FROM user_account WHERE id = ?", (user_id,))


@pytest.fixture
def host():
    db.init_db()
    _cleanup()
    auth.create_account(f"{USERNAME}@example.test", "Props Host", username=USERNAME)
    client = TestClient(app)
    response = login_as(client, USERNAME, url="/login?lang=en", follow_redirects=False)
    assert response.status_code == 303, response.text
    try:
        yield client
    finally:
        _cleanup()


def _entity(name="Ukázka Pole s.r.o.", owner=None) -> int:
    return db.insert("legal_entity", {
        "name": name, "seat": "Praha 1", "ico": "04656679", "contact_email": "pole@example.test",
        "owner_user_id": owner or _owner(), "created_at": db.utcnow(),
    })


def _property(name, entity_id, owner=None, **over) -> int:
    values = {
        "internal_name": name, "owner_user_id": owner or _owner(), "legal_entity_id": entity_id,
        "automation_mode": "manual", "submit_after_hours": 24, "default_purpose": "10",
        "permalink_token": auth.new_permalink_token(), "permalink_pin": auth.new_permalink_pin(),
        "addr_obec": "Praha", "active": 1, "created_at": db.utcnow(),
    }
    values.update(over)
    return db.insert("apartment", values)


def _summary(page):
    start = page.index('id="property-summaries"')
    return page[start:page.index("</section>", start)]


# --- one / many / none / archived ------------------------------------------------

def test_no_business_and_no_property_states_stay_distinct(host):
    empty = host.get("/apartments?lang=en").text
    assert 'id="property-summaries"' not in empty
    # 0099: the shared records are the Properties sub-page tabs; with no
    # business there is no Business & legal details tab yet.
    assert 'href="/entities?edit=' not in empty
    assert "Add operator" in empty
    entity_id = _entity()
    ready = host.get("/apartments?lang=en").text
    assert "No properties yet." in ready and 'href="/apartments/new"' in ready
    assert 'id="property-summaries"' not in ready
    # The one shared business is linked once, in its own editor scope.
    assert ready.count(f'href="/entities?edit={entity_id}&amp;next=/apartments"') == 1


def test_list_rows_show_setup_calendars_and_open_inside_the_menu(host):
    entity_id = _entity()
    first = _property("Byt Alfa", entity_id, addr_obec="Brno", uby_name="UBY-FACILITY",
                      uby_idub="123456789012", uby_mark="UBYX", uby_ws_user="ws-login-x")
    second = _property("Chata Beta", entity_id, automation_mode="scheduled", submit_after_hours=6)
    page = host.get("/apartments?lang=en").text
    table = page[page.index('class="table-cards properties-table"'):page.index("</table>")]
    for apartment_id in (first, second):
        assert f'<a class="btn small" href="/apartments/{apartment_id}">Open</a>' not in table
        assert f'<a class="row-menu-item" href="/apartments/{apartment_id}" role="menuitem">Open</a>' in table
        assert f'href="/apartments/{apartment_id}?view=settings&amp;section=guests#communication"' in table
        assert f'href="/apartments/{apartment_id}?view=settings&amp;section=automation#automation"' in table
    # 0098 (owner): no police/UbyPort value under the name (address, facility
    # name, IDUB, mark, login); the row shows the avatar and the name only.
    assert "property-location" not in table and ">Brno<" not in table
    for police in ("UBY-FACILITY", "123456789012", "UBYX", "ws-login-x"):
        assert police not in page, police
    assert re.search(r'<span class="pill (amber|green)">', table)
    # Old hashes that pointed at the wrong group are gone.
    assert "#ubyport\" role=\"menuitem\"" not in table
    # Two businesses: the shared link opens the list, never an arbitrary one.
    _entity(name="Druhá s.r.o.")
    assert '<a class="sub-tab" href="/entities">Business &amp; legal details</a>' in host.get("/apartments").text


def test_summary_is_visible_read_only_and_links_to_each_editor(host):
    entity_id = _entity()
    first = _property("Byt Alfa", entity_id)
    second = _property("Chata Beta", entity_id, automation_mode="scheduled", submit_after_hours=6)
    archived = _property("Starý byt", entity_id, archived_at=db.utcnow())
    page = host.get("/apartments?lang=en").text
    summary = _summary(page)
    assert "<details" not in page[page.index('data-sub-tabs'):]
    assert "Guest links and reporting timing" in summary
    # 0098 (owner): the summary now carries the inline timing control and the
    # New PIN form; it posts only to the scoped timing route and regenerate-pin.
    actions = set(re.findall(r'<form[^>]*action="([^"]+)"', summary))
    assert actions == {f"/apartments/{i}/{route}" for i in (first, second)
                       for route in ("regenerate-pin", "automation-timing")}
    assert "<textarea" not in summary and 'name="default_purpose"' not in summary
    for apartment_id in (first, second):
        assert f'href="/apartments/{apartment_id}"' in summary
    token = db.query_one("SELECT permalink_token FROM apartment WHERE id = ?", (first,))["permalink_token"]
    assert f"/l/{token}" in summary
    assert '<option value="manual" selected>Only when I press send' in summary
    assert '<option value="scheduled" selected>Automatically, after a delay' in summary
    assert 'value="6" data-timing-hours-input' in summary
    assert "Starý byt" not in summary
    # Archived properties are off the working list; Restore lives in
    # Settings › Data & archive › Archived (owner, 2026-10-13).
    assert f'action="/apartments/{archived}/unarchive"' not in page
    archive = host.get("/settings/archived?lang=en").text
    assert f'action="/apartments/{archived}/unarchive"' in archive


def test_listing_never_creates_a_guest_link_slug(host):
    entity_id = _entity()
    apartment_id = _property("Byt Alfa", entity_id)
    before = db.query_one("SELECT COUNT(*) AS n FROM apartment_slug WHERE apartment_id = ?",
                          (apartment_id,))["n"]
    host.get("/apartments")
    after = db.query_one("SELECT COUNT(*) AS n FROM apartment_slug WHERE apartment_id = ?",
                         (apartment_id,))["n"]
    assert after == before


def test_czech_labels_render(host):
    entity_id = _entity()
    _property("Byt Alfa", entity_id)
    page = host.get("/apartments?lang=cs").text
    assert "Odkazy pro hosty a načasování hlášení" in _summary(page)
    assert ">Otevřít</a>" in page
    assert not re.search(r">\s*properties\.[a-z_.]+\s*<", page)


def test_lock_account_link_only_when_connected(host):
    _entity()
    body = host.get("/apartments").text
    body = body[body.index("<main") : body.index("</main>")]
    assert 'href="/smart-locks"' not in body
    with patch("app.ttlock.enabled", return_value=True), \
            patch("app.ttlock.account_for", return_value={"id": 1, "username": "x"}):
        page = host.get("/apartments?lang=en").text
        urls = {item.get("url") for item in host.get("/api/command-palette").json()["items"]}
    main = page[page.index("<main") : page.index("</main>")]
    assert main.count('href="/smart-locks"') == 1 and "Door lock account" in main
    assert "/smart-locks" in urls


# --- legacy hub URLs and Search ----------------------------------------------------

def test_hub_redirects_for_none_one_and_many(host):
    # 0101: /guest-links stays for e-mails already sent; /automation is gone.
    response = host.get("/guest-links", follow_redirects=False)
    assert response.headers["location"] == "/apartments#property-summaries"
    assert host.get("/automation", follow_redirects=False).status_code == 404
    entity_id = _entity()
    first = _property("Byt Alfa", entity_id)
    assert host.get("/guest-links", follow_redirects=False).headers["location"] == (
        f"/apartments/{first}?view=settings&section=guests#communication")
    items = host.get("/api/command-palette").json()["items"]
    urls = {item["url"] for item in items if "url" in item}
    assert f"/apartments/{first}?view=settings&section=guests#communication" in urls
    assert f"/apartments/{first}?view=settings&section=automation#automation" in urls
    _property("Chata Beta", entity_id)
    assert host.get("/guest-links", follow_redirects=False).headers["location"] == (
        "/apartments#property-summaries")
    urls = {item.get("url") for item in host.get("/api/command-palette").json()["items"]}
    assert "/apartments#property-summaries" in urls
    assert {"/apartments", "/entities", f"/entities?edit={entity_id}&next=/invoices#entity-invoice"} <= urls
    assert not {"/guest-links", "/automation", "/invoices/settings"} & urls


# --- browser: list and summary fit 360-2048, EN and CS -----------------------------

BROWSER_USER = "propsnav0078"


@pytest.fixture(scope="module")
def browser_host():
    db.init_db()
    username = f"{BROWSER_USER}-{secrets.token_hex(3)}"
    owner_id = auth.create_account(f"{username}@example.test", "Pole Host", username=username)
    entity_id = _entity(owner=owner_id)
    _property("Byt Alfa", entity_id, owner=owner_id, addr_obec="Praha")
    _property("Chata Beta u lesa s dlouhým názvem", entity_id, owner=owner_id,
              addr_obec="Horní Planá", automation_mode="scheduled", submit_after_hours=6)
    _property("Studio Gama", entity_id, owner=owner_id, addr_obec="Brno",
              automation_mode="immediate")
    _property("Starý byt", entity_id, owner=owner_id, archived_at=db.utcnow())
    client = TestClient(app)
    response = login_as(client, username, url="/login?lang=en", follow_redirects=False)
    assert response.status_code == 303, response.text
    yield {"client": client, "owner": owner_id}
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


_FIT_JS = """() => {
  const vw = document.documentElement.clientWidth;
  const bad = [];
  const sel = '.sub-tabs a, .properties-table a, .properties-table button, '
    + '.property-summaries a, .property-summaries h2, .property-summaries button';
  for (const el of document.querySelectorAll(sel)) {
    const r = el.getBoundingClientRect();
    if (!r.width || !r.height) continue;
    if (r.right > vw + 1 || r.left < -1) bad.push(el.textContent.trim().slice(0, 30));
  }
  const opens = [...document.querySelectorAll('.properties-table .row-actions > a.btn')]
    .map(a => Math.round(a.getBoundingClientRect().right));
  const lane = document.querySelector('.properties-table').closest('.panel').getBoundingClientRect();
  const summary = document.querySelector('.property-summaries .panel').getBoundingClientRect();
  const title = document.querySelector('.property-summaries-title');
  return {scroll: document.documentElement.scrollWidth, vw, bad, opens,
          lane: [Math.round(lane.left), Math.round(lane.right)],
          summary: [Math.round(summary.left), Math.round(summary.right)],
          titleVisible: title.getBoundingClientRect().height > 0,
          details: document.querySelectorAll('.property-summaries details').length};
}"""


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


def test_properties_page_fits_every_width_and_both_languages(browser_host, live_base):
    sync_api = pytest.importorskip("playwright.sync_api")
    from tests.browser_support import chromium_launch_kwargs

    capture = os.environ.get("UBYHOST_CAPTURE_0078") == "1"
    cookie = browser_host["client"].cookies.get(auth.SESSION_COOKIE)
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        try:
            for width in (360, 390, 768, 1024, 1280, 1440, 2048):
                context = browser.new_context(viewport={"width": width, "height": 900})
                context.add_cookies([{"name": auth.SESSION_COOKIE, "value": cookie,
                                      "url": live_base + "/"}])
                page = context.new_page()
                for lang in ("en", "cs"):
                    page.goto(f"{live_base}/apartments?lang={lang}")
                    for collapsed in ((False, True) if width >= 1024 else (False,)):
                        _sidebar(page, collapsed)
                        fit = page.evaluate(_FIT_JS)
                        key = (width, lang, collapsed)
                        assert fit["scroll"] <= fit["vw"], (key, fit)
                        assert not fit["bad"], (key, fit)
                        assert fit["titleVisible"] and fit["details"] == 0, (key, fit)
                        assert len(fit["opens"]) == 3, (key, fit)
                        assert abs(fit["lane"][0] - fit["summary"][0]) <= 2, (key, fit)
                        assert abs(fit["lane"][1] - fit["summary"][1]) <= 2, (key, fit)
                        if width >= 1024:
                            # Open sits at the same right edge on every row.
                            assert max(fit["opens"]) - min(fit["opens"]) <= 2, (key, fit)
                    _sidebar(page, False)
                    if capture and width in (360, 390, 1280):
                        EVIDENCE.mkdir(parents=True, exist_ok=True)
                        page.screenshot(path=str(EVIDENCE / f"properties-{width}-{lang}.png"),
                                        full_page=True)
                # Old hub URL with several properties lands on the summary.
                page.goto(f"{live_base}/guest-links?lang=en")
                assert page.url.endswith("/apartments#property-summaries")
                box = page.locator("#property-summaries").bounding_box()
                assert box and box["y"] < 900, box
                context.close()
        finally:
            browser.close()
