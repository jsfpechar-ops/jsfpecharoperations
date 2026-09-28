"""BE-2: the retention job computes its row set, and deletes only when enabled.

Dry-run is the default (Rule 7). These tests seed expired and current guests and
assert that a dry run changes nothing, that the autopurge flag scopes deletion
to the requested owner, and that the due-notice fires once per owner per month.
"""
from __future__ import annotations

import base64
import json
import time
from datetime import date, datetime, timedelta, timezone

import pytest

from app import claim, config, db, housebook, passport_photos, scheduler, retention

PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVR4nGMAAQAABQAB"
    "DQottAAAAABJRU5ErkJggg=="
)


@pytest.fixture(autouse=True)
def _cleanup():
    db.init_db()
    _purge()
    yield
    _purge()


def _purge():
    db.init_db()
    for row in db.query("SELECT id FROM apartment WHERE permalink_token LIKE 'retjob-%'"):
        db.execute(
            "DELETE FROM guest WHERE reservation_id IN"
            " (SELECT id FROM reservation WHERE apartment_id = ?)",
            (row["id"],),
        )
        db.execute("DELETE FROM reservation WHERE apartment_id = ?", (row["id"],))
        db.execute("DELETE FROM apartment WHERE id = ?", (row["id"],))
    db.execute("DELETE FROM legal_entity WHERE name = 'RetJob'")
    for row in db.query("SELECT id FROM user_account WHERE username LIKE 'retjob-%'"):
        db.execute("DELETE FROM alert WHERE owner_user_id = ?", (row["id"],))
        db.execute("DELETE FROM audit WHERE owner_user_id = ?", (row["id"],))
        db.execute("DELETE FROM user_account WHERE id = ?", (row["id"],))
    db.execute("DELETE FROM alert WHERE dedupe_key LIKE 'retention_due:%'")
    db.execute("DELETE FROM settings WHERE key = 'retention_last_run'")


def _owner(username: str = "retjob-host") -> int:
    db.init_db()
    return db.insert(
        "user_account",
        {
            "username": username,
            "display_name": username,
            "password_hash": "x",
            "role": "host",
            "created_at": db.utcnow(),
        },
    )


def _guest(
    owner_user_id: int,
    *,
    stay_end: date,
    token: str,
    photo: bool = False,
    stay_to: str | None = None,
) -> int:
    db.init_db()
    now = db.utcnow()
    entity_id = db.insert(
        "legal_entity",
        {"name": "RetJob", "created_at": now, "owner_user_id": owner_user_id},
    )
    apartment_id = db.insert(
        "apartment",
        {
            "legal_entity_id": entity_id,
            "owner_user_id": owner_user_id,
            "internal_name": "Flat",
            "permalink_token": token,
            "automation_mode": "manual",
            "default_purpose": "10",
            "active": 1,
            "created_at": now,
        },
    )
    reservation_id = db.insert(
        "reservation",
        {
            "apartment_id": apartment_id,
            "uid": f"stay-{token}",
            "date_from": (stay_end - timedelta(days=2)).isoformat(),
            "date_to": stay_end.isoformat(),
            "status": "active",
            "created_at": now,
            "updated_at": now,
        },
    )
    guest_id = db.insert(
        "guest",
        {
            "reservation_id": reservation_id,
            "surname": "Smith",
            "first_name": "John",
            "stay_from": (stay_end - timedelta(days=2)).isoformat(),
            "stay_to": stay_to if stay_to is not None else stay_end.isoformat(),
            "nationality": "GBR",
            "purpose": "10",
            "entered_by": "guest",
            "created_at": now,
            "updated_at": now,
        },
    )
    if photo:
        passport_photos.save_photo(guest_id, PNG_BYTES, "image/png")
        assert passport_photos.has_photo(guest_id)
    return guest_id


def _six_years_ago() -> date:
    return housebook.retention_cutoff(date.today()) - timedelta(days=1)


def test_a_dry_run_counts_the_row_set_and_deletes_nothing(monkeypatch):
    monkeypatch.setattr(config, "RETENTION_AUTOPURGE", False)
    owner = _owner()
    expired = _guest(owner, stay_end=_six_years_ago(), token="retjob-old", photo=True)
    fresh = _guest(owner, stay_end=date.today() - timedelta(days=30), token="retjob-new")

    summary = retention.run()

    assert summary["dry_run"] is True
    assert summary["counts"]["guests"] >= 1
    assert db.query_one("SELECT id FROM guest WHERE id = ?", (expired,))
    assert passport_photos.has_photo(expired)
    assert db.query_one("SELECT id FROM guest WHERE id = ?", (fresh,))

    audit = db.query_one(
        "SELECT detail FROM audit WHERE action = 'retention_run' ORDER BY id DESC LIMIT 1"
    )
    assert json.loads(audit["detail"])["dry_run"] is True
    stored = json.loads(db.get_setting("retention_last_run"))
    assert stored["dry_run"] is True


