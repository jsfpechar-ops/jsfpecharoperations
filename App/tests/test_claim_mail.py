"""Guest claim, magic-link confirmation, and staging-safe mail."""
from __future__ import annotations

import base64
import json
import pathlib
import re
from datetime import datetime, time, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app import claim, config, db, i18n, mail, mail_notify, reporting
from app.routes import guest
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
        browser.cookies.set(guest.LANG_COOKIE, "en")
        claim_page = browser.get(f"/l/{TOKEN}/{current}")
        assert claim_page.status_code == 200
        assert "Your host" in claim_page.text
        assert "Questions? Contact your host." in claim_page.text
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


def test_separate_controller_does_not_change_guest_mail_reply_to(monkeypatch):
    current, _past, _far, apartment_id = _seed()
    controller_id = db.insert(
        "legal_entity",
        {
            "name": "Controller only",
            "contact_email": "privacy@controller.test",
            "created_at": db.utcnow(),
        },
    )
    db.update(
        "apartment",
        apartment_id,
        {"data_controller_entity_id": controller_id},
    )
    monkeypatch.setattr(mail, "backend_name", lambda: "console")
    monkeypatch.setattr(mail, "mail_enabled", lambda: True)
    try:
        reservation = db.query_one(
            "SELECT * FROM reservation WHERE id = ?", (current,)
        )
        apartment = db.query_one(
            "SELECT * FROM apartment WHERE id = ?", (apartment_id,)
        )
        ok, err, _secret = claim.start_claim(
            reservation,
            apartment,
            email="reply-to-check@claim.test",
            party_size=1,
            lang="en",
        )
        assert ok, err
        queued = db.query_one(
            "SELECT payload FROM email_outbox WHERE reservation_id = ? "
            "ORDER BY id DESC",
            (current,),
        )
        assert json.loads(queued["payload"])["reply_to"] == "host@claim.test"
    finally:
        db.execute("DELETE FROM console_mail_log")
        db.execute("DELETE FROM email_outbox")
        _cleanup()
        db.execute("DELETE FROM legal_entity WHERE id = ?", (controller_id,))


def test_claim_form_and_privacy_notice_disclose_email_and_cookies(monkeypatch):
    current, _past, _far, apartment_id = _seed()
    monkeypatch.setattr(config, "OPERATOR_NAME", "Release Operator s.r.o.")
    monkeypatch.setattr(config, "OPERATOR_ICO", "12345678")
    monkeypatch.setattr(config, "OPERATOR_ADDRESS", "Release Street 1, Prague")
    monkeypatch.setattr(config, "OPERATOR_EMAIL", "release-privacy@ubyhost.test")
    try:
        browser = TestClient(app)
        browser.cookies.set(guest.LANG_COOKIE, "en")
        claim_page = browser.get(f"/l/{TOKEN}/{current}")
        assert "We send your private link here." in claim_page.text
        assert "Only your group can open the forms." in claim_page.text
        assert "one reminder the day before arrival if forms are missing" in claim_page.text
        assert "a receipt (your host gets a copy)" in claim_page.text
        assert "Only necessary cookies" in claim_page.text
        assert "PIN access (7 days)" in claim_page.text
        assert "this stay (60 days)" in claim_page.text
        assert "No marketing." in claim_page.text
        assert "How your data is handled" in claim_page.text

        privacy = browser.get(f"/l/{TOKEN}/privacy")
        assert privacy.status_code == 200
        assert "E-mail messages and masking" in privacy.text
        assert "Necessary cookies" in privacy.text
        assert "Party size is used to determine whether every expected guest form is complete" in privacy.text
        assert "normally deleted after 14 days" in privacy.text
        assert "Release Operator s.r.o." in privacy.text
        # A-30: the guest notice names the operator but no longer prints the
        # UbyHost support address; guest questions go to the host/controller.
        assert "release-privacy@ubyhost.test" not in privacy.text
        assert "Temporary passport photo or PDF" not in privacy.text

        db.update(
            "apartment",
            apartment_id,
            {"passport_photo_policy": "required_foreign"},
        )
        policy_privacy = browser.get(f"/l/{TOKEN}/privacy")
        assert "Temporary passport photo or PDF" in policy_privacy.text
        assert "Restricted operator or infrastructure access" in policy_privacy.text
    finally:
        _cleanup()


def test_disabled_mail_uses_pin_date_form_without_collecting_email(monkeypatch):
    current, _past, _far, _apartment_id = _seed()
    monkeypatch.setattr(mail, "mail_enabled", lambda: False)
    try:
        browser = TestClient(app)
        browser.cookies.set(guest.LANG_COOKIE, "en")
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
        browser.cookies.set(guest.LANG_COOKIE, "en")
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


def _claim_secret(current, *, email="guest@claim.test", resend=False):
    reservation = db.query_one("SELECT * FROM reservation WHERE id = ?", (current,))
    apartment = db.query_one("SELECT * FROM apartment WHERE permalink_token = ?", (TOKEN,))
    ok, err, secret = claim.start_claim(
        reservation,
        apartment,
        email=email,
        party_size=2,
        lang="en",
        resend=resend,
    )
    assert ok, err
    return reservation, secret


def _age_claim(current, seconds):
    """Move the claim's clock back so the resend cooldown has elapsed."""
    stamp = (datetime.now(timezone.utc) - timedelta(seconds=seconds)).replace(
        microsecond=0
    ).isoformat()
    db.execute(
        "UPDATE reservation_claim SET updated_at = ? WHERE reservation_id = ?",
        (stamp, current),
    )


def _age_claimed_at(reservation_id: int, hours: int) -> None:
    stamp = (
        datetime.now(timezone.utc) - timedelta(hours=hours)
    ).replace(microsecond=0).isoformat()
    db.execute(
        "UPDATE reservation_claim SET claimed_at = ? WHERE reservation_id = ?",
        (stamp, reservation_id),
    )


def test_claim_secret_is_spent_by_the_confirmation():
    """The e-mailed secret confirms once; the cookie is the access after that."""
    current, _past, _far, _apartment_id = _seed()
    try:
        reservation, secret = _claim_secret(current)
        assert claim.confirm(reservation, secret)

        row = claim.ensure_row(current)
        assert row["state"] == "claimed"
        assert row["token_hash"] is None
        assert not claim.confirm(reservation, secret)
        assert not claim.confirm(reservation, secret)
    finally:
        _cleanup()


