"""Shared host month picker navigation (stay fees, invoices)."""
from __future__ import annotations

from datetime import date

from app import list_month_filter


def test_unfiltered_view_has_no_next_month():
    nav = list_month_filter.month_filter_nav(None, date(2026, 9, 30), month_required=False)
    assert nav["month_key"] == ""
    assert nav["filter_active"] is False
    assert nav["prev_month_key"] == "2026-08"
    assert nav["next_month_key"] is None


def test_filtered_view_caps_next_month_at_today():
    nav = list_month_filter.month_filter_nav(date(2026, 9, 1), date(2026, 9, 30), month_required=False)
    assert nav["month_key"] == "2026-09"
    assert nav["filter_active"] is True
    assert nav["prev_month_key"] == "2026-08"
    assert nav["next_month_key"] is None


def test_filtered_view_can_step_forward_before_the_current_month():
    nav = list_month_filter.month_filter_nav(date(2026, 8, 1), date(2026, 9, 30), month_required=False)
    assert nav["next_month_key"] == "2026-09"


def test_month_bounds_match_the_calendar_month():
    first, last = list_month_filter.month_bounds(date(2026, 2, 15))
    assert (first, last) == (date(2026, 2, 1), date(2026, 2, 28))
