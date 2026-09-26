"""Stay-fee guest form (step 6) and stay page (step 7).

The Form and Stay-page rows of docs/plans/PLAN_POPLATEK_Z_POBYTU.md §14.
"""
from __future__ import annotations

import base64
from datetime import timedelta

from fastapi.testclient import TestClient

from app import claim, db
from app.main import app
from app.routes import guest
from tests.conftest import complete_guest_claim

SIGNATURE = "data:image/png;base64," + base64.b64encode(
    bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
        "890000000a49444154789c6300010000050001od7a1f0000000049454e44ae42"
        "6082".replace("od", "0d")
    )
).decode()

TOKEN = "stayfeeguests"


def _cleanup():
    apartment = db.query_one("SELECT * FROM apartment WHERE permalink_token = ?", (TOKEN,))
    if not apartment:
        return
    db.execute(
        "DELETE FROM guest WHERE reservation_id IN "
        "(SELECT id FROM reservation WHERE apartment_id = ?)",
        (apartment["id"],),
    )
    db.execute("DELETE FROM reservation WHERE apartment_id = ?", (apartment["id"],))
    db.execute("DELETE FROM apartment WHERE id = ?", (apartment["id"],))


def _make(rate: int = 50):
    db.init_db()
    _cleanup()
    now = db.utcnow()
    today = claim.prague_today()
    apartment_id = db.insert(
        "apartment",
        {
            "internal_name": "Fee guest flat",
            "permalink_token": TOKEN,
            "permalink_window_days": 14,
            "default_purpose": "10",
            "automation_mode": "manual",
            "stay_fee_rate_czk": rate,
            "addr_obec": "Praha",
            "active": 1,
            "created_at": now,
        },
    )
    reservation_id = db.insert(
        "reservation",
        {
            "apartment_id": apartment_id,
            "source": "booking",
            "uid": "fee-guest-1",
            "date_from": today.isoformat(),
            "date_to": (today + timedelta(days=4)).isoformat(),
            "status": "active",
            "created_at": now,
            "updated_at": now,
        },
    )
    return apartment_id, reservation_id


def _form(**over):
    data = {
        "surname": "Smith",
        "first_name": "John Paul",
        "birth_date": "1.1.1990",
        "nationality": "GBR",
        "doc_number": "P1234567",
        "res_street": "Baker Street 221B",
        "res_city": "London",
        "res_country": "GBR",
        "purpose": "10",
        "party_size": "1",
        "signature": SIGNATURE,
        "legal_ack": "1",
    }
    data.update(over)
    return data


def _open_form(rate: int):
    _apt, res = _make(rate)
    browser = TestClient(app)
    browser.cookies.set(guest.LANG_COOKIE, "en")
    complete_guest_claim(browser, TOKEN, res, party_size=1)
    return browser, res


def _step_one(html: str) -> str:
    start = html.index('data-step-title="Your details"')
    end = html.index('data-step-title="Permanent home address"', start)
    return html[start:end]


def test_rate_zero_renders_no_doc_type_and_no_optional_row():
    try:
        browser, res = _open_form(0)
        page = browser.get(f"/l/{TOKEN}/{res}/new", follow_redirects=True)
        assert page.status_code == 200
        assert 'id="doc_type"' not in page.text
        assert "g-more" not in page.text
    finally:
        _cleanup()


def test_rate_50_renders_both_inside_step_one_and_adds_no_step():
    try:
        browser, res = _open_form(0)
        off = browser.get(f"/l/{TOKEN}/{res}/new", follow_redirects=True).text
        _cleanup()
        browser, res = _open_form(50)
        on = browser.get(f"/l/{TOKEN}/{res}/new", follow_redirects=True).text
        assert 'id="doc_type"' in on
        assert "g-more" in on
        step_one = _step_one(on)
        assert 'id="doc_type"' in step_one
        assert "g-more" in step_one
        # No new wizard step: the two additions live inside step 1.
        assert on.count("data-guest-step") == off.count("data-guest-step")
    finally:
        _cleanup()


def test_missing_doc_type_is_rejected_when_the_fee_is_on():
    try:
        browser, res = _open_form(50)
        response = browser.post(
            f"/l/{TOKEN}/{res}/save", data=_form(), follow_redirects=False
        )
        assert response.status_code == 422
        assert "Choose the type of your document" in response.text
        assert (
            db.query_one("SELECT 1 AS x FROM guest WHERE reservation_id = ?", (res,))
            is None
        )
    finally:
        _cleanup()


def test_child_in_parent_passport_stores_the_passport_type():
    try:
        browser, res = _open_form(50)
        response = browser.post(
            f"/l/{TOKEN}/{res}/save",
            data=_form(doc_number="", child_in_passport="1", parent_doc_number="XY987654"),
            follow_redirects=False,
        )
        assert response.status_code == 303, response.text
        row = db.query_one("SELECT * FROM guest WHERE reservation_id = ?", (res,))
        assert row["doc_type"] == "pas"
    finally:
        _cleanup()
