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
        db.execute(
            "DELETE FROM rate_limit_event WHERE scope LIKE 'claim_%' OR scope = 'claim_start'"
        )
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
    db.execute(
        "DELETE FROM rate_limit_event WHERE scope LIKE 'claim_%' OR scope = 'claim_start'"
    )


def _seed():
    db.init_db()
    _cleanup()
    now = db.utcnow()
    today = claim.prague_today()
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


def test_claim_form_and_privacy_notice_disclose_email_and_cookies():
    current, _past, _far, apartment_id = _seed()
    try:
        browser = TestClient(app)
        claim_page = browser.get(f"/l/{TOKEN}/{current}")
        assert "one reminder if the forms are incomplete" in claim_page.text
        assert "Strictly necessary cookies" in claim_page.text
        assert "no advertising or analytics cookies" in claim_page.text
        assert "How your data is handled" in claim_page.text

        privacy = browser.get(f"/l/{TOKEN}/privacy")
        assert privacy.status_code == 200
        assert "E-mail messages and masking" in privacy.text
        assert "Necessary cookies" in privacy.text
        assert "normally deleted after 14 days" in privacy.text
        assert "Temporary passport photo or PDF" not in privacy.text

        db.update(
            "apartment",
            apartment_id,
            {"passport_photo_policy": "required_foreign"},
        )
        policy_privacy = browser.get(f"/l/{TOKEN}/privacy")
        assert "Temporary passport photo or PDF" in policy_privacy.text
    finally:
        _cleanup()


def test_disabled_mail_uses_pin_date_form_without_collecting_email(monkeypatch):
    current, _past, _far, _apartment_id = _seed()
    monkeypatch.setattr(mail, "mail_enabled", lambda: False)
    try:
        browser = TestClient(app)
        form = browser.get(f"/l/{TOKEN}/{current}", follow_redirects=True)
        assert form.status_code == 200
        assert 'name="surname"' in form.text
        assert 'name="party_size"' in form.text
        assert 'name="guest_email"' not in form.text
        assert "Send me the form link" not in form.text
        assert "passport_photo" not in form.text

        party = browser.post(
            f"/l/{TOKEN}/{current}/party",
            data={"party_size": "2"},
            follow_redirects=False,
        )
        assert party.status_code == 303
        assert db.query_one(
            "SELECT declared_guests FROM reservation WHERE id = ?", (current,)
        )["declared_guests"] == 2

        privacy = browser.get(f"/l/{TOKEN}/privacy")
        assert "does not collect your e-mail" in privacy.text
        assert "E-mail messages and masking" not in privacy.text
        assert "Necessary cookies" in privacy.text
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


def test_incomplete_claimed_guest_receives_one_day_before_reminder(monkeypatch):
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
            browser, TOKEN, current, email="guest-reminder@claim.test", party_size=1
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
        assert summary["guest"] == 1
        reminder = db.query_one(
            "SELECT l.* FROM console_mail_log l "
            "JOIN email_outbox o ON o.id = l.outbox_id "
            "WHERE l.to_email = ? AND o.kind = 'reminder_guest'",
            ("guest-reminder@claim.test",),
        )
        assert reminder
        assert reminder["subject"] == "Please finish your guest registration"
        assert "only incomplete-registration reminder" in reminder["body_text"]

        claim.sweep_reminders()
        assert db.query_one(
            "SELECT COUNT(*) AS n FROM console_mail_log l "
            "JOIN email_outbox o ON o.id = l.outbox_id "
            "WHERE l.to_email = ? AND o.kind = 'reminder_guest'",
            ("guest-reminder@claim.test",),
        )["n"] == 1
    finally:
        db.execute("DELETE FROM alert WHERE reservation_id = ?", (current,))
        db.execute("DELETE FROM console_mail_log")
        db.execute("DELETE FROM email_outbox")
        _cleanup()


def test_guest_facing_assignment_masks_email_and_lock_hides_it():
    current, _past, _far, _apartment_id = _seed()
    address = "private-address@claim.test"
    try:
        owner = TestClient(app)
        complete_guest_claim(owner, TOKEN, current, email=address, party_size=1)

        public = TestClient(app).get(f"/l/{TOKEN}/{current}")
        assert public.status_code == 200
        assert mail.mask_email(address) in public.text
        assert address not in public.text
        assert "Claim Facility" in public.text
        assert "Your selected stay" in public.text
        assert "secure link sent to this address" in public.text
        assert "This is not my reservation" in public.text
        assert "host@claim.test" in public.text

        claim.lock_guest_access(current)
        locked = owner.get(f"/l/{TOKEN}/{current}")
        assert locked.status_code == 404
        assert address not in locked.text
    finally:
        _cleanup()


def test_provisional_claim_does_not_resend_same_email_without_resend_flag(monkeypatch):
    current, _past, _far, _apartment_id = _seed()
    monkeypatch.setattr(mail, "backend_name", lambda: "console")
    monkeypatch.setattr(mail, "mail_enabled", lambda: True)
    try:
        reservation = db.query_one("SELECT * FROM reservation WHERE id = ?", (current,))
        apartment = db.query_one("SELECT * FROM apartment WHERE permalink_token = ?", (TOKEN,))
        ok, err, secret = claim.start_claim(
            reservation,
            apartment,
            email="once@claim.test",
            party_size=1,
            lang="en",
        )
        assert ok and secret
        first_count = db.query_one(
            "SELECT COUNT(*) AS n FROM email_outbox WHERE kind IN ('claim','claim_resend')"
        )["n"]
        ok2, err2, secret2 = claim.start_claim(
            reservation,
            apartment,
            email="once@claim.test",
            party_size=1,
            lang="en",
            resend=False,
        )
        assert not ok2
        assert err2 == "already_sent"
        assert secret2 is None
        assert (
            db.query_one(
                "SELECT COUNT(*) AS n FROM email_outbox WHERE kind IN ('claim','claim_resend')"
            )["n"]
            == first_count
        )
    finally:
        db.execute("DELETE FROM console_mail_log")
        db.execute("DELETE FROM email_outbox")
        db.execute("DELETE FROM rate_limit_event")
        _cleanup()


