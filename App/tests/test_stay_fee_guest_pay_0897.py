"""0897 phase 0: host settings for guest payment of the stay fee.

The kill switch UBYHOST_STAY_FEE_GUEST_PAY is off by default. With it off the
block renders disabled and a save ignores the posted guest fields, so stored
values survive a switch-off and a later switch-on. With it on, the fields are
saved; a Revolut link is accepted only on https and revolut.me / revolut.com.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import auth, config, db
from app.main import app
from app.routes import stay_fees as stay_fee_routes
from tests.conftest import login_as

USERNAME = "stay-fee-guest-0897"
GOOD_LINK = "https://revolut.me/jan"


def _cleanup():
    for user in db.query("SELECT id FROM user_account WHERE username = ?", (USERNAME,)):
        owner_id = user["id"]
        db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (owner_id,))
        db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (owner_id,))
        db.execute("DELETE FROM audit WHERE owner_user_id = ?", (owner_id,))
        db.execute("DELETE FROM user_account WHERE id = ?", (owner_id,))


def _property_data(entity_id: int, **overrides):
    data = {
        "internal_name": "Guest Pay Flat",
        "addr_city": "Praha",
        "addr_obec": "Praha",
        "addr_house_no": "12",
        "addr_zip": "120 00",
        "uby_idub": "123456789012",
        "uby_mark": "abc",
        "uby_name": "Penzion Guest",
        "uby_contact": "host@guest.test",
        "uby_ws_user": "UBY-WSguest",
        "permalink_window_days": "2",
        "permalink_reachback_days": "30",
        "legal_entity_id": str(entity_id),
    }
    data.update(overrides)
    return data


@pytest.fixture
def host(monkeypatch):
    db.init_db()
    _cleanup()
    owner_id = auth.create_account(f"{USERNAME}@example.test", "Guest Pay Host", username=USERNAME)
    entity_id = db.insert("legal_entity", {
        "name": "Guest Pay s.r.o.", "owner_user_id": owner_id, "created_at": db.utcnow(),
        "iban": "CZ6508000000192000145399",
        "bank_account": "19-2000145399/0800",
    })
    client = TestClient(app)
    assert login_as(client, USERNAME, url="/login?lang=en", follow_redirects=False).status_code == 303
    created = client.post("/apartments", data=_property_data(entity_id), follow_redirects=False)
    assert created.status_code == 303, created.text
    apartment = db.query_one("SELECT id FROM apartment WHERE owner_user_id = ?", (owner_id,))
    monkeypatch.setattr(config, "STAY_FEE_GUEST_PAY", False)
    try:
        yield client, apartment["id"]
    finally:
        _cleanup()


def _save(client, apartment_id, guest=None):
    """Save the property with the fee fields; guest=None means the block is not in the form."""
    page = client.get(f"/apartments/{apartment_id}?lang=en")
    assert page.status_code == 200
    token = page.text.split('name="csrf-token" content="')[1].split('"')[0]
    entity = db.query_one("SELECT legal_entity_id FROM apartment WHERE id = ?", (apartment_id,))
    data = _property_data(entity["legal_entity_id"], _csrf=token, stay_fee_rate_czk="50", stay_fee_vs="123456")
    if guest is not None:
        data["stay_fee_guest_form"] = "1"
        data.update(guest)
    return client.post(f"/apartments/{apartment_id}", data=data, follow_redirects=False)


def _stored(apartment_id):
    return db.query_one(
        "SELECT stay_fee_collect, stay_fee_guest_rails, stay_fee_guest_revolut_link, stay_fee_guest_cash_note "
        "FROM apartment WHERE id = ?",
        (apartment_id,),
    )


def _set_stored(apartment_id):
    db.execute(
        "UPDATE apartment SET stay_fee_collect = 1, stay_fee_guest_rails = 'qr', "
        "stay_fee_guest_revolut_link = ?, stay_fee_guest_cash_note = 'Reception' WHERE id = ?",
        (GOOD_LINK, apartment_id),
    )


def test_flag_off_hides_the_block(host, monkeypatch):
    client, apartment_id = host
    monkeypatch.setattr(config, "STAY_FEE_GUEST_PAY", False)
    page = client.get(f"/apartments/{apartment_id}?lang=en")
    assert page.status_code == 200
    assert 'id="stay-fee-guest-pay"' not in page.text
    assert "Turned off on this deployment" not in page.text


def test_flag_off_ignores_posted_guest_fields_and_keeps_stored_values(host, monkeypatch):
    client, apartment_id = host
    monkeypatch.setattr(config, "STAY_FEE_GUEST_PAY", False)
    _set_stored(apartment_id)
    before = dict(_stored(apartment_id))
    _save(client, apartment_id, guest={
        "stay_fee_guest_rails": ["cash"],
        "stay_fee_guest_revolut_link": "https://revolut.me/other",
        "stay_fee_guest_cash_note": "changed",
    })
    assert dict(_stored(apartment_id)) == before


def test_flag_on_saves_the_guest_fields(host, monkeypatch):
    client, apartment_id = host
    monkeypatch.setattr(config, "STAY_FEE_GUEST_PAY", True)
    response = _save(client, apartment_id, guest={
        "stay_fee_collect": "1",
        "stay_fee_guest_rails": ["revolut", "cash", "qr", "bogus"],
        "stay_fee_guest_revolut_link": f"  {GOOD_LINK}  ",
        "stay_fee_guest_cash_note": "  Pay at reception  ",
    })
    assert response.status_code == 303, response.text
    stored = _stored(apartment_id)
    assert stored["stay_fee_collect"] == 1
    assert stored["stay_fee_guest_rails"] == "cash,qr,revolut"
    assert stored["stay_fee_guest_revolut_link"] == GOOD_LINK
    assert stored["stay_fee_guest_cash_note"] == "Pay at reception"


def test_flag_on_without_the_block_in_the_form_leaves_guest_fields_alone(host, monkeypatch):
    client, apartment_id = host
    monkeypatch.setattr(config, "STAY_FEE_GUEST_PAY", True)
    _set_stored(apartment_id)
    before = dict(_stored(apartment_id))
    _save(client, apartment_id, guest=None)
    assert dict(_stored(apartment_id)) == before


def test_flag_on_switch_off_is_a_checkbox_that_stores_zero(host, monkeypatch):
    client, apartment_id = host
    monkeypatch.setattr(config, "STAY_FEE_GUEST_PAY", True)
    _set_stored(apartment_id)
    _save(client, apartment_id, guest={"stay_fee_guest_rails": ["qr"]})
    stored = _stored(apartment_id)
    assert stored["stay_fee_collect"] == 0
    assert stored["stay_fee_guest_rails"] == "qr"


@pytest.mark.parametrize("bad", [
    "http://revolut.me/jan",
    "https://revolut.me.evil.example/jan",
    "https://evil.example/revolut.me",
    "https://user@revolut.me/jan",
    "https://revolut.me:8443/jan",
    "javascript:alert(1)",
])
def test_flag_on_refuses_a_link_outside_revolut(host, monkeypatch, bad):
    client, apartment_id = host
    monkeypatch.setattr(config, "STAY_FEE_GUEST_PAY", True)
    before = dict(_stored(apartment_id))
    response = _save(client, apartment_id, guest={"stay_fee_guest_revolut_link": bad})
    assert response.status_code == 400
    assert "Use an https link on revolut.me or revolut.com." in response.text
    assert dict(_stored(apartment_id)) == before


@pytest.mark.parametrize("good", [
    GOOD_LINK,
    "https://www.revolut.com/pay/abc",
    "https://pay.revolut.me/jan",
])
def test_revolut_link_accepts_the_allowed_hosts(good):
    assert stay_fee_routes.revolut_link_ok(good)


@pytest.mark.parametrize("bad", [
    "",
    "revolut.me/jan",
    "http://revolut.me/jan",
    "https://revolut.me.evil.example/jan",
    "https://evil.example/revolut.me",
    "https://notrevolut.me/jan",
    "https://user:pw@revolut.me/jan",
    "https://revolut.me:8443/jan",
    "https://revolut.me\\@evil.example/",
])
def test_revolut_link_refuses_everything_else(bad):
    assert not stay_fee_routes.revolut_link_ok(bad)


def test_cash_note_is_capped_at_300_characters(host, monkeypatch):
    client, apartment_id = host
    monkeypatch.setattr(config, "STAY_FEE_GUEST_PAY", True)
    _save(client, apartment_id, guest={"stay_fee_guest_cash_note": "a" * 400})
    assert len(_stored(apartment_id)["stay_fee_guest_cash_note"]) == 300


def test_revolut_link_adds_revolut_rail_when_checkbox_omitted(host, monkeypatch):
    client, apartment_id = host
    monkeypatch.setattr(config, "STAY_FEE_GUEST_PAY", True)
    response = _save(
        client,
        apartment_id,
        guest={
            "stay_fee_guest_rails": ["qr"],
            "stay_fee_guest_revolut_link": GOOD_LINK,
        },
    )
    assert response.status_code == 303, response.text
    assert "revolut" in _stored(apartment_id)["stay_fee_guest_rails"]


def test_qr_rail_without_operator_account_refuses_save(host, monkeypatch):
    client, apartment_id = host
    monkeypatch.setattr(config, "STAY_FEE_GUEST_PAY", True)
    entity = db.query_one("SELECT legal_entity_id FROM apartment WHERE id = ?", (apartment_id,))
    db.update(
        "legal_entity",
        entity["legal_entity_id"],
        {"iban": None, "bank_account": None},
    )
    response = _save(
        client,
        apartment_id,
        guest={"stay_fee_collect": "1", "stay_fee_guest_rails": ["qr"], "stay_fee_guest_operator_account": ""},
    )
    assert response.status_code == 400
    assert "Enter your business bank account" in response.text


def test_qr_rail_saves_operator_account_on_legal_entity(host, monkeypatch):
    client, apartment_id = host
    monkeypatch.setattr(config, "STAY_FEE_GUEST_PAY", True)
    entity = db.query_one("SELECT legal_entity_id FROM apartment WHERE id = ?", (apartment_id,))
    account = "19-2000145399/0800"
    response = _save(
        client,
        apartment_id,
        guest={
            "stay_fee_guest_rails": ["qr", "iban"],
            "stay_fee_guest_operator_account": account,
        },
    )
    assert response.status_code == 303, response.text
    row = db.query_one(
        "SELECT bank_account, iban FROM legal_entity WHERE id = ?",
        (entity["legal_entity_id"],),
    )
    assert row["bank_account"] == "19-2000145399/0800"
    assert (row["iban"] or "").startswith("CZ")


def test_qr_rail_shows_preview_when_operator_has_iban(host, monkeypatch):
    client, apartment_id = host
    monkeypatch.setattr(config, "STAY_FEE_GUEST_PAY", True)
    entity = db.query_one("SELECT legal_entity_id FROM apartment WHERE id = ?", (apartment_id,))
    db.update(
        "legal_entity",
        entity["legal_entity_id"],
        {"iban": "CZ6508000000192000145399", "bank_account": "19-2000145399/0800"},
    )
    _save(client, apartment_id, guest={"stay_fee_guest_rails": ["qr"]})
    page = client.get(f"/apartments/{apartment_id}?view=settings&section=reporting&lang=en")
    assert page.status_code == 200
    assert 'id="stay-fee-guest-preview"' in page.text
    assert "data:image/png;base64," in page.text
    assert "CZ65 0800" in page.text or "CZ650800" in page.text


def test_stored_operator_account_shows_before_any_rail_is_saved(host, monkeypatch):
    client, apartment_id = host
    monkeypatch.setattr(config, "STAY_FEE_GUEST_PAY", True)
    page = client.get(f"/apartments/{apartment_id}?view=settings&section=reporting&lang=en")
    assert page.status_code == 200
    assert 'value="CZ6508000000192000145399"' in page.text or 'value="19-2000145399/0800"' in page.text
    assert "data:image/png;base64," in page.text
    assert "hidden" not in page.text.split('id="stay-fee-guest-preview"')[1].split(">")[0]


def _csrf(client, apartment_id):
    page = client.get(f"/apartments/{apartment_id}?lang=en")
    return page.text.split('name="csrf-token" content="')[1].split('"')[0]


def test_live_preview_endpoint_returns_a_qr_for_a_typed_account(host, monkeypatch):
    client, apartment_id = host
    monkeypatch.setattr(config, "STAY_FEE_GUEST_PAY", True)
    token = _csrf(client, apartment_id)
    ok = client.post(
        f"/stay-fees/{apartment_id}/guest-pay-preview",
        data={"account": "19-2000145399/0800", "rate": "30"},
        headers={"x-csrf-token": token},
    )
    assert ok.status_code == 200
    body = ok.json()
    assert body["ok"] is True and body["qr"].startswith("data:image/png;base64,")
    assert body["account"].replace(" ", "").startswith("CZ")
    bad = client.post(
        f"/stay-fees/{apartment_id}/guest-pay-preview",
        data={"account": "123"},
        headers={"x-csrf-token": token},
    ).json()
    assert bad["ok"] is False and bad["invalid"] is True


def test_live_preview_endpoint_is_off_with_the_kill_switch(host, monkeypatch):
    client, apartment_id = host
    token = _csrf(client, apartment_id)
    monkeypatch.setattr(config, "STAY_FEE_GUEST_PAY", False)
    response = client.post(
        f"/stay-fees/{apartment_id}/guest-pay-preview",
        data={"account": "19-2000145399/0800"},
        headers={"x-csrf-token": token},
    )
    assert response.status_code == 404


def _save_rate(client, apartment_id, rate, collect=True):
    page = client.get(f"/apartments/{apartment_id}?lang=en")
    token = page.text.split('name="csrf-token" content="')[1].split('"')[0]
    entity = db.query_one("SELECT legal_entity_id FROM apartment WHERE id = ?", (apartment_id,))
    data = _property_data(entity["legal_entity_id"], _csrf=token, stay_fee_rate_czk=str(rate), stay_fee_vs="123456")
    data["stay_fee_guest_form"] = "1"
    data["stay_fee_guest_rails"] = ["cash"]
    if collect:
        data["stay_fee_collect"] = "1"
    return client.post(f"/apartments/{apartment_id}", data=data, follow_redirects=False)


def test_asking_guests_to_pay_without_a_rate_is_refused(host, monkeypatch):
    client, apartment_id = host
    monkeypatch.setattr(config, "STAY_FEE_GUEST_PAY", True)
    response = _save_rate(client, apartment_id, 0)
    assert response.status_code == 400
    assert "per person per night" in response.text
    assert _stored(apartment_id)["stay_fee_collect"] in (0, None)


def test_asking_guests_to_pay_with_a_rate_saves(host, monkeypatch):
    client, apartment_id = host
    monkeypatch.setattr(config, "STAY_FEE_GUEST_PAY", True)
    assert _save_rate(client, apartment_id, 30).status_code == 303
    assert _stored(apartment_id)["stay_fee_collect"] == 1


def test_a_zero_rate_is_fine_while_guests_are_not_asked_to_pay(host, monkeypatch):
    client, apartment_id = host
    monkeypatch.setattr(config, "STAY_FEE_GUEST_PAY", True)
    assert _save_rate(client, apartment_id, 0, collect=False).status_code == 303


def test_default_rail_is_saved_only_when_that_rail_is_enabled(host, monkeypatch):
    client, apartment_id = host
    monkeypatch.setattr(config, "STAY_FEE_GUEST_PAY", True)
    ok = _save(client, apartment_id, guest={
        "stay_fee_guest_rails": ["qr", "revolut"],
        "stay_fee_guest_default_rail": "revolut",
        "stay_fee_guest_revolut_link": GOOD_LINK,
    })
    assert ok.status_code == 303, ok.text
    row = db.query_one("SELECT stay_fee_guest_default_rail FROM apartment WHERE id = ?", (apartment_id,))
    assert row["stay_fee_guest_default_rail"] == "revolut"
    _save(client, apartment_id, guest={
        "stay_fee_guest_rails": ["qr"],
        "stay_fee_guest_default_rail": "cash",
    })
    row = db.query_one("SELECT stay_fee_guest_default_rail FROM apartment WHERE id = ?", (apartment_id,))
    assert row["stay_fee_guest_default_rail"] == ""


def test_the_setup_wizard_does_not_ask_about_guest_payment(host, monkeypatch):
    client, apartment_id = host
    monkeypatch.setattr(config, "STAY_FEE_GUEST_PAY", True)
    page = client.get(f"/apartments/{apartment_id}/setup/stay_fee?lang=en")
    assert page.status_code == 200
    assert 'id="stay-fee-guest-pay"' not in page.text


def _save_collect(client, apartment_id, rails, link="", rate=30):
    page = client.get(f"/apartments/{apartment_id}?lang=en")
    token = page.text.split('name="csrf-token" content="')[1].split('"')[0]
    entity = db.query_one("SELECT legal_entity_id FROM apartment WHERE id = ?", (apartment_id,))
    data = _property_data(entity["legal_entity_id"], _csrf=token, stay_fee_rate_czk=str(rate), stay_fee_vs="123456")
    data["stay_fee_guest_form"] = "1"
    data["stay_fee_collect"] = "1"
    data["stay_fee_guest_rails"] = rails
    if link:
        data["stay_fee_guest_revolut_link"] = link
    return client.post(f"/apartments/{apartment_id}", data=data, follow_redirects=False)


def test_collecting_with_no_way_to_pay_is_refused(host, monkeypatch):
    client, apartment_id = host
    monkeypatch.setattr(config, "STAY_FEE_GUEST_PAY", True)
    response = _save_collect(client, apartment_id, [])
    assert response.status_code == 400
    assert "Pick at least one way" in response.text


def test_revolut_without_a_link_is_refused(host, monkeypatch):
    client, apartment_id = host
    monkeypatch.setattr(config, "STAY_FEE_GUEST_PAY", True)
    response = _save_collect(client, apartment_id, ["revolut"])
    assert response.status_code == 400
    assert "Revolut link" in response.text


def test_the_bank_account_is_not_required_while_collection_is_off(host, monkeypatch):
    client, apartment_id = host
    monkeypatch.setattr(config, "STAY_FEE_GUEST_PAY", True)
    entity = db.query_one("SELECT legal_entity_id FROM apartment WHERE id = ?", (apartment_id,))
    db.update("legal_entity", entity["legal_entity_id"], {"iban": None, "bank_account": None})
    response = _save(client, apartment_id, guest={"stay_fee_guest_rails": ["qr"]})
    assert response.status_code == 303, response.text


def test_the_qr_option_says_it_is_for_czech_and_slovak_guests_only(host, monkeypatch):
    client, apartment_id = host
    monkeypatch.setattr(config, "STAY_FEE_GUEST_PAY", True)
    page = client.get(f"/apartments/{apartment_id}?lang=en")
    assert "Only Czech and Slovak guests see and can use this." in page.text


# --- 0958: the guest card as the guest sees it, through the real save route ----

def _enable_guest_card(monkeypatch):
    from app import mail

    monkeypatch.setattr(config, "STAY_FEE_GUEST_PAY", True)
    monkeypatch.setattr(config, "GUEST_PIN_REQUIRED", False)
    monkeypatch.setattr(mail, "mail_enabled", lambda: False)


def _guest_stay(apartment_id, rails, declared=1):
    from datetime import timedelta
    from app import claim

    token = db.query_one("SELECT permalink_token FROM apartment WHERE id = ?", (apartment_id,))["permalink_token"]
    today = claim.prague_today()
    now = db.utcnow()
    stay = db.insert("reservation", {
        "apartment_id": apartment_id, "source": "airbnb", "uid": f"0958-{apartment_id}-{declared}-{rails}",
        "date_from": today.isoformat(), "date_to": (today + timedelta(days=3)).isoformat(),
        "status": "active", "declared_guests": declared, "created_at": now, "updated_at": now,
    })
    db.update("apartment", apartment_id, {
        "stay_fee_collect": 1, "stay_fee_rate_czk": 50, "stay_fee_guest_rails": rails,
        "stay_fee_guest_revolut_link": "", "stay_fee_guest_cash_note": "",
    })
    return token, stay


def _guest_saves(guest, token, stay, nationality="GBR", **overrides):
    from tests.test_endtoend import guest_form_data, passport_files

    return guest.post(
        f"/l/{token}/{stay}/save",
        data=guest_form_data(nationality=nationality, **overrides),
        files=passport_files(nationality),
        follow_redirects=False,
    )


def test_0958_one_gbr_guest_with_iban_only_sees_iban_and_no_qr(host, monkeypatch):
    from tests.conftest import complete_guest_claim

    _enable_guest_card(monkeypatch)
    client, apartment_id = host
    token, stay = _guest_stay(apartment_id, "iban")
    guest = TestClient(app)
    complete_guest_claim(guest, token, stay, party_size=1)
    response = _guest_saves(guest, token, stay)
    assert response.status_code == 303, response.text
    assert response.headers["location"].endswith("#fee-pay")
    page = guest.get(f"/l/{token}/{stay}?lang=en")
    assert 'id="fee-pay"' in page.text
    assert "5399" in page.text
    assert "g-fee-qr-img" not in page.text


def test_0958_one_cze_guest_from_abroad_sees_iban_and_qr(host, monkeypatch):
    from tests.conftest import complete_guest_claim

    _enable_guest_card(monkeypatch)
    client, apartment_id = host
    token, stay = _guest_stay(apartment_id, "qr")
    guest = TestClient(app)
    complete_guest_claim(guest, token, stay, party_size=1)
    response = _guest_saves(guest, token, stay, nationality="CZE", res_country="GBR", res_city="London")
    assert response.status_code == 303, response.text
    assert response.headers["location"].endswith("#fee-pay")
    page = guest.get(f"/l/{token}/{stay}?lang=en")
    assert "5399" in page.text
    assert "g-fee-qr-img" in page.text


def test_0958_card_waits_until_both_declared_guests_have_registered(host, monkeypatch):
    from tests.conftest import complete_guest_claim

    _enable_guest_card(monkeypatch)
    client, apartment_id = host
    token, stay = _guest_stay(apartment_id, "iban", declared=2)
    guest = TestClient(app)
    complete_guest_claim(guest, token, stay, party_size=2)
    assert _guest_saves(guest, token, stay).status_code == 303
    assert 'id="fee-pay"' not in guest.get(f"/l/{token}/{stay}?lang=en").text
    assert _guest_saves(guest, token, stay, surname="Second", doc_number="P7654321").status_code == 303
    assert 'id="fee-pay"' in guest.get(f"/l/{token}/{stay}?lang=en").text


def test_0958_czech_resident_of_the_property_municipality_sees_no_card(host, monkeypatch):
    from tests.conftest import complete_guest_claim

    _enable_guest_card(monkeypatch)
    client, apartment_id = host
    token, stay = _guest_stay(apartment_id, "iban")
    guest = TestClient(app)
    complete_guest_claim(guest, token, stay, party_size=1)
    response = _guest_saves(guest, token, stay, nationality="CZE", res_country="CZE", res_city="Praha")
    assert response.status_code == 303, response.text
    assert 'id="fee-pay"' not in guest.get(f"/l/{token}/{stay}?lang=en").text
