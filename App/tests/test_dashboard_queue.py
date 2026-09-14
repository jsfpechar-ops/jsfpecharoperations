"""The Overview is a work queue, so a stay that needs a host must appear in it.

The failure these guard against is silent: the stay sits under "Upcoming",
the host reads "nothing needs action", and the three-working-day window closes.
"""
from __future__ import annotations

from app import reporting


def _row(reservation_id: int, status: str, urgency: str = "soon") -> dict:
    return {
        "reservation": {"id": reservation_id},
        "progress": {"status": status},
        "urgency": urgency,
    }


def _bucket_of(groups: dict, reservation_id: int) -> str:
    for name, rows in groups.items():
        if any(row["reservation"]["id"] == reservation_id for row in rows):
            return name
    return "nowhere"


def test_a_stay_waiting_on_a_passport_check_is_work_for_the_host():
    """Only the host can clear ``awaiting_verification``.

    Every guest has filled the form. Nothing else will happen on its own: a
    manual apartment never auto-sends, so if this is not on the queue the host
    has no reason to open the app before the deadline passes.
    """
    groups = reporting.queue_groups([_row(1, "awaiting_verification", "soon")])

    assert _bucket_of(groups, 1) == "needs_action"


def test_a_passport_check_is_not_hidden_until_it_is_already_late():
    """Surfacing it only once overdue is surfacing it too late to comply."""
    groups = reporting.queue_groups([_row(1, "awaiting_verification", "future")])

    assert _bucket_of(groups, 1) != "upcoming"


def test_a_stay_waiting_on_the_guest_is_not_filed_as_host_work():
    """The host cannot fill the form for a guest who has not arrived."""
    groups = reporting.queue_groups([_row(1, "awaiting_guest", "soon")])

    assert _bucket_of(groups, 1) == "waiting"


def test_finished_stays_stay_out_of_the_queue():
    groups = reporting.queue_groups(
        [_row(1, "reported", "ok"), _row(2, "not_required", "ok")]
    )

    assert _bucket_of(groups, 1) == "completed"
    assert _bucket_of(groups, 2) == "completed"


def test_rejected_and_incomplete_stays_are_host_work():
    groups = reporting.queue_groups(
        [_row(1, "failed"), _row(2, "incomplete"), _row(3, "ready")]
    )

    assert [row["reservation"]["id"] for row in groups["needs_action"]] == [1, 2, 3]


def test_a_stay_lands_in_exactly_one_bucket():
    """Double-counting a stay makes the queue counts lie."""
    rows = [
        _row(1, "failed", "overdue"),
        _row(2, "awaiting_guest", "soon"),
        _row(3, "awaiting_verification", "soon"),
        _row(4, "reported", "ok"),
        _row(5, "awaiting_guest", "overdue"),
    ]

    groups = reporting.queue_groups(rows)

    seen = [row["reservation"]["id"] for rows_ in groups.values() for row in rows_]
    assert sorted(seen) == [1, 2, 3, 4, 5]
    assert len(seen) == len(set(seen))


def test_an_overdue_stay_waiting_on_a_guest_becomes_host_work():
    """Past the deadline the host has to chase, or report what they have."""
    groups = reporting.queue_groups([_row(1, "awaiting_guest", "overdue")])

    assert _bucket_of(groups, 1) == "needs_action"


def test_the_counts_match_the_buckets():
    rows = [
        _row(1, "awaiting_verification", "soon"),
        _row(2, "awaiting_guest", "soon"),
        _row(3, "ready", "urgent"),
        _row(4, "failed", "overdue"),
    ]

    groups = reporting.queue_groups(rows)
    counts = reporting.queue_counts(rows, groups)

    assert counts["attention"] == len(groups["needs_action"]) == 3
    assert counts["awaiting"] == len(groups["waiting"]) == 1
    assert counts["ready"] == 1
    assert counts["overdue"] == 1