def test_claim_confirm_checks_the_token_version(monkeypatch):
    """A secret is only good for the issue of the claim it came from.

    ``_row`` is patched to hand the first read a version one behind the row on
    disk, which is what a re-issue landing between the read and the write looks
    like. The confirmation must then match no row at all.
    """
    current, _past, _far, _apartment_id = _seed()
    try:
        reservation, secret = _claim_secret(current)
        real_row = claim._row
        reads = []

        def stale_first_read(reservation_id):
            row = real_row(reservation_id)
            reads.append(row)
            if len(reads) == 1 and row is not None:
                stale = dict(row)
                stale["token_version"] = int(row["token_version"] or 0) - 1
                return stale
            return row

        monkeypatch.setattr(claim, "_row", stale_first_read)
        assert not claim.confirm(reservation, secret)
        assert claim.ensure_row(current)["state"] == "provisional"
        assert claim.ensure_row(current)["token_hash"]
        assert claim.confirm(reservation, secret)
        assert claim.ensure_row(current)["state"] == "claimed"
    finally:
        _cleanup()


def test_claim_confirm_refuses_a_superseded_secret_on_a_claimed_row(monkeypatch):
    """A stale secret cannot ride on the claim already being CLAIMED.

    The first read is forged to look like the issue the old secret came from,
    so the write matches no row at all. The confirmation must report failure
    instead of reading the claimed state back and calling that a success, and
    the live secret must be untouched.
    """
    current, _past, _far, _apartment_id = _seed()
    try:
        reservation, first = _claim_secret(current)
        assert claim.confirm(reservation, first)
        _age_claim(current, claim.RESEND_COOLDOWN_SECONDS + 5)
        reservation, second = _claim_secret(current, resend=True)

        real_row = claim._row
        forged = dict(real_row(current))
        forged["token_hash"] = claim.token_hash(first)
        forged["token_version"] = int(forged["token_version"] or 0) - 1
        reads = []

        def first_read_forged(reservation_id):
            reads.append(reservation_id)
            return forged if len(reads) == 1 else real_row(reservation_id)

        monkeypatch.setattr(claim, "_row", first_read_forged)
        assert not claim.confirm(reservation, first)
        assert claim.ensure_row(current)["token_hash"] == claim.token_hash(second)
        assert claim.confirm(reservation, second)
    finally:
        _cleanup()


def test_reissued_claim_secret_retires_the_previous_one():
    current, _past, _far, _apartment_id = _seed()
    try:
        reservation, first = _claim_secret(current)
        assert claim.confirm(reservation, first)
        _age_claim(current, claim.RESEND_COOLDOWN_SECONDS + 5)

        reservation, second = _claim_secret(current, resend=True)
        assert second != first
        assert not claim.confirm(reservation, first)
        assert claim.confirm(reservation, second)
    finally:
        _cleanup()


def test_confirmed_device_keeps_access_and_a_replayed_link_does_not():
    current, _past, _far, _apartment_id = _seed()
    try:
        _reservation, secret = _claim_secret(current)
        browser = TestClient(app)
        browser.cookies.set(guest.LANG_COOKIE, "en")
        confirmed = browser.post(
            f"/l/{TOKEN}/{current}/claim/confirm",
            data={"secret": secret},
            follow_redirects=False,
        )
        assert confirmed.status_code == 303
        assert "claim_error" not in confirmed.headers["location"]
        assert browser.get(f"/l/{TOKEN}/{current}").status_code == 200
        # Re-opening the spent link on the confirmed device continues to the stay.
        reopened = browser.get(f"/l/{TOKEN}/{current}/claim", follow_redirects=False)
        assert reopened.status_code == 303
        assert reopened.headers["location"] == f"/l/{TOKEN}/{current}?lang=en"

        stranger = TestClient(app)
        replay = stranger.post(
            f"/l/{TOKEN}/{current}/claim/confirm",
            data={"secret": secret},
            follow_redirects=False,
        )
        assert replay.status_code == 303
        assert "claim_error=1" in replay.headers["location"]
        assert claim.ensure_row(current)["state"] == "claimed"
        assert claim.ensure_row(current)["token_hash"] is None
    finally:
        _cleanup()


def test_console_backend_logs_claim_link_without_its_secret(monkeypatch):
    """The console log holds a usable link for the owner and no secret at rest.

    This test used to assert that the logged body carried the working secret.
    That was the finding being fixed, so the assertion is inverted rather than
    removed: what is stored must not be usable, and what the owner is shown
    must be.
    """
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
        assert "#c=" in logged["body_text"]
        assert mail.CLAIM_SECRET_MARKER in logged["body_text"]
        assert mail.extract_claim_secret(logged["body_text"]) == ""
        assert secret not in logged["body_text"]

        queued = db.query_one(
            "SELECT payload FROM email_outbox WHERE kind = ? ORDER BY id DESC",
            ("claim",),
        )
        assert queued
        payload = json.loads(queued["payload"])
        assert secret not in payload["text"]
        assert mail.delivery_body(payload).count(secret) == 1

        # What Settings shows the owner is the delivered body, secret included.
        shown = mail.recent_console_messages(apartment["owner_user_id"])[0]
        assert mail.extract_claim_secret(shown["body_text"]) == secret
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
        browser.cookies.set(guest.LANG_COOKIE, "en")
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
        browser.cookies.set(guest.LANG_COOKIE, "en")
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
            "SELECT * FROM console_mail_log WHERE subject LIKE 'Check-in today,%'"
        )
        assert host_mail
        assert re.search(r"\d+/\d+ registered", host_mail["subject"]), host_mail["subject"]
        assert "have registered" in host_mail["body_text"]
        assert "fresh link" not in host_mail["body_text"]
        assert "24-hour grace period" not in host_mail["body_text"]
        # The host app prints the date as DD.MM.YYYY; the mail must not print
        # the raw ISO the reservation table stores.
        assert check_in.strftime("%d.%m.%Y") in host_mail["body_text"]
        assert check_in.isoformat() not in host_mail["body_text"]

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


