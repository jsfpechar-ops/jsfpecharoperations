"""Save confirmations say what happened and what to do next.

"Saved." was the whole confirmation for a stay, a guest and a property, so a
host who had just pasted credentials from the police letter could not tell from
the message whether the property could report yet. Each confirmation now names
the next step, or names what is still missing.
"""
from __future__ import annotations

import base64
from datetime import date, timedelta
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient

from app import auth, db, host_i18n
from app.main import app

PASSWORD = "Secure-Password-123"
USERNAME = "flash-next-step-host"

SIGNATURE = "data:image/png;base64," + base64.b64encode(
    bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
        "890000000a49444154789c6300010000050001od7a1f0000000049454e44ae42"
        "6082".replace("od", "0d")
    )
).decode()

# validate_apartment()'s eight reporting fields, in readiness-checklist order.
REPORT_FIELD_KEYS = (
    "idub",
    "mark",
    "facility_name",
    "house_no",
    "zip",
    "obec",
    "ws_user",
    "password",
)

# Everything validate_apartment() reports on, so nothing is left to name.
COMPLETE_PROPERTY = {
    "internal_name": "Flash Flat",
    "addr_obec": "Praha",
    "addr_house_no": "12",
    "addr_zip": "110 00",
    "uby_idub": "123456789012",
    "uby_mark": "ABCDE",
    "uby_name": "Penzion Flash",
    "uby_ws_user": "UBY-WS123abc",
    "uby_ws_password": "police-secret",
    "active": "on",
}

GUEST = {
    "surname": "Novak",
    "first_name": "Jan",
    "birth_date": "01011990",
    "nationality": "CZE",
    "doc_number": "12345678",
    "res_street": "Vinohradska 1",
    "res_city": "Praha",
    "res_country": "CZE",
    "purpose": "10",
}


def _cleanup():
    user_ids = [
        row["id"]
        for row in db.query(
            "SELECT id FROM user_account WHERE username = ?", (USERNAME,)
        )
    ]
    for user_id in user_ids:
        apartments = "(SELECT id FROM apartment WHERE owner_user_id = ?)"
        stays = f"(SELECT id FROM reservation WHERE apartment_id IN {apartments})"
        db.execute(f"DELETE FROM guest WHERE reservation_id IN {stays}", (user_id,))
        db.execute(
            f"DELETE FROM reservation WHERE apartment_id IN {apartments}",
            (user_id,),
        )
        db.execute("DELETE FROM alert WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM audit WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM user_account WHERE id = ?", (user_id,))


