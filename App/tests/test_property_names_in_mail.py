"""Guests read the same property name in their e-mail as on the guest pages.

The guest pages lead with the host's own name (``internal_name``). The mail
used to lead with the police-register name (``uby_name``), which hosts often
fill with a short code, so a guest saw "Downtown Comfort" on the page and
"č1" in the inbox. The register name still goes to UbyPort; it just stops
reaching the guest when a friendlier name exists.
"""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app import auth, claim, config, db, i18n, invoices, mail, mail_notify
from app.main import app
from tests.conftest import login_as
from tests.invoice_stay_helper import drop_stays, stay_form

INTERNAL = "Downtown Comfort Loft"
REGISTER = "č1"

APARTMENT = {
    "internal_name": INTERNAL,
    "uby_name": REGISTER,
    "legal_entity_id": None,
}
RESERVATION = {"id": 1, "date_from": "2026-09-25", "date_to": "2026-09-28"}
LINK = f"{config.PUBLIC_BASE_URL}/l/propnametok/1/claim#c=secret"
STAY_URL = f"{config.PUBLIC_BASE_URL}/l/propnametok/1"


def test_the_label_prefers_the_hosts_own_name():
    assert mail_notify.property_label(APARTMENT, "en") == INTERNAL


def test_the_label_falls_back_to_the_register_name():
    apartment = {**APARTMENT, "internal_name": "  "}
    assert mail_notify.property_label(apartment, "en") == REGISTER


def test_the_label_falls_back_to_a_translated_stand_in_when_both_are_empty():
    apartment = {**APARTMENT, "internal_name": "", "uby_name": None}
    assert mail_notify.property_label(apartment, "cs") == i18n.translator("cs")(
        "mail_property_fallback"
    )


@pytest.mark.parametrize("lang", ["en", "cs"])
@pytest.mark.parametrize(
    "kind, extra",
    [
        ("claim", {"link": LINK}),
        ("claim_resend", {"link": LINK, "resend": True}),
        ("reminder_guest", {"stay_url": STAY_URL, "filled": 1, "expected": 3}),
        ("completion", {"stay_url": STAY_URL}),
    ],
)
def test_every_guest_mail_names_the_property_as_the_guest_pages_do(kind, extra, lang):
    content = claim._guest_mail_content(kind, APARTMENT, RESERVATION, lang=lang, **extra)

    assert INTERNAL in content["subject"], content["subject"]
    assert REGISTER not in content["subject"]
    assert INTERNAL in content["text"]
    assert REGISTER not in content["text"]


# --- invoice_issued --------------------------------------------------------

USERNAME = "property-name-mail-host"
TOKEN = "propnamemailtoken"


def _owner_id():
    row = db.query_one("SELECT id FROM user_account WHERE username = ?", (USERNAME,))
    return row["id"] if row else None


def _cleanup():
    user_id = _owner_id()
    if not user_id:
        return
    db.execute(
        "INSERT INTO settings (key, value) VALUES ('invoice_purge_unlock', '1') "
        "ON CONFLICT(key) DO UPDATE SET value = '1'"
    )
    db.execute(
        "DELETE FROM invoice_item WHERE invoice_id IN (SELECT id FROM invoice WHERE owner_user_id = ?)",
        (user_id,),
    )
    db.execute("DELETE FROM invoice WHERE owner_user_id = ?", (user_id,))
    drop_stays(user_id)
    db.execute(
        "INSERT INTO settings (key, value) VALUES ('invoice_purge_unlock', '') "
        "ON CONFLICT(key) DO UPDATE SET value = ''"
    )
    db.execute(
        "DELETE FROM reservation WHERE apartment_id IN (SELECT id FROM apartment WHERE owner_user_id = ?)",
        (user_id,),
    )
    db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (user_id,))
    db.execute(
        "DELETE FROM invoice_sequence WHERE legal_entity_id IN "
        "(SELECT id FROM legal_entity WHERE owner_user_id = ?)",
        (user_id,),
    )
    db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (user_id,))
    db.execute("DELETE FROM audit WHERE owner_user_id = ?", (user_id,))
    db.execute("DELETE FROM alert WHERE owner_user_id = ?", (user_id,))
    db.execute("DELETE FROM email_outbox WHERE owner_user_id = ?", (user_id,))
    db.execute("DELETE FROM user_account WHERE id = ?", (user_id,))


@pytest.fixture
def host(monkeypatch):
    db.init_db()
    _cleanup()
    auth.create_account(f"{USERNAME}@example.test", "Property Name Host", username=USERNAME)
    monkeypatch.setattr(mail, "mail_enabled", lambda: True)
    client = TestClient(app)
    response = login_as(client, USERNAME, url="/login?lang=en", follow_redirects=False)
    assert response.status_code == 303, response.text
    try:
        yield client
    finally:
        _cleanup()


