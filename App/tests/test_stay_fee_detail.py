"""Host-only stay-fee detail page: report, payment panel and guest decisions."""
from __future__ import annotations

import re
import secrets
from datetime import date
from urllib.parse import unquote

import pytest
from fastapi.testclient import TestClient

from app import auth, claim, db
from app.main import app

PASSWORD = f"Stay-fee-detail-{secrets.token_urlsafe(12)}-9"
SIGNATURE = "data:image/png;base64,AAAA"
IBAN = "CZ3008000000192000781379"
ACCOUNT = "19-2000781379/0800"


def _cleanup():
    for user in db.query(
        "SELECT id FROM user_account WHERE username LIKE 'stay-fee-detail-%'"
    ):
        owner_id = user["id"]
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
    owner_id = auth.create_account(
        "stay-fee-detail-owner",
        PASSWORD,
        "Detail Demo",
        role="host",
        must_change_password=False,
    )
    entity_id = db.insert("legal_entity", {
        "name": "Detail Demo s.r.o.",
        "owner_user_id": owner_id,
        "created_at": db.utcnow(),
    })
    client = TestClient(app)
    logged_in = client.post(
        "/login?lang=en",
        data={"username": "stay-fee-detail-owner", "password": PASSWORD},
        follow_redirects=False,
    )
    assert logged_in.status_code == 303
    try:
        yield client, owner_id, entity_id
    finally:
        _cleanup()


