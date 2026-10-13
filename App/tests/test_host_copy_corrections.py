"""0087 host copy and address corrections: route and browser regressions."""
from __future__ import annotations

import json
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

USERNAME = "copy-corrections-host"
REPO_ROOT = Path(__file__).resolve().parents[2]
MEASURE_WIDTHS = (360, 390, 760, 1024, 1280, 1440, 1680, 2048)
SHOT_WIDTHS = (360, 390, 1280)

_OVERFLOW_JS = """(selector) => {
  const vw = window.innerWidth;
  const root = selector ? document.querySelector(selector) : document.documentElement;
  const offenders = [];
  const scope = selector ? root : document.body;
  for (const el of scope.querySelectorAll('input, textarea, select, button, .field')) {
    const r = el.getBoundingClientRect();
    if (!r.width || !r.height) continue;
    if (r.right > vw + 1 || r.left < -1) {
      offenders.push({id: el.id || '', tag: el.tagName, right: Math.round(r.right), vw});
    }
  }
  return {
    scrollWidth: document.documentElement.scrollWidth,
    vw,
    offenders: offenders.slice(0, 8),
  };
}"""


def _evidence_dir() -> Path | None:
    if os.environ.get("UBYHOST_CAPTURE_0087") != "1":
        return None
    target = REPO_ROOT / "docs" / "tasks" / "0087-evidence"
    target.mkdir(parents=True, exist_ok=True)
    return target


def _maybe_shot(page, name: str) -> None:
    folder = _evidence_dir()
    if folder:
        page.screenshot(path=str(folder / name), full_page=True)


def _cleanup():
    for row in db.query("SELECT id FROM user_account WHERE username = ?", (USERNAME,)):
        owner_id = row["id"]
        for apt in db.query("SELECT id FROM apartment WHERE owner_user_id = ?", (owner_id,)):
            apt_id = apt["id"]
            db.execute(
                "DELETE FROM guest WHERE reservation_id IN (SELECT id FROM reservation WHERE apartment_id = ?)",
                (apt_id,),
            )
            db.execute("DELETE FROM reservation WHERE apartment_id = ?", (apt_id,))
            db.execute("DELETE FROM stay_fee_filing WHERE apartment_id = ?", (apt_id,))
        db.execute("DELETE FROM audit WHERE owner_user_id = ?", (owner_id,))
        db.execute("DELETE FROM alert WHERE owner_user_id = ?", (owner_id,))
        db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (owner_id,))
        db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (owner_id,))
        db.execute("DELETE FROM user_account WHERE id = ?", (owner_id,))


@pytest.fixture
def host():
    db.init_db()
    _cleanup()
    owner_id = auth.create_account(f"{USERNAME}@example.test", "Copy Host", role="host", username=USERNAME)
    entity_id = db.insert(
        "legal_entity",
        {
            "name": "Copy Operator s.r.o.",
            "seat": "Praha",
            "ico": "12345678",
            "contact_email": "copy@example.test",
            "owner_user_id": owner_id,
            "created_at": db.utcnow(),
        },
    )
    client = TestClient(app)
    assert login_as(client, USERNAME, url="/login?lang=en", follow_redirects=False).status_code == 303
    try:
        yield {"client": client, "owner": owner_id, "entity": entity_id}
    finally:
        _cleanup()


def _apartment_payload(entity_id: int, **extra):
    data = {
        "internal_name": "Copy Flat",
        "legal_entity_id": str(entity_id),
        "addr_obec": "Praha",
        "addr_house_no": "10",
        "addr_zip": "11000",
        "addr_street": "Structured Street",
        "uby_idub": "123456789012",
        "uby_ws_user": "UBY-WSabcdef",
        "uby_ws_password": "secret",
        "active": "on",
        "automation_mode": "manual",
        "submit_after_hours": "24",
        "default_purpose": "10",
    }
    data.update(extra)
    return data