def _entity() -> int:
    return db.insert(
        "legal_entity",
        {
            "name": "Issuer s.r.o.", "seat": "Praha 1", "ico": "04656679",
            "registry_entry": "Fyzická osoba zapsaná v živnostenském rejstříku",
            "vat_status": "non_payer", "invoice_due_days": 14,
            "owner_user_id": _owner_id(), "created_at": db.utcnow(),
        },
    )


def _stay(entity_id: int) -> int:
    now = db.utcnow()
    apartment_id = db.insert(
        "apartment",
        {
            "legal_entity_id": entity_id,
            "owner_user_id": _owner_id(),
            "internal_name": INTERNAL,
            "uby_name": REGISTER,
            "permalink_token": TOKEN,
            "automation_mode": "manual",
            "default_purpose": "10",
            "active": 1,
            "created_at": now,
        },
    )
    return db.insert(
        "reservation",
        {
            "apartment_id": apartment_id,
            "source": "airbnb",
            "uid": "property-name-stay",
            "date_from": "2026-09-25",
            "date_to": "2026-09-28",
            "status": "active",
            "created_at": now,
            "updated_at": now,
        },
    )


def _send_invoice(client, reservation_id=None) -> dict:
    if reservation_id is None:
        # Route now requires a stay; keep the plain-subject case via the library
        # path that 0019 left open when stay is omitted (old invoices).
        entity = db.query_one(
            "SELECT * FROM legal_entity WHERE owner_user_id = ? ORDER BY id DESC",
            (_owner_id(),),
        )
        form = {
            "buyer_name": "Buyer", "buyer_email": "buyer@example.test",
            "already_paid": "1", "lang": "en",
            "item_description": ["Accommodation"], "item_quantity": ["1"],
            "item_unit": ["ks"], "item_unit_price": ["1000"], "item_vat_rate": ["0"],
        }
        draft = invoices.build_draft(entity, form, "en", today=claim.prague_today())
        draft.update({"legal_entity_id": entity["id"], "owner_user_id": _owner_id()})
        invoice_id = invoices.issue(draft, _owner_id())
    else:
        response = client.post(
            "/invoices",
            data={
                "buyer_name": "Buyer", "buyer_email": "buyer@example.test",
                "already_paid": "1", "lang": "en",
                **stay_form(reservation_id),
                "item_description": ["Accommodation"], "item_quantity": ["1"],
                "item_unit": ["ks"], "item_unit_price": ["1000"], "item_vat_rate": ["0"],
            },
            follow_redirects=False,
        )
        invoice_id = int(response.headers["location"].split("?")[0].rsplit("/", 1)[1])
    client.post(f"/invoices/{invoice_id}/send", follow_redirects=False)
    row = db.query_one(
        "SELECT * FROM email_outbox WHERE kind = 'invoice_issued' AND owner_user_id = ? "
        "ORDER BY id DESC",
        (_owner_id(),),
    )
    assert row is not None
    return {"subject": row["subject"], "payload": json.loads(row["payload"])}


def test_an_invoice_for_a_stay_names_its_property(host):
    entity_id = _entity()
    reservation_id = _stay(entity_id)

    sent = _send_invoice(host, reservation_id)

    assert INTERNAL in sent["subject"]
    assert REGISTER not in sent["subject"]
    assert INTERNAL in sent["payload"]["text"]
    assert INTERNAL in sent["payload"]["html"]


def test_an_invoice_without_a_stay_keeps_the_plain_subject(host):
    _entity()

    sent = _send_invoice(host)

    t = i18n.translator("en")
    assert t("mail_invoice_property") not in sent["payload"]["text"]
    assert INTERNAL not in sent["subject"]
    assert sent["subject"].startswith("Invoice ")
    assert "–" not in sent["subject"]


@pytest.mark.parametrize("lang", ["en", "cs"])
def test_the_invoice_subject_with_a_stay_reads_naturally(lang):
    content = mail_notify.build_invoice_issued(
        lang=lang,
        property_name="Issuer s.r.o.",
        number="2026-0001",
        total="1 000 Kč",
        download_url=f"{config.PUBLIC_BASE_URL}/invoice/d/token",
        stay_property=INTERNAL,
    )
    expected = {"en": "Invoice 2026-0001 – ", "cs": "Faktura 2026-0001 – "}[lang]
    assert content["subject"] == expected + INTERNAL
