"""0077: one fee editor and one normaliser (0101: the old setup URL is gone)."""
from __future__ import annotations

import os
import re
import secrets
import socket
import threading
import time
from pathlib import Path
from urllib.parse import quote

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


def _save_property(client, apartment_id: int, entity_id: int, form: dict, **extra):
    return client.post(
        f"/apartments/{apartment_id}",
        data={**{k: str(v) for k, v in NON_FEE.items() if k != "permalink_pin"},
              "legal_entity_id": str(entity_id), **form, **extra},
        follow_redirects=False,
    )


# --- 0101: the old setup URL is gone; the editor keeps the way back --------


def test_the_old_setup_url_is_gone(host):
    client, owner_id, entity_id = host
    apartment_id = _property(owner_id, entity_id)
    assert client.get(f"/stay-fees/{apartment_id}/setup", follow_redirects=False).status_code == 404
    posted = client.post(f"/stay-fees/{apartment_id}/setup", data=_fee_form(), follow_redirects=False)
    assert posted.status_code in (404, 405)
    assert _row(apartment_id)["stay_fee_rate_czk"] in (None, 0)


def test_the_fee_editor_keeps_the_way_back(host):
    client, owner_id, entity_id = host
    apartment_id = _property(owner_id, entity_id)
    back = f"/stay-fees/{apartment_id}?month=2026-07"
    page = client.get(_canonical(apartment_id, back).split("#", 1)[0] + "&lang=en")
    assert page.status_code == 200
    assert 'id="stay-fee-settings"' in page.text
    assert f'name="fee_return_to" value="{back}"' in page.text
    assert f'href="{back}"' in page.text
    assert "Back to stay fees" in page.text


@pytest.mark.parametrize("unsafe", [
    "//evil.example/stay-fees", "https://evil.example/stay-fees", "/apartments/1", "/stay-fees/999999",
])
def test_unsafe_or_foreign_return_is_dropped(host, unsafe):
    client, owner_id, entity_id = host
    apartment_id = _property(owner_id, entity_id)
    page = client.get(f"/apartments/{apartment_id}?view=settings&return_to={quote(unsafe, safe='')}")
    assert 'name="fee_return_to"' not in page.text


# --- the one normaliser behind the property save --------------------------


@pytest.mark.parametrize("form", [
    _fee_form(),
    _fee_form(stay_fee_rate_czk="99", stay_fee_cadence="weekly", stay_fee_vs="abc12345678901"),
    _fee_form(stay_fee_rate_czk="0", account_prefix="", account_number="", account_bank=""),
    _fee_form(stay_fee_authority_name="", stay_fee_payee="  Obec  ", stay_fee_instruction="x" * 600),
])
def test_property_save_stores_the_normalised_fee_values(host, form):
    client, owner_id, entity_id = host
    apartment_id = _property(owner_id, entity_id, stay_fee_rate_czk=10, stay_fee_vs="1")

    response = _save_property(client, apartment_id, entity_id, form)

    assert response.status_code == 303
    expected = stay_fee_routes.fee_form_values(form)
    stay_fee_routes.apply_fee_account(expected)
    assert {key: _row(apartment_id)[key] for key in expected} == expected


def test_iban_only_account_survives_an_unrelated_fee_save(host):
    client, owner_id, entity_id = host
    iban = "CZ6508000000192000145399"
    stored = {"stay_fee_rate_czk": 20, "stay_fee_council_account": iban, "stay_fee_council_iban": iban}
    apartment_id = _property(owner_id, entity_id, **stored)
    form = _fee_form(_stay_fee_account_existing=iban, account_prefix="", account_number="", account_bank="")

    _save_property(client, apartment_id, entity_id, form)

    row = _row(apartment_id)
    assert (row["stay_fee_council_account"], row["stay_fee_council_iban"]) == (iban, iban)
    assert row["stay_fee_authority_name"] == "Council office"


def test_blank_account_clears(host):
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
    _save_property(client, apartment_id, entity_id, form)
    row = _row(apartment_id)
    assert row["stay_fee_council_account"] is None and row["stay_fee_council_iban"] is None


# --- the way back after save and after a refusal --------------------------


def test_save_returns_to_the_exact_report_period(host):
    client, owner_id, entity_id = host
    apartment_id = _property(owner_id, entity_id)
    back = f"/stay-fees/{apartment_id}?month=2026-07"
    settings = f"/apartments/{apartment_id}?view=settings&section=reporting"

    full = _save_property(client, apartment_id, entity_id, _fee_form(), fee_return_to=back, return_to=settings)
    assert full.headers["location"].startswith(back + "&msg=")

    listed = _save_property(
        client, apartment_id, entity_id,
        _fee_form(), fee_return_to="/stay-fees?month=2026-06&status=ready", return_to=settings,
    )
    assert listed.headers["location"].startswith("/stay-fees?month=2026-06&status=ready&msg=")


def test_rate_zero_returns_to_the_list_of_the_same_month(host):
    client, owner_id, entity_id = host
    apartment_id = _property(owner_id, entity_id, stay_fee_rate_czk=20)
    response = _save_property(
        client, apartment_id, entity_id,
        _fee_form(stay_fee_rate_czk="0"), fee_return_to=f"/stay-fees/{apartment_id}?month=2026-07",
    )
    assert response.headers["location"].startswith("/stay-fees?month=2026-07&msg=")
    assert _row(apartment_id)["stay_fee_rate_czk"] == 0


def test_invalid_account_saves_nothing_and_keeps_what_was_typed(host):
    client, owner_id, entity_id = host
    apartment_id = _property(owner_id, entity_id, stay_fee_rate_czk=20, stay_fee_vs="1")
    before = _row(apartment_id)
    back = f"/stay-fees/{apartment_id}?month=2026-07"
    form = _fee_form(account_number="1234567890", stay_fee_vs="777", fee_return_to=back)
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
                 '#property-settings-form button.ui-btn-primary[type="submit"]').first.click()
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
                page.locator(f'a.ui-btn[href^="/apartments/{unset}?view=settings"]').click()
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
                # Park the pointer first: it still rests where the "Set up" link was clicked, and
                # focus() scrolls the page so another "?" tip can end up under it and take the open state.
                page.mouse.move(0, 0)
                help_button.focus()
                assert page.locator("#stay_fee_authority_databox-help").is_visible(), (width, locale)
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
