"""The shared Stay fee / Invoices filter model."""
from __future__ import annotations

from datetime import date

from app import list_filter

TODAY = date(2026, 9, 15)


def _parse(params, default=None):
    return list_filter.parse(
        params, today=TODAY, statuses=("paid", "unpaid"), default_month=default, apartment_ids=(4, 7)
    )


def test_unknown_values_fall_back_to_the_default_view():
    view = _parse({"month": "2027-01", "apartment": "99", "status": "bogus", "q": "  "}, date(2026, 8, 1))
    assert (view.month, view.apartment_id, view.status, view.q) == (date(2026, 8, 1), None, "", "")
    assert view.active_count() == 0


def test_active_filters_are_counted_and_kept_in_links():
    view = _parse({"month": "2026-07", "apartment": "7", "status": "paid", "q": "Novák  s.r.o."})
    assert view.q == "Novák s.r.o."
    assert view.active_count() == 4
    ctx = list_filter.context(view, action="/invoices", today=TODAY, period_label_key="x",
                              properties=(), statuses=(), search=True)
    assert ctx["filter_prev_href"].startswith("/invoices?month=2026-06&apartment=7&status=paid&q=")
    assert ctx["filter_next_href"].startswith("/invoices?month=2026-08&")
    assert ctx["filter_reset_href"] == "/invoices"


def test_no_next_month_past_the_current_one():
    view = _parse({"month": "2026-09"})
    ctx = list_filter.context(view, action="/stay-fees", today=TODAY, period_label_key="x",
                              properties=(), statuses=())
    assert ctx["filter_next_href"] is None
