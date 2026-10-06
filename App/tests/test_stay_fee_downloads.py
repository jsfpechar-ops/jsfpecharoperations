"""Host-only stay-fee downloads: the hlášení PDF and the evidenční kniha CSV."""
from __future__ import annotations

import io
import secrets
from datetime import date
from urllib.parse import unquote

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader

from app import auth, claim, db, stay_fee
from app.main import app
from tests.conftest import login_as

SIGNATURE = "data:image/png;base64,AAAA"
IBAN = "CZ3008000000192000781379"
ACCOUNT = "19-2000781379/0800"


def _cleanup():
    for user in db.query(
        "SELECT id FROM user_account WHERE username LIKE 'stay-fee-downloads-%'"
    ):
        owner_id = user["id"]
        db.execute(
            "DELETE FROM stay_fee_filing WHERE apartment_id IN "
            "(SELECT id FROM apartment WHERE owner_user_id = ?)",
            (owner_id,),
        )
        db.execute(
            "DELETE FROM guest WHERE reservation_id IN (SELECT id FROM reservation "
            "WHERE apartment_id IN (SELECT id FROM apartment WHERE owner_user_id = ?))",
            (owner_id,),
        )
        db.execute(
            "DELETE FROM reservation WHERE apartment_id IN "
            "(SELECT id FROM apartment WHERE owner_user_id = ?)",
            (owner_id,),
        )
        db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (owner_id,))
        db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (owner_id,))
        db.execute("DELETE FROM audit WHERE owner_user_id = ?", (owner_id,))
        db.execute("DELETE FROM alert WHERE owner_user_id = ?", (owner_id,))
        db.execute("DELETE FROM email_outbox WHERE owner_user_id = ?", (owner_id,))
        db.execute("DELETE FROM user_account WHERE id = ?", (owner_id,))


@pytest.fixture
def host(monkeypatch):
    db.init_db()
    _cleanup()
    monkeypatch.setattr(claim, "prague_today", lambda: date(2026, 9, 30))
    owner_id = auth.create_account("stay-fee-downloads-owner@example.test", "Downloads Demo", role="host", username="stay-fee-downloads-owner")
    entity_id = db.insert("legal_entity", {
        "name": "Downloads Demo s.r.o.",
        "owner_user_id": owner_id,
        "created_at": db.utcnow(),
    })
    client = TestClient(app)
    logged_in = login_as(client, "stay-fee-downloads-owner", url="/login?lang=en", follow_redirects=False)
    assert logged_in.status_code == 303
    try:
        yield client, owner_id, entity_id
    finally:
        _cleanup()


def _property(owner_id, entity_id, name, *, rate=50, cadence="monthly",
              vs="123456", authority="Městský úřad", iban=IBAN, account=ACCOUNT):
    return db.insert("apartment", {
        "internal_name": name,
        "owner_user_id": owner_id,
        "legal_entity_id": entity_id,
        "addr_obec": "Praha 3",
        "stay_fee_rate_czk": rate,
        "stay_fee_cadence": cadence,
        "stay_fee_vs": vs,
        "stay_fee_authority_name": authority,
        "stay_fee_council_account": account,
        "stay_fee_council_iban": iban,
        "created_at": db.utcnow(),
    })


def _stay(apartment_id, date_from, date_to, guests):
    now = db.utcnow()
    reservation_id = db.insert("reservation", {
        "apartment_id": apartment_id,
        "uid": f"stay-fee-downloads-{apartment_id}-{date_from}",
        "date_from": date_from,
        "date_to": date_to,
        "status": "active",
        "created_at": now,
        "updated_at": now,
    })
    guest_ids = []
    for index, extra in enumerate(guests):
        guest = {
            "reservation_id": reservation_id,
            "first_name": f"Guest {index + 1}",
            "surname": "Demo",
            "birth_date": "01011990",
            "nationality": "DEU",
            "signature_png": SIGNATURE,
            "created_at": now,
            "updated_at": now,
        }
        guest.update(extra)
        guest_ids.append(db.insert("guest", guest))
    return reservation_id, guest_ids


def _csrf(client, apartment_id, month="2026-08") -> str:
    page = client.get(f"/stay-fees/{apartment_id}?month={month}")
    return page.text.split('name="csrf-token" content="')[1].split('"')[0]


def _finalize(client, apartment_id, month="2026-08", *, rate="50", guests=()):
    data = {
        "_csrf": _csrf(client, apartment_id, month),
        "month": month,
        "rate_czk": rate,
    }
    if guests:
        data["confirm_collected"] = "1"
        for guest_id, amount in guests:
            data[f"collected_{guest_id}"] = str(amount)
    return client.post(
        f"/stay-fees/{apartment_id}/finalize",
        data=data,
        follow_redirects=False,
    )


def _pdf_text(content: bytes) -> str:
    reader = PdfReader(io.BytesIO(content))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def test_login_is_required_for_both_downloads():
    db.init_db()
    _cleanup()
    auth.create_account("stay-fee-downloads-owner@example.test", "Downloads Demo", role="host", username="stay-fee-downloads-owner")
    try:
        client = TestClient(app)
        for path in ("/stay-fees/1/pdf", "/stay-fees/1/csv"):
            response = client.get(path, follow_redirects=False)
            assert response.status_code == 303
            assert response.headers["location"].startswith("/login")
    finally:
        _cleanup()