def test_unclaimed_stay_reminds_the_host_to_send_the_link_again(monkeypatch):
    """UX-27: no link was ever sent, so the mail must not say one was.

    The old copy read "Registration link sent to: the guest has not claimed the
    stay yet" and then told the host to watch the guest finish a form that was
    never opened.
    """
    current, _past, _far, _apartment_id = _seed()
    check_in = claim.prague_today()
    try:
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
        host_mail = db.query_one(
            "SELECT * FROM console_mail_log WHERE subject LIKE 'Incomplete registration:%'"
        )
        assert host_mail
        assert "Nobody has opened the registration yet" in host_mail["body_text"]
        assert "Registration link sent to" not in host_mail["body_text"]
        assert "the guest has not claimed the stay yet" not in host_mail["body_text"]
        assert "None" not in host_mail["body_text"]
        assert "None" not in host_mail["subject"]
    finally:
        db.execute("DELETE FROM alert WHERE reservation_id = ?", (current,))
        db.execute("DELETE FROM console_mail_log")
        db.execute("DELETE FROM email_outbox")
        _cleanup()


def test_incomplete_stay_inside_the_reach_back_window_stays_reachable():
    """Apartment picker hides past arrivals; the stay link still works.

    W3.5 bounded this affordance by ``permalink_reachback_days``. The stay here
    checked in yesterday, so it is inside any window: the point of this test is
    that the reach-back bound did not close a forgotten form that is still
    recent. The out-of-window half is
    ``test_stay_link_reach_back_window_bounds_a_forgotten_form``.
    """
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
        browser.cookies.set(guest.LANG_COOKIE, "en")
        address = "forgotten@claim.test"
        complete_guest_claim(browser, TOKEN, past, email=address, party_size=1)

        apartment_landing = TestClient(app).get(f"/l/{TOKEN}?lang=en")
        assert apartment_landing.status_code == 200
        # Jinja escapes the apostrophe in the rendered title.
        assert "There&#39;s nothing to register yet" in apartment_landing.text
        assert (
            "Registration opens a few days before arrival. Come back to this same link then. "
            "Already arrived? Message your host. They can send you a direct link to your stay."
        ) in apartment_landing.text
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


def test_stay_link_reach_back_window_bounds_a_forgotten_form():
    """W3.5 [F23]: a stay link reaches back a bounded number of days.

    Inverted from the behaviour this file used to pin: an incomplete past stay
    stayed reachable for ever, so an out-of-window id answered 200 where an id
    that never existed answered 404 — which told a stranger which reservation
    ids belong to the apartment.
    """
    _current, _past, _far, apartment_id = _seed()
    today = claim.prague_today()
    now = db.utcnow()
    try:
        recent = db.insert(
            "reservation",
            {
                "apartment_id": apartment_id,
                "source": "airbnb",
                "uid": "claim-recent",
                "date_from": (today - timedelta(days=7)).isoformat(),
                "date_to": (today - timedelta(days=5)).isoformat(),
                "status": "active",
                "created_at": now,
                "updated_at": now,
            },
        )
        old = db.insert(
            "reservation",
            {
                "apartment_id": apartment_id,
                "source": "airbnb",
                "uid": "claim-old",
                "date_from": (today - timedelta(days=732)).isoformat(),
                "date_to": (today - timedelta(days=730)).isoformat(),
                "status": "active",
                "created_at": now,
                "updated_at": now,
            },
        )

        browser = TestClient(app)
        browser.cookies.set(guest.LANG_COOKIE, "en")
        # Inside the default year: a stay that ended last week can still be filed.
        assert browser.get(f"/l/{TOKEN}/{recent}").status_code == 200

        out_of_window = browser.get(f"/l/{TOKEN}/{old}")
        assert out_of_window.status_code == 404
        assert "no longer open" in out_of_window.text

        # A stranger cannot tell an old id from an id that never existed. The
        # language switcher echoes the path that was asked for, so normalise
        # only that echo: everything else has to be byte-identical.
        def shape(response, reservation_id):
            return response.status_code, response.text.replace(
                f"/l/{TOKEN}/{reservation_id}", "/l/{TOKEN}/{ID}"
            )

        never_existed = browser.get(f"/l/{TOKEN}/987654")
        assert never_existed.status_code == 404
        assert shape(never_existed, 987654) == shape(out_of_window, old)

        # The window is the apartment's setting, not a hard-coded year.
        db.update("apartment", apartment_id, {"permalink_reachback_days": 1})
        assert browser.get(f"/l/{TOKEN}/{recent}").status_code == 404
        assert browser.get(f"/l/{TOKEN}/{old}").status_code == 404
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
        browser.cookies.set(guest.LANG_COOKIE, "en")
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


def test_a_fresh_claim_does_not_get_the_day_before_reminder_immediately(monkeypatch):
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
            browser, TOKEN, current, email="guest-fresh@claim.test", party_size=5
        )
        monkeypatch.setattr(mail, "backend_name", lambda: "console")
        monkeypatch.setattr(mail, "mail_enabled", lambda: True)
        monkeypatch.setattr(
            claim.deadlines,
            "local_now",
            lambda now=None: now or datetime.combine(today, time(10, 0)),
        )
        assert claim.sweep_reminders()["guest"] == 0
    finally:
        db.execute("DELETE FROM console_mail_log")
        db.execute("DELETE FROM email_outbox")
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
        browser.cookies.set(guest.LANG_COOKIE, "en")
        complete_guest_claim(
            browser, TOKEN, current, email="guest-reminder@claim.test", party_size=1
        )
        _age_claimed_at(current, claim.REMINDER_GUEST_MIN_HOURS_AFTER_CLAIM + 1)
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
        # E-12 [UX-78]: the subject names the stay and the count the sweep
        # already had in hand -- the party is 1 and nobody has filled the form.
        apartment = db.query_one(
            "SELECT * FROM apartment WHERE id = ?", (_apartment_id,)
        )
        property_name = mail_notify.property_label(apartment, "en")
        assert reminder["subject"] == i18n.STRINGS["en"][
            "mail_reminder_guest_subject"
        ] % {"property": property_name, "filled": 0, "expected": 1}
        assert i18n.STRINGS["en"]["mail_reminder_guest_intro"] % {
            "missing": 1
        } in reminder["body_text"]
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


def test_day_before_guest_reminder_waits_six_hours_after_claim(monkeypatch):
    """A tomorrow stay must not get the incomplete reminder right after claiming."""
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
        browser.cookies.set(guest.LANG_COOKIE, "en")
        complete_guest_claim(
            browser, TOKEN, current, email="fresh-claim@claim.test", party_size=1
        )
        monkeypatch.setattr(mail, "backend_name", lambda: "console")
        monkeypatch.setattr(mail, "mail_enabled", lambda: True)
        monkeypatch.setattr(
            claim.deadlines,
            "local_now",
            lambda now=None: now or datetime.combine(today, time(10, 0)),
        )

        assert claim.sweep_reminders()["guest"] == 0
        assert db.query_one(
            "SELECT COUNT(*) AS n FROM email_outbox WHERE kind = 'reminder_guest'"
        )["n"] == 0
    finally:
        db.execute("DELETE FROM console_mail_log")
        db.execute("DELETE FROM email_outbox")
        _cleanup()


