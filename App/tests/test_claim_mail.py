"""Guest claim, magic-link confirmation, and staging-safe mail."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta

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
            "guest_message": "Welcome to Claim Facility.\nPlease complete this before arrival.",
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


def test_guest_pages_show_host_contact_not_ubyhost_support():
    current, _past, _far, _apartment_id = _seed()
    try:
        browser = TestClient(app)
        claim_page = browser.get(f"/l/{TOKEN}/{current}")
        assert claim_page.status_code == 200
        assert "Your host" in claim_page.text
        assert "If you need anything about this stay" in claim_page.text
        assert "Claim Mail" in claim_page.text
        assert "host@claim.test" in claim_page.text
        assert "+420111222333" in claim_page.text
        assert "mailto:host@claim.test" in claim_page.text
        assert "mailto:support@ubyhost.com" not in claim_page.text

        complete_guest_claim(browser, TOKEN, current, party_size=1)
        form = browser.get(f"/l/{TOKEN}/{current}/new")
        assert form.status_code == 200
        assert "Your host" in form.text
        assert "host@claim.test" in form.text
        assert "A message from your host" in form.text
        assert "Welcome to Claim Facility." in form.text
        assert "Please complete this before arrival." in form.text
        assert "mailto:support@ubyhost.com" not in form.text
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


def test_incomplete_guest_gets_24_hour_grace_and_host_is_notified(monkeypatch):
    current, _past, _far, _apartment_id = _seed()
    check_in = date.today()
    try:
        browser = TestClient(app)
        complete_guest_claim(browser, TOKEN, current, party_size=1)
        reservation = db.query_one("SELECT * FROM reservation WHERE id = ?", (current,))

        monkeypatch.setattr(mail, "backend_name", lambda: "console")
        monkeypatch.setattr(mail, "mail_enabled", lambda: True)
        clock = [datetime.combine(check_in, time(10, 0))]
        monkeypatch.setattr(
            claim.deadlines,
            "local_now",
            lambda now=None: now if now is not None else clock[0],
        )
        notified = claim.sweep_reminders()
        assert notified["host"] == 1
        assert not claim.ensure_row(current)["guest_access_locked_at"]
        assert claim.guest_access_open(
            reservation,
            claim.ensure_row(current),
            datetime.combine(check_in, time(23, 59)),
        )
        host_mail = db.query_one(
            "SELECT * FROM console_mail_log WHERE subject LIKE 'Incomplete registration:%'"
        )
        assert host_mail
        assert "24-hour grace period" in host_mail["body_text"]

        after_grace = datetime.combine(check_in + timedelta(days=1), time(0, 1))
        clock[0] = after_grace
        expired = claim.sweep_reminders()
        assert expired["locked"] == 1
        assert not claim.guest_access_open(reservation, claim.ensure_row(current))

        claim.reopen_guest_access(current)
        assert claim.guest_access_open(reservation, claim.ensure_row(current))
    finally:
        db.execute("DELETE FROM alert WHERE reservation_id = ?", (current,))
        db.execute("DELETE FROM console_mail_log")
        db.execute("DELETE FROM email_outbox")
        _cleanup()


def test_incomplete_guest_does_not_receive_day_before_reminder(monkeypatch):
    current, _past, _far, _apartment_id = _seed()
    today = date.today()
    try:
        db.update(
            "reservation",
            current,
            {
                "date_from": (today + timedelta(days=1)).isoformat(),
                "date_to": (today + timedelta(days=4)).isoformat(),
            },
        )
        browser = TestClient(app)
        complete_guest_claim(
            browser, TOKEN, current, email="guest-no-reminder@claim.test", party_size=1
        )
        monkeypatch.setattr(mail, "backend_name", lambda: "console")
        monkeypatch.setattr(mail, "mail_enabled", lambda: True)
        monkeypatch.setattr(
            claim.deadlines,
            "local_now",
            lambda now=None: now or datetime.combine(today, time(10, 0)),
        )

        summary = claim.sweep_reminders()

        assert summary["host"] == 0
        assert "reminder_guest" not in mail.KINDS
        assert not db.query_one(
            "SELECT 1 AS x FROM console_mail_log WHERE to_email = ?",
            ("guest-no-reminder@claim.test",),
        )
    finally:
        db.execute("DELETE FROM alert WHERE reservation_id = ?", (current,))
        db.execute("DELETE FROM console_mail_log")
        db.execute("DELETE FROM email_outbox")
        _cleanup()
