"""One filter model for the host list pages (Stay fee, Invoices).

Both pages share the same controls and behaviour: a month with previous/next
steps, a property, a status, and, on Invoices only, a text search. A page
passes only what genuinely differs: whether a month is required, its default,
the status options and whether search is offered.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from typing import Iterable, Optional, Sequence, Tuple
from urllib.parse import urlencode

from . import stay_fee

SEARCH_MAX = 60


@dataclass(frozen=True)
class ListFilter:
    month: Optional[date]
    apartment_id: Optional[int]
    status: str
    q: str
    default_month: Optional[date]

    @property
    def month_key(self) -> str:
        return stay_fee.month_key(self.month) if self.month else ""

    def active_count(self) -> int:
        """Filters that differ from the page's default view."""
        return sum((
            self.month != self.default_month,
            self.apartment_id is not None,
            bool(self.status),
            bool(self.q),
        ))

    def query(self, **changes) -> str:
        """Query string for this view with some fields changed ('' when empty)."""
        view = replace(self, **changes) if changes else self
        params = []
        if view.month:
            params.append(("month", stay_fee.month_key(view.month)))
        if view.apartment_id is not None:
            params.append(("apartment", str(view.apartment_id)))
        if view.status:
            params.append(("status", view.status))
        if view.q:
            params.append(("q", view.q))
        return urlencode(params)


def parse(
    params,
    *,
    today: date,
    statuses: Iterable[str],
    default_month: Optional[date],
    apartment_ids: Iterable[int],
) -> ListFilter:
    """Read the query string; anything unknown or out of range falls back."""
    month = stay_fee.parse_month(params.get("month"))
    if month is not None and not (date(2000, 1, 1) <= month <= today.replace(day=1)):
        month = None
    if month is None:
        month = default_month
    raw_apartment = (params.get("apartment") or "").strip()
    apartment_id = int(raw_apartment) if raw_apartment.isdigit() else None
    if apartment_id not in set(apartment_ids):
        apartment_id = None
    status = (params.get("status") or "").strip()
    if status not in set(statuses):
        status = ""
    q = " ".join((params.get("q") or "").split())[:SEARCH_MAX]
    return ListFilter(month, apartment_id, status, q, default_month)


def context(
    view: ListFilter,
    *,
    action: str,
    today: date,
    period_label_key: str,
    properties: Sequence,
    statuses: Sequence[Tuple[str, str]],
    search: bool = False,
) -> dict:
    """Template context for ``_list_filter.html``."""
    max_month = today.replace(day=1)
    anchor = view.month or max_month
    prev_month = stay_fee.shift_month(anchor, -1)
    next_month = stay_fee.shift_month(anchor, 1)
    has_next = view.month is not None and next_month <= max_month

    def href(**changes) -> str:
        query = view.query(**changes)
        return f"{action}?{query}" if query else action

    return {
        "filter": view,
        "filter_action": action,
        "filter_period_label_key": period_label_key,
        "filter_max_month": stay_fee.month_key(max_month),
        "filter_prev_href": href(month=prev_month),
        "filter_next_href": href(month=next_month) if has_next else None,
        "filter_month_optional": view.default_month is None,
        "filter_properties": properties,
        "filter_statuses": statuses,
        "filter_search": search,
        "filter_active": view.active_count(),
        "filter_reset_href": action,
    }