def test_property_forms_render_without_address_line(host):
    client = host["client"]
    for path in ("/apartments/new?lang=en", "/apartments/new?lang=cs"):
        page = client.get(path).text
        assert 'name="address_line"' not in page
        assert "property-address-police" not in page
    created = client.post("/apartments", data=_apartment_payload(host["entity"]), follow_redirects=False)
    assert created.status_code == 303
    apartment_id = db.query_one("SELECT id FROM apartment WHERE internal_name = ?", ("Copy Flat",))["id"]
    for lang in ("en", "cs"):
        page = client.get(f"/apartments/{apartment_id}?lang={lang}").text
        assert 'name="address_line"' not in page
        assert "police-derived" not in page


def test_legacy_address_line_submission_is_ignored(host):
    client = host["client"]
    created = client.post(
        "/apartments",
        data=_apartment_payload(
            host["entity"],
            address_line="Fake 999/1, 99999 Elsewhere",
            addr_street="Kept Street",
        ),
        follow_redirects=False,
    )
    assert created.status_code == 303
    row = db.query_one("SELECT addr_street, addr_obec FROM apartment WHERE internal_name = ?", ("Copy Flat",))
    assert row["addr_street"] == "Kept Street"
    assert row["addr_obec"] == "Praha"


def test_address_only_save_preserves_credentials_and_automation(host):
    client = host["client"]
    client.post("/setup/welcome", follow_redirects=False)
    client.post(
        "/setup/name",
        data={"internal_name": "Wizard Preserve", "active": "1"},
        follow_redirects=False,
    )
    apartment_id = db.query_one(
        "SELECT id FROM apartment WHERE internal_name = ?", ("Wizard Preserve",)
    )["id"]
    db.update(
        "apartment",
        apartment_id,
        {
            "uby_idub": "123456789012",
            "uby_ws_user": "UBY-WSabcdef",
            "uby_ws_password_enc": db.encrypt_secret("secret-pass"),
            "guest_message": "Custom welcome",
            "automation_mode": "scheduled",
            "submit_after_hours": 12,
            "addr_street": "Old",
            "addr_house_no": "1",
            "addr_zip": "11000",
            "addr_obec": "Praha",
        },
    )
    before = db.query_one("SELECT * FROM apartment WHERE id = ?", (apartment_id,))
    response = client.post(
        "/setup/address",
        data={
            "internal_name": before["internal_name"],
            "active": "1",
            "addr_street": "New lane",
            "addr_house_no": "22",
            "addr_zip": "12000",
            "addr_obec": "Praha",
            "return_to": "/setup/bookings",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    after = db.query_one("SELECT * FROM apartment WHERE id = ?", (apartment_id,))
    assert after["addr_street"] == "New lane"
    assert after["uby_ws_user"] == before["uby_ws_user"]
    assert after["guest_message"] == before["guest_message"]
    assert after["automation_mode"] == before["automation_mode"]


def test_invalid_address_keeps_draft_on_setup_error(host):
    client = host["client"]
    client.post("/setup/welcome", follow_redirects=False)
    client.post("/setup/name", data={"internal_name": "Draft flat", "active": "1"}, follow_redirects=False)
    apartment_id = db.query_one(
        "SELECT id FROM apartment WHERE internal_name = ?", ("Draft flat",)
    )["id"]
    db.update(
        "apartment",
        apartment_id,
        {
            "addr_street": "Keep me",
            "addr_house_no": "5",
            "addr_zip": "12000",
            "addr_obec": "Praha",
        },
    )
    response = client.post(
        "/setup/address",
        data={
            "internal_name": "Draft flat",
            "active": "1",
            "addr_street": "Broken",
            "addr_house_no": "",
            "addr_zip": "",
            "addr_obec": "Praha",
            "return_to": "/setup/bookings",
        },
        follow_redirects=False,
    )
    assert response.status_code == 400
    assert 'value="Broken"' in response.text
    assert 'name="address_line"' not in response.text


def test_guest_message_default_is_editable_and_custom_survives(host):
    client = host["client"]
    default_en = host_i18n.STRINGS["en"]["apartment.form.guest_message.default"]
    page = client.get("/apartments/new?lang=en").text
    assert default_en in page
    custom = "Keep this exact custom greeting."
    created = client.post(
        "/apartments",
        data=_apartment_payload(host["entity"], guest_message=custom),
        follow_redirects=False,
    )
    assert created.status_code == 303
    apartment_id = db.query_one("SELECT id FROM apartment WHERE internal_name = ?", ("Copy Flat",))["id"]
    row = db.query_one("SELECT guest_message FROM apartment WHERE id = ?", (apartment_id,))
    assert row["guest_message"] == custom
    edit = client.get(f"/apartments/{apartment_id}?lang=en").text
    assert custom in edit


def test_housebook_help_link_without_legal_accordion(host):
    client = host["client"]
    for lang in ("en", "cs"):
        page = client.get(f"/housebook?lang={lang}").text
        assert "housebook-legal-details" not in page
        assert 'href="/guide#housebook"' in page
        assert host_i18n.STRINGS[lang]["housebook.legal_title"] not in page


def test_guide_housebook_anchor_contains_legal_copy(host):
    client = host["client"]
    for lang in ("en", "cs"):
        page = client.get(f"/guide?lang={lang}").text
        assert 'id="housebook"' in page
        assert host_i18n.STRINGS[lang]["housebook.legal_paper"] in page
        assert host_i18n.STRINGS[lang]["housebook.legal_inspection"] in page


def test_password_field_has_one_sentence(host):
    client = host["client"]
    stored = "keep-me-secret"
    created = client.post(
        "/apartments",
        data=_apartment_payload(host["entity"], uby_ws_password=stored),
        follow_redirects=False,
    )
    assert created.status_code == 303
    apartment_id = db.query_one("SELECT id FROM apartment WHERE internal_name = ?", ("Copy Flat",))["id"]
    before_enc = db.query_one("SELECT uby_ws_password_enc FROM apartment WHERE id = ?", (apartment_id,))[
        "uby_ws_password_enc"
    ]
    edit = client.get(f"/apartments/{apartment_id}?lang=en").text
    hint = host_i18n.STRINGS["en"]["apartment.form.ubyport.password_edit_hint"]
    assert edit.count(hint) == 1
    password_input = re.search(
        r'<input[^>]*id="uby_ws_password"[^>]*>',
        edit,
    )
    assert password_input
    tag = password_input.group(0)
    assert 'placeholder="••••••••"' in tag
    assert 'value="' not in tag
    assert 'aria-describedby="uby_ws_password-hint"' in tag
    assert stored not in edit
    updated = client.post(
        f"/apartments/{apartment_id}",
        data=_apartment_payload(host["entity"], uby_ws_password="", internal_name="Copy Flat"),
        follow_redirects=False,
    )
    assert updated.status_code == 303
    after_enc = db.query_one("SELECT uby_ws_password_enc FROM apartment WHERE id = ?", (apartment_id,))[
        "uby_ws_password_enc"
    ]
    assert after_enc == before_enc

    new_page = client.get("/apartments/new?lang=en").text
    new_input = re.search(r'<input[^>]*id="uby_ws_password"[^>]*>', new_page)
    assert new_input
    assert "placeholder=" not in new_input.group(0)
    new_hint = host_i18n.STRINGS["en"]["apartment.form.ubyport.password_new_hint"]
    assert new_page.count(new_hint) == 1


def test_edit_shows_stored_guest_message_exactly(host):
    client = host["client"]
    apartment_id = db.insert(
        "apartment",
        {
            "internal_name": "Blank message flat",
            "owner_user_id": host["owner"],
            "legal_entity_id": host["entity"],
            "addr_obec": "Praha",
            "guest_message": "",
            "permalink_token": f"bm{secrets.token_hex(4)}",
            "permalink_pin": "123456",
            "active": 1,
            "created_at": db.utcnow(),
        },
    )
    default_en = host_i18n.STRINGS["en"]["apartment.form.guest_message.default"]
    edit = client.get(f"/apartments/{apartment_id}?lang=en").text
    match = re.search(
        r'<textarea id="guest_message"[^>]*>(.*?)</textarea>',
        edit,
        re.DOTALL,
    )
    assert match is not None
    assert match.group(1) == ""
    assert default_en not in match.group(0)


def test_stay_fee_detail_has_no_external_databox_button(host):
    client = host["client"]
    apartment_id = db.insert(
        "apartment",
        {
            "internal_name": "Fee flat",
            "owner_user_id": host["owner"],
            "legal_entity_id": host["entity"],
            "addr_obec": "Praha",
            "stay_fee_rate_czk": 50,
            "permalink_token": f"fee{secrets.token_hex(4)}",
            "permalink_pin": "123456",
            "active": 1,
            "created_at": db.utcnow(),
        },
    )
    page = client.get(f"/stay-fees/{apartment_id}?month=2026-08&lang=en").text
    assert "mojedatovaschranka.cz" not in page
    pdf = client.get(f"/stay-fees/{apartment_id}/pdf?month=2026-08")
    assert pdf.status_code == 200


def _free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _open_property_reporting_sections(page) -> None:
    page.evaluate(
        """() => {
          const u = document.querySelector('#ubyport');
          const a = document.querySelector('#address');
          if (u) u.open = true;
          if (a) a.open = true;
        }"""
    )


def _set_sidebar(page, collapsed: bool) -> None:
    page.evaluate(
        """(wantCollapsed) => {
          const isCollapsed = document.body.classList.contains('sidebar-collapsed');
          if (wantCollapsed === isCollapsed) return;
          const btn = document.querySelector('button[data-sidebar-collapse]');
          if (btn && btn.offsetParent !== null) {
            btn.click();
            return;
          }
          document.body.classList.toggle('sidebar-collapsed', wantCollapsed);
        }""",
        collapsed,
    )
    page.wait_for_function(
        f"() => document.body.classList.contains('sidebar-collapsed') === {str(collapsed).lower()}"
    )


def _assert_lane_fits(page, section: str) -> None:
    result = page.evaluate(_OVERFLOW_JS, section)
    assert result["scrollWidth"] <= result["vw"] + 1, result
    assert not result["offenders"], result


@pytest.fixture
def browser_base(host):
    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 15
    while not server.started and time.time() < deadline:
        time.sleep(0.05)
    if not server.started:
        pytest.fail("the test server did not start")
    cookie = host["client"].cookies.get(auth.SESSION_COOKIE)
    yield {"url": f"http://127.0.0.1:{port}", "cookie": cookie, "host": host}
    server.should_exit = True
    thread.join(timeout=5)


@pytest.mark.skipif(not REQUIRE_BROWSER, reason="browser checks required when UBYHOST_REQUIRE_BROWSER=1")
def test_copy_correction_pages_browser_evidence(browser_base):
    base = browser_base["url"]
    cookie = browser_base["cookie"]
    host = browser_base["host"]
    client = host["client"]
    client.post("/setup/welcome", follow_redirects=False)
    client.post("/setup/name", data={"internal_name": "Wizard error flat", "active": "1"}, follow_redirects=False)
    wizard_id = db.query_one(
        "SELECT id FROM apartment WHERE internal_name = ?", ("Wizard error flat",)
    )["id"]
    db.update(
        "apartment",
        wizard_id,
        {
            "addr_street": "Keep me",
            "addr_house_no": "5",
            "addr_zip": "12000",
            "addr_obec": "Praha",
        },
    )
    apartment_id = db.insert(
        "apartment",
        {
            "internal_name": "Evidence Flat",
            "owner_user_id": host["owner"],
            "legal_entity_id": host["entity"],
            "addr_obec": "Praha",
            "addr_house_no": "1",
            "addr_zip": "11000",
            "addr_street": "Evidence Street",
            "uby_idub": "123456789012",
            "uby_mark": "EVID01",
            "uby_name": "Evidence facility",
            "uby_contact": "evidence@example.test",
            "guest_message": "Evidence custom message",
            "stay_fee_rate_czk": 50,
            "stay_fee_authority_name": "Synthetic council",
            "permalink_token": f"ev{secrets.token_hex(4)}",
            "permalink_pin": "123456",
            "active": 1,
            "created_at": db.utcnow(),
        },
    )
    measurements: list[dict] = []

    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        for lang in ("en", "cs"):
            context = browser.new_context(viewport={"width": 1280, "height": 1000}, has_touch=True)
            context.add_cookies([{"name": auth.SESSION_COOKIE, "value": cookie, "url": base + "/"}])
            page = context.new_page()

            for width in SHOT_WIDTHS:
                page.set_viewport_size({"width": width, "height": 900})
                page.goto(f"{base}/apartments/new?lang={lang}")
                assert page.locator('input[name="address_line"]').count() == 0
                _assert_lane_fits(page, "#address")
                _maybe_shot(page, f"property-new-{width}-{lang}.png")

                page.goto(f"{base}/apartments/{apartment_id}?lang={lang}")
                _open_property_reporting_sections(page)
                assert page.locator('input[name="address_line"]').count() == 0
                assert page.locator(".property-address-police").count() == 0
                assert page.locator(".police-derived").count() == 0
                _assert_lane_fits(page, "#address")
                _assert_lane_fits(page, "#ubyport")
                _maybe_shot(page, f"property-edit-{width}-{lang}.png")

                page.goto(f"{base}/housebook?lang={lang}")
                assert page.locator("#housebook-legal-details").count() == 0
                _assert_lane_fits(page, "main.wrap")
                _maybe_shot(page, f"housebook-{width}-{lang}.png")

                page.goto(f"{base}/stay-fees/{apartment_id}?month=2026-08&lang={lang}")
                assert page.locator('a[href*="mojedatovaschranka"]').count() == 0
                _assert_lane_fits(page, "main.wrap")
                _maybe_shot(page, f"stay-fee-{width}-{lang}.png")

            page.goto(f"{base}/setup/address?lang={lang}")
            page.evaluate("document.querySelector('.wizard-form')?.setAttribute('novalidate', 'novalidate')")
            page.locator("#addr_street").fill("Broken")
            page.locator("#addr_house_no").fill("")
            page.locator("#addr_zip").fill("")
            page.locator("button.wizard-continue").click()
            page.wait_for_selector(".wizard-error", state="visible")
            assert page.locator(".wizard-error").count() == 1
            assert page.locator("#addr_street").input_value() == "Broken"
            _assert_lane_fits(page, ".wizard-form")
            _maybe_shot(page, f"setup-address-error-{lang}.png")

            for width in MEASURE_WIDTHS:
                page.set_viewport_size({"width": width, "height": 900})
                page.goto(f"{base}/apartments/{apartment_id}?lang={lang}#address")
                _open_property_reporting_sections(page)
                for collapsed in (False, True):
                    _set_sidebar(page, collapsed)
                    fit = page.evaluate(_OVERFLOW_JS, "#address")
                    main = page.evaluate(
                        """() => {
                          const m = document.querySelector('main.wrap.with-sidebar');
                          if (!m) return null;
                          const r = m.getBoundingClientRect();
                          return {left: r.left, right: r.right, width: r.width, clientWidth: m.clientWidth};
                        }"""
                    )
                    measurements.append(
                        {
                            "lang": lang,
                            "width": width,
                            "sidebar": "collapsed" if collapsed else "expanded",
                            "address": fit,
                            "main": main,
                        }
                    )
                    assert fit["scrollWidth"] <= fit["vw"] + 1, fit
                    assert not fit["offenders"], fit

            context.close()
        browser.close()

    folder = _evidence_dir()
    if folder:
        (folder / "measurements.json").write_text(json.dumps(measurements, indent=2), encoding="utf-8")
