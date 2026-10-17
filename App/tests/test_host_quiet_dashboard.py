from datetime import date, timedelta

from app import reporting


def test_dashboard_includes_prague_current_and_thirty_day_boundary_only():
    today = date(2026, 10, 10)

    def candidate(offset, nights=2):
        arrival = today + timedelta(days=offset)
        return reporting.dashboard_overview_candidate(
            {"date_from": arrival.isoformat(), "date_to": (arrival + timedelta(days=nights)).isoformat()},
            {"status": "awaiting_guest"},
            "future",
            today,
        )

    long_current = reporting.dashboard_overview_candidate(
        {"date_from": "2026-07-01", "date_to": "2026-10-12"},
        {"status": "awaiting_guest"}, "overdue", today,
    )

    assert long_current
    assert candidate(30)
    assert not candidate(31)


def test_dashboard_keeps_old_unresolved_failure_and_overdue_but_skips_finished():
    today = date(2026, 10, 10)
    old_stay = {"date_from": "2025-01-01", "date_to": "2025-01-03"}

    assert reporting.dashboard_overview_candidate(old_stay, {"status": "failed"}, "ok", today)
    assert reporting.dashboard_overview_candidate(old_stay, {"status": "awaiting_guest"}, "overdue", today)
    assert not reporting.dashboard_overview_candidate(old_stay, {"status": "reported"}, "overdue", today)
    assert not reporting.dashboard_overview_candidate(old_stay, {"status": "ready"}, "ok", today)


def test_dashboard_row_limit_is_five_total_and_counts_only_hidden_actionable_stays():
    needs_action = [{"reservation": {"id": stay_id}} for stay_id in range(1, 8)]
    groups = {
        "needs_action": needs_action,
        "waiting": [{"reservation": {"id": 8}}],
        "upcoming": [{"reservation": {"id": 9}}],
        "completed": [{"reservation": {"id": 10}}],
    }

    counts = reporting.queue_counts([], groups)
    shown, overflow = reporting.dashboard_display_groups(groups, today=date(2026, 10, 10))

    assert counts["attention"] == 7
    assert len(shown["needs_action"]) + len(shown["current"]) == 5
    assert [row["reservation"]["id"] for row in shown["needs_action"]] == [1, 2, 3, 4, 5]
    assert shown["current"] == []
    assert overflow == 2


def test_dashboard_fills_unused_slots_with_current_rows_without_duplicate_stays():
    groups = {
        "needs_action": [{"reservation": {"id": 1}}],
        "waiting": [{"reservation": {"id": 2}}],
        "upcoming": [{"reservation": {"id": 3}}, {"reservation": {"id": 4}}],
        "completed": [{"reservation": {"id": 5}}],
    }

    shown, overflow = reporting.dashboard_display_groups(groups, today=date(2026, 10, 10))
    ids = [row["reservation"]["id"] for section in shown.values() for row in section]

    assert len(ids) == 5
    assert len(ids) == len(set(ids))
    assert overflow == 0


def test_dashboard_prefers_a_current_stay_to_a_later_waiting_arrival():
    groups = {
        "needs_action": [],
        "waiting": [{"reservation": {"id": 2, "date_from": "2026-10-20", "date_to": "2026-10-22"}, "urgency": "future"}],
        "upcoming": [],
        "completed": [{"reservation": {"id": 1, "date_from": "2026-10-01", "date_to": "2026-10-12"}, "urgency": "overdue"}],
    }

    shown, _ = reporting.dashboard_display_groups(groups, today=date(2026, 10, 10), limit=1)

    assert [row["reservation"]["id"] for row in shown["current"]] == [1]
