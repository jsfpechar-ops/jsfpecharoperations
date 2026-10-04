"""Milestone celebrations and the lightweight time-saved estimate."""
from __future__ import annotations

from typing import Optional, Tuple

from . import db

MILESTONES = (10, 50, 100, 250, 500, 1000)
MINUTES_PER_MANUAL_REPORT = 8


def sent_guest_count(owner_user_id: Optional[int] = None) -> int:
    row = db.query_one(
        """
        SELECT COUNT(*) AS n
        FROM guest g
        JOIN reservation r ON r.id = g.reservation_id
        JOIN apartment a ON a.id = r.apartment_id
        WHERE g.submit_state = 'sent'
          -- WP23: a guest filed by hand in UbyPort saved the host nothing.
          AND g.manual_filed_at IS NULL
          AND (? IS NULL OR a.owner_user_id = ?)
        """,
        (owner_user_id, owner_user_id),
    )
    return int(row["n"]) if row else 0


def minutes_saved(owner_user_id: Optional[int] = None) -> int:
    return sent_guest_count(owner_user_id) * MINUTES_PER_MANUAL_REPORT


def _last_celebrated(owner_user_id: int) -> int:
    return int(db.get_setting(f"celebration_{owner_user_id}", "0") or 0)


def pending_milestone(owner_user_id: int) -> Optional[int]:
    """Highest milestone reached but not yet congratulated."""
    count = sent_guest_count(owner_user_id)
    last = _last_celebrated(owner_user_id)
    reached = [m for m in MILESTONES if count >= m]
    if not reached:
        return None
    highest = max(reached)
    return highest if highest > last else None


def acknowledge(owner_user_id: int, milestone: int) -> None:
    db.set_setting(f"celebration_{owner_user_id}", str(milestone))


def celebration_context(owner_user_id: int) -> Tuple[Optional[int], int, int]:
    milestone = pending_milestone(owner_user_id)
    count = sent_guest_count(owner_user_id)
    return milestone, count, minutes_saved(owner_user_id)