def test_claim_resend_enforces_cooldown(monkeypatch):
    current, _past, _far, _apartment_id = _seed()
    monkeypatch.setattr(mail, "backend_name", lambda: "console")
    monkeypatch.setattr(mail, "mail_enabled", lambda: True)
    try:
        reservation = db.query_one("SELECT * FROM reservation WHERE id = ?", (current,))
        apartment = db.query_one("SELECT * FROM apartment WHERE permalink_token = ?", (TOKEN,))
        ok, err, _secret = claim.start_claim(
            reservation,
            apartment,
            email="cooldown@claim.test",
            party_size=1,
            lang="en",
        )
        assert ok, err
        ok2, err2, _ = claim.start_claim(
            reservation,
            apartment,
            email="cooldown@claim.test",
            party_size=1,
            lang="en",
            resend=True,
        )
        assert not ok2
        assert err2 == "cooldown"
    finally:
        db.execute("DELETE FROM console_mail_log")
        db.execute("DELETE FROM email_outbox")
        db.execute("DELETE FROM rate_limit_event")
        _cleanup()


def test_claim_mail_caps_recipient_and_reservation(monkeypatch):
    current, _past, _far, apartment_id = _seed()
    monkeypatch.setattr(mail, "backend_name", lambda: "console")
    monkeypatch.setattr(mail, "mail_enabled", lambda: True)
    monkeypatch.setattr(claim, "RESEND_COOLDOWN_SECONDS", 0)
    monkeypatch.setattr(claim, "CLAIM_MAIL_PER_RECIPIENT_MAX", 1)
    monkeypatch.setattr(claim, "CLAIM_MAIL_PER_RESERVATION_MAX", 3)
    try:
        apartment = db.query_one("SELECT * FROM apartment WHERE id = ?", (apartment_id,))
        reservation = db.query_one("SELECT * FROM reservation WHERE id = ?", (current,))
        addr = "capped@claim.test"
        ok, err, _ = claim.start_claim(
            reservation,
            apartment,
            email=addr,
            party_size=1,
            lang="en",
        )
        assert ok, err
        claim.release(current)
        reservation = db.query_one("SELECT * FROM reservation WHERE id = ?", (current,))
        ok2, err2, _ = claim.start_claim(
            reservation,
            apartment,
            email=addr,
            party_size=1,
            lang="en",
        )
        assert not ok2
        assert err2 == "recipient_rate"

        # Fresh addresses still hit the per-reservation cap (independent of recipient).
        db.execute(
            "DELETE FROM rate_limit_event WHERE scope = ?",
            ("claim_mail_reservation",),
        )
        monkeypatch.setattr(claim, "CLAIM_MAIL_PER_RECIPIENT_MAX", 10)
        monkeypatch.setattr(claim, "CLAIM_MAIL_PER_RESERVATION_MAX", 2)
        for index in range(2):
            claim.release(current)
            reservation = db.query_one("SELECT * FROM reservation WHERE id = ?", (current,))
            ok, err, _ = claim.start_claim(
                reservation,
                apartment,
                email=f"stay{index}@claim.test",
                party_size=1,
                lang="en",
            )
            assert ok, err
        claim.release(current)
        reservation = db.query_one("SELECT * FROM reservation WHERE id = ?", (current,))
        ok3, err3, _ = claim.start_claim(
            reservation,
            apartment,
            email="stay-extra@claim.test",
            party_size=1,
            lang="en",
        )
        assert not ok3
        assert err3 == "rate"
    finally:
        db.execute("DELETE FROM console_mail_log")
        db.execute("DELETE FROM email_outbox")
        db.execute("DELETE FROM rate_limit_event")
        _cleanup()


def test_party_post_does_not_enqueue_duplicate_claim_mail(monkeypatch):
    current, _past, _far, _apartment_id = _seed()
    monkeypatch.setattr(mail, "backend_name", lambda: "console")
    monkeypatch.setattr(mail, "mail_enabled", lambda: True)
    try:
        browser = TestClient(app)
        first = browser.post(
            f"/l/{TOKEN}/{current}/party",
            data={"party_size": "2", "guest_email": "victim-abuse@example.com"},
            follow_redirects=False,
        )
        assert first.status_code == 303
        assert "claim_sent=1" in first.headers["location"]
        second = browser.post(
            f"/l/{TOKEN}/{current}/party",
            data={"party_size": "2", "guest_email": "victim-abuse@example.com"},
            follow_redirects=False,
        )
        assert second.status_code == 303
        assert "claim_sent=1" in second.headers["location"]
        assert (
            db.query_one(
                "SELECT COUNT(*) AS n FROM email_outbox WHERE to_email = ?",
                ("victim-abuse@example.com",),
            )["n"]
            == 1
        )
    finally:
        db.execute("DELETE FROM console_mail_log")
        db.execute("DELETE FROM email_outbox")
        db.execute("DELETE FROM rate_limit_event")
        _cleanup()