def test_the_emergency_reminder_body_keeps_the_count_and_the_device(monkeypatch):
    """E-12 [UX-78]: the branded composer is an enhancement, not the contract.

    When it raises, the caller's plain body is what the guest receives, so it
    has to carry the same two facts the branded mail leads with.
    """
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
        browser.cookies.set(guest.LANG_COOKIE, "en")
        complete_guest_claim(
            browser, TOKEN, current, email="guest-fallback@claim.test", party_size=1
        )
        _age_claimed_at(current, claim.REMINDER_GUEST_MIN_HOURS_AFTER_CLAIM + 1)
        monkeypatch.setattr(mail, "backend_name", lambda: "console")
        monkeypatch.setattr(mail, "mail_enabled", lambda: True)
        monkeypatch.setattr(
            claim.deadlines,
            "local_now",
            lambda now=None: now or datetime.combine(today, time(10, 0)),
        )

        def _boom(**_kwargs):
            raise RuntimeError("composer down")

        monkeypatch.setattr(mail_notify, "build_reminder_guest", _boom)

        assert claim.sweep_reminders()["guest"] == 1
        reminder = db.query_one(
            "SELECT l.* FROM console_mail_log l "
            "JOIN email_outbox o ON o.id = l.outbox_id "
            "WHERE l.to_email = ? AND o.kind = 'reminder_guest'",
            ("guest-fallback@claim.test",),
        )
        assert reminder
        # The body has to carry the same two facts the branded mail leads with:
        # how much of the party is registered, and that the link wants the
        # device that started the stay. Read them out of the catalogue rather
        # than repeating the copy, so a deliberate wording change cannot leave
        # this asserting text the app no longer sends.
        expected_intro = i18n.STRINGS["en"]["mail_reminder_guest_intro"] % {"missing": 1}
        assert expected_intro in reminder["body_text"]
        assert i18n.STRINGS["en"]["mail_reminder_guest_device"] in reminder["body_text"]
        assert not reminder["body_html"]
    finally:
        db.execute("DELETE FROM alert WHERE reservation_id = ?", (current,))
        db.execute("DELETE FROM console_mail_log")
        db.execute("DELETE FROM email_outbox")
        _cleanup()


def test_the_emergency_claim_body_is_the_catalogued_copy(monkeypatch):
    """E-19 [UX-135]: the fallback is composed, not hand-written in claim.py.

    The body only ships when the branded composer throws, which is exactly when
    nobody is looking at it. It used to be a hard-coded string outside
    ``i18n.py``, so the Czech version said "your host" in English and the dates
    were printed as raw ISO -- a stay printed two ways on the one surface where
    the guest has no page to fall back on.
    """
    current, _past, _far, _apartment_id = _seed()
    try:
        monkeypatch.setattr(mail, "backend_name", lambda: "console")
        monkeypatch.setattr(mail, "mail_enabled", lambda: True)

        def _boom(**_kwargs):
            raise RuntimeError("composer down")

        monkeypatch.setattr(mail_notify, "build_claim_link", _boom)

        reservation = db.query_one("SELECT * FROM reservation WHERE id = ?", (current,))
        apartment = db.query_one(
            "SELECT * FROM apartment WHERE id = ?", (reservation["apartment_id"],)
        )
        ok, err, _secret = claim.start_claim(
            reservation, apartment, email="guest-claim-fb@claim.test", party_size=1,
            lang="cs",
        )
        assert ok, err
        logged = db.query_one(
            "SELECT l.* FROM console_mail_log l "
            "JOIN email_outbox o ON o.id = l.outbox_id "
            "WHERE o.kind = 'claim' ORDER BY l.id DESC"
        )
        assert logged
        body = logged["body_text"]
        t = i18n.translator("cs")
        assert t("mail_claim_expiry") in body
        assert t("mail_claim_action") in body
        # No English leaked into the Czech body, and no raw ISO dates either.
        assert "your host" not in body
        assert "expires in 30 minutes" not in body
        assert f"{reservation['date_from']}" not in body
        assert f"{reservation['date_to']}" not in body
        assert not logged["body_html"]
    finally:
        db.execute("DELETE FROM console_mail_log")
        db.execute("DELETE FROM email_outbox")
        _cleanup()


def test_expire_holds_releases_a_provisional_claim_after_the_window():
    """Stale e-mail holds must free the stay for another guest address."""
    current, _past, _far, _apartment_id = _seed()
    try:
        claim.ensure_row(current)
        past_until = (
            datetime.now(timezone.utc) - timedelta(minutes=claim.HOLD_MINUTES + 1)
        ).replace(microsecond=0).isoformat()
        now = db.utcnow()
        db.execute(
            "UPDATE reservation_claim SET state = ?, email = ?, provisional_until = ?, "
            "token_hash = 'held', updated_at = ? WHERE reservation_id = ?",
            (claim.PROVISIONAL, "held@claim.test", past_until, now, current),
        )

        released = claim.expire_holds(now=now)
        row = claim.ensure_row(current)

        assert released == 1
        assert row["state"] == claim.UNCLAIMED
        assert row["token_hash"] is None
        assert row["provisional_until"] is None
    finally:
        _cleanup()


def test_provisional_hold_blocks_a_different_email_until_it_expires():
    current, _past, _far, apartment_id = _seed()
    apartment = db.query_one("SELECT * FROM apartment WHERE id = ?", (apartment_id,))
    reservation = db.query_one("SELECT * FROM reservation WHERE id = ?", (current,))
    try:
        ok, err, _secret = claim.start_claim(
            reservation,
            apartment,
            email="first@claim.test",
            party_size=2,
            lang="en",
        )
        assert ok, err

        ok_other, err_other, _ = claim.start_claim(
            reservation,
            apartment,
            email="second@claim.test",
            party_size=2,
            lang="en",
        )
        assert not ok_other
        assert err_other == "held"
    finally:
        db.execute("DELETE FROM email_outbox")
        db.execute("DELETE FROM console_mail_log")
        _cleanup()


