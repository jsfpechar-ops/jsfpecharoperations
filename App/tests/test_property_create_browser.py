"""0092: one short Add property page, its server rules and its browser fit."""
from __future__ import annotations

import os
import re
import secrets
import socket
import threading
import time
from pathlib import Path

import pytest
import uvicorn
from fastapi.testclient import TestClient

REQUIRE_BROWSER = os.environ.get("UBYHOST_REQUIRE_BROWSER") == "1"
if REQUIRE_BROWSER:
    import playwright.sync_api as sync_api
else:
    sync_api = pytest.importorskip("playwright.sync_api")

from app import auth, db, host_i18n
from app.main import app
from tests.browser_support import chromium_launch_kwargs
from tests.conftest import login_as

EVIDENCE = Path(__file__).resolve().parents[2] / "docs" / "tasks" / "0092-evidence"
SHARED_IDS = (
    "internal_name", "city_en", "legal_entity_id", "addr_okres", "addr_obec", "addr_obec_cast",
    "addr_street", "addr_house_no", "addr_orient_no", "addr_zip",
)
# Settings that belong to the property page after it exists, never to create.
NOT_ON_CREATE = (
    "automation_mode", "submit_after_hours", "uby_idub", "uby_ws_user",
    "uby_ws_password", "uby_mark", "uby_name", "uby_contact", "guest_message", "notes",
    "permalink_pin", "permalink_window_days", "passport_photo_policy", "door_codes", "lock_id",
    "stay_fee_rate_czk", "active", "address_line",
)


def setup_module():
    db.init_db()


def _host(entities: int = 1, prefix: str = "create"):
    username = f"{prefix}-{secrets.token_hex(4)}"
    owner_id = auth.create_account(f"{username}@example.test", "Create Host", role="host", username=username)
    entity_ids = [
        db.insert("legal_entity", {
            "name": "Synthetic Operator s.r.o." if index == 0 else f"Second Operator {index}",
            "contact_email": f"op{index}@example.test",
            "owner_user_id": owner_id,
            "created_at": db.utcnow(),
        })
        for index in range(entities)
    ]
    client = TestClient(app)
    assert login_as(client, username, url="/login?lang=en", follow_redirects=False).status_code == 303
    return {"client": client, "owner": owner_id, "entities": entity_ids, "username": username}


def _rows(owner_id):
    return db.query("SELECT * FROM apartment WHERE owner_user_id = ? ORDER BY id", (owner_id,))


def _form(**overrides):
    data = {
        "internal_name": "Synthetic Loft",
        "city_en": "Brno",
        "addr_obec": "Praha",
        "addr_house_no": "12",
        "addr_zip": "11000",
    }
    data.update(overrides)
    return data


def _ids(html):
    return re.findall(r'\sid="([^"]+)"', html)


# --- page shape -------------------------------------------------------------


def test_create_page_is_short_and_has_each_field_once():
    host = _host(1)
    page = host["client"].get("/apartments/new?lang=en").text
    assert page.count('action="/apartments"') == 1
    ids = _ids(page)
    for field in SHARED_IDS:
        assert ids.count(field) == 1, field
        assert page.count(f'name="{field}"') == 1, field
    for field in NOT_ON_CREATE:
        assert f'name="{field}"' not in page, field
    assert len(ids) == len(set(ids)), "duplicate ids"
    content = page[page.index('<header class="page-header"'):]
    for gone in ('class="section-nav"', "onboarding-banner", "more-options", "<details", "Step 1 of"):
        assert gone not in content, gone
    # The purpose default is the existing tourism code, carried as one hidden value.
    assert page.count('name="default_purpose"') == 1
    assert '<input type="hidden" name="default_purpose" value="10">' in page
    assert host_i18n.translate("en", "property_create.submit") in page
    for key in ("property_create.next_calendar", "property_create.next_guests", "property_create.next_reporting"):
        assert host_i18n.translate("en", key) in page
    # Routine helper text is behind the shared ? help, still linked to its input.
    assert 'aria-describedby="internal_name-help"' in page
    assert 'id="addr_zip-help" role="tooltip"' in page


