"""A guest who finished registering is never left waiting in silence for a door code."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from app import config, db, deadlines, door_codes, ttlock

PREFIX = "dc-safe-"
_counter = 0


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    db.init_db()
    _purge()
    monkeypatch.setattr(config, "DOOR_CODES_ENABLED", True)
    monkeypatch.setattr(config, "TTLOCK_CLIENT_ID", "cid")
    monkeypatch.setattr(config, "TTLOCK_CLIENT_SECRET", "csecret")
    monkeypatch.setattr(config, "DOOR_CODES_LIVE", False)
    monkeypatch.setattr(config, "MAIL_BACKEND", "console")
    monkeypatch.setattr(door_codes, "check_lock_clocks", lambda: {})
    monkeypatch.setattr(ttlock, "find_code_by_name", lambda *a, **k: None)
    yield
    _purge()


def _purge():
    for owner in db.query("SELECT id FROM user_account WHERE username LIKE ?", (PREFIX + "%",)):
        oid = owner["id"]
        for apt in db.query("SELECT id FROM apartment WHERE owner_user_id = ?", (oid,)):
            db.execute("DELETE FROM alert WHERE apartment_id = ?", (apt["id"],))
            db.execute("DELETE FROM email_outbox WHERE owner_user_id = ?", (oid,))
            db.execute("DELETE FROM door_code WHERE apartment_id = ?", (apt["id"],))
            db.execute("DELETE FROM reservation WHERE apartment_id = ?", (apt["id"],))
        db.execute("DELETE FROM audit WHERE owner_user_id = ?", (oid,))
        db.execute("DELETE FROM lock_account WHERE owner_user_id = ?", (oid,))
        db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (oid,))
        db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (oid,))
        db.execute("DELETE FROM user_account WHERE id = ?", (oid,))


def _stay(registered_minutes_ago: int) -> tuple[int, int, int]:
    """A registered manual stay on a property with a lock. Returns owner, apartment, stay."""
    global _counter
    _counter += 1
    now = db.utcnow()
    owner = db.insert(
        "user_account",
        {
            "username": f"{PREFIX}{_counter}",
            "display_name": "Host",
            "password_hash": "x",
            "role": "host",
            "created_at": now,
        },
    )
    entity = db.insert(
        "legal_entity",
        {
            "name": "Safe",
            "seat": "Praha",
            "created_at": now,
            "owner_user_id": owner,
            "contact_email": "host@example.test",
        },
    )
    apartment = db.insert(
        "apartment",
        {
            "legal_entity_id": entity,
            "owner_user_id": owner,
            "internal_name": "Flat",
            "permalink_token": f"{PREFIX}tok-{_counter}",
            "automation_mode": "manual",
            "default_purpose": "10",
            "active": 1,
            "created_at": now,
            "lock_provider": "ttlock",
            "lock_id": "35662508",
            "checkin_hour": 10,
            "checkout_hour": 15,
        },
    )
    db.insert(
        "lock_account",
        {
            "owner_user_id": owner,
            "provider": "ttlock",
            "username": f"x_{PREFIX}{_counter}",
            "status": "ok",
            "created_at": now,
            "updated_at": now,
        },
    )
    today = deadlines.local_now().date()
    done = (datetime.now(timezone.utc) - timedelta(minutes=registered_minutes_ago)).replace(
        microsecond=0
    )
    stay = db.insert(
        "reservation",
        {
            "apartment_id": apartment,
            "source": "manual",
            "uid": f"{PREFIX}stay-{_counter}",
            "date_from": today.isoformat(),
            "date_to": (today + timedelta(days=1)).isoformat(),
            "status": "active",
            "registration_completed_at": done.isoformat(),
            "created_at": now,
            "updated_at": now,
        },
    )
    return owner, apartment, stay


def _view(stay: int, apartment: int):
    return door_codes.view(
        db.query_one("SELECT * FROM reservation WHERE id = ?", (stay,)),
        db.query_one("SELECT * FROM apartment WHERE id = ?", (apartment,)),
    )


def _open_alert(stay: int):
    return db.query_one(
        "SELECT * FROM alert WHERE dedupe_key = ? AND resolved_at IS NULL",
        (f"door_code_delayed:{stay}",),
    )


def _failing_ttlock(monkeypatch):
    def boom(*args, **kwargs):
        raise ttlock.TTLockError("down", kind="transient")

    monkeypatch.setattr(ttlock, "create_period_code", boom)


def test_a_fresh_wait_is_preparing_with_no_alert(monkeypatch):
    _failing_ttlock(monkeypatch)
    _, apartment, stay = _stay(registered_minutes_ago=1)
    door_codes.reconcile()
    assert _view(stay, apartment) == {"state": "preparing"}
    assert _open_alert(stay) is None


def test_a_long_wait_tells_the_guest_and_the_host(monkeypatch):
    _failing_ttlock(monkeypatch)
    _, apartment, stay = _stay(registered_minutes_ago=15)
    door_codes.reconcile()
    assert _view(stay, apartment) == {"state": "delayed"}
    alert = _open_alert(stay)
    assert alert is not None
    assert "reason=" in alert["detail"]


def test_the_alert_clears_when_the_code_arrives(monkeypatch):
    _failing_ttlock(monkeypatch)
    _, apartment, stay = _stay(registered_minutes_ago=15)
    door_codes.reconcile()
    assert _open_alert(stay) is not None

    monkeypatch.setattr(ttlock, "create_period_code", lambda *a, **k: ("4821937", "99"))
    db.execute("UPDATE door_code SET next_attempt_at = NULL WHERE reservation_id = ?", (stay,))
    door_codes.reconcile()
    assert _view(stay, apartment)["state"] == "issued"
    assert _open_alert(stay) is None


def test_a_stay_with_no_row_at_all_is_still_reported(monkeypatch):
    """The property is not set up for codes, so no row is ever made."""
    _, apartment, stay = _stay(registered_minutes_ago=15)
    db.execute("UPDATE apartment SET checkin_hour = NULL WHERE id = ?", (apartment,))
    door_codes.reconcile()
    assert db.query_one("SELECT id FROM door_code WHERE reservation_id = ?", (stay,)) is None
    assert _view(stay, apartment) == {"state": "delayed"}
    assert _open_alert(stay) is not None


def test_a_silent_exit_leaves_its_reason(monkeypatch):
    _, apartment, stay = _stay(registered_minutes_ago=1)
    row_id = door_codes.ensure_row(stay)
    db.execute("UPDATE lock_account SET status = 'reauth_needed'")
    assert door_codes.issue(row_id) is False
    row = db.query_one("SELECT state, last_error FROM door_code WHERE id = ?", (row_id,))
    assert row["state"] == door_codes.PENDING
    assert row["last_error"] == "no_account"


def test_a_broken_cancellation_phase_cannot_block_issuing(monkeypatch):
    _, apartment, stay = _stay(registered_minutes_ago=1)
    monkeypatch.setattr(ttlock, "create_period_code", lambda *a, **k: ("4821937", "99"))

    def broken(_now):
        raise RuntimeError("boom")

    monkeypatch.setattr(door_codes, "_handle_cancellations", broken)
    monkeypatch.setattr(door_codes, "_handle_moves", broken)
    counts = door_codes.reconcile()
    assert counts["issued"] == 1
    assert _view(stay, apartment)["state"] == "issued"


def test_the_ttlock_error_number_is_kept_for_the_host(monkeypatch):
    def refused(*args, **kwargs):
        raise ttlock.TTLockError("keyboardPwd conflict", code=-3004, kind="transient")

    monkeypatch.setattr(ttlock, "create_period_code", refused)
    _, apartment, stay = _stay(registered_minutes_ago=15)
    door_codes.reconcile()
    row = db.query_one("SELECT last_error FROM door_code WHERE reservation_id = ?", (stay,))
    assert row["last_error"] == "transient:-3004"
    assert "transient:-3004" in _open_alert(stay)["detail"]


def _mails(stay: int):
    return db.query(
        "SELECT kind, to_email, cc_email FROM email_outbox WHERE reservation_id = ?", (stay,)
    )


def test_a_missing_code_mails_only_the_host_with_support_in_copy(monkeypatch):
    _failing_ttlock(monkeypatch)
    _, apartment, stay = _stay(registered_minutes_ago=15)
    door_codes.reconcile()
    door_codes.reconcile()
    rows = _mails(stay)
    assert [(r["kind"], r["to_email"], r["cc_email"]) for r in rows] == [
        ("door_code_notice", "host@example.test", "support@ubyhost.com")
    ]


def test_the_final_failure_notice_also_copies_support(monkeypatch):
    from app import mail_notify

    _, apartment, stay = _stay(registered_minutes_ago=1)
    row_id = door_codes.ensure_row(stay)
    mail_notify.door_code_notice(row_id, "failed")
    rows = _mails(stay)
    assert [(r["to_email"], r["cc_email"]) for r in rows] == [
        ("host@example.test", "support@ubyhost.com")
    ]


def test_guests_see_the_exact_first_use_deadline():
    from app import mail_notify

    for lang in ("en", "cs", "de", "es", "fr"):
        content = mail_notify.build_door_code(
            lang=lang,
            property_name="Flat",
            checkin="08.10.2026 16:00",
            checkout="10.10.2026 11:00",
            first_use_by="09.10.2026 15:00",
        )
        assert "09.10.2026 15:00" in content["text"]
    en = mail_notify.build_door_code(
        lang="en", property_name="Flat", checkin="a", checkout="b", first_use_by="c"
    )
    assert "If you have not used it by c, it stops working. Then ask your host for a new code." in en["text"]


def test_the_guide_walks_through_authorized_admin():
    """Read the copy itself: the page language depends on what other tests left behind."""
    from app.guide_i18n import GUIDE_STRINGS

    for lang in ("en", "cs"):
        strings = GUIDE_STRINGS[lang]
        steps = " ".join(strings[f"guide.door_codes.step{n}"] for n in range(1, 10))
        assert "Create Admin" in steps
        assert "Manage their own users only" in steps
        assert "Smart locks" not in steps and "Check for locks" not in steps
        assert "Remote unlock" not in steps
    en = GUIDE_STRINGS["en"]
    assert "within 24 hours after its start time" in en["guide.door_codes.how3"]
    assert "Passcodes" in en["guide.door_codes.how7"]


def test_the_host_mail_says_why_in_words_and_keeps_the_raw_reason_for_support(monkeypatch):
    def refused(*args, **kwargs):
        raise ttlock.TTLockError("refused", code=-1026, kind="transient")

    monkeypatch.setattr(ttlock, "create_period_code", refused)
    _, apartment, stay = _stay(registered_minutes_ago=15)
    door_codes.reconcile()
    row = db.query_one(
        "SELECT payload FROM email_outbox WHERE reservation_id = ?", (stay,)
    )
    body = json.loads(row["payload"])["text"]
    assert "TTLock refused or did not answer [transient:-1026]" in body
    assert "keeps trying" not in body


def test_a_property_with_no_lock_set_says_so_instead_of_claiming_to_retry():
    _, apartment, stay = _stay(registered_minutes_ago=15)
    db.execute("UPDATE apartment SET checkin_hour = NULL WHERE id = ?", (apartment,))
    door_codes.reconcile()
    row = db.query_one(
        "SELECT payload FROM email_outbox WHERE reservation_id = ?", (stay,)
    )
    body = json.loads(row["payload"])["text"]
    assert "no lock or no check-in and check-out time saved" in body


def test_a_dead_ttlock_connection_is_explained_in_the_delayed_host_mail():
    _, apartment, stay = _stay(registered_minutes_ago=15)
    row_id = door_codes.ensure_row(stay)
    assert row_id is not None
    db.execute("UPDATE lock_account SET status = 'reauth_needed'")
    assert door_codes.issue(row_id) is False
    door_codes.reconcile()
    row = db.query_one(
        "SELECT payload FROM email_outbox WHERE reservation_id = ? AND kind = 'door_code_notice'",
        (stay,),
    )
    body = json.loads(row["payload"])["text"]
    assert "TTLock connection needs to be set up again [no_account]" in body


def test_a_moved_stay_updates_the_passcode_window_when_ttlock_accepts(monkeypatch):
    monkeypatch.setattr(ttlock, "create_period_code", lambda *a, **k: ("4821937", "code-old"))
    _, apartment, stay = _stay(registered_minutes_ago=1)
    door_codes.reconcile()
    row = db.query_one("SELECT * FROM door_code WHERE reservation_id = ?", (stay,))
    assert row["state"] == door_codes.ISSUED
    old_valid_to = row["valid_to"]

    reservation = db.query_one("SELECT date_from, date_to FROM reservation WHERE id = ?", (stay,))
    apt = db.query_one(
        "SELECT checkin_hour, checkout_hour FROM apartment WHERE id = ?", (apartment,)
    )
    new_to = (
        datetime.fromisoformat(reservation["date_to"]).date() + timedelta(days=2)
    ).isoformat()
    db.execute("UPDATE reservation SET date_to = ? WHERE id = ?", (new_to, stay))

    changes = []

    def record_change(account_id, lock_id, code_id, start_ms, end_ms, priority):
        changes.append((code_id, start_ms, end_ms))

    monkeypatch.setattr(ttlock, "change_code_period", record_change)
    door_codes.reconcile()

    row = db.query_one("SELECT * FROM door_code WHERE reservation_id = ?", (stay,))
    assert row["provider_code_id"] == "code-old"
    assert row["valid_to"] != old_valid_to
    assert changes and changes[0][0] == "code-old"
    _, end_ms = ttlock.stay_window(
        reservation["date_from"],
        new_to,
        apt["checkin_hour"],
        apt["checkout_hour"],
        config.DOOR_CODE_BUFFER_HOURS,
    )
    assert door_codes._iso_to_ms(row["valid_to"]) == end_ms
    assert db.query_one(
        "SELECT 1 AS ok FROM audit WHERE action = 'door_code_moved' AND detail LIKE ?",
        (f"%door_code={row['id']}%",),
    )


def test_a_never_used_code_is_replaced_not_retried_forever(monkeypatch):
    """TTLock -3008 on change: create a new passcode instead of retrying change forever."""
    assert ttlock.ERROR_KINDS[-3008] == "unused_code"
    monkeypatch.setattr(ttlock, "create_period_code", lambda *a, **k: ("4821937", "code-old"))
    _, apartment, stay = _stay(registered_minutes_ago=1)
    door_codes.reconcile()
    row = db.query_one("SELECT * FROM door_code WHERE reservation_id = ?", (stay,))
    assert row["state"] == door_codes.ISSUED
    assert row["provider_code_id"] == "code-old"

    res = db.query_one("SELECT date_to FROM reservation WHERE id = ?", (stay,))
    new_to = (datetime.fromisoformat(res["date_to"]).date() + timedelta(days=2)).isoformat()
    db.execute("UPDATE reservation SET date_to = ? WHERE id = ?", (new_to, stay))

    def refuse_change(*args, **kwargs):
        raise ttlock.TTLockError("never used", code=-3008, kind="unused_code")

    deleted = []

    monkeypatch.setattr(ttlock, "change_code_period", refuse_change)
    monkeypatch.setattr(ttlock, "create_period_code", lambda *a, **k: ("9911223", "code-new"))
    monkeypatch.setattr(ttlock, "delete_code", lambda *a, **k: deleted.append(a[2]))

    door_codes.reconcile()
    row = db.query_one("SELECT * FROM door_code WHERE reservation_id = ?", (stay,))
    assert row["provider_code_id"] == "code-new"
    assert db.decrypt_field(row["pin_enc"]) == "9911223"
    assert row["next_attempt_at"] is None
    assert deleted == ["code-old"]
    assert db.query_one(
        "SELECT 1 AS ok FROM audit WHERE action = 'door_code_replaced' AND detail LIKE ?",
        (f"%door_code={row['id']}%",),
    )