def test_mistyped_address_takes_over_after_the_hold_grace(monkeypatch):
    """A typo must not cost a guest the whole 30-minute hold."""
    current, _past, _far, apartment_id = _seed()
    monkeypatch.setattr(mail, "backend_name", lambda: "console")
    monkeypatch.setattr(mail, "mail_enabled", lambda: True)
    apartment = db.query_one("SELECT * FROM apartment WHERE id = ?", (apartment_id,))
    try:
        reservation = db.query_one("SELECT * FROM reservation WHERE id = ?", (current,))
        ok, err, wrong_secret = claim.start_claim(
            reservation,
            apartment,
            email="typo@claim.test",
            party_size=2,
            lang="en",
        )
        assert ok, err

        # Inside the grace window another address is still held off.
        held_ok, held_err, _secret = claim.start_claim(
            reservation,
            apartment,
            email="correct@claim.test",
            party_size=2,
            lang="en",
        )
        assert not held_ok
        assert held_err == "held"

        # Age the hold past the grace window but keep it inside the hold itself.
        started = datetime.now(timezone.utc) - timedelta(
            seconds=claim.HOLD_TAKEOVER_SECONDS + 5
        )
        until = (started + timedelta(minutes=claim.HOLD_MINUTES)).replace(
            microsecond=0
        ).isoformat()
        db.execute(
            "UPDATE reservation_claim SET provisional_until = ?, updated_at = ? "
            "WHERE reservation_id = ?",
            (until, db.utcnow(), current),
        )

        reservation = db.query_one("SELECT * FROM reservation WHERE id = ?", (current,))
        again_ok, again_err, right_secret = claim.start_claim(
            reservation,
            apartment,
            email="correct@claim.test",
            party_size=2,
            lang="en",
        )
        assert again_ok, again_err

        row = claim.ensure_row(current)
        assert row["email"] == "correct@claim.test"
        assert row["token_hash"] == claim.token_hash(right_secret)
        # The link sent to the mistyped address is dead.
        assert not claim.confirm(reservation, wrong_secret)
    finally:
        db.execute("DELETE FROM email_outbox")
        db.execute("DELETE FROM console_mail_log")
        db.execute("DELETE FROM rate_limit_event")
        _cleanup()


def test_guest_facing_assignment_masks_email_and_lock_hides_it():
    current, _past, _far, _apartment_id = _seed()
    address = "private-address@claim.test"
    try:
        owner = TestClient(app)
        owner.cookies.set(guest.LANG_COOKIE, "en")
        complete_guest_claim(owner, TOKEN, current, email=address, party_size=1)

        public = TestClient(app).get(f"/l/{TOKEN}/{current}?lang=en")
        assert public.status_code == 200
        assert mail.mask_email(address) in public.text
        assert address not in public.text
        assert "Claim flat" in public.text
        assert "Claim Facility" not in public.text
        assert "Your selected stay" in public.text
        assert "send the private link again" in public.text
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


def test_default_claim_mail_caps_tolerate_a_retrying_guest(monkeypatch):
    """The shipped caps must let a real guest retry.

    A guest who mistypes an address, or whose link never arrives, submits the
    form more than once; the abuse caps are there to stop bulk misuse, not to
    lock a single booking out after a couple of attempts.
    """
    current, _past, _far, apartment_id = _seed()
    monkeypatch.setattr(mail, "backend_name", lambda: "console")
    monkeypatch.setattr(mail, "mail_enabled", lambda: True)
    apartment = db.query_one("SELECT * FROM apartment WHERE id = ?", (apartment_id,))
    try:
        for attempt in range(claim.CLAIM_MAIL_PER_RECIPIENT_MAX):
            claim.release(current)
            reservation = db.query_one("SELECT * FROM reservation WHERE id = ?", (current,))
            ok, err, _secret = claim.start_claim(
                reservation,
                apartment,
                email="retry@claim.test",
                party_size=1,
                lang="en",
            )
            assert ok, f"same-address attempt {attempt + 1} was blocked: {err}"

        claim.release(current)
        reservation = db.query_one("SELECT * FROM reservation WHERE id = ?", (current,))
        ok, err, _secret = claim.start_claim(
            reservation,
            apartment,
            email="retry@claim.test",
            party_size=1,
            lang="en",
        )
        assert not ok
        assert err == "recipient_rate"

        db.execute("DELETE FROM rate_limit_event WHERE scope LIKE 'claim_mail_%'")
        for attempt in range(claim.CLAIM_MAIL_PER_RESERVATION_MAX):
            claim.release(current)
            reservation = db.query_one("SELECT * FROM reservation WHERE id = ?", (current,))
            ok, err, _secret = claim.start_claim(
                reservation,
                apartment,
                email=f"group{attempt}@claim.test",
                party_size=1,
                lang="en",
            )
            assert ok, f"group attempt {attempt + 1} was blocked: {err}"

        claim.release(current)
        reservation = db.query_one("SELECT * FROM reservation WHERE id = ?", (current,))
        ok, err, _secret = claim.start_claim(
            reservation,
            apartment,
            email="group-extra@claim.test",
            party_size=1,
            lang="en",
        )
        assert not ok
        assert err == "rate"
    finally:
        db.execute("DELETE FROM console_mail_log")
        db.execute("DELETE FROM email_outbox")
        db.execute("DELETE FROM rate_limit_event")
        _cleanup()


def test_party_post_stays_smooth_for_a_retrying_guest(monkeypatch):
    """Fumbling the claim form must never surface the rate banner."""
    current, _past, _far, _apartment_id = _seed()
    monkeypatch.setattr(mail, "backend_name", lambda: "console")
    monkeypatch.setattr(mail, "mail_enabled", lambda: True)
    try:
        browser = TestClient(app)
        browser.cookies.set(guest.LANG_COOKIE, "en")
        typo = browser.post(
            f"/l/{TOKEN}/{current}/party",
            data={"party_size": "3", "guest_email": "not-an-email"},
            follow_redirects=False,
        )
        assert typo.status_code == 303
        assert "claim_error=rate" not in typo.headers["location"]
        for attempt in range(5):
            response = browser.post(
                f"/l/{TOKEN}/{current}/party",
                data={"party_size": "3", "guest_email": "smooth@example.com"},
                follow_redirects=False,
            )
            assert response.status_code == 303
            location = response.headers["location"]
            assert "claim_error=rate" not in location, f"attempt {attempt + 1}: {location}"
    finally:
        db.execute("DELETE FROM console_mail_log")
        db.execute("DELETE FROM email_outbox")
        db.execute("DELETE FROM rate_limit_event")
        _cleanup()


