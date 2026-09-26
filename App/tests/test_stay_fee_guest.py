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
    if apartment:
        db.execute(
            "DELETE FROM guest WHERE reservation_id IN "
            "(SELECT id FROM reservation WHERE apartment_id = ?)",
            (apartment["id"],),
        )
        db.execute("DELETE FROM reservation WHERE apartment_id = ?", (apartment["id"],))
        db.execute("DELETE FROM apartment WHERE id = ?", (apartment["id"],))
    db.execute("DELETE FROM legal_entity WHERE name = ?", ("Fee Entity",))


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


# --- the stay page ---------------------------------------------------------

IBAN = "CZ9106000000000000000123"
LINK = "https://paypal.me/fee"


def _make_full(*, rate=50, policy="on", expected=3, link="", cash=0, paid=False):
    db.init_db()
    _cleanup()
    now = db.utcnow()
    today = claim.prague_today()
    entity_id = db.insert(
        "legal_entity",
        {"name": "Fee Entity", "bank_account": "123/0600", "iban": IBAN, "created_at": now},
    )
    apartment_id = db.insert(
        "apartment",
        {
            "legal_entity_id": entity_id,
            "internal_name": "Fee guest flat",
            "permalink_token": TOKEN,
            "permalink_window_days": 14,
            "default_purpose": "10",
            "automation_mode": "manual",
            "stay_fee_rate_czk": rate,
            "stay_fee_policy": policy,
            "stay_fee_payment_link": link or None,
            "stay_fee_cash": cash,
            "addr_obec": "Praha",
            "active": 1,
            "created_at": now,
        },
    )
    values = {
        "apartment_id": apartment_id,
        "source": "booking",
        "uid": "fee-guest-stay",
        "date_from": today.isoformat(),
        "date_to": (today + timedelta(days=4)).isoformat(),
        "status": "active",
        "created_at": now,
        "updated_at": now,
    }
    if expected is not None:
        values["expected_guests_override"] = expected
    if paid:
        values["stay_fee_paid_at"] = now
        values["stay_fee_paid_amount_czk"] = 600
    reservation_id = db.insert("reservation", values)
    return apartment_id, reservation_id


def _sign(browser, res, *, nationality="GBR", fee_claim=None, n=1):
    for i in range(n):
        page = browser.get(f"/l/{TOKEN}/{res}/new", follow_redirects=True)
        assert page.status_code == 200, page.text
        data = _form(
            surname=f"Guest{i + 1}",
            first_name=f"Person{i + 1}",
            doc_number=f"P100000{i}",
            nationality=nationality,
            doc_type="op" if nationality == "CZE" else "pas",
        )
        if fee_claim:
            data["fee_claim"] = fee_claim
        response = browser.post(
            f"/l/{TOKEN}/{res}/save", data=data, follow_redirects=False
        )
        assert response.status_code == 303, response.text


def _open_stay(*, expected=3, **kw):
    _apt, res = _make_full(expected=expected, **kw)
    browser = TestClient(app)
    browser.cookies.set(guest.LANG_COOKIE, "en")
    complete_guest_claim(browser, TOKEN, res, party_size=expected or 1)
    return browser, res


def test_partial_registration_shows_only_the_so_far_line():
    try:
        browser, res = _open_stay(expected=3)
        _sign(browser, res, n=2)
        page = browser.get(f"/l/{TOKEN}/{res}", follow_redirects=True)
        assert 'class="g-fee-soon"' in page.text
        assert "g-card g-fee" not in page.text
        assert "g-fee-qr" not in page.text
    finally:
        _cleanup()


def test_full_registration_shows_one_card_one_qr_and_the_bank_details():
    try:
        browser, res = _open_stay(expected=3)
        _sign(browser, res, n=3)
        page = browser.get(f"/l/{TOKEN}/{res}", follow_redirects=True)
        assert page.text.count('class="g-card g-fee"') == 1
        assert page.text.count('class="g-fee-qr"') == 1
        assert "data:image/png;base64" in page.text
        assert "600" in page.text  # 3 people x 4 nights x 50 Kč
        assert 'download="qr-platba-8' in page.text
        # Copy inputs hold the raw IBAN (no spaces) and the VS.
        assert f'value="{IBAN}"' in page.text
        assert f'value="8{str(res).zfill(9)}"' in page.text
    finally:
        _cleanup()