def test_one_operator_is_chosen_and_one_submit_creates_a_manual_property():
    host = _host(1)
    page = host["client"].get("/apartments/new").text
    assert f'<option value="{host["entities"][0]}" selected>' in page
    hidden = dict(re.findall(r'<input type="hidden" name="([^"]+)" value="([^"]*)">', page))
    hidden.pop("_csrf", None)
    response = host["client"].post(
        "/apartments", data={**hidden, **_form(legal_entity_id=str(host["entities"][0]), active="0")},
        follow_redirects=False,
    )
    assert response.status_code == 303
    (row,) = _rows(host["owner"])
    assert response.headers["location"].startswith(f"/apartments/{row['id']}?view=bookings&created=1")
    assert response.headers["location"].endswith("#calendar-connect")
    assert row["internal_name"] == "Synthetic Loft" and row["city_en"] == "Brno"
    assert row["legal_entity_id"] == host["entities"][0]
    assert row["data_controller_entity_id"] is None
    assert (row["active"], row["automation_mode"], row["default_purpose"]) == (1, "manual", "10")
    assert row["guest_message"] == host_i18n.translate("en", "apartment.form.guest_message.default")
    assert row["lock_provider"] is None and not row["uby_ws_password_enc"]
    assert (row["addr_obec"], row["addr_house_no"], row["addr_zip"]) == ("Praha", "12", "11000")
    # The first-use choice is optional and appears only right after create.
    detail = host["client"].get(response.headers["location"]).text
    assert 'class="panel property-first-use"' in detail
    assert f'href="/reservations?new=1&amp;apartment={row["id"]}#add-stay-panel"' in detail
    assert f'href="/apartments/{row["id"]}?view=bookings#calendar-connect"' in detail
    assert 'class="panel property-first-use"' not in host["client"].get(f"/apartments/{row['id']}").text


def test_several_operators_need_a_choice_and_keep_the_draft():
    host = _host(2)
    page = host["client"].get("/apartments/new").text
    assert '<option value="" disabled selected>' in page
    draft = _form(addr_obec="Brno", addr_house_no="12", addr_zip="602 00", addr_street="Synthetic")
    response = host["client"].post("/apartments", data=draft, follow_redirects=False)
    assert response.status_code == 400
    for value in ("Synthetic Loft", "Brno", "602 00", "Synthetic"):
        assert f'value="{value}"' in response.text
    assert host_i18n.translate("en", "apartment.form.operator.required") in response.text
    assert _rows(host["owner"]) == []


def test_no_operator_detour_keeps_name_city_and_address():
    host = _host(0)
    draft = _form(addr_obec="Olomouc", addr_house_no="7", operator_refresh="1")
    response = host["client"].post("/apartments", data=draft, follow_redirects=False)
    assert response.status_code == 200
    for value in ("Synthetic Loft", "Brno", "Olomouc", "7"):
        assert f'value="{value}"' in response.text
    assert 'name="operator_refresh"' in response.text
    assert 'href="/entities"' in response.text
    assert _rows(host["owner"]) == []
    # The business is added in another tab; "Check again" then offers it.
    entity_id = db.insert("legal_entity", {"name": "Late Operator", "owner_user_id": host["owner"], "created_at": db.utcnow()})
    again = host["client"].post("/apartments", data=draft, follow_redirects=False)
    assert f'<option value="{entity_id}" selected>' in again.text
    assert 'value="Olomouc"' in again.text


def test_blank_name_and_invalid_address_parts_are_refused_with_values():
    host = _host(1)
    response = host["client"].post(
        "/apartments",
        data=_form(internal_name="  ", legal_entity_id=str(host["entities"][0]),
                   addr_house_no="12345", addr_zip="12", addr_obec="Praha"),
        follow_redirects=False,
    )
    assert response.status_code == 400
    html = response.text
    assert 'id="internal_name-error"' in html
    assert re.search(r'id="addr_house_no"[^>]*aria-invalid="true"', html)
    assert re.search(r'id="addr_zip"[^>]*aria-invalid="true"', html)
    assert not re.search(r'id="addr_obec"[^>]*aria-invalid', html)
    assert 'value="12345"' in html and 'value="Praha"' in html
    assert _rows(host["owner"]) == []
    czech = host["client"].post(
        "/apartments?lang=cs", data=_form(legal_entity_id=str(host["entities"][0]), addr_zip="12"),
        follow_redirects=False,
    )
    assert czech.status_code == 400
    assert "Postcode must be exactly 5 digits." not in czech.text