def test_the_sent_claim_page_confirms_the_address_and_folds_the_form_away(monkeypatch):
    """Once a link is on its way the guest is done — don't render the form again."""
    current, _past, _far, _apartment_id = _seed()
    monkeypatch.setattr(mail, "backend_name", lambda: "console")
    monkeypatch.setattr(mail, "mail_enabled", lambda: True)
    try:
        browser = TestClient(app)
        browser.cookies.set(guest.LANG_COOKIE, "en")

        before = browser.get(f"/l/{TOKEN}/{current}")
        assert 'class="g-card g-fold"' not in before.text
        assert "No e-mail after a few minutes?" not in before.text

        sent = browser.post(
            f"/l/{TOKEN}/{current}/party",
            data={"party_size": "2", "guest_email": "foldaway@example.com"},
            follow_redirects=False,
        )
        assert sent.status_code == 303
        assert "claim_sent=1" in sent.headers["location"]

        page = browser.get(sent.headers["location"], follow_redirects=False)
        assert page.status_code == 200
        masked = db.query_one(
            "SELECT email_masked FROM reservation_claim WHERE reservation_id = ?", (current,)
        )["email_masked"]
        assert masked
        assert f"We sent a link to {masked}." in page.text
        assert "It works for 30 minutes" in page.text
        assert "If it asks for the PIN again, enter the same PIN." in page.text
        # The form is still there, but behind a closed disclosure.
        assert '<details class="g-card g-fold">' in page.text
        assert "No e-mail after a few minutes? Check spam, or send it again" in page.text
        assert "<details class=\"g-card g-fold\" open" not in page.text
        assert 'name="guest_email"' in page.text
        # And no staging instructions for a production guest.
        assert "staging" not in page.text.lower()
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
        browser.cookies.set(guest.LANG_COOKIE, "en")
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


# --- W2.4: a stored claim link must not carry its secret -------------------

class _FakeSes:
    def __init__(self):
        self.calls = []

    def send_email(self, **kwargs):
        self.calls.append(kwargs)
        return {"MessageId": "fake-message-id"}


def _claim_outbox_row(reservation, apartment, email="w24@claim.test"):
    """Queue one real claim message and return (outbox row, secret)."""
    ok, err, secret = claim.start_claim(
        reservation,
        apartment,
        email=email,
        party_size=1,
        lang="en",
    )
    assert ok, err
    row = db.query_one("SELECT * FROM email_outbox ORDER BY id DESC")
    assert row
    return row, secret


def test_the_stored_payload_holds_no_usable_claim_secret():
    current, _past, _far, _apartment_id = _seed()
    try:
        reservation = db.query_one("SELECT * FROM reservation WHERE id = ?", (current,))
        apartment = db.query_one("SELECT * FROM apartment WHERE permalink_token = ?", (TOKEN,))
        row, secret = _claim_outbox_row(reservation, apartment)
        stored = row["payload"]
        assert secret not in stored
        assert mail.CLAIM_SECRET_MARKER in stored
        assert mail.extract_claim_secret(stored) == ""
        # And the secret that is stored is not stored as itself.
        assert mail.delivery_body(json.loads(stored)).count(secret) == 1
    finally:
        db.execute("DELETE FROM console_mail_log")
        db.execute("DELETE FROM email_outbox")
        _cleanup()


def test_a_claim_link_that_cannot_be_opened_does_not_send():
    current, _past, _far, _apartment_id = _seed()
    try:
        reservation = db.query_one("SELECT * FROM reservation WHERE id = ?", (current,))
        apartment = db.query_one("SELECT * FROM apartment WHERE permalink_token = ?", (TOKEN,))
        row, _secret = _claim_outbox_row(reservation, apartment)
        logged_before = db.query_one("SELECT COUNT(*) AS n FROM console_mail_log")["n"]
        # Retry from a clean queue so drain picks the row up immediately.
        db.update(
            "email_outbox",
            row["id"],
            {"next_attempt_at": db.utcnow(), "state": mail.QUEUED},
        )

        def _refuse(_token, fallback=None):
            raise db.DecryptionError("bad key")

        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(mail, "mail_enabled", lambda: True)
            patch.setattr(db, "decrypt_field", _refuse)
            summary = mail.drain(limit=4)

        assert summary["sent"] == 0
        after = db.query_one("SELECT * FROM email_outbox WHERE id = ?", (row["id"],))
        # Still queued, so a key problem is recoverable rather than losing the
        # guest's link. Terminal failure comes after eight attempts.
        assert after["state"] == mail.QUEUED
        assert "bad key" in after["last_error"]
        # Nothing was logged as sent: the retry left no second log entry.
        assert (
            db.query_one("SELECT COUNT(*) AS n FROM console_mail_log")["n"] == logged_before
        )
    finally:
        db.execute("DELETE FROM console_mail_log")
        db.execute("DELETE FROM email_outbox")
        _cleanup()


def test_a_message_without_a_claim_link_is_delivered_unchanged():
    payload = {"text": "Your stay starts tomorrow.", "lang": "en"}
    assert mail.delivery_body(payload) == "Your stay starts tomorrow."
    assert mail.stored_body(payload) == "Your stay starts tomorrow."
    # Settings renders every logged body through the same reveal path, so a
    # message with no claim link must come out untouched.
    assert mail._reveal_claim_secret("Your stay starts tomorrow.", None) == (
        "Your stay starts tomorrow."
    )
    assert mail._reveal_claim_secret("Your stay starts tomorrow.", "{}") == (
        "Your stay starts tomorrow."
    )


def test_a_link_queued_before_the_secret_was_split_out_still_sends():
    """A rolling deploy leaves older rows holding a cleartext link.

    Those rows carry no marker, so they are delivered as stored. The release
    after this one can stop honouring them once the queue has drained.
    """
    payload = {"text": "Open .../claim#c=" + "A" * 32, "lang": "en"}
    assert mail.delivery_body(payload) == payload["text"]


