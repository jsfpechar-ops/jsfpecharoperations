"""0765: phone Today lists stays in the check-in window (_key_rows)."""
from __future__ import annotations

from datetime import date

from app.routes.admin import _key_rows


def _row(date_from: str, date_to: str, *, status: str = "active") -> dict:
    return {"reservation": {"date_from": date_from, "date_to": date_to, "status": status}}


def test_key_rows_classifies_stays_in_the_window():
    today = date(2026, 11, 5)
    rows = [
        _row("2026-11-03", "2026-11-07"),  # arrived (in window, not today/tomorrow/leaves)
        _row("2026-11-05", "2026-11-08"),  # today
        _row("2026-11-06", "2026-11-09"),  # tomorrow
        _row("2026-11-01", "2026-11-05"),  # leaves today (check-in before window)
        _row("2026-11-10", "2026-11-12"),  # check-in after tomorrow
        _row("2026-10-28", "2026-10-30"),  # ended before the window
    ]
    kinds = {
        str(r["reservation"]["date_from"])[:10]: r["key_kind"]
        for r in _key_rows(rows, today)
    }
    assert kinds == {
        "2026-11-01": "leaves",
        "2026-11-03": "arrived",
        "2026-11-05": "today",
        "2026-11-06": "tomorrow",
    }


def test_key_rows_skips_inactive_stays():
    today = date(2026, 11, 5)
    rows = [_row("2026-11-05", "2026-11-08", status="cancelled")]
    assert _key_rows(rows, today) == []
