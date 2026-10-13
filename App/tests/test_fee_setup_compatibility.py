"""0077: one fee editor, the legacy setup URL as an adapter, one normaliser."""
from __future__ import annotations

import os
import re
import secrets
import socket
import threading
import time
from pathlib import Path
from urllib.parse import quote, unquote

import pytest

REQUIRE_BROWSER = os.environ.get("UBYHOST_REQUIRE_BROWSER") == "1"
if REQUIRE_BROWSER:
    import playwright.sync_api as sync_api
else:
    sync_api = pytest.importorskip("playwright.sync_api")

import uvicorn
from fastapi.testclient import TestClient

from app import auth, db
from app.main import app
from app.routes import stay_fees as stay_fee_routes
from tests.browser_support import chromium_launch_kwargs
from tests.conftest import login_as

USERNAME = "fee-setup-compat-host"
OTHER = "fee-setup-compat-other"
FEE_COLUMNS = (
    "stay_fee_rate_czk",
    "stay_fee_cadence",
    "stay_fee_vs",
    "stay_fee_council_account",
    "stay_fee_council_iban",
    "stay_fee_authority_name",
    "stay_fee_authority_address",
    "stay_fee_authority_contact",
    "stay_fee_authority_databox",
    "stay_fee_payee",
    "stay_fee_instruction",
)
# Everything a fee-only save must leave alone.
NON_FEE = {
    "internal_name": "Compat Flat",
    "notes": "private note",
    "guest_message": "Welcome!",
    "uby_ws_user": "ws-user",
    "uby_idub": "123456789012",
    "uby_name": "Compat",
    "permalink_pin": "123456",
    "permalink_window_days": 3,
    "automation_mode": "manual",
    "default_purpose": "10",
    "addr_obec": "Praha",
    "addr_house_no": "12",
    "addr_zip": "11000",
}


def _cleanup() -> None:
    for name in (USERNAME, OTHER):
        user = db.query_one("SELECT id FROM user_account WHERE username = ?", (name,))
        if not user:
            continue
        owner_id = user["id"]
        db.execute("DELETE FROM audit WHERE owner_user_id = ?", (owner_id,))
        db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (owner_id,))
        db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (owner_id,))
        db.execute("DELETE FROM user_account WHERE id = ?", (owner_id,))


def _owner(name: str) -> int:
    return db.query_one("SELECT id FROM user_account WHERE username = ?", (name,))["id"]


def _property(owner_id: int, entity_id, **fee) -> int:
    return db.insert("apartment", {
        **NON_FEE,
        "owner_user_id": owner_id,
        "legal_entity_id": entity_id,
        "permalink_token": "compat-" + secrets.token_hex(8),
        "active": 1,
        "created_at": db.utcnow(),
        **fee,
    })


@pytest.fixture
def host():
    db.init_db()
    _cleanup()
    auth.create_account(f"{USERNAME}@example.test", "Fee compat host", username=USERNAME)
    auth.create_account(f"{OTHER}@example.test", "Other host", username=OTHER)
    client = TestClient(app)
    login = login_as(client, USERNAME, url="/login?lang=en", follow_redirects=False)
    assert login.status_code == 303, login.text
    owner_id = _owner(USERNAME)
    entity_id = db.insert("legal_entity", {
        "name": "Compat Operator", "owner_user_id": owner_id, "created_at": db.utcnow(),
    })
    try:
        yield client, owner_id, entity_id
    finally:
        _cleanup()


def _row(apartment_id: int) -> dict:
    return dict(db.query_one("SELECT * FROM apartment WHERE id = ?", (apartment_id,)))


def _fee(row: dict) -> tuple:
    return tuple(row[key] for key in FEE_COLUMNS)


def _fee_form(**overrides) -> dict:
    data = {
        "_stay_fee_account_existing": "",
        "stay_fee_rate_czk": "25",
        "stay_fee_cadence": "monthly",
        "stay_fee_vs": "12 34",
        "account_prefix": "19",
        "account_number": "2000781379",
        "account_bank": "0800",
        "stay_fee_authority_name": "  Council office ",
        "stay_fee_authority_address": "Town Hall",
        "stay_fee_authority_contact": "office@example.test",
        "stay_fee_authority_databox": "ABC1234",
        "stay_fee_payee": "",
        "stay_fee_instruction": "",
    }
    data.update(overrides)
    return data


def _canonical(apartment_id: int, back: str) -> str:
    return (
        f"/apartments/{apartment_id}?view=settings&section=reporting"
        f"&return_to={quote(back, safe='')}#stay-fee-settings"
    )