def test_the_owner_sees_a_working_link_and_another_host_does_not():
    current, _past, _far, _apartment_id = _seed()
    try:
        reservation = db.query_one("SELECT * FROM reservation WHERE id = ?", (current,))
        apartment = db.query_one("SELECT * FROM apartment WHERE permalink_token = ?", (TOKEN,))
        _row, secret = _claim_outbox_row(reservation, apartment)
        db.update(
            "email_outbox",
            db.query_one("SELECT MAX(id) AS id FROM email_outbox")["id"],
            {"owner_user_id": 987001},
        )

        mine = mail.recent_console_messages(987001)
        assert len(mine) == 1
        assert mail.extract_claim_secret(mine[0]["body_text"]) == secret
        assert set(mine[0]) >= {"id", "to_email", "subject", "body_text"}
        assert "outbox_payload" not in mine[0]

        assert mail.recent_console_messages(987002) == []
        # A platform admin already saw the working link before this change, and
        # who may see what is not part of this work item, so the branch that
        # owns no workspace keeps its old behaviour.
        for row in mail.recent_console_messages(None):
            assert mail.extract_claim_secret(row["body_text"]) == secret
    finally:
        db.execute("DELETE FROM console_mail_log")
        db.execute("DELETE FROM email_outbox")
        _cleanup()


def test_a_secret_that_cannot_be_read_leaves_the_marker_rather_than_failing():
    current, _past, _far, _apartment_id = _seed()
    try:
        reservation = db.query_one("SELECT * FROM reservation WHERE id = ?", (current,))
        apartment = db.query_one("SELECT * FROM apartment WHERE permalink_token = ?", (TOKEN,))
        _row, _secret = _claim_outbox_row(reservation, apartment)

        def _refuse(_token, fallback=None):
            raise db.DecryptionError("bad key")

        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(db, "decrypt_field", _refuse)
            shown = mail.recent_console_messages(apartment["owner_user_id"])

        assert shown
        assert mail.CLAIM_SECRET_MARKER in shown[0]["body_text"]
        assert mail.extract_claim_secret(shown[0]["body_text"]) == ""
    finally:
        db.execute("DELETE FROM console_mail_log")
        db.execute("DELETE FROM email_outbox")
        _cleanup()


def test_settings_shows_the_host_a_working_claim_link(monkeypatch):
    from tests.test_accounts import _account, _apartment, _clean_accounts, _login

    current, _past, _far, _apartment_id = _seed()
    _clean_accounts()
    owner_id = _account("boundary-w24")
    host_apartment_id = _apartment(owner_id, "W24 flat", "w24tok")
    try:
        monkeypatch.setattr(mail, "backend_name", lambda: "console")
        monkeypatch.setattr(mail, "mail_enabled", lambda: True)
        reservation = db.query_one("SELECT * FROM reservation WHERE id = ?", (current,))
        apartment = db.query_one("SELECT * FROM apartment WHERE permalink_token = ?", (TOKEN,))
        row, secret = _claim_outbox_row(reservation, apartment)
        db.update("email_outbox", row["id"], {"owner_user_id": owner_id})
        # The apartment the outbox row points at belongs to the host too, so
        # the Settings query finds it.
        db.update("apartment", apartment["id"], {"owner_user_id": owner_id})

        page = _login("boundary-w24").get("/settings")
        assert page.status_code == 200
        assert mail.CLAIM_SECRET_MARKER not in page.text
        assert f"#c={secret}" in page.text
    finally:
        db.execute("DELETE FROM console_mail_log")
        db.execute("DELETE FROM email_outbox")
        db.update("apartment", _apartment_id, {"owner_user_id": None})
        _cleanup()
        _clean_accounts()
        assert host_apartment_id


def test_ses_delivers_the_secret_but_never_stores_it(monkeypatch):
    current, _past, _far, _apartment_id = _seed()
    try:
        reservation = db.query_one("SELECT * FROM reservation WHERE id = ?", (current,))
        apartment = db.query_one("SELECT * FROM apartment WHERE permalink_token = ?", (TOKEN,))
        row, secret = _claim_outbox_row(reservation, apartment)
        db.update(
            "email_outbox",
            row["id"],
            {"next_attempt_at": db.utcnow(), "state": mail.QUEUED},
        )

        fake = _FakeSes()
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(mail, "backend_name", lambda: "ses")
            patch.setattr(mail, "mail_enabled", lambda: True)
            patch.setattr(mail, "_ses_client", lambda: fake)
            patch.setattr(config, "MAIL_FROM", "host@claim.test")
            summary = mail.drain(limit=4)

        assert summary["sent"] == 1
        assert len(fake.calls) == 1
        sent = fake.calls[0]["Message"]["Body"]["Text"]["Data"]
        assert f"#c={secret}" in sent
        assert mail.CLAIM_SECRET_MARKER not in sent
        stored = db.query_one("SELECT payload FROM email_outbox WHERE id = ?", (row["id"],))
        assert secret not in stored["payload"]
    finally:
        db.execute("DELETE FROM console_mail_log")
        db.execute("DELETE FROM email_outbox")
        _cleanup()


# --- UX-74: a guest's answer always goes back to the host -------------------
#
# A guest has no account and no way back into the app. Answering the mail is
# the one route they have, so Reply-To has to reach the host who owns the stay
# and never UbyHost support. It used to be set by hand at three call sites;
# now every guest kind is built through ``mail_notify.guest_payload``.


def _guest_outbox_rows():
    placeholders = ",".join("?" for _ in mail.GUEST_KINDS)
    return db.query(
        f"SELECT id, kind, payload FROM email_outbox "
        f"WHERE kind IN ({placeholders}) ORDER BY id",
        tuple(mail.GUEST_KINDS),
    )


def test_every_mail_kind_is_classified_as_guest_or_host():
    """UX-74: a new kind has to say whose mail it is.

    The invoice plan adds guest kinds whose table does not mention Reply-To.
    Splitting ``KINDS`` means the next kind cannot be added without landing on
    one side or the other.
    """
    assert set(mail.KINDS) == set(mail.GUEST_KINDS) | set(mail.HOST_KINDS)
    assert not set(mail.GUEST_KINDS) & set(mail.HOST_KINDS)


def test_the_registered_mail_kinds_are_the_ones_the_app_can_send():
    """UX-134: ``KINDS`` must describe what the app actually sends.

    ``dates_changed`` sat in this tuple for months with no composer, no call
    site and no copy, while ``docs/SES.md`` promised it stayed plain text. A
    kind nobody can send is a promise the app does not keep, so the tuple is
    pinned here: adding one back has to be a deliberate edit to this test.
    """
    assert set(mail.KINDS) == {
        "claim",
        "claim_resend",
        "reminder_guest",
        "reminder_host",
        "completion",
        "submission_problem",
        "invoice_issued",
        "workspace_deletion",
        "cancelled_with_guests",
        "deadline_at_risk",
        "manual_deadline",
        "deadline_digest",
        # WP12: the three lifecycle tips (lifecycle_mail.py, mail_notify.build_lifecycle).
        "lifecycle_no_property",
        "lifecycle_no_calendar",
        "lifecycle_no_guest",
        "signup_verify",
        "signup_exists",
        "signup_admin",
        # Task 0002: the login e-mail change notice.
        "email_changed",
        # Task 0003: the login link, the invitation and the address confirmation.
        "login_link",
        "account_invite",
        "email_confirm",
        "passkey_added",
        "door_code",
        "door_code_notice",
    }