def test_autopurge_deletes_only_the_scoped_owners_expired_guests(monkeypatch):
    monkeypatch.setattr(config, "RETENTION_AUTOPURGE", True)
    owner = _owner("retjob-a")
    other = _owner("retjob-b")
    expired = _guest(owner, stay_end=_six_years_ago(), token="retjob-a-old", photo=True)
    fresh = _guest(owner, stay_end=date.today() - timedelta(days=30), token="retjob-a-new")
    other_expired = _guest(other, stay_end=_six_years_ago(), token="retjob-b-old")

    summary = retention.run(dry_run=False, owner_user_id=owner)

    assert summary["dry_run"] is False
    assert db.query_one("SELECT id FROM guest WHERE id = ?", (expired,)) is None
    assert not passport_photos.has_photo(expired)
    assert db.query_one("SELECT id FROM guest WHERE id = ?", (fresh,)) is not None
    assert db.query_one("SELECT id FROM guest WHERE id = ?", (other_expired,)) is not None


def test_a_malformed_stay_to_falls_back_to_the_reservation_end():
    owner = _owner("retjob-mal")
    old = date.today() - timedelta(days=365 * 7)
    guest_id = _guest(owner, stay_end=old, token="retjob-mal", stay_to="garbage")
    assert guest_id in housebook.expired_guest_ids()


def test_the_due_notice_fires_once_per_owner_per_month(monkeypatch):
    monkeypatch.setattr(config, "RETENTION_AUTOPURGE", False)
    owner = _owner("retjob-due")
    # The six-year clock on this stay ends 15 days from today.
    stay_end = housebook.retention_cutoff(date.today()) + timedelta(days=15)
    _guest(owner, stay_end=stay_end, token="retjob-due")

    retention.run()
    key = f"retention_due:{owner}:{date.today().strftime('%Y-%m')}"
    alert = db.query_one("SELECT * FROM alert WHERE dedupe_key = ?", (key,))
    assert alert is not None
    assert alert["kind"] == "retention_due"
    params = json.loads(alert["params"])
    assert params["days"] == config.RETENTION_NOTICE_DAYS
    assert params["count"] >= 1

    retention.run()
    rows = db.query("SELECT id FROM alert WHERE dedupe_key = ?", (key,))
    assert len(rows) == 1


def test_the_scheduler_registers_the_retention_job(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "retjob.sqlite3")
    monkeypatch.setattr(config, "ENABLE_SCHEDULER", True)
    db.init_db()
    try:
        scheduler.start()
        assert scheduler._scheduler.get_job("retention") is not None
    finally:
        scheduler.shutdown()


# --- BE-3: reservation / claim / contact minimisation ------------------------


def _contact_case(
    owner_user_id: int,
    *,
    token: str,
    date_to: date,
    claim_email: str | None = "claim@example.test",
    guest_email: str | None = "guest@example.test",
    phone_last4: str | None = "1234",
    filled_ip: str | None = "203.0.113.9",
    guest: bool = True,
):
    db.init_db()
    now = db.utcnow()
    entity_id = db.insert(
        "legal_entity",
        {"name": "RetJob", "created_at": now, "owner_user_id": owner_user_id},
    )
    apartment_id = db.insert(
        "apartment",
        {
            "legal_entity_id": entity_id,
            "owner_user_id": owner_user_id,
            "internal_name": "Flat",
            "permalink_token": token,
            "automation_mode": "manual",
            "default_purpose": "10",
            "active": 1,
            "created_at": now,
        },
    )
    reservation_id = db.insert(
        "reservation",
        {
            "apartment_id": apartment_id,
            "uid": f"stay-{token}",
            "date_from": (date_to - timedelta(days=2)).isoformat(),
            "date_to": date_to.isoformat(),
            "status": "active",
            "guest_email": guest_email,
            "phone_last4": phone_last4,
            "created_at": now,
            "updated_at": now,
        },
    )
    db.insert(
        "reservation_claim",
        {
            "reservation_id": reservation_id,
            "state": "claimed",
            "email": claim_email,
            "email_masked": "c***@example.test",
            "created_at": now,
            "updated_at": now,
        },
    )
    guest_id = None
    if guest:
        guest_id = db.insert(
            "guest",
            {
                "reservation_id": reservation_id,
                "surname": "S",
                "first_name": "J",
                "stay_from": (date_to - timedelta(days=2)).isoformat(),
                "stay_to": date_to.isoformat(),
                "nationality": "GBR",
                "purpose": "10",
                "entered_by": "guest",
                "filled_ip": filled_ip,
                "created_at": now,
                "updated_at": now,
            },
        )
    return reservation_id, guest_id