def _property(owner_id, entity_id, name, *, rate=50, cadence="monthly", city="Praha 3",
              vs="123456", authority="Městský úřad", iban=IBAN, account=ACCOUNT):
    return db.insert("apartment", {
        "internal_name": name,
        "owner_user_id": owner_id,
        "legal_entity_id": entity_id,
        "addr_obec": city,
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
        "uid": f"stay-fee-detail-{apartment_id}-{date_from}",
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


def _csrf(client) -> str:
    match = re.search(
        r'<meta name="csrf-token" content="([^"]+)"', client.get("/stay-fees").text
    )
    assert match
    return match.group(1)


def _decide(client, apartment_id, guest_id, decision, reason="", month="2026-08"):
    return client.post(
        "/stay-fees/guest-decision",
        data={
            "_csrf": _csrf(client),
            "guest_id": guest_id,
            "apartment_id": apartment_id,
            "month": month,
            "decision": decision,
            "reason": reason,
        },
        follow_redirects=True,
    )


def test_login_is_required():
    db.init_db()
    _cleanup()
    auth.create_account(
        "stay-fee-detail-owner",
        PASSWORD,
        "Detail Demo",
        role="host",
        must_change_password=False,
    )
    try:
        response = TestClient(app).get("/stay-fees/1", follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"].startswith("/login")
    finally:
        _cleanup()


def test_another_owners_property_redirects_with_an_error(host):
    client, _owner_id, _entity_id = host
    other_id = auth.create_account(
        "stay-fee-detail-other",
        PASSWORD,
        "Other Demo",
        role="host",
        must_change_password=False,
    )
    other_entity_id = db.insert("legal_entity", {
        "name": "Other Demo s.r.o.",
        "owner_user_id": other_id,
        "created_at": db.utcnow(),
    })
    private_id = _property(other_id, other_entity_id, "Private Other Demo")

    response = client.get(f"/stay-fees/{private_id}", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"].startswith("/stay-fees")
    assert "This property no longer exists." in unquote(response.headers["location"])


def test_a_property_without_a_rate_is_not_a_stay_fee_property(host):
    client, owner_id, entity_id = host
    off_id = _property(owner_id, entity_id, "Rate Off Demo", rate=0)

    response = client.get(f"/stay-fees/{off_id}", follow_redirects=False)

    assert response.status_code == 303
    assert "This property no longer exists." in unquote(response.headers["location"])


def test_metrics_show_the_group_totals(host):
    client, owner_id, entity_id = host
    first = _property(owner_id, entity_id, "Detail Demo")
    second = _property(owner_id, entity_id, "Detail Sibling Demo")
    _stay(first, "2026-08-10", "2026-08-14", [{}])
    _stay(second, "2026-08-10", "2026-08-13", [{}])

    response = client.get(f"/stay-fees/{first}?month=2026-08")

    assert response.status_code == 200
    assert "350\u00a0Kč" in response.text
    assert '<div class="metric-value">7</div>' in response.text
    assert '<div class="metric-value">0</div>' in response.text  # exempt bed-days


def test_the_group_note_lists_the_sibling_properties(host):
    client, owner_id, entity_id = host
    first = _property(owner_id, entity_id, "Detail Demo")
    _property(owner_id, entity_id, "Detail Sibling Demo")

    response = client.get(f"/stay-fees/{first}?month=2026-08")

    assert response.status_code == 200
    assert "Detail Sibling Demo" in response.text
    assert "same legal entity and variable symbol" in response.text
    assert "The guest list below is this property only." in response.text


def test_the_guest_list_is_this_property_only(host):
    client, owner_id, entity_id = host
    first = _property(owner_id, entity_id, "Detail Demo")
    second = _property(owner_id, entity_id, "Detail Sibling Demo")
    _stay(first, "2026-08-10", "2026-08-14", [{"first_name": "Mine"}])
    _stay(second, "2026-08-10", "2026-08-14", [{"first_name": "Theirs"}])

    response = client.get(f"/stay-fees/{first}?month=2026-08")

    assert response.status_code == 200
    assert "Mine Demo" in response.text
    assert "Theirs Demo" not in response.text


def test_qr_is_present_with_an_account_and_variable_symbol(host):
    client, owner_id, entity_id = host
    apartment_id = _property(owner_id, entity_id, "Detail Demo")
    _stay(apartment_id, "2026-08-10", "2026-08-14", [{}])

    response = client.get(f"/stay-fees/{apartment_id}?month=2026-08")

    assert response.status_code == 200
    assert 'class="fee-qr"' in response.text
    assert '<img src="data:image/png' in response.text
    assert "QR Platba" in response.text
    assert "Scan in your banking app" in response.text
    assert "SPD*1.0*ACC:" in response.text
    assert "Payment details ready" in response.text


def test_qr_is_absent_without_a_council_account(host):
    client, owner_id, entity_id = host
    apartment_id = _property(
        owner_id, entity_id, "No Account Demo", vs=None, iban=None, account=None
    )
    _stay(apartment_id, "2026-08-10", "2026-08-14", [{}])

    response = client.get(f"/stay-fees/{apartment_id}?month=2026-08")

    assert response.status_code == 200
    assert 'class="fee-qr"' not in response.text
    assert "data:image/png" not in response.text
    assert "Payment details missing" in response.text


def test_exempt_without_a_reason_is_refused(host):
    client, owner_id, entity_id = host
    apartment_id = _property(owner_id, entity_id, "Detail Demo")
    _, guest_ids = _stay(apartment_id, "2026-08-10", "2026-08-14", [{}])

    response = _decide(client, apartment_id, guest_ids[0], "exempt")

    assert "Give a reason when you exempt a guest." in response.text
    stored = db.query_one("SELECT * FROM guest WHERE id = ?", (guest_ids[0],))
    assert stored["fee_host_decision"] is None
    assert stored["fee_host_reason"] is None
    assert db.query_one("SELECT * FROM audit WHERE action = 'stay_fee_decision'") is None


def test_exempt_with_a_reason_lowers_the_total_and_keeps_the_reason_out_of_the_log(host):
    client, owner_id, entity_id = host
    apartment_id = _property(owner_id, entity_id, "Detail Demo")
    _, guest_ids = _stay(apartment_id, "2026-08-10", "2026-08-14", [{}])

    before = client.get(f"/stay-fees/{apartment_id}?month=2026-08")
    assert "200\u00a0Kč" in before.text

    response = _decide(
        client, apartment_id, guest_ids[0], "exempt", reason="ZTP/P card checked"
    )

    assert response.status_code == 200
    assert "Saved." in response.text
    assert "200\u00a0Kč" not in response.text
    assert "0\u00a0Kč" in response.text
    stored = db.query_one("SELECT * FROM guest WHERE id = ?", (guest_ids[0],))
    assert stored["fee_host_decision"] == "exempt"
    assert stored["fee_host_reason"] == "ZTP/P card checked"
    entry = db.query_one(
        "SELECT * FROM audit WHERE action = 'stay_fee_decision' ORDER BY id DESC LIMIT 1"
    )
    assert entry["detail"] == f"guest_id={guest_ids[0]} decision=exempt"
    assert "ZTP/P" not in entry["detail"]
    assert "reason" not in entry["detail"]


def test_charging_a_minor_raises_the_total(host):
    client, owner_id, entity_id = host
    apartment_id = _property(owner_id, entity_id, "Detail Demo")
    _, guest_ids = _stay(
        apartment_id, "2026-08-10", "2026-08-14", [{"birth_date": "01012015"}]
    )

    before = client.get(f"/stay-fees/{apartment_id}?month=2026-08")
    assert "Exempt — under 18" in before.text
    assert "0\u00a0Kč" in before.text

    response = _decide(client, apartment_id, guest_ids[0], "charge")

    assert response.status_code == 200
    assert "200\u00a0Kč" in response.text
    stored = db.query_one("SELECT * FROM guest WHERE id = ?", (guest_ids[0],))
    assert stored["fee_host_decision"] == "charge"


def test_automatic_puts_the_guest_back_on_the_default_rule(host):
    client, owner_id, entity_id = host
    apartment_id = _property(owner_id, entity_id, "Detail Demo")
    _, guest_ids = _stay(
        apartment_id, "2026-08-10", "2026-08-14", [{"birth_date": "01012015"}]
    )
    _decide(client, apartment_id, guest_ids[0], "charge")
    charged = client.get(f"/stay-fees/{apartment_id}?month=2026-08")
    assert "200\u00a0Kč" in charged.text

    response = _decide(client, apartment_id, guest_ids[0], "")

    assert response.status_code == 200
    stored = db.query_one("SELECT * FROM guest WHERE id = ?", (guest_ids[0],))
    assert stored["fee_host_decision"] is None
    assert "Exempt — under 18" in response.text
    assert "200\u00a0Kč" not in response.text


def test_a_guest_of_another_owner_cannot_be_decided(host):
    client, owner_id, entity_id = host
    apartment_id = _property(owner_id, entity_id, "Detail Demo")
    _stay(apartment_id, "2026-08-10", "2026-08-14", [{}])
    other_id = auth.create_account(
        "stay-fee-detail-other",
        PASSWORD,
        "Other Demo",
        role="host",
        must_change_password=False,
    )
    other_entity_id = db.insert("legal_entity", {
        "name": "Other Demo s.r.o.",
        "owner_user_id": other_id,
        "created_at": db.utcnow(),
    })
    other_apartment = _property(other_id, other_entity_id, "Private Other Demo")
    _, other_guests = _stay(other_apartment, "2026-08-10", "2026-08-14", [{}])

    response = client.post(
        "/stay-fees/guest-decision",
        data={
            "_csrf": _csrf(client),
            "guest_id": other_guests[0],
            "apartment_id": apartment_id,
            "month": "2026-08",
            "decision": "exempt",
            "reason": "ZTP/P card checked",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert "This guest no longer exists." in unquote(response.headers["location"])
    stored = db.query_one("SELECT * FROM guest WHERE id = ?", (other_guests[0],))
    assert stored["fee_host_decision"] is None


def test_exactly_one_primary_button_when_the_report_is_ready(host):
    client, owner_id, entity_id = host
    apartment_id = _property(owner_id, entity_id, "Detail Demo")
    _stay(apartment_id, "2026-08-10", "2026-08-14", [{}])

    response = client.get(f"/stay-fees/{apartment_id}?month=2026-08")

    assert response.status_code == 200
    assert response.text.count("btn accent primary") == 1
    assert 'class="btn accent primary" href="/stay-fees/' in response.text
    assert "Download PDF" in response.text


def test_a_blocked_report_has_no_primary_button(host):
    client, owner_id, entity_id = host
    apartment_id = _property(owner_id, entity_id, "Detail Demo", vs=None)
    _stay(apartment_id, "2026-08-10", "2026-08-14", [{}])

    response = client.get(f"/stay-fees/{apartment_id}?month=2026-08")

    assert response.status_code == 200
    assert "btn accent primary" not in response.text
    assert "Add the variable symbol the council gave you." in response.text
    assert f'href="/apartments/{apartment_id}#stay-fee-settings"' in response.text


def test_the_page_renders_no_placeholder_or_raw_key(host):
    client, owner_id, entity_id = host
    apartment_id = _property(owner_id, entity_id, "Detail Demo")
    _stay(apartment_id, "2026-08-10", "2026-08-14", [{}])

    response = client.get(f"/stay-fees/{apartment_id}?month=2026-08")

    assert response.status_code == 200
    assert "undefined" not in response.text
    assert "stay_fees." not in response.text
    assert "{{" not in response.text