def test_complete_address_is_saved_as_typed_without_parsing():
    host = _host(1)
    response = host["client"].post(
        "/apartments",
        data=_form(legal_entity_id=str(host["entities"][0]), addr_street="Nádražní 12/3",
                   addr_zip="602 00", address_line="Other street 1, 11000 Praha"),
        follow_redirects=False,
    )
    assert response.status_code == 303
    (row,) = _rows(host["owner"])
    assert row["addr_street"] == "Nádražní 12/3"
    assert row["addr_zip"] == "60200"
    assert row["addr_obec"] == "Praha" and row["addr_house_no"] == "12"


def test_partial_address_is_refused_and_the_draft_kept():
    host = _host(1)
    response = host["client"].post(
        "/apartments",
        data=_form(legal_entity_id=str(host["entities"][0]), addr_street="Nádražní 12/3",
                   addr_zip="602 00", addr_obec="", addr_house_no=""),
        follow_redirects=False,
    )
    assert response.status_code == 400
    assert re.search(r'id="addr_obec"[^>]*aria-invalid="true"', response.text)
    assert re.search(r'id="addr_house_no"[^>]*aria-invalid="true"', response.text)
    assert 'value="Nádražní 12/3"' in response.text and 'value="602 00"' in response.text
    assert _rows(host["owner"]) == []


def test_foreign_operator_and_foreign_copy_are_refused():
    other = _host(1, "create-foreign")
    host = _host(1)
    response = host["client"].post(
        "/apartments", data=_form(legal_entity_id=str(other["entities"][0])), follow_redirects=False
    )
    assert response.status_code == 400
    assert "Synthetic Operator" in response.text  # only the host's own option
    assert _rows(host["owner"]) == []
    foreign = db.insert("apartment", {
        "internal_name": "Foreign Flat", "owner_user_id": other["owner"], "legal_entity_id": other["entities"][0],
        "permalink_token": f"foreign{secrets.token_hex(4)}", "permalink_pin": "123456", "active": 1,
        "created_at": db.utcnow(),
    })
    assert host["client"].get(f"/apartments/new?copy_from={foreign}").status_code == 404
    # A forged copy_from on POST copies nothing and names nothing.
    forged = host["client"].post(
        "/apartments", data=_form(internal_name="", copy_from=str(foreign)), follow_redirects=False
    )
    assert "Foreign Flat" not in forged.text


def test_copy_is_an_explicit_choice_and_survives_a_refusal():
    host = _host(1)
    source = db.insert("apartment", {
        "internal_name": "Copy Source", "owner_user_id": host["owner"], "legal_entity_id": host["entities"][0],
        "automation_mode": "scheduled", "submit_after_hours": 6, "default_purpose": "10",
        "permalink_window_days": 5, "stay_fee_rate_czk": 40, "stay_fee_cadence": "quarterly",
        "stay_fee_authority_name": "Synthetic Council", "permalink_token": f"copy{secrets.token_hex(4)}",
        "permalink_pin": "123456", "active": 1, "created_at": db.utcnow(),
    })
    plain = host["client"].get("/apartments/new").text
    assert 'name="copy_from"' in plain and 'type="hidden" name="automation_mode"' not in plain
    page = host["client"].get(f"/apartments/new?copy_from={source}").text
    assert "Copy Source" in page
    for name, value in (("automation_mode", "scheduled"), ("submit_after_hours", "6"),
                        ("stay_fee_rate_czk", "40"), ("copy_from", str(source))):
        assert f'<input type="hidden" name="{name}" value="{value}">' in page, name
    hidden = dict(re.findall(r'<input type="hidden" name="([^"]+)" value="([^"]*)">', page))
    refused = host["client"].post("/apartments", data={**hidden, "internal_name": ""}, follow_redirects=False)
    assert refused.status_code == 400
    assert '<input type="hidden" name="automation_mode" value="scheduled">' in refused.text
    created = host["client"].post(
        "/apartments", data={**hidden, "internal_name": "Copied Loft", "legal_entity_id": str(host["entities"][0]),
              "addr_obec": "Praha", "addr_house_no": "12", "addr_zip": "11000"},
        follow_redirects=False,
    )
    assert created.status_code == 303
    row = db.query_one("SELECT * FROM apartment WHERE internal_name = 'Copied Loft' AND owner_user_id = ?", (host["owner"],))
    assert (row["automation_mode"], row["submit_after_hours"], row["permalink_window_days"]) == ("scheduled", 6, 5)
    assert (row["stay_fee_rate_czk"], row["stay_fee_cadence"], row["stay_fee_authority_name"]) == (40, "quarterly", "Synthetic Council")