def test_no_registered_mail_kind_is_dead():
    """Every kind in ``KINDS`` is reachable from somewhere outside ``mail.py``.

    The kind has to be named as a string literal by a composer, a call site or
    a copy key. ``dates_changed`` failed exactly this: it was only ever a local
    variable name in ``icalsync.py``, never a kind anyone could send.
    """
    app_dir = pathlib.Path(mail.__file__).parent
    sources = [
        path.read_text(encoding="utf-8")
        for path in app_dir.rglob("*.py")
        if path.name != "mail.py"
    ]
    for kind in mail.KINDS:
        assert any(f'"{kind}"' in text or f"'{kind}'" in text for text in sources), kind


def test_every_guest_kind_sends_the_answer_back_to_the_host(monkeypatch):
    """UX-74: all four guest kinds route a reply to the entity, not to support."""
    current, _past, _far, apartment_id = _seed()
    check_in = claim.prague_today()
    try:
        monkeypatch.setattr(mail, "backend_name", lambda: "console")
        monkeypatch.setattr(mail, "mail_enabled", lambda: True)
        browser = TestClient(app)
        browser.cookies.set(guest.LANG_COOKIE, "en")
        reservation = db.query_one("SELECT * FROM reservation WHERE id = ?", (current,))
        apartment = db.query_one("SELECT * FROM apartment WHERE id = ?", (apartment_id,))

        # The link a guest is first sent, confirmed, then re-sent when it is lost.
        complete_guest_claim(
            browser, TOKEN, current, email="reply-to-all@claim.test", party_size=1
        )
        _age_claim(current, 600)
        ok, err, _secret = claim.start_claim(
            reservation,
            apartment,
            email="reply-to-all@claim.test",
            party_size=1,
            lang="en",
            resend=True,
        )
        assert ok, err

        # The reminder the sweep sends the day before check-in.
        db.update(
            "reservation",
            current,
            {
                "date_from": (check_in + timedelta(days=1)).isoformat(),
                "date_to": (check_in + timedelta(days=4)).isoformat(),
            },
        )
        monkeypatch.setattr(
            claim.deadlines,
            "local_now",
            lambda now=None: now or datetime.combine(check_in, time(10, 0)),
        )
        _age_claimed_at(current, claim.REMINDER_GUEST_MIN_HOURS_AFTER_CLAIM + 1)
        assert claim.sweep_reminders()["guest"] == 1

        # The receipt, once everyone on the stay is registered.
        monkeypatch.setattr(
            claim.reporting,
            "reservation_progress",
            lambda _reservation: {"expected": 1, "filled": 1, "incomplete": []},
        )
        claim.maybe_notify_completion(
            db.query_one("SELECT * FROM reservation WHERE id = ?", (current,)),
            apartment,
        )

        rows = _guest_outbox_rows()
        # The claim flow sends these four; invoice_issued is a guest kind too but
        # is triggered by the host, not here.
        assert {row["kind"] for row in rows} == {
            "claim",
            "claim_resend",
            "reminder_guest",
            "completion",
        }
        for row in rows:
            payload = json.loads(row["payload"])
            assert payload.get("reply_to") == "host@claim.test", (row["kind"], payload)
            assert "support@" not in payload["reply_to"]
    finally:
        db.execute("DELETE FROM alert WHERE reservation_id = ?", (current,))
        db.execute("DELETE FROM console_mail_log")
        db.execute("DELETE FROM email_outbox")
        _cleanup()


def test_a_guest_mail_with_no_answer_address_still_goes_out_and_is_logged(
    monkeypatch, caplog
):
    """UX-74: a missing entity address costs the routing, not the guest's link.

    The warning is the tripwire for a future kind that forgets Reply-To; the
    message itself still has to be sent, because the guest is waiting on it.
    """
    _cleanup()
    monkeypatch.setattr(mail, "backend_name", lambda: "console")
    monkeypatch.setattr(mail, "mail_enabled", lambda: True)
    try:
        with caplog.at_level("WARNING", logger="ubyhost.mail"):
            outbox_id = mail.enqueue(
                kind="claim",
                idempotency_key="ux74-claim-without-reply-to",
                to_email="guest@ux74.test",
                subject="A link with nowhere to answer",
                payload={"text": "body", "lang": "en"},
            )
        assert outbox_id is not None
        row = db.query_one("SELECT * FROM email_outbox WHERE id = ?", (outbox_id,))
        assert row and "reply_to" not in json.loads(row["payload"])
        assert any(
            "no reply_to" in record.getMessage() and record.levelname == "WARNING"
            for record in caplog.records
        ), [record.getMessage() for record in caplog.records]
    finally:
        db.execute("DELETE FROM console_mail_log")
        db.execute("DELETE FROM email_outbox")
        _cleanup()


def test_a_guest_payload_leaves_out_a_reply_address_the_entity_does_not_have(
    monkeypatch,
):
    """UX-74: no contact address means no Reply-To, and no empty-string header."""
    current, _past, _far, apartment_id = _seed()
    entity_id = None
    try:
        entity_id = db.insert(
            "legal_entity",
            {"name": "Reachable Nowhere", "contact_email": "", "created_at": db.utcnow()},
        )
        db.update("apartment", apartment_id, {"legal_entity_id": entity_id})
        apartment = db.query_one("SELECT * FROM apartment WHERE id = ?", (apartment_id,))
        payload = mail_notify.guest_payload(
            apartment, {"text": "body", "html": "<p>body</p>"}, "en"
        )
        assert "reply_to" not in payload
        assert payload["html"] == "<p>body</p>"
    finally:
        db.execute("DELETE FROM alert WHERE reservation_id = ?", (current,))
        db.execute("DELETE FROM console_mail_log")
        db.execute("DELETE FROM email_outbox")
        _cleanup()
        if entity_id:
            db.execute("DELETE FROM legal_entity WHERE id = ?", (entity_id,))