# --- legacy GET adapter ---------------------------------------------------


def test_legacy_setup_url_lands_on_the_one_fee_editor_with_the_way_back(host):
    client, owner_id, entity_id = host
    apartment_id = _property(owner_id, entity_id)

    plain = client.get(f"/stay-fees/{apartment_id}/setup", follow_redirects=False)
    assert plain.status_code == 303
    location = plain.headers["location"]
    assert location.startswith(f"/apartments/{apartment_id}?view=settings&section=reporting&return_to=")
    assert location.endswith("#stay-fee-settings")
    assert re.search(r"return_to=%2Fstay-fees%2F\d+%3Fmonth%3D\d{4}-\d{2}#", location)

    month = client.get(f"/stay-fees/{apartment_id}/setup?month=2026-07", follow_redirects=False)
    assert month.headers["location"] == _canonical(apartment_id, f"/stay-fees/{apartment_id}?month=2026-07")

    listed = client.get(
        f"/stay-fees/{apartment_id}/setup?return_to="
        + quote("/stay-fees?month=2026-06&status=not_setup", safe=""),
        follow_redirects=False,
    )
    assert listed.headers["location"] == _canonical(apartment_id, "/stay-fees?month=2026-06&status=not_setup")

    page = client.get(f"/stay-fees/{apartment_id}/setup?month=2026-07&lang=en")
    assert page.status_code == 200
    assert 'id="stay-fee-settings"' in page.text
    assert f'name="fee_return_to" value="/stay-fees/{apartment_id}?month=2026-07"' in page.text
    assert f'href="/stay-fees/{apartment_id}?month=2026-07"' in page.text
    assert "Back to stay fees" in page.text


@pytest.mark.parametrize("unsafe", [
    "//evil.example/stay-fees", "https://evil.example/stay-fees", "/apartments/1", "/stay-fees/999999",
])
def test_unsafe_or_foreign_return_is_dropped(host, unsafe):
    client, owner_id, entity_id = host
    apartment_id = _property(owner_id, entity_id)

    response = client.get(
        f"/stay-fees/{apartment_id}/setup?return_to={quote(unsafe, safe='')}", follow_redirects=False
    )
    back = unquote(response.headers["location"].split("return_to=", 1)[1].split("#", 1)[0])
    assert back.startswith(f"/stay-fees/{apartment_id}?month=")

    page = client.get(f"/apartments/{apartment_id}?view=settings&return_to={quote(unsafe, safe='')}")
    assert 'name="fee_return_to"' not in page.text