def test_the_pdf_is_the_council_report(host):
    client, owner_id, entity_id = host
    apartment_id = _property(owner_id, entity_id, "Downloads Demo")
    _stay(apartment_id, "2026-08-10", "2026-08-14", [{}])
    guest_id = db.query_one("SELECT id FROM guest ORDER BY id DESC")["id"]
    assert _finalize(client, apartment_id, guests=[(guest_id, 200)]).status_code == 303

    response = client.get(f"/stay-fees/{apartment_id}/pdf?month=2026-08")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/pdf")
    assert response.content.startswith(b"%PDF")
    assert (
        "hlaseni-poplatek-z-pobytu-2026-08-123456.pdf"
        in response.headers["content-disposition"]
    )
    text = _pdf_text(response.content)
    assert "Městský úřad" in text
    assert "za srpen 2026" in text
    assert "VS 123456" in text
    assert "200 Kč" in text


def test_a_running_period_is_blocked(host):
    client, owner_id, entity_id = host
    apartment_id = _property(owner_id, entity_id, "Downloads Demo")
    _stay(apartment_id, "2026-09-10", "2026-09-14", [{}])

    response = client.get(
        f"/stay-fees/{apartment_id}/pdf?month=2026-09", follow_redirects=False
    )

    assert response.status_code == 303
    location = unquote(response.headers["location"])
    assert location.startswith(f"/stay-fees/{apartment_id}?month=2026-09")
    assert "Save the period first" in location


def test_a_zero_period_still_renders(host):
    client, owner_id, entity_id = host
    apartment_id = _property(owner_id, entity_id, "Downloads Demo")
    assert _finalize(client, apartment_id).status_code == 303

    response = client.get(f"/stay-fees/{apartment_id}/pdf?month=2026-08")

    assert response.status_code == 200
    assert response.content.startswith(b"%PDF")
    text = _pdf_text(response.content)
    assert "nevznikla povinnost" in text
    assert "0 Kč" in text


def test_a_quarterly_pdf_says_quarterly(host, monkeypatch):
    monkeypatch.setattr(claim, "prague_today", lambda: date(2026, 10, 3))
    client, owner_id, entity_id = host
    apartment_id = _property(
        owner_id, entity_id, "Downloads Demo", rate=21, cadence="quarterly"
    )
    guest_id = None
    _stay(apartment_id, "2026-07-10", "2026-07-12", [{}])
    guest_id = db.query_one("SELECT id FROM guest ORDER BY id DESC")["id"]
    saved = _finalize(client, apartment_id, rate="21", guests=[(guest_id, 42)])
    assert saved.status_code == 303

    response = client.get(f"/stay-fees/{apartment_id}/pdf?month=2026-08")

    assert response.status_code == 200
    text = _pdf_text(response.content)
    assert "ČTVRTLETNÍ HLÁŠENÍ" in text
    assert "za 3. čtvrtletí 2026" in text
    assert "42 Kč" in text


def test_the_csv_is_the_register_with_a_bom(host):
    client, owner_id, entity_id = host
    apartment_id = _property(owner_id, entity_id, "Downloads Demo")
    _stay(apartment_id, "2026-08-10", "2026-08-14", [{}])
    guest_id = db.query_one("SELECT id FROM guest ORDER BY id DESC")["id"]
    assert _finalize(client, apartment_id, guests=[(guest_id, 200)]).status_code == 303

    response = client.get(f"/stay-fees/{apartment_id}/csv?month=2026-08")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert response.content.startswith(b"\xef\xbb\xbf")
    assert (
        f"evidencni-kniha-2026-08-{apartment_id}.csv"
        in response.headers["content-disposition"]
    )
    text = response.content.decode("utf-8-sig")
    lines = text.splitlines()
    assert lines[0].split(";") == [label for _, label in stay_fee.REGISTER_COLUMNS]
    assert "Demo;Guest 1" in text


def test_a_restricted_guest_is_blanked_in_the_csv(host):
    client, owner_id, entity_id = host
    apartment_id = _property(owner_id, entity_id, "Downloads Demo")
    _stay(apartment_id, "2026-08-10", "2026-08-14", [
        {"first_name": "Visible"},
        {"first_name": "Secret", "surname": "Hidden", "restricted_at": db.utcnow()},
    ])
    guests = db.query("SELECT id FROM guest ORDER BY id")
    assert _finalize(
        client,
        apartment_id,
        guests=[(row["id"], 200) for row in guests],
    ).status_code == 303

    response = client.get(f"/stay-fees/{apartment_id}/csv?month=2026-08")

    assert response.status_code == 200
    text = response.content.decode("utf-8-sig")
    assert stay_fee.RESTRICTED_NOTE in text
    assert "Secret" in text
    assert "Hidden" in text
    assert "Visible" in text


def test_another_owners_property_is_refused(host):
    client, _owner_id, _entity_id = host
    other_id = auth.create_account("stay-fee-downloads-other@example.test", "Other Demo", role="host", username="stay-fee-downloads-other")
    other_entity_id = db.insert("legal_entity", {
        "name": "Other Demo s.r.o.",
        "owner_user_id": other_id,
        "created_at": db.utcnow(),
    })
    private_id = _property(other_id, other_entity_id, "Private Other Demo")
    _stay(private_id, "2026-08-10", "2026-08-14", [{}])

    for path in (f"/stay-fees/{private_id}/pdf", f"/stay-fees/{private_id}/csv"):
        response = client.get(f"{path}?month=2026-08", follow_redirects=False)
        assert response.status_code == 303
        assert unquote(response.headers["location"]).startswith("/stay-fees?")
        assert "This property no longer exists." in unquote(
            response.headers["location"]
        )