def test_existing_settings_stay_reachable_after_create():
    host = _host(1)
    host["client"].post("/apartments", data=_form(legal_entity_id=str(host["entities"][0])), follow_redirects=False)
    (row,) = _rows(host["owner"])
    page = host["client"].get(f"/apartments/{row['id']}").text
    for field in ("uby_idub", "uby_ws_password", "guest_message", "permalink_pin", "automation_mode",
                  "stay_fee_rate_czk", "notes", "addr_obec", "internal_name"):
        assert f'name="{field}"' in page, field
    ids = _ids(page)
    for field in SHARED_IDS:
        assert ids.count(field) == 1, field


def test_create_needs_login_and_admin_preview_creates_for_the_previewed_host():
    anonymous = TestClient(app)
    assert anonymous.get("/apartments/new", follow_redirects=False).status_code in (302, 303)
    assert anonymous.post("/apartments", data=_form(), follow_redirects=False).status_code in (302, 303)
    host = _host(1, "create-previewed")
    admin_name = f"create-admin-{secrets.token_hex(3)}"
    auth.create_account(f"{admin_name}@example.test", "Create Admin", role="admin", username=admin_name)
    admin = TestClient(app)
    assert login_as(admin, admin_name, url="/login?lang=en", follow_redirects=False).status_code == 303
    assert admin.post(f"/admin/users/{host['owner']}/impersonate", data={"reason": "support"},
                      follow_redirects=False).status_code == 303
    page = admin.get("/apartments/new").text
    assert f'<option value="{host["entities"][0]}" selected>' in page
    response = admin.post("/apartments", data=_form(legal_entity_id=str(host["entities"][0])), follow_redirects=False)
    assert response.status_code == 303
    assert len(_rows(host["owner"])) == 1


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
    if os.environ.get("UBYHOST_CAPTURE_0092") == "1":
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


_FIT_JS = """() => {
  const vw = document.documentElement.clientWidth;
  const bad = [];
  for (const el of document.querySelectorAll('.property-create input, .property-create select, .property-create .btn, .property-create h2, .property-create label')) {
    const r = el.getBoundingClientRect();
    if (!r.width || !r.height) continue;
    if (r.right > vw + 1 || r.left < -1) bad.push(el.id || el.className || el.tagName);
  }
  const main = document.querySelector('.property-create-main').getBoundingClientRect();
  const next = document.querySelector('.property-create-next').getBoundingClientRect();
  return {scroll: document.documentElement.scrollWidth, vw, bad,
          side: next.left >= main.right - 1, below: next.top >= main.bottom - 1,
          mainWidth: Math.round(main.width)};
}"""


