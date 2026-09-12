"""Milestone celebrations and minutes-saved estimate."""
from __future__ import annotations

from app import auth, celebrations, db


PASSWORD = "Secure-Password-123"
USERNAME = "celebration-host"


def _clean() -> None:
    db.init_db()
    for username in (USERNAME, "celebration-other"):
        user = db.query_one("SELECT id FROM user_account WHERE username = ?", (username,))
        if not user:
            continue
        owner_id = user["id"]
        db.execute(
            "DELETE FROM guest WHERE reservation_id IN "
            "(SELECT id FROM reservation WHERE apartment_id IN "
            "(SELECT id FROM apartment WHERE owner_user_id = ?))",
            (owner_id,),
        )
        db.execute(
            "DELETE FROM reservation WHERE apartment_id IN "
            "(SELECT id FROM apartment WHERE owner_user_id = ?)",
            (owner_id,),
        )
        db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (owner_id,))
        db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (owner_id,))
        db.execute("DELETE FROM user_account WHERE id = ?", (owner_id,))
        db.execute("DELETE FROM settings WHERE key = ?", (f"celebration_{owner_id}",))


def _owner(username: str = USERNAME) -> int:
    return auth.create_account(
        username, PASSWORD, "Celebration host", must_change_password=False
    )


def _reservation(owner_id: int, token: str) -> int:
    entity_id = db.insert(
        "legal_entity",
        {"name": f"{token} entity", "owner_user_id": owner_id, "created_at": db.utcnow()},
    )
    apartment_id = db.insert(
        "apartment",
        {
            "legal_entity_id": entity_id,
            "owner_user_id": owner_id,
            "internal_name": f"{token} flat",
            "permalink_token": token,
            "permalink_pin": "1234",
            "automation_mode": "manual",
            "submit_after_hours": 24,
            "permalink_window_days": 3,
            "default_purpose": "10",
            "active": 1,
            "created_at": db.utcnow(),
        },
    )
    return db.insert(
        "reservation",
        {
            "apartment_id": apartment_id,
            "source": "manual",
            "uid": f"{token}-stay",
            "date_from": "2026-09-01",
            "date_to": "2026-09-05",
            "status": "active",
            "created_at": db.utcnow(),
            "updated_at": db.utcnow(),
        },
    )


def _add_sent_guests(reservation_id: int, count: int) -> None:
    now = db.utcnow()
    for _ in range(count):
        db.insert(
            "guest",
            {
                "reservation_id": reservation_id,
                "entered_by": "host",
                "submit_state": "sent",
                "created_at": now,
                "updated_at": now,
            },
        )


def test_sent_guest_count_and_minutes_saved_are_owner_scoped():
    _clean()
    owner_id = _owner()
    other_id = _owner("celebration-other")
    try:
        _add_sent_guests(_reservation(owner_id, "celebration-a"), 3)
        _add_sent_guests(_reservation(other_id, "celebration-b"), 5)

        assert celebrations.sent_guest_count(owner_id) == 3
        assert celebrations.sent_guest_count(other_id) == 5
        assert celebrations.minutes_saved(owner_id) == 3 * celebrations.MINUTES_PER_MANUAL_REPORT
    finally:
        _clean()


def test_pending_milestone_returns_highest_unacknowledged_threshold():
    _clean()
    owner_id = _owner()
    reservation_id = _reservation(owner_id, "celebration-milestone")
    try:
        assert celebrations.pending_milestone(owner_id) is None

        _add_sent_guests(reservation_id, 9)
        assert celebrations.pending_milestone(owner_id) is None

        _add_sent_guests(reservation_id, 1)
        assert celebrations.pending_milestone(owner_id) == 10

        celebrations.acknowledge(owner_id, 10)
        assert celebrations.pending_milestone(owner_id) is None

        _add_sent_guests(reservation_id, 40)
        assert celebrations.pending_milestone(owner_id) == 50
    finally:
        _clean()


def test_celebration_context_reflects_acknowledged_state():
    _clean()
    owner_id = _owner()
    reservation_id = _reservation(owner_id, "celebration-context")
    try:
        _add_sent_guests(reservation_id, 12)
        milestone, count, minutes = celebrations.celebration_context(owner_id)
        assert milestone == 10
        assert count == 12
        assert minutes == 12 * celebrations.MINUTES_PER_MANUAL_REPORT

        celebrations.acknowledge(owner_id, 10)
        milestone, count, minutes = celebrations.celebration_context(owner_id)
        assert milestone is None
        assert count == 12
        assert minutes == 12 * celebrations.MINUTES_PER_MANUAL_REPORT
    finally:
        _clean()
