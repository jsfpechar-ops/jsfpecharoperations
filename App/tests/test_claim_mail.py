"""Guest claim, magic-link confirmation, and staging-safe mail."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app import claim, db, mail, reporting
from app.main import app
from tests.conftest import complete_guest_claim

TOKEN = "claimmailtok"


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
    db.execute(
        "DELETE FROM legal_entity WHERE name = ? AND id NOT IN "
        "(SELECT legal_entity_id FROM apartment WHERE legal_entity_id IS NOT NULL)",
        ("Claim Mail",),
    )


def _seed():
    db.init_db()
    _cleanup()
    now = db.utcnow()
    today = date.today()
    entity_id = db.insert(
        "legal_entity",
        {
            "name": "Claim Mail",
            "contact_email": "host@claim.test",
            "contact_phone": "+420111222333",
            "created_at": now,
        },
    )
    apartment_id = db.insert(
        "apartment",
        {
            "legal_entity_id": entity_id,
            "internal_name": "Claim flat",
            "uby_name": "Claim Facility",
            "permalink_token": TOKEN,
            "permalink_window_days": 2,
            "default_purpose": "10",
            "automation_mode": "scheduled",
            "submit_after_hours": 24,
            "active": 1,
            "created_at": now,
        },
    )
    current = db.insert(
        "reservation",
        {
            "apartment_id": apartment_id,
            "source": "airbnb",
            "uid": "claim-now",
            "date_from": today.isoformat(),
            "date_to": (today + timedelta(days=3)).isoformat(),
            "status": "active",
            "created_at": now,
            "updated_at": now,
        },
    )
    past = db.insert(
        "reservation",
        {
            "apartment_id": apartment_id,
            "source": "airbnb",
            "uid": "claim-past",
            "date_from": (today - timedelta(days=1)).isoformat(),
            "date_to": (today + timedelta(days=2)).isoformat(),
            "status": "active",
            "created_at": now,
            "updated_at": now,
        },
    )
    far = db.insert(
        "reservation",
        {
            "apartment_id": apartment_id,
            "source": "airbnb",
            "uid": "claim-far",
            "date_from": (today + timedelta(days=10)).isoformat(),
            "date_to": (today + timedelta(days=13)).isoformat(),
            "status": "active",
            "created_at": now,
            "updated_at": now,
        },
    )
    return current, past, far, apartment_id


def test_picker_hides_past_and_far_check_ins():
    current, past, far, _apartment_id = _seed()
    try:
        page = TestClient(app).get(f"/l/{TOKEN}", follow_redirects=True)
        assert page.status_code == 200
        assert f"/l/{TOKEN}/{current}" in page.text or "guest_email" in page.text
        assert f"/l/{TOKEN}/{past}" not in page.text
        assert f"/l/{TOKEN}/{far}" not in page.text
    finally:
        _cleanup()


def test_magic_link_get_does_not_assign():
    current, _past, _far, _apartment_id = _seed()
    try:
        browser = TestClient(app)
        reservation = db.query_one("SELECT * FROM reservation WHERE id = ?", (current,))
        apartment = db.query_one("SELECT * FROM apartment WHERE permalink_token = ?", (TOKEN,))
        ok, err, secret = claim.start_claim(
            reservation,
            apartment,
            email="guest@claim.test",
            party_size=2,
            lang="en",
        )
        assert ok, err
        opened = browser.get(f"/l/{TOKEN}/{current}/claim#c={secret}")
        assert opened.status_code == 200
        row = claim.ensure_row(current)
        assert row["state"] == "provisional"
        assert "Yes, this is my stay" in opened.text
        confirmed = browser.post(
            f"/l/{TOKEN}/{current}/claim/confirm",
            data={"secret": secret},
            follow_redirects=False,
        )
        assert confirmed.status_code == 303
        assert claim.ensure_row(current)["state"] == "claimed"
    finally:
        _cleanup()


def test_console_backend_logs_claim_link(monkeypatch):
    current, _past, _far, _apartment_id = _seed()
    try:
        monkeypatch.setattr(mail, "backend_name", lambda: "console")
        monkeypatch.setattr(mail, "mail_enabled", lambda: True)
        reservation = db.query_one("SELECT * FROM reservation WHERE id = ?", (current,))
        apartment = db.query_one("SELECT * FROM apartment WHERE permalink_token = ?", (TOKEN,))
        ok, err, secret = claim.start_claim(
            reservation,
            apartment,
            email="guest@claim.test",
            party_size=1,
            lang="en",
        )
        assert ok, err
        logged = db.query_one("SELECT * FROM console_mail_log ORDER BY id DESC")
        assert logged
        assert mail.extract_claim_secret(logged["body_text"]) == secret
        assert "#c=" in logged["body_text"]
    finally:
        db.execute("DELETE FROM console_mail_log")
        db.execute("DELETE FROM email_outbox")
        _cleanup()


def test_passport_policy_defaults_off():
    current, _past, _far, apartment_id = _seed()
    try:
        apartment = db.query_one("SELECT * FROM apartment WHERE id = ?", (apartment_id,))
        assert apartment["passport_photo_policy"] == "off"
        guest = {
            "nationality": "GBR",
            "reservation_id": current,
            "entered_by": "guest",
            "identity_verified_at": None,
        }
        assert reporting.guest_needs_passport_photo(guest, apartment) is False
        db.update("apartment", apartment_id, {"passport_photo_policy": "required_foreign"})
        apartment = db.query_one("SELECT * FROM apartment WHERE id = ?", (apartment_id,))
        assert reporting.guest_needs_passport_photo(guest, apartment) is True
    finally:
        _cleanup()


def test_host_can_release_and_reopen_claim():
    current, _past, _far, _apartment_id = _seed()
    try:
        browser = TestClient(app)
        complete_guest_claim(browser, TOKEN, current, party_size=1)
        claim.lock_guest_access(current)
        assert claim.ensure_row(current)["guest_access_locked_at"]
        claim.reopen_guest_access(current)
        assert not claim.ensure_row(current)["guest_access_locked_at"]
        claim.release(current)
        assert claim.ensure_row(current)["state"] == "unclaimed"
    finally:
        _cleanup()


def test_start_claim_rejects_invalid_email_and_party_size():
    current, _past, _far, _apartment_id = _seed()
    try:
        reservation = db.query_one("SELECT * FROM reservation WHERE id = ?", (current,))
        apartment = db.query_one("SELECT * FROM apartment WHERE permalink_token = ?", (TOKEN,))
        ok, err, secret = claim.start_claim(
            reservation, apartment, email="not-an-email", party_size=1, lang="en"
        )
        assert not ok and err == "bad_email" and secret is None
        ok, err, secret = claim.start_claim(
            reservation, apartment, email="guest@claim.test", party_size=0, lang="en"
        )
        assert not ok and err == "bad_party" and secret is None
        ok, err, secret = claim.start_claim(
            reservation, apartment, email="guest@claim.test", party_size=61, lang="en"
        )
        assert not ok and err == "bad_party" and secret is None
    finally:
        db.execute("DELETE FROM email_outbox")
        _cleanup()


def test_provisional_hold_blocks_a_different_email():
    current, _past, _far, _apartment_id = _seed()
    try:
        reservation = db.query_one("SELECT * FROM reservation WHERE id = ?", (current,))
        apartment = db.query_one("SELECT * FROM apartment WHERE permalink_token = ?", (TOKEN,))
        ok, err, _secret = claim.start_claim(
            reservation, apartment, email="first@claim.test", party_size=2, lang="en"
        )
        assert ok, err
        ok, err, secret = claim.start_claim(
            reservation, apartment, email="other@claim.test", party_size=2, lang="en"
        )
        assert not ok and err == "held" and secret is None
    finally:
        db.execute("DELETE FROM console_mail_log")
        db.execute("DELETE FROM email_outbox")
        _cleanup()


def test_expire_holds_returns_stale_provisional_to_unclaimed():
    current, _past, _far, _apartment_id = _seed()
    try:
        claim.ensure_row(current)
        stale = (datetime.now(timezone.utc) - timedelta(hours=1)).replace(microsecond=0).isoformat()
        db.execute(
            "UPDATE reservation_claim SET state = ?, email = ?, provisional_until = ?, "
            "token_hash = ?, updated_at = ? WHERE reservation_id = ?",
            (
                claim.PROVISIONAL,
                "guest@claim.test",
                stale,
                claim.token_hash("stale-secret"),
                db.utcnow(),
                current,
            ),
        )
        assert claim.expire_holds() == 1
        row = claim.ensure_row(current)
        assert row["state"] == claim.UNCLAIMED
        assert row["token_hash"] is None
        assert row["provisional_until"] is None
    finally:
        _cleanup()


def test_confirm_rejects_wrong_or_expired_secret():
    current, _past, _far, _apartment_id = _seed()
    try:
        reservation = db.query_one("SELECT * FROM reservation WHERE id = ?", (current,))
        ok, err, secret = claim.start_claim(
            reservation,
            db.query_one("SELECT * FROM apartment WHERE permalink_token = ?", (TOKEN,)),
            email="guest@claim.test",
            party_size=1,
            lang="en",
        )
        assert ok, err
        assert not claim.confirm(reservation, "wrong-secret")
        stale = (datetime.now(timezone.utc) - timedelta(minutes=5)).replace(microsecond=0).isoformat()
        db.execute(
            "UPDATE reservation_claim SET provisional_until = ? WHERE reservation_id = ?",
            (stale, current),
        )
        assert not claim.confirm(reservation, secret)
        # confirm() calls expire_holds() first, so an expired provisional becomes unclaimed.
        assert claim.ensure_row(current)["state"] == claim.UNCLAIMED
    finally:
        db.execute("DELETE FROM console_mail_log")
        db.execute("DELETE FROM email_outbox")
        _cleanup()


def test_expire_on_cancel_locks_guest_and_fails_queued_mail():
    current, _past, _far, apartment_id = _seed()
    try:
        reservation = db.query_one("SELECT * FROM reservation WHERE id = ?", (current,))
        claim.ensure_row(current)
        now = db.utcnow()
        outbox_id = db.insert(
            "email_outbox",
            {
                "idempotency_key": f"cancel-test:{current}",
                "kind": "claim",
                "reservation_id": current,
                "apartment_id": apartment_id,
                "to_email": "guest@claim.test",
                "subject": "test",
                "payload": "{}",
                "state": mail.QUEUED,
                "attempts": 0,
                "next_attempt_at": now,
                "created_at": now,
                "updated_at": now,
            },
        )
        claim.expire_on_cancel(reservation)
        row = claim.ensure_row(current)
        assert row["token_hash"] is None
        assert row["guest_access_locked_at"]
        outbox = db.query_one("SELECT * FROM email_outbox WHERE id = ?", (outbox_id,))
        assert outbox["state"] == mail.FAILED
    finally:
        db.execute("DELETE FROM console_mail_log")
        db.execute("DELETE FROM email_outbox")
        _cleanup()
