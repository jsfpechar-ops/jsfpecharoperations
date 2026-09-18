"""Guest claim, magic-link confirmation, and staging-safe mail."""
from __future__ import annotations

import base64
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
    current, _past, _far, _apartment_id = _seed()
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


def test_passport_upload_requirement_is_retired():
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
        assert reporting.guest_needs_passport_photo(guest, apartment) is False
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


def test_incomplete_guest_stays_open_after_check_in_and_host_is_notified(monkeypatch):
    current, _past, _far, _apartment_id = _seed()
    check_in = claim.prague_today()
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
        assert notified["locked"] == 0
        assert not claim.ensure_row(current)["guest_access_locked_at"]
        assert claim.guest_access_open(reservation, claim.ensure_row(current))
        host_mail = db.query_one(
            "SELECT * FROM console_mail_log WHERE subject LIKE 'Incomplete registration:%'"
        )
        assert host_mail
        assert "registration link" in host_mail["body_text"]
        assert "24-hour grace period" not in host_mail["body_text"]

        next_day = datetime.combine(check_in + timedelta(days=1), time(0, 1))
        clock[0] = next_day
        later = claim.sweep_reminders()
        assert later["locked"] == 0
        assert claim.guest_access_open(reservation, claim.ensure_row(current))
        assert not claim.ensure_row(current)["guest_access_locked_at"]

        claim.lock_guest_access(current)
        assert not claim.guest_access_open(reservation, claim.ensure_row(current))
        claim.reopen_guest_access(current)
        assert claim.guest_access_open(reservation, claim.ensure_row(current))
    finally:
        db.execute("DELETE FROM alert WHERE reservation_id = ?", (current,))
        db.execute("DELETE FROM console_mail_log")
        db.execute("DELETE FROM email_outbox")
        _cleanup()


def test_incomplete_past_stay_remains_reachable_via_stay_link():
    """Apartment picker hides past arrivals; stay-specific link stays open."""
    current, past, _far, _apartment_id = _seed()
    try:
        # Leave only a past incomplete stay in this apartment's calendar window.
        db.update(
            "reservation",
            current,
            {
                "date_from": (claim.prague_today() + timedelta(days=10)).isoformat(),
                "date_to": (claim.prague_today() + timedelta(days=13)).isoformat(),
            },
        )
        browser = TestClient(app)
        address = "forgotten@claim.test"
        complete_guest_claim(browser, TOKEN, past, email=address, party_size=1)

        apartment_landing = TestClient(app).get(f"/l/{TOKEN}")
        assert apartment_landing.status_code == 200
        assert "There are no upcoming stays to fill in right now." in apartment_landing.text
        assert f"/l/{TOKEN}/{past}" not in apartment_landing.text

        stay = browser.get(f"/l/{TOKEN}/{past}", follow_redirects=True)
        assert stay.status_code == 200
        assert "That stay is no longer open for registration" not in stay.text

        # Confirmed device can also recover via the apartment link.
        recovered = browser.get(f"/l/{TOKEN}", follow_redirects=True)
        assert recovered.status_code == 200
        assert "That stay is no longer open for registration" not in recovered.text

        stranger = TestClient(app).get(f"/l/{TOKEN}/{past}")
        assert stranger.status_code == 200
        assert mail.mask_email(address) in stranger.text
        assert address not in stranger.text
        assert f"/l/{TOKEN}/{past}" not in TestClient(app).get(f"/l/{TOKEN}").text

        claim.lock_guest_access(past)
        locked = browser.get(f"/l/{TOKEN}/{past}")
        assert locked.status_code == 404
    finally:
        _cleanup()


def test_completed_past_stay_is_not_exposed_on_bare_stay_link():
    current, past, _far, _apartment_id = _seed()
    try:
        db.update(
            "reservation",
            current,
            {
                "date_from": (claim.prague_today() + timedelta(days=10)).isoformat(),
                "date_to": (claim.prague_today() + timedelta(days=13)).isoformat(),
            },
        )
        browser = TestClient(app)
        complete_guest_claim(browser, TOKEN, past, email="done@claim.test", party_size=1)
        now = db.utcnow()
        signature = "data:image/png;base64," + base64.b64encode(
            bytes.fromhex(
                "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
                "890000000a49444154789c63000100000500010d0a1f0000000049454e44ae42"
                "6082"
            )
        ).decode()
        db.insert(
            "guest",
            {
                "reservation_id": past,
                "surname": "Guest",
                "first_name": "Done",
                "birth_date": "01011990",
                "nationality": "DEU",
                "doc_number": "C1234567",
                "res_street": "Street 1",
                "res_city": "Berlin",
                "res_country": "DEU",
                "purpose": "10",
                "is_lead": 1,
                "entered_by": "guest",
                "signature_png": signature,
                "signed_at": now,
                "submit_state": reporting.PENDING,
                "created_at": now,
                "updated_at": now,
            },
        )
        db.update("reservation", past, {"declared_guests": 1, "updated_at": now})
        reservation = db.query_one("SELECT * FROM reservation WHERE id = ?", (past,))
        progress = reporting.reservation_progress(reservation)
        assert progress["filled"] >= 1
        assert not progress["incomplete"]

        stranger = TestClient(app).get(f"/l/{TOKEN}/{past}")
        assert stranger.status_code == 404

        owner = browser.get(f"/l/{TOKEN}/{past}", follow_redirects=True)
        assert owner.status_code == 200
        assert "That stay is no longer open for registration" not in owner.text
    finally:
        _cleanup()


def test_incomplete_claimed_guest_receives_one_day_before_reminder(monkeypatch):
    current, _past, _far, _apartment_id = _seed()
    today = claim.prague_today()
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

        claim.lock_guest_access(current)
        locked = owner.get(f"/l/{TOKEN}/{current}")
        assert locked.status_code == 404
        assert address not in locked.text
    finally:
        _cleanup()