@pytest.fixture
def host():
    db.init_db()
    _cleanup()
    auth.create_account(USERNAME, PASSWORD, "Flash Host", must_change_password=False)
    client = TestClient(app)
    response = client.post(
        "/login",
        data={"username": USERNAME, "password": PASSWORD},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    client.cookies.set(host_i18n.LANG_COOKIE, "en")
    try:
        yield client
    finally:
        _cleanup()


@pytest.fixture
def czech_host(host):
    host.cookies.set(host_i18n.LANG_COOKIE, "cs")
    return host


def _flash(location: str, kind: str = "msg") -> str:
    return parse_qs(urlparse(location).query)[kind][0]


def _label_list(lang: str) -> str:
    """The reporting field names as the host reads them, in checklist order."""
    return ", ".join(
        host_i18n.STRINGS[lang][f"apartment.form.readiness.item.{key}"]
        for key in REPORT_FIELD_KEYS
    )


def _create_property(client, **overrides) -> int:
    data = {"internal_name": "Flash Flat", "active": "on"}
    data.update(overrides)
    response = client.post("/apartments", data=data, follow_redirects=False)
    assert response.status_code == 303, response.text
    row = db.query_one(
        "SELECT id FROM apartment WHERE owner_user_id = "
        "(SELECT id FROM user_account WHERE username = ?) ORDER BY id DESC LIMIT 1",
        (USERNAME,),
    )
    return row["id"]


def _save_property(client, apartment_id: int, **overrides) -> str:
    data = {"internal_name": "Flash Flat", "active": "on"}
    data.update(overrides)
    response = client.post(
        f"/apartments/{apartment_id}", data=data, follow_redirects=False
    )
    assert response.status_code == 303, response.text
    return response.headers["location"]


def _create_stay(client, apartment_id: int) -> int:
    today = date.today()
    response = client.post(
        "/reservations",
        data={
            "apartment_id": str(apartment_id),
            "date_from": today.isoformat(),
            "date_to": (today + timedelta(days=3)).isoformat(),
            "expected_guests": "2",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    row = db.query_one(
        "SELECT id FROM reservation WHERE apartment_id = ? ORDER BY id DESC LIMIT 1",
        (apartment_id,),
    )
    return row["id"]


def _add_guest(client, reservation_id: int) -> int:
    response = client.post(
        f"/reservations/{reservation_id}/guests",
        data={**GUEST, "signature": SIGNATURE},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    row = db.query_one(
        "SELECT id FROM guest WHERE reservation_id = ? ORDER BY id DESC LIMIT 1",
        (reservation_id,),
    )
    return row["id"]


@pytest.mark.parametrize(
    "key, english, czech",
    [
        (
            "flash.reservations.created",
            "Stay created. Next, copy the guest link or add guests yourself.",
            "Pobyt vytvořen. Teď zkopírujte odkaz pro hosty, nebo hosty zadejte sami.",
        ),
        ("flash.reservations.saved", "Stay saved.", "Pobyt uložen."),
        (
            "flash.guests.saved",
            "Guest saved. %(filled)s of %(expected)s forms are complete.",
            "Host uložen. Hotové formuláře: %(filled)s/%(expected)s.",
        ),
        (
            "flash.apartments.saved",
            "Saved. Still missing for police reporting: %(fields)s.",
            "Uloženo. Pro hlášení policii ještě chybí: %(fields)s.",
        ),
        (
            "flash.apartments.saved_ready",
            "Saved. This property is ready to report.",
            "Uloženo. Ubytování je připravené k hlášení.",
        ),
        (
            "flash.apartments.connection_ok",
            "Connection works. UbyPort accepted your web-service login.",
            "Spojení funguje. UbyPort přijal vaše přihlašovací údaje.",
        ),
        (
            "flash.reservations.claim_released",
            "Assignment released. Another e-mail can now claim this stay.",
            "Přiřazení uvolněno. Pobyt teď může převzít jiný e-mail.",
        ),
    ],
)
def test_each_confirmation_carries_the_audited_copy(key, english, czech):
    assert host_i18n.STRINGS["en"][key] == english
    assert host_i18n.STRINGS["cs"][key] == czech


def test_the_property_confirmation_names_what_is_still_missing(host):
    apartment_id = _create_property(host)
    location = _save_property(host, apartment_id)
    expected = host_i18n.translate(
        "en", "flash.apartments.saved", fields=_label_list("en")
    )
    assert _flash(location) == expected
    assert "IDUB" in expected, "the list has to name the fields, not count them"


def test_the_property_confirmation_is_czech_for_a_czech_host(czech_host):
    apartment_id = _create_property(czech_host)
    location = _save_property(czech_host, apartment_id)
    expected = host_i18n.translate(
        "cs", "flash.apartments.saved", fields=_label_list("cs")
    )
    assert _flash(location) == expected
    assert "Saved" not in _flash(location)


def test_the_property_confirmation_lists_only_the_missing_fields(host):
    apartment_id = _create_property(host)
    location = _save_property(host, apartment_id, uby_idub="123456789012")
    message = _flash(location)
    assert "IDUB" not in message, "a filled field must not be listed"
    assert "Postcode" in message
    assert "Password" in message


def test_a_complete_property_is_confirmed_ready_to_report(host):
    apartment_id = _create_property(host)
    location = _save_property(host, apartment_id, **COMPLETE_PROPERTY)
    assert _flash(location) == host_i18n.translate(
        "en", "flash.apartments.saved_ready"
    )


def test_a_complete_property_reads_czech_for_a_czech_host(czech_host):
    apartment_id = _create_property(czech_host)
    location = _save_property(czech_host, apartment_id, **COMPLETE_PROPERTY)
    assert _flash(location) == host_i18n.translate(
        "cs", "flash.apartments.saved_ready"
    )


def test_the_guest_confirmation_counts_the_completed_forms(host):
    apartment_id = _create_property(host)
    reservation_id = _create_stay(host, apartment_id)
    guest_id = _add_guest(host, reservation_id)
    response = host.post(
        f"/guests/{guest_id}",
        data={**GUEST, "return_to": f"/guests/{guest_id}"},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    assert _flash(response.headers["location"]) == host_i18n.translate(
        "en", "flash.guests.saved", filled=1, expected=2
    )


def test_the_guest_confirmation_is_czech(czech_host):
    apartment_id = _create_property(czech_host)
    reservation_id = _create_stay(czech_host, apartment_id)
    guest_id = _add_guest(czech_host, reservation_id)
    response = czech_host.post(
        f"/guests/{guest_id}",
        data={**GUEST, "return_to": f"/guests/{guest_id}"},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    assert _flash(response.headers["location"]) == host_i18n.translate(
        "cs", "flash.guests.saved", filled=1, expected=2
    )


def test_the_guest_confirmation_counts_nothing_when_the_stay_declares_nobody(host):
    """A stay with no declared guest count has no denominator to report."""
    apartment_id = _create_property(host)
    today = date.today()
    host.post(
        "/reservations",
        data={
            "apartment_id": str(apartment_id),
            "date_from": today.isoformat(),
            "date_to": (today + timedelta(days=3)).isoformat(),
        },
        follow_redirects=False,
    )
    reservation_id = db.query_one(
        "SELECT id FROM reservation WHERE apartment_id = ? ORDER BY id DESC LIMIT 1",
        (apartment_id,),
    )["id"]
    guest_id = _add_guest(host, reservation_id)
    response = host.post(
        f"/guests/{guest_id}",
        data={**GUEST, "return_to": f"/guests/{guest_id}"},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    assert _flash(response.headers["location"]) == host_i18n.translate(
        "en", "flash.guests.saved_plain"
    )


def test_the_stay_created_confirmation_names_the_next_step(host):
    apartment_id = _create_property(host)
    today = date.today()
    response = host.post(
        "/reservations",
        data={
            "apartment_id": str(apartment_id),
            "date_from": today.isoformat(),
            "date_to": (today + timedelta(days=3)).isoformat(),
        },
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    assert _flash(response.headers["location"]) == host_i18n.translate(
        "en", "flash.reservations.created"
    )


def test_the_stay_saved_confirmation_says_which_record_was_saved(host):
    apartment_id = _create_property(host)
    reservation_id = _create_stay(host, apartment_id)
    response = host.post(
        f"/reservations/{reservation_id}",
        data={"return_to": f"/reservations/{reservation_id}"},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    assert _flash(response.headers["location"]) == host_i18n.translate(
        "en", "flash.reservations.saved"
    )


def test_the_claim_release_confirmation_is_the_audited_sentence(host):
    apartment_id = _create_property(host)
    reservation_id = _create_stay(host, apartment_id)
    response = host.post(
        f"/reservations/{reservation_id}/release-claim", follow_redirects=False
    )
    assert response.status_code == 303, response.text
    assert _flash(response.headers["location"]) == host_i18n.translate(
        "en", "flash.reservations.claim_released"
    )


def test_the_connection_confirmation_is_the_audited_sentence(host, mock_ubyport):
    apartment_id = _create_property(host, **COMPLETE_PROPERTY)
    response = host.post(
        f"/apartments/{apartment_id}/test-connection", follow_redirects=False
    )
    assert response.status_code == 303, response.text
    location = response.headers["location"]
    assert _flash(location) == host_i18n.translate(
        "en", "flash.apartments.connection_ok"
    )
    assert "max batch" not in location, "the batch size belongs in the activity log"


def test_the_new_keys_exist_in_both_languages():
    for key in (
        "flash.reservations.created",
        "flash.reservations.saved",
        "flash.guests.saved",
        "flash.guests.saved_plain",
        "flash.apartments.saved",
        "flash.apartments.saved_ready",
        "flash.apartments.connection_ok",
        "flash.reservations.claim_released",
    ):
        assert key in host_i18n.STRINGS["en"], key
        assert key in host_i18n.STRINGS["cs"], key