def _old_end() -> date:
    return date.today() - timedelta(days=100)


def _empty_old_end() -> date:
    return housebook.retention_cutoff(date.today()) - timedelta(days=1)


def test_contact_minimisation_dry_run_changes_nothing(monkeypatch):
    monkeypatch.setattr(config, "RETENTION_AUTOPURGE", False)
    owner = _owner("retjob-c1")
    reservation_id, guest_id = _contact_case(owner, token="retjob-c1", date_to=_old_end())
    empty_id, _ = _contact_case(
        owner, token="retjob-c1e", date_to=_empty_old_end(), guest=False,
        claim_email=None, guest_email=None, phone_last4=None,
    )

    summary = retention.run(dry_run=True, owner_user_id=owner)
    counts = summary["counts"]
    assert counts["claim_emails"] >= 1
    assert counts["reservation_contacts"] >= 1
    assert counts["submitter_ips"] >= 1
    assert counts["empty_reservations"] >= 1

    assert db.query_one(
        "SELECT email FROM reservation_claim WHERE reservation_id = ?", (reservation_id,)
    )["email"] == "claim@example.test"
    row = db.query_one(
        "SELECT guest_email, phone_last4 FROM reservation WHERE id = ?", (reservation_id,)
    )
    assert row["guest_email"] and row["phone_last4"]
    assert db.query_one("SELECT filled_ip FROM guest WHERE id = ?", (guest_id,))["filled_ip"]
    assert db.query_one("SELECT id FROM reservation WHERE id = ?", (empty_id,))


def test_contact_minimisation_live_nulls_and_deletes(monkeypatch):
    monkeypatch.setattr(config, "RETENTION_AUTOPURGE", True)
    owner = _owner("retjob-c2")
    reservation_id, guest_id = _contact_case(owner, token="retjob-c2", date_to=_old_end())
    empty_id, _ = _contact_case(
        owner, token="retjob-c2e", date_to=_empty_old_end(), guest=False,
        claim_email=None, guest_email=None, phone_last4=None,
    )
    recent_id, recent_guest = _contact_case(
        owner, token="retjob-c2r", date_to=date.today() - timedelta(days=5)
    )

    summary = retention.run(dry_run=False, owner_user_id=owner)
    assert summary["counts"]["claim_emails"] >= 1

    assert db.query_one(
        "SELECT email FROM reservation_claim WHERE reservation_id = ?", (reservation_id,)
    )["email"] is None
    row = db.query_one(
        "SELECT guest_email, phone_last4 FROM reservation WHERE id = ?", (reservation_id,)
    )
    assert row["guest_email"] is None and row["phone_last4"] is None
    assert db.query_one("SELECT filled_ip FROM guest WHERE id = ?", (guest_id,))["filled_ip"] is None
    assert db.query_one("SELECT id FROM reservation WHERE id = ?", (empty_id,)) is None

    # A stay still inside the grace window is untouched.
    assert db.query_one(
        "SELECT email FROM reservation_claim WHERE reservation_id = ?", (recent_id,)
    )["email"] == "claim@example.test"
    assert db.query_one("SELECT filled_ip FROM guest WHERE id = ?", (recent_guest,))["filled_ip"]


def test_a_completion_receipt_is_not_queued_without_an_address(monkeypatch):
    owner = _owner("retjob-noaddr")
    reservation_id, _ = _contact_case(
        owner, token="retjob-noaddr", date_to=date.today(), claim_email=None
    )
    reservation = db.query_one(
        "SELECT r.*, a.permalink_token, a.internal_name, a.owner_user_id, a.legal_entity_id "
        "FROM reservation r JOIN apartment a ON a.id = r.apartment_id WHERE r.id = ?",
        (reservation_id,),
    )
    apartment = db.query_one(
        "SELECT * FROM apartment WHERE id = ?", (reservation["apartment_id"],)
    )
    monkeypatch.setattr(
        claim.reporting,
        "reservation_progress",
        lambda _r: {"expected": 1, "filled": 1, "incomplete": False, "status": "complete"},
    )
    claim.maybe_notify_completion(reservation, apartment)
    assert db.query(
        "SELECT id FROM email_outbox WHERE reservation_id = ?", (reservation_id,)
    ) == []


