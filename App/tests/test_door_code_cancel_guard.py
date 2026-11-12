"""1116: the cancellation pass must not overwrite a row that issue() has claimed.

_handle_cancellations reads the door codes of cancelled stays with one SELECT
and writes each row afterwards. issue() also runs outside the scheduler (the
guest registration request calls on_registration_complete), so it can claim a
pending row in between. These tests run issue()'s claim at that moment by
wrapping db.query: no threads, no sleeps.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app import db, deadlines, door_codes

PREFIX = "dc-cguard-"
_counter = 0

CANCEL_SELECT = "SELECT dc.* FROM door_code dc"
# The claim UPDATE at the top of door_codes.issue, verbatim.
CLAIM_SQL = (
    "UPDATE door_code SET state = ?, claimed_at = ?, attempts = attempts + 1, updated_at = ? "
    "WHERE id = ? AND state IN (?, ?) AND (next_attempt_at IS NULL OR next_attempt_at <= ?) "
    "AND (claimed_at IS NULL OR claimed_at < ?)"
)


@pytest.fixture(autouse=True)
def _env():
    db.init_db()
    _purge()
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


def _cancelled_stay() -> tuple[int, int]:
    """A registered manual stay on a property with a lock, then cancelled. Returns apartment, stay."""
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
            "name": "Guard",
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
    today = deadlines.local_now().date()
    stay = db.insert(
        "reservation",
        {
            "apartment_id": apartment,
            "source": "manual",
            "uid": f"{PREFIX}stay-{_counter}",
            "date_from": today.isoformat(),
            "date_to": (today + timedelta(days=1)).isoformat(),
            "status": "cancelled",
            "registration_completed_at": now,
            "created_at": now,
            "updated_at": now,
        },
    )
    return apartment, stay


def _code(apartment: int, stay: int, state: str, valid_to: str | None = None) -> int:
    now = db.utcnow()
    values = {
        "reservation_id": stay,
        "apartment_id": apartment,
        "lock_id": "35662508",
        "code_kind": "random",
        "state": state,
        "attempts": 0,
        "created_at": now,
        "updated_at": now,
    }
    if valid_to is not None:
        values["valid_to"] = valid_to
        values["pin_enc"] = db.encrypt_field("4821937")
        values["provider_code_id"] = "pid-1"
        values["issued_at"] = now
    return db.insert("door_code", values)


def _state(row_id: int):
    row = db.query_one("SELECT state FROM door_code WHERE id = ?", (row_id,))
    return row["state"] if row else None


def _claim(row_id: int) -> int:
    """Run issue()'s claim on the row, as a guest request would."""
    now = door_codes._now()
    now_iso = door_codes._iso(now)
    cutoff = door_codes._iso(now - timedelta(minutes=door_codes.LEASE_MINUTES))
    return db.execute(
        CLAIM_SQL,
        (
            door_codes.ISSUING,
            now_iso,
            now_iso,
            row_id,
            door_codes.PENDING,
            door_codes.RETRYING,
            now_iso,
            cutoff,
        ),
    )


def _claim_after_select(monkeypatch, row_id: int, revive_stay: int | None = None) -> dict:
    """Claim the row right after _handle_cancellations' SELECT has read it."""
    real_query = db.query
    seen: dict = {}

    def query(sql, params=()):
        rows = real_query(sql, params)
        if not seen and sql.startswith(CANCEL_SELECT):
            if revive_stay is not None:
                db.execute(
                    "UPDATE reservation SET status = 'active' WHERE id = ?", (revive_stay,)
                )
            seen["claimed"] = _claim(row_id)
        return rows

    monkeypatch.setattr(db, "query", query)
    return seen


def test_a_row_claimed_after_the_select_is_not_revoked(monkeypatch):
    apartment, stay = _cancelled_stay()
    row_id = _code(apartment, stay, door_codes.PENDING)
    seen = _claim_after_select(monkeypatch, row_id)

    door_codes._handle_cancellations(db.utcnow())

    assert seen == {"claimed": 1}
    assert _state(row_id) == door_codes.ISSUING


def test_a_claimed_row_is_not_deleted_when_the_stay_comes_back(monkeypatch):
    # Revived between the SELECT and issue()'s eligibility check: issue() goes
    # on to create the TTLock code, so its row must still be there.
    apartment, stay = _cancelled_stay()
    row_id = _code(apartment, stay, door_codes.PENDING)
    seen = _claim_after_select(monkeypatch, row_id, revive_stay=stay)

    door_codes._handle_cancellations(db.utcnow())

    assert seen == {"claimed": 1}
    assert _state(row_id) == door_codes.ISSUING


def test_an_unclaimed_pending_row_of_a_cancelled_stay_is_revoked():
    apartment, stay = _cancelled_stay()
    row_id = _code(apartment, stay, door_codes.PENDING)

    door_codes._handle_cancellations(db.utcnow())

    assert _state(row_id) == door_codes.REVOKED


def test_an_issued_row_of_a_cancelled_stay_goes_to_revoke_pending(monkeypatch):
    monkeypatch.setattr(door_codes, "_revoke_one", lambda row_id: None)
    future = (datetime.now(timezone.utc) + timedelta(days=2)).replace(microsecond=0).isoformat()
    apartment, stay = _cancelled_stay()
    row_id = _code(apartment, stay, door_codes.ISSUED, valid_to=future)

    door_codes._handle_cancellations(db.utcnow())

    assert _state(row_id) == door_codes.REVOKE_PENDING


def test_keep_issued_does_not_overwrite_a_revoked_row():
    apartment, stay = _cancelled_stay()
    row = _code(apartment, stay, "revoked", valid_to="2099-01-01T00:00:00+00:00")
    door_codes._keep_issued(row, db.utcnow())
    assert _state(row) == "revoked"


def test_keep_issued_still_restores_a_revoke_pending_row():
    apartment, stay = _cancelled_stay()
    row = _code(apartment, stay, "revoke_pending", valid_to="2099-01-01T00:00:00+00:00")
    door_codes._keep_issued(row, db.utcnow())
    assert _state(row) == "issued"


def test_reactivated_delete_leaves_a_row_that_moved_on(monkeypatch):
    apartment, stay = _cancelled_stay()
    db.execute("UPDATE reservation SET status = 'active' WHERE id = ?", (stay,))
    row = _code(apartment, stay, "revoked")
    real_query = db.query
    seen: dict = {}

    def query(sql, params=()):
        rows = real_query(sql, params)
        if not seen and "r.status = 'active' AND r.archived_at IS NULL" in sql and params == ("revoked",):
            seen["moved"] = db.execute(
                "UPDATE door_code SET state = 'pending' WHERE id = ?", (row,)
            )
        return rows

    monkeypatch.setattr(db, "query", query)
    door_codes._handle_cancellations(db.utcnow())
    assert seen.get("moved") == 1
    assert _state(row) == "pending"