def test_create_page_fits_and_follow_ups_move_below_when_narrow(base):
    host = _host(2, "create-browser")
    cookie = host["client"].cookies.get(auth.SESSION_COOKIE)
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        context = browser.new_context(viewport={"width": 1280, "height": 1000})
        context.add_cookies([{"name": auth.SESSION_COOKIE, "value": cookie, "url": base + "/"}])
        page = context.new_page()
        for width in (360, 390, 1280):
            page.set_viewport_size({"width": width, "height": 900})
            for lang in ("en", "cs"):
                page.goto(f"{base}/apartments/new?lang={lang}")
                fit = page.evaluate(_FIT_JS)
                assert fit["scroll"] <= fit["vw"] and not fit["bad"], (width, lang, fit)
                if width < 900:
                    assert fit["below"], (width, fit)
                assert page.locator("#internal_name").is_visible()
                assert page.locator("#addr_zip").is_visible()
                assert page.locator(".property-create-actions .btn.primary").is_visible()
                _shot(page, f"create-{width}-{lang}")
        for collapsed in (False, True):
            for width in (760, 1024, 1440, 1680, 1920, 2048):
                page.set_viewport_size({"width": width, "height": 900})
                page.goto(f"{base}/apartments/new?lang=cs")
                _sidebar(page, collapsed)
                page.wait_for_timeout(50)
                fit = page.evaluate(_FIT_JS)
                assert fit["scroll"] <= fit["vw"] and not fit["bad"], (width, collapsed, fit)
                assert fit["side"] or fit["below"], (width, collapsed, fit)
                if fit["side"]:
                    assert fit["mainWidth"] >= 420, (width, collapsed, fit)
        _sidebar(page, False)

        # The ? help is reachable by keyboard and tap; no title-only tooltip.
        page.set_viewport_size({"width": 1280, "height": 900})
        page.goto(f"{base}/apartments/new?lang=en")
        page.locator('[aria-controls="addr_zip-help"]').focus()
        assert page.locator("#addr_zip-help").is_visible()

        # Browser validation keeps the host on the page without a name/operator.
        page.locator("#city_en").fill("Brno")
        page.locator(".property-create-actions .btn.primary").click()
        assert page.url.endswith("/apartments/new?lang=en")
        assert db.query("SELECT id FROM apartment WHERE owner_user_id = ?", (host["owner"],)) == []

        # Server error state with a long name, then a successful create.
        page.evaluate("() => document.querySelector('#property-create-form').noValidate = true")
        page.locator("#internal_name").fill("Synthetic Riverside Apartment With An Unusually Long Name")
        page.locator("#addr_zip").fill("12")
        page.locator(".property-create-actions .btn.primary").click()
        page.wait_for_load_state()
        assert page.locator("#legal_entity_id[aria-invalid=true]").count() == 1
        assert page.locator("#addr_zip-error").is_visible()
        assert page.locator("#addr_zip").input_value() == "12"
        assert page.evaluate(_FIT_JS)["scroll"] <= 1280
        _shot(page, "create-error-1280-en")
        page.select_option("#legal_entity_id", str(host["entities"][1]))
        page.locator("#addr_zip").fill("11000")
        page.locator("#addr_obec").fill("Praha")
        page.locator("#addr_house_no").fill("12")
        page.locator(".property-create-actions .btn.primary").click()
        page.wait_for_load_state()
        assert "created=1" in page.url
        assert page.locator(".property-first-use").is_visible()
        _shot(page, "created-1280-en")
        page.set_viewport_size({"width": 390, "height": 900})
        page.reload()
        assert page.locator(".property-first-use .btn").count() == 3
        _shot(page, "created-390-en")
        browser.close()


def test_create_page_works_without_javascript(base):
    host = _host(1, "create-nojs")
    cookie = host["client"].cookies.get(auth.SESSION_COOKIE)
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        context = browser.new_context(viewport={"width": 390, "height": 900}, java_script_enabled=False)
        context.add_cookies([{"name": auth.SESSION_COOKIE, "value": cookie, "url": base + "/"}])
        page = context.new_page()
        page.goto(f"{base}/apartments/new?lang=cs")
        page.locator("#internal_name").fill("Synthetic No-JS Flat")
        page.locator("#addr_obec").fill("Praha")
        page.locator("#addr_house_no").fill("12")
        page.locator("#addr_zip").fill("11000")
        page.locator(".property-create-actions .btn.primary").click()
        page.wait_for_load_state()
        assert "created=1" in page.url
        row = db.query_one("SELECT * FROM apartment WHERE owner_user_id = ?", (host["owner"],))
        assert row["internal_name"] == "Synthetic No-JS Flat" and row["addr_obec"] == "Praha"
        browser.close()