def test_a_reminder_sweep_survives_a_nulled_address(monkeypatch):
    monkeypatch.setattr(config, "RETENTION_AUTOPURGE", True)
    owner = _owner("retjob-c3")
    reservation_id, _ = _contact_case(owner, token="retjob-c3", date_to=_old_end())
    retention.run(dry_run=False, owner_user_id=owner)
    # Must not raise, and must queue nothing for this stay.
    claim.sweep_reminders()
    assert db.query(
        "SELECT id FROM email_outbox WHERE reservation_id = ? AND kind = 'reminder_guest'",
        (reservation_id,),
    ) == []


# --- BE-4: audit, alert, rate-limit and acceptance retention -----------------


def _days_ago_iso(days: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).replace(microsecond=0).isoformat()


def test_log_and_acceptance_retention(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "logs.sqlite3")
    monkeypatch.setattr(config, "RETENTION_AUTOPURGE", False)
    db.init_db()

    owner = db.insert(
        "user_account",
        {
            "username": "retjob-logs",
            "display_name": "l",
            "password_hash": "x",
            "role": "host",
            "created_at": db.utcnow(),
        },
    )
    # Disabled long ago, so its acceptance evidence is past "life + 3 years".
    disabled = db.insert(
        "user_account",
        {
            "username": "retjob-off",
            "display_name": "o",
            "password_hash": "x",
            "role": "host",
            "active": 0,
            "created_at": db.utcnow(),
            "last_login_at": "2019-01-01T00:00:00+00:00",
        },
    )
    old = _days_ago_iso(config.AUDIT_RETENTION_DAYS + 10)
    fresh = _days_ago_iso(1)

    for action, at, who in (
        ("login", old, owner),
        ("login", old, disabled),
        ("login", fresh, owner),
        ("legal_accepted", old, owner),
    ):
        db.execute(
            "INSERT INTO audit (at, actor, action, detail, owner_user_id) VALUES (?,?,?,?,?)",
            (at, "x", action, "", who),
        )

    db.execute(
        "INSERT INTO alert (level, kind, message, created_at, resolved_at, owner_user_id) "
        "VALUES ('warning','x','m',?,?,?)",
        (old, old, owner),
    )
    db.execute(
        "INSERT INTO alert (level, kind, message, created_at, resolved_at, owner_user_id) "
        "VALUES ('warning','x','m',?,?,?)",
        (fresh, fresh, owner),
    )
    db.execute(
        "INSERT INTO alert (level, kind, message, created_at, owner_user_id) "
        "VALUES ('warning','x','m',?,?)",
        (old, owner),
    )

    db.execute(
        "INSERT INTO rate_limit_event (scope, key, at) VALUES ('s','old',?)",
        (time.time() - 48 * 3600,),
    )
    db.execute(
        "INSERT INTO rate_limit_event (scope, key, at) VALUES ('s','new',?)",
        (time.time(),),
    )

    for who in (owner, disabled):
        db.execute(
            "INSERT INTO legal_acceptance "
            "(user_account_id, document, version, accepted_at, method) VALUES (?,?,?,?,?)",
            (who, "terms", "1.0", old, "backfill"),
        )

    dry = retention.run(dry_run=True)
    counts = dry["counts"]
    assert counts["audit_rows"] >= 2  # the two old login rows
    assert counts["alerts"] >= 1
    assert counts["rate_limit_events"] >= 1
    assert counts["legal_acceptance"] >= 1
    assert db.query_one(
        "SELECT COUNT(*) AS n FROM audit WHERE at = ? AND action = 'login'", (old,)
    )["n"] == 2, "a dry run must delete nothing"

    retention.run(dry_run=False)

    assert db.query_one(
        "SELECT COUNT(*) AS n FROM audit WHERE at = ? AND action = 'login'", (old,)
    )["n"] == 0
    assert db.query_one(
        "SELECT COUNT(*) AS n FROM audit WHERE action = 'legal_accepted'"
    )["n"] == 1, "acceptance evidence is not an ordinary audit row"
    assert db.query_one(
        "SELECT COUNT(*) AS n FROM audit WHERE at = ?", (fresh,)
    )["n"] == 1
    assert db.query_one(
        "SELECT COUNT(*) AS n FROM alert WHERE resolved_at IS NOT NULL"
    )["n"] == 1
    assert db.query_one(
        "SELECT COUNT(*) AS n FROM alert WHERE resolved_at IS NULL"
    )["n"] == 1
    assert db.query_one(
        "SELECT COUNT(*) AS n FROM rate_limit_event"
    )["n"] == 1
    assert db.query_one(
        "SELECT COUNT(*) AS n FROM legal_acceptance WHERE user_account_id = ?", (disabled,)
    )["n"] == 0
    assert db.query_one(
        "SELECT COUNT(*) AS n FROM legal_acceptance WHERE user_account_id = ?", (owner,)
    )["n"] == 1