def test_cze_guest_sees_the_qr_before_the_online_button():
    try:
        browser, res = _open_stay(expected=1, link=LINK)
        _sign(browser, res, nationality="CZE", n=1)
        page = browser.get(f"/l/{TOKEN}/{res}", follow_redirects=True)
        assert page.text.index("g-fee-qr") < page.text.index('target="_blank"')
    finally:
        _cleanup()


def test_foreign_guest_sees_the_online_button_before_the_qr():
    try:
        browser, res = _open_stay(expected=1, link=LINK)
        _sign(browser, res, nationality="GBR", n=1)
        page = browser.get(f"/l/{TOKEN}/{res}", follow_redirects=True)
        assert page.text.index('target="_blank"') < page.text.index("g-fee-qr")
    finally:
        _cleanup()


def test_a_claim_does_not_change_the_total_and_never_shows_on_the_page():
    try:
        browser, res = _open_stay(expected=1)
        _sign(browser, res, n=1, fee_claim="disability_card")
        page = browser.get(f"/l/{TOKEN}/{res}", follow_redirects=True)
        assert "200" in page.text  # 1 person x 4 nights x 50 Kč, unchanged
        assert "exempt" not in page.text
        assert "osvobozen" not in page.text
        assert "ZTP/P" not in page.text
    finally:
        _cleanup()


def test_policy_off_shows_nothing():
    try:
        browser, res = _open_stay(expected=1, policy="off")
        _sign(browser, res, n=1)
        page = browser.get(f"/l/{TOKEN}/{res}", follow_redirects=True)
        assert "g-card g-fee" not in page.text
        assert "g-fee-soon" not in page.text
        assert "Local stay fee" not in page.text
    finally:
        _cleanup()


def test_paid_shows_only_the_thank_you_line_and_no_qr():
    try:
        browser, res = _open_stay(expected=1, paid=True)
        _sign(browser, res, n=1)
        page = browser.get(f"/l/{TOKEN}/{res}", follow_redirects=True)
        assert "paid. Thank you" in page.text
        assert "g-fee-qr" not in page.text
    finally:
        _cleanup()


# --- the completion e-mail -------------------------------------------------


def _completion_mail(res, lang="en"):
    from app import claim

    apartment = db.query_one(
        "SELECT * FROM apartment WHERE permalink_token = ?", (TOKEN,)
    )
    reservation = db.query_one("SELECT * FROM reservation WHERE id = ?", (res,))
    return claim._guest_mail_content(
        "completion", apartment, reservation, lang=lang, stay_url="http://example.test/x"
    )


def test_completion_mail_carries_the_total_iban_and_vs():
    try:
        browser, res = _open_stay(expected=1)
        _sign(browser, res, n=1)
        mail = _completion_mail(res)
        assert "200" in mail["text"]
        assert "IBAN" in mail["text"]
        assert "CZ91 0600 0000 0000 0000 0123" in mail["text"]
        assert f"8{str(res).zfill(9)}" in mail["text"]
    finally:
        _cleanup()


def test_completion_mail_has_no_fee_facts_when_the_policy_is_off():
    try:
        browser, res = _open_stay(expected=1, policy="off")
        _sign(browser, res, n=1)
        mail = _completion_mail(res)
        assert IBAN not in mail["text"]
        assert "Local stay fee" not in mail["text"]
    finally:
        _cleanup()


def test_completion_mail_has_no_fee_facts_when_the_rate_is_zero():
    try:
        browser, res = _open_stay(expected=1, rate=0)
        _sign(browser, res, n=1)
        mail = _completion_mail(res)
        assert IBAN not in mail["text"]
        assert "Local stay fee" not in mail["text"]
    finally:
        _cleanup()


# --- legal notice and privacy ----------------------------------------------


def test_legal_notice_and_privacy_show_the_fee_only_when_the_rate_is_positive():
    try:
        browser, res = _open_stay(expected=1, rate=50)
        form = browser.get(f"/l/{TOKEN}/{res}/new", follow_redirects=True)
        assert "Act No. 565/1990" in form.text
        privacy = browser.get(f"/l/{TOKEN}/privacy")
        assert "Stay-fee register" in privacy.text

        _cleanup()
        browser, res = _open_stay(expected=1, rate=0)
        form = browser.get(f"/l/{TOKEN}/{res}/new", follow_redirects=True)
        assert "Act No. 565/1990" not in form.text
        privacy = browser.get(f"/l/{TOKEN}/privacy")
        assert "Stay-fee register" not in privacy.text
    finally:
        _cleanup()