def test_legacy_setup_keeps_its_guards(host):
    client, owner_id, entity_id = host
    archived = _property(owner_id, entity_id, archived_at=db.utcnow(), active=0)
    foreign = _property(_owner(OTHER), None)
    for apartment_id in (archived, foreign, 999999):
        response = client.get(f"/stay-fees/{apartment_id}/setup", follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"].startswith("/stay-fees?")
        assert "err=" in response.headers["location"]
    posted = client.post(f"/stay-fees/{foreign}/setup", data=_fee_form(), follow_redirects=False)
    assert posted.status_code == 303 and "err=" in posted.headers["location"]
    assert _row(foreign)["stay_fee_rate_czk"] in (None, 0)


# --- one normaliser, two entry points ------------------------------------


@pytest.mark.parametrize("form", [
    _fee_form(),
    _fee_form(stay_fee_rate_czk="99", stay_fee_cadence="weekly", stay_fee_vs="abc12345678901"),
    _fee_form(stay_fee_rate_czk="0", account_prefix="", account_number="", account_bank=""),
    _fee_form(stay_fee_authority_name="", stay_fee_payee="  Obec  ", stay_fee_instruction="x" * 600),
])
def test_property_save_and_legacy_post_store_identical_fee_values(host, form):
    client, owner_id, entity_id = host
    via_property = _property(owner_id, entity_id, stay_fee_rate_czk=10, stay_fee_vs="1")
    via_legacy = _property(owner_id, entity_id, stay_fee_rate_czk=10, stay_fee_vs="1")
    property_form = {
        **{key: str(value) for key, value in NON_FEE.items() if key != "permalink_pin"},
        "legal_entity_id": str(entity_id),
        **form,
    }

    first = client.post(f"/apartments/{via_property}", data=property_form, follow_redirects=False)
    second = client.post(f"/stay-fees/{via_legacy}/setup", data=form, follow_redirects=False)

    assert first.status_code == second.status_code == 303
    assert _fee(_row(via_property)) == _fee(_row(via_legacy))
    expected = stay_fee_routes._fee_values(form)
    assert {key: _row(via_legacy)[key] for key in expected} == expected


def test_iban_only_account_survives_an_unrelated_fee_save_on_both_paths(host):
    client, owner_id, entity_id = host
    iban = "CZ6508000000192000145399"
    stored = {"stay_fee_rate_czk": 20, "stay_fee_council_account": iban, "stay_fee_council_iban": iban}
    via_property = _property(owner_id, entity_id, **stored)
    via_legacy = _property(owner_id, entity_id, **stored)
    form = _fee_form(_stay_fee_account_existing=iban, account_prefix="", account_number="", account_bank="")

    client.post(
        f"/apartments/{via_property}",
        data={**{k: str(v) for k, v in NON_FEE.items() if k != "permalink_pin"},
              "legal_entity_id": str(entity_id), **form},
        follow_redirects=False,
    )
    client.post(f"/stay-fees/{via_legacy}/setup", data=form, follow_redirects=False)

    for apartment_id in (via_property, via_legacy):
        row = _row(apartment_id)
        assert (row["stay_fee_council_account"], row["stay_fee_council_iban"]) == (iban, iban)
        assert row["stay_fee_authority_name"] == "Council office"


def test_blank_account_clears_on_both_paths(host):
    client, owner_id, entity_id = host
    stored = {
        "stay_fee_rate_czk": 20,
        "stay_fee_council_account": "19-2000781379/0800",
        "stay_fee_council_iban": "CZ3008000000192000781379",
    }
    apartment_id = _property(owner_id, entity_id, **stored)
    form = _fee_form(
        _stay_fee_account_existing="19-2000781379/0800",
        account_prefix="", account_number="", account_bank="",
    )
    client.post(f"/stay-fees/{apartment_id}/setup", data=form, follow_redirects=False)
    row = _row(apartment_id)
    assert row["stay_fee_council_account"] is None and row["stay_fee_council_iban"] is None


def test_legacy_post_is_fee_only_and_leaves_every_other_field(host):
    client, owner_id, entity_id = host
    apartment_id = _property(owner_id, entity_id)
    before = _row(apartment_id)

    response = client.post(f"/stay-fees/{apartment_id}/setup", data=_fee_form(), follow_redirects=False)

    assert response.status_code == 303
    after = _row(apartment_id)
    for key, value in before.items():
        if key not in FEE_COLUMNS:
            assert after[key] == value, key
    assert after["stay_fee_rate_czk"] == 25
    assert after["stay_fee_vs"] == "1234"
    audit = db.query("SELECT action FROM audit WHERE owner_user_id = ? ORDER BY id", (owner_id,))
    assert [row["action"] for row in audit][-1:] == ["stay_fee_setup"]


# --- the way back after save and after a refusal --------------------------


def test_save_returns_to_the_exact_report_period(host):
    client, owner_id, entity_id = host
    apartment_id = _property(owner_id, entity_id)
    back = f"/stay-fees/{apartment_id}?month=2026-07"

    legacy = client.post(
        f"/stay-fees/{apartment_id}/setup",
        data=_fee_form(fee_return_to=back),
        follow_redirects=False,
    )
    assert legacy.headers["location"].startswith(back + "&msg=")

    full = client.post(
        f"/apartments/{apartment_id}",
        data={**{k: str(v) for k, v in NON_FEE.items() if k != "permalink_pin"},
              "legal_entity_id": str(entity_id), **_fee_form(), "fee_return_to": back,
              "return_to": f"/apartments/{apartment_id}?view=settings&section=reporting"},
        follow_redirects=False,
    )
    assert full.headers["location"].startswith(back + "&msg=")
    assert "&msg=" in full.headers["location"]

    listed = client.post(
        f"/stay-fees/{apartment_id}/setup",
        data=_fee_form(fee_return_to="/stay-fees?month=2026-06&status=ready"),
        follow_redirects=False,
    )
    assert listed.headers["location"].startswith("/stay-fees?month=2026-06&status=ready&msg=")


def test_rate_zero_returns_to_the_list_of_the_same_month(host):
    client, owner_id, entity_id = host
    apartment_id = _property(owner_id, entity_id, stay_fee_rate_czk=20)
    response = client.post(
        f"/stay-fees/{apartment_id}/setup",
        data=_fee_form(stay_fee_rate_czk="0", fee_return_to=f"/stay-fees/{apartment_id}?month=2026-07"),
        follow_redirects=False,
    )
    assert response.headers["location"].startswith("/stay-fees?month=2026-07&msg=")
    assert _row(apartment_id)["stay_fee_rate_czk"] == 0


def test_legacy_post_without_return_keeps_its_old_landing(host):
    client, owner_id, entity_id = host
    apartment_id = _property(owner_id, entity_id)
    on = client.post(f"/stay-fees/{apartment_id}/setup", data=_fee_form(), follow_redirects=False)
    assert re.match(rf"/stay-fees/{apartment_id}\?month=\d{{4}}-\d{{2}}&msg=", on.headers["location"])
    off = client.post(
        f"/stay-fees/{apartment_id}/setup", data=_fee_form(stay_fee_rate_czk="0"), follow_redirects=False
    )
    assert off.headers["location"].startswith("/stay-fees?msg=")


@pytest.mark.parametrize("path", ["legacy", "property"])
def test_invalid_account_saves_nothing_and_keeps_what_was_typed(host, path):
    client, owner_id, entity_id = host
    apartment_id = _property(owner_id, entity_id, stay_fee_rate_czk=20, stay_fee_vs="1")
    before = _row(apartment_id)
    back = f"/stay-fees/{apartment_id}?month=2026-07"
    form = _fee_form(account_number="1234567890", stay_fee_vs="777", fee_return_to=back)
    if path == "legacy":
        response = client.post(f"/stay-fees/{apartment_id}/setup?lang=en", data=form)
    else:
        response = client.post(
            f"/apartments/{apartment_id}?lang=en",
            data={**{k: str(v) for k, v in NON_FEE.items() if k != "permalink_pin"},
                  "internal_name": "Typed name", "legal_entity_id": str(entity_id), **form},
        )

    assert response.status_code == 400
    assert _row(apartment_id) == before
    text = response.text
    assert 'id="stay-fee-account-error"' in text
    assert "Enter a valid Czech bank account or IBAN." in text
    assert 'value="777"' in text and 'value="1234567890"' in text
    assert 'value="Council office"' in text
    assert f'name="fee_return_to" value="{back}"' in text
    assert re.search(r'data-settings-group="reporting"[^>]*>|is-active" data-settings-group="reporting"', text)
    assert text.count('action="/apartments/') >= 1
    if path == "property":
        assert 'value="Typed name"' in text


# --- markup: one editor, nothing folded -----------------------------------


def test_fee_editor_is_the_only_one_and_shows_the_council_block(host):
    client, owner_id, entity_id = host
    apartment_id = _property(owner_id, entity_id, stay_fee_rate_czk=20)
    page = client.get(f"/apartments/{apartment_id}?view=settings&section=reporting&lang=en").text
    section = page.split('id="stay-fee-settings"', 1)[1].split("</section>", 1)[0]
    assert "<details" not in section and "<summary" not in section
    assert 'id="stay-fee-council"' in section
    assert section.count('name="stay_fee_rate_czk"') == 1
    assert page.count('name="stay_fee_authority_name"') == 1
    assert 'aria-describedby="stay_fee_authority_databox-help"' in section
    assert 'id="stay_fee_authority_databox-help"' in section
    for name in ("account_prefix", "account_number", "account_bank", "_stay_fee_account_existing"):
        assert page.count(f'name="{name}"') == 1


def test_report_fix_links_open_the_fee_editor_and_payer_editor(host):
    client, owner_id, entity_id = host
    with_entity = _property(owner_id, entity_id, stay_fee_rate_czk=20)
    without_entity = _property(owner_id, None, stay_fee_rate_czk=20)

    page = client.get(f"/stay-fees/{with_entity}?month=2026-07&lang=en").text
    assert f'href="{_canonical(with_entity, f"/stay-fees/{with_entity}?month=2026-07")}"'.replace("&", "&amp;") in page

    bare = client.get(f"/stay-fees/{without_entity}?month=2026-07&lang=en").text
    assert (
        f'href="/apartments/{without_entity}?view=settings&amp;section=property&amp;return_to='
        f'%2Fstay-fees%2F{without_entity}%3Fmonth%3D2026-07#settings-property"'
    ) in bare
    db.update("legal_entity", entity_id, {"name": ""})
    named = client.get(f"/stay-fees/{with_entity}?month=2026-07&lang=en").text
    assert f'href="/entities?edit={entity_id}"' in named


# --- browser: the editor fits, is visible and comes back to the report ----

EVIDENCE = Path(__file__).resolve().parents[2] / "docs" / "tasks" / "0077-evidence"


@pytest.fixture
def live(host):
    client, owner_id, entity_id = host
    unset = _property(owner_id, entity_id, internal_name="Synthetic Flat with a long name to wrap")
    _property(
        owner_id, entity_id, internal_name="Synthetic Configured Flat",
        stay_fee_rate_czk=50, stay_fee_vs="123456", stay_fee_authority_name="Synthetic Town Office",
        stay_fee_council_account="19-2000781379/0800", stay_fee_council_iban="CZ3008000000192000781379",
    )
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
        pytest.fail("the fee setup test server did not start")
    try:
        yield client.cookies.get(auth.SESSION_COOKIE), f"http://127.0.0.1:{port}", unset
    finally:
        server.should_exit = True
        thread.join(timeout=5)


def _save(page):
    page.locator('#property-settings-form [data-property-save] button[type="submit"], '
                 '#property-settings-form button.btn.primary[type="submit"]').first.click()
    page.wait_for_load_state("networkidle")


def test_set_up_link_opens_visible_editor_and_save_returns_to_the_list(live):
    cookie, base, unset = live
    capture = os.environ.get("UBYHOST_CAPTURE_0077") == "1"
    if capture:
        EVIDENCE.mkdir(parents=True, exist_ok=True)
    month = "2026-08"
    with sync_api.sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(**chromium_launch_kwargs())
        except Exception:
            if REQUIRE_BROWSER:
                raise
            pytest.skip("Chromium is required for the fee editor browser check")
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        context.add_cookies([{"name": auth.SESSION_COOKIE, "value": cookie, "url": base + "/"}])
        page = context.new_page()
        for locale in ("en", "cs"):
            for width in (360, 390, 1280):
                page.set_viewport_size({"width": width, "height": 900})
                page.goto(f"{base}/stay-fees?month={month}&lang={locale}")
                page.wait_for_load_state("networkidle")
                page.locator(f'a.btn[href^="/apartments/{unset}?view=settings"]').click()
                page.wait_for_load_state("networkidle")
                assert "section=reporting" in page.url and page.url.endswith("#stay-fee-settings")
                assert page.locator("html").get_attribute("lang") == locale
                section = page.locator("#stay-fee-settings")
                assert section.is_visible()
                # The council block is part of the editor, not a fold (plan section 4 rule 2).
                for field in ("stay_fee_rate_czk", "stay_fee_vs", "account_number",
                              "stay_fee_authority_name", "stay_fee_authority_databox", "stay_fee_instruction"):
                    assert page.locator(f"#{field}").is_visible(), (field, width, locale)
                assert page.locator("#stay-fee-settings details").count() == 0
                back = page.locator(".fee-return-note a")
                assert back.is_visible() and back.get_attribute("href") == f"/stay-fees?month={month}"
                assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"), (width, locale)
                for box in (section.bounding_box(), back.bounding_box()):
                    assert box and box["x"] >= -1 and box["x"] + box["width"] <= width + 1, (width, locale, box)
                help_button = page.locator('[aria-controls="stay_fee_authority_databox-help"]')
                help_button.focus()
                assert page.locator("#stay_fee_authority_databox-help").is_visible()
                help_button.blur()
                if capture:
                    page.evaluate("document.getElementById('stay-fee-settings').scrollIntoView({block: 'start'}); window.scrollBy(0, -88)")
                    page.screenshot(path=str(EVIDENCE / f"fee-editor-{locale}-{width}.png"))
                    page.evaluate("document.getElementById('stay-fee-council').scrollIntoView({block: 'start'}); window.scrollBy(0, -88)")
                    page.screenshot(path=str(EVIDENCE / f"fee-council-{locale}-{width}.png"))
            # One refused and one good save per locale: the way back survives the refusal.
            page.set_viewport_size({"width": 1280, "height": 900})
            page.fill("#stay_fee_rate_czk", "0")
            page.fill("#account_number", "1234567890")
            page.fill("#account_bank", "0800")
            _save(page)
            assert page.locator("#stay-fee-account-error").is_visible()
            assert page.input_value("#account_number") == "1234567890"
            if capture:
                page.locator("#stay-fee-payment").scroll_into_view_if_needed()
                page.screenshot(path=str(EVIDENCE / f"fee-editor-refused-{locale}-1280.png"))
            page.fill("#account_number", "")
            page.fill("#account_bank", "")
            _save(page)
            assert f"/stay-fees?month={month}" in page.url, page.url
            if capture:
                page.screenshot(path=str(EVIDENCE / f"fee-list-after-save-{locale}-1280.png"))
        context.close()
        browser.close()
