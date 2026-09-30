"""Host-only stay-fee list page."""
from __future__ import annotations

import re
import secrets
from datetime import date
from html import unescape

import pytest
from fastapi.testclient import TestClient

from app import auth, claim, db
from app.main import app

PASSWORD = f"Stay-fee-list-{secrets.token_urlsafe(12)}-9"
SIGNATURE = "data:image/png;base64,AAAA"


def _cleanup():
    for user in db.query(
        "SELECT id FROM user_account WHERE username LIKE 'stay-fee-list-%'"
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
        "stay-fee-list-owner",
        PASSWORD,
        "List Demo",
        role="host",
        must_change_password=False,
    )
    entity_id = db.insert("legal_entity", {
        "name": "List Demo s.r.o.",
        "owner_user_id": owner_id,
        "created_at": db.utcnow(),
    })
    client = TestClient(app)
    logged_in = client.post(
        "/login?lang=en",
        data={"username": "stay-fee-list-owner", "password": PASSWORD},
        follow_redirects=False,
    )
    assert logged_in.status_code == 303
    try:
        yield client, owner_id, entity_id
    finally:
        _cleanup()


def _property(owner_id, entity_id, name, *, rate=50, cadence="monthly", city="Praha 3"):
    return db.insert("apartment", {
        "internal_name": name,
        "owner_user_id": owner_id,
        "legal_entity_id": entity_id,
        "addr_obec": city,
        "stay_fee_rate_czk": rate,
        "stay_fee_cadence": cadence,
        "stay_fee_vs": "123456",
        "stay_fee_authority_name": "Městský úřad",
        "created_at": db.utcnow(),
    })


def _stay(apartment_id, date_from, date_to, guests):
    now = db.utcnow()
    reservation_id = db.insert("reservation", {
        "apartment_id": apartment_id,
        "uid": f"stay-fee-list-{apartment_id}-{date_from}",
        "date_from": date_from,
        "date_to": date_to,
        "status": "active",
        "created_at": now,
        "updated_at": now,
    })
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
        db.insert("guest", guest)


def _row_for(html, apartment_id):
    match = re.search(
        rf'<tr class="clickable-row" data-href="/stay-fees/{apartment_id}\?month=2026-08".*?</tr>',
        html,
        re.DOTALL,
    )
    assert match, f"missing list row for apartment {apartment_id}"
    text = unescape(re.sub(r"<[^>]+>", " ", match.group(0)))
    return re.sub(r"\s+", " ", text).strip()


def test_login_is_required():
    db.init_db()
    _cleanup()
    auth.create_account(
        "stay-fee-list-owner",
        PASSWORD,
        "List Demo",
        role="host",
        must_change_password=False,
    )
    try:
        response = TestClient(app).get("/stay-fees", follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"].startswith("/login")
    finally:
        _cleanup()


def test_no_active_property_shows_empty_state_without_primary_button(host):
    client, owner_id, entity_id = host
    _property(owner_id, entity_id, "Disabled Demo", rate=0)

    response = client.get("/stay-fees?month=2026-08")

    assert response.status_code == 200
    assert "No property has a stay fee yet" in response.text
    assert 'href="/apartments"' in response.text
    assert "btn accent primary" not in response.text


def test_monthly_and_quarterly_rows_show_czech_periods_and_totals(host):
    client, owner_id, entity_id = host
    monthly = _property(owner_id, entity_id, "Monthly Demo", rate=50)
    quarterly = _property(
        owner_id, entity_id, "Quarterly Demo", rate=21, cadence="quarterly"
    )
    _stay(monthly, "2026-08-10", "2026-08-14", [{}, {"birth_date": "01012015"}])
    _stay(quarterly, "2026-07-10", "2026-07-12", [{}])

    response = client.get("/stay-fees?month=2026-08&lang=cs")

    assert response.status_code == 200
    assert "Srpen 2026" in _row_for(response.text, monthly)
    assert "4 4 200 Kč" in _row_for(response.text, monthly)
    assert "3. čtvrtletí 2026" in _row_for(response.text, quarterly)
    assert "2 0 42 Kč" in _row_for(response.text, quarterly)


def test_another_owners_properties_never_appear(host):
    client, owner_id, entity_id = host
    _property(owner_id, entity_id, "My Demo")
    other_id = auth.create_account(
        "stay-fee-list-other",
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
    _property(other_id, other_entity_id, "Private Other Demo")

    response = client.get("/stay-fees?month=2026-08")

    assert response.status_code == 200
    assert "My Demo" in response.text
    assert "Private Other Demo" not in response.text


def test_chips_mark_the_selected_month(host):
    client, _owner_id, _entity_id = host

    response = client.get("/stay-fees?month=2026-08&lang=cs")

    assert response.status_code == 200
    assert '<a class="chip on"' in response.text
    assert 'href="?month=2026-08" aria-current="page"' in response.text
    assert "Červenec 2026" in response.text
    assert "Srpen 2026" in response.text
    assert "Září 2026" in response.text


def test_future_month_redirects_to_default(host):
    client, _owner_id, _entity_id = host

    response = client.get("/stay-fees?month=2026-10", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/stay-fees?month=2026-08"


def test_sidebar_link_exists(host):
    client, _owner_id, _entity_id = host

    response = client.get("/stay-fees")

    assert response.status_code == 200
    assert 'href="/stay-fees"' in response.text
    assert "Stay fee" in response.text


def test_command_palette_lists_stay_fee_page(host):
    client, _owner_id, _entity_id = host

    response = client.get("/api/command-palette")

    assert response.status_code == 200
    assert any(item["url"] == "/stay-fees" for item in response.json()["items"])
