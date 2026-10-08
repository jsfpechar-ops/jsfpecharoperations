"""Host funnel for the admin, read from rows that already exist (WP11, review 5.2).

No new tracking: every stage is the first row of some table the product writes
anyway. One aggregate query returns one row per host account; nothing here
touches a guest table beyond counting completed stays and filings, so the page
and the CSV carry host account data only (e-mail-like username and name are
fine here, guest data is not).

WP20 (self sign-up) fills the hook: ``SIGNUP_STAGES`` adds "signed up" and
"e-mail verified" before "created" (admin-created accounts have neither), and
``SIGNUP_SOURCE_COLUMNS`` adds "UTM or ad click present" (yes/no, empty for an
account that did not sign up itself); WP21 adds the stored source (google,
meta or none). Every consumer (the page, the stage
counts and the CSV) reads ``stages()`` and ``csv_columns()``.
"""
from __future__ import annotations

import csv
import io
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, Iterator, List, Optional, Tuple
from zoneinfo import ZoneInfo

from . import config, db
from .csv_safety import csv_safe

# Safety cap; far above the host count this page is meant for.
MAX_ROWS = 5000

# WP20: stages before "created", as (key, column in the query row).
SIGNUP_STAGES: Tuple[Tuple[str, str], ...] = (
    ("signed_up", "signup_at"),
    ("email_verified", "email_verified_at"),
)
# WP20: extra per-account columns for the CSV, as (key, column).
SIGNUP_SOURCE_COLUMNS: Tuple[Tuple[str, str], ...] = (
    ("signup_source_present", "signup_source_present"),
    # WP21: google, meta or none (signup.signup_source).
    ("signup_source", "signup_source"),
)

# The funnel order. A host's stage is the furthest one with a date.
CORE_STAGES: Tuple[Tuple[str, str], ...] = (
    ("created", "created_at"),
    ("first_login", "first_login_at"),
    ("legal_accepted", "legal_accepted_at"),
    ("first_entity", "first_entity_at"),
    ("first_property", "first_property_at"),
    ("first_calendar", "first_calendar_at"),
    ("first_guest", "first_guest_at"),
    ("first_filing", "first_filing_at"),
    ("retained", "retained_at"),
)

FILED_STATES = ("ok", "ok_duplicate", "partial")


def stages() -> Tuple[Tuple[str, str], ...]:
    return SIGNUP_STAGES + CORE_STAGES


def _month_starts(now: Optional[datetime] = None) -> Tuple[str, str, str, str]:
    """UTC ISO bounds of the previous and current local calendar month.

    Returns (previous start, current start, previous label, current label).
    """
    zone = ZoneInfo(config.TIMEZONE)
    local = (now or datetime.now(timezone.utc)).astimezone(zone)
    current = local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    previous = (
        current.replace(year=current.year - 1, month=12)
        if current.month == 1
        else current.replace(month=current.month - 1)
    )

    def utc(moment: datetime) -> str:
        return moment.astimezone(timezone.utc).replace(microsecond=0).isoformat()

    return utc(previous), utc(current), previous.strftime("%Y-%m"), current.strftime("%Y-%m")


_FILED = ", ".join("?" for _ in FILED_STATES)

# Correlated subqueries keyed on owner_user_id use the existing owner indexes
# (idx_audit_owner, idx_entity_owner, idx_apartment_owner); the per-host
# filing numbers come from one grouped join over submission.
_SQL = (
    "SELECT u.id, u.username, u.display_name, u.active, u.created_at, u.last_login_at, "
    "u.signup_at, u.email_verified_at, u.signup_source, "
    # WP20: did the self sign-up carry a UTM label or a consented ad click?
    "CASE WHEN u.signup_at IS NULL THEN NULL "
    "WHEN COALESCE(u.signup_utm_source, '') <> '' OR COALESCE(u.signup_utm_medium, '') <> '' "
    "OR COALESCE(u.signup_utm_campaign, '') <> '' "
    "OR EXISTS (SELECT 1 FROM ad_click c WHERE c.user_account_id = u.id) "
    "THEN 'yes' ELSE 'no' END AS signup_source_present, "
    "COALESCE((SELECT MIN(au.at) FROM audit au WHERE au.owner_user_id = u.id "
    "AND au.action IN ('login', 'two_factor_login')), u.last_login_at) AS first_login_at, "
    "(SELECT MIN(la.accepted_at) FROM legal_acceptance la "
    "WHERE la.user_account_id = u.id) AS legal_accepted_at, "
    "(SELECT MIN(le.created_at) FROM legal_entity le "
    "WHERE le.owner_user_id = u.id) AS first_entity_at, "
    "(SELECT MIN(a.created_at) FROM apartment a "
    "WHERE a.owner_user_id = u.id) AS first_property_at, "
    "(SELECT MIN(f.created_at) FROM ical_feed f JOIN apartment a ON a.id = f.apartment_id "
    "WHERE a.owner_user_id = u.id AND f.last_status = 'ok') AS first_calendar_at, "
    "(SELECT MIN(r.registration_completed_at) FROM reservation r "
    "JOIN apartment a ON a.id = r.apartment_id "
    "WHERE a.owner_user_id = u.id AND r.registration_completed_at IS NOT NULL) AS first_guest_at, "
    "fs.first_filing_at, fs.last_filing_at, "
    "COALESCE(fs.filings_previous, 0) AS filings_previous, "
    "COALESCE(fs.filings_current, 0) AS filings_current "
    "FROM user_account u "
    "LEFT JOIN ("
    "SELECT a.owner_user_id, "
    "MIN(COALESCE(s.finished_at, s.created_at)) AS first_filing_at, "
    "MAX(COALESCE(s.finished_at, s.created_at)) AS last_filing_at, "
    "SUM(CASE WHEN s.created_at >= ? AND s.created_at < ? THEN 1 ELSE 0 END) AS filings_previous, "
    "SUM(CASE WHEN s.created_at >= ? THEN 1 ELSE 0 END) AS filings_current "
    "FROM submission s JOIN apartment a ON a.id = s.apartment_id "
    f"WHERE s.state IN ({_FILED}) GROUP BY a.owner_user_id"
    ") fs ON fs.owner_user_id = u.id "
    "WHERE u.role = 'host' ORDER BY u.created_at, u.id LIMIT ?"
)


def rows(now: Optional[datetime] = None) -> Dict[str, Any]:
    """One dict per host account, the stage counts, and the month labels."""
    previous_start, current_start, previous_label, current_label = _month_starts(now)
    raw = db.query(
        _SQL,
        (previous_start, current_start, current_start, *FILED_STATES, MAX_ROWS),
    )
    order = stages()
    items: List[Dict[str, Any]] = []
    for row in raw:
        item = dict(row)
        # Retained: filed in both of the last two calendar months.
        item["retained_at"] = (
            item["last_filing_at"]
            if item["filings_previous"] and item["filings_current"]
            else None
        )
        stage, stage_at = "", None
        for key, column in order:
            if item.get(column):
                stage, stage_at = key, item[column]
        item["stage"] = stage
        item["stage_at"] = stage_at
        item["stages_done"] = sum(1 for _key, column in order if item.get(column))
        items.append(item)
    counts = {key: 0 for key, _column in order}
    for item in items:
        for key, column in order:
            if item.get(column):
                counts[key] += 1
    return {
        "rows": items,
        "counts": counts,
        "stages": [key for key, _column in order],
        "stage_columns": list(order),
        "previous_month": previous_label,
        "current_month": current_label,
        "stages_total": len(order),
    }


def csv_columns(previous_month: str, current_month: str) -> List[Tuple[str, str]]:
    """(header, row key) pairs, the same columns as the page table."""
    columns: List[Tuple[str, str]] = [
        ("account_id", "id"),
        ("username", "username"),
        ("name", "display_name"),
        ("active", "active"),
    ]
    columns += [(key, column) for key, column in SIGNUP_SOURCE_COLUMNS]
    columns += [(key, column) for key, column in stages()]
    columns += [
        (f"filings_{previous_month}", "filings_previous"),
        (f"filings_{current_month}", "filings_current"),
        ("last_login", "last_login_at"),
        ("last_filing", "last_filing_at"),
        ("stage", "stage"),
        ("stage_at", "stage_at"),
    ]
    return columns


def iter_csv(data: Dict[str, Any]) -> Iterator[str]:
    columns = csv_columns(data["previous_month"], data["current_month"])
    buffer = io.StringIO()
    writer = csv.writer(buffer)

    def flush() -> str:
        value = buffer.getvalue()
        buffer.seek(0)
        buffer.truncate(0)
        return value

    writer.writerow([header for header, _key in columns])
    yield flush()
    for item in data["rows"]:
        writer.writerow(
            [csv_safe("" if item.get(key) is None else item.get(key)) for _header, key in columns]
        )
        yield flush()


WEEKS = 12
ACTIVE_DAYS = 30


def overview(data: Dict[str, Any], now: Optional[datetime] = None) -> Dict[str, Any]:
    """Stat cards and funnel bars, computed from what rows() already returned."""
    moment = now or datetime.now(timezone.utc)
    cutoff = (moment - timedelta(days=ACTIVE_DAYS)).replace(microsecond=0).isoformat()
    rows_ = data["rows"]
    cards = {
        "hosts": len(rows_),
        "active": sum(1 for r in rows_ if r.get("last_login_at") and r["last_login_at"] >= cutoff),
        "filings_current": sum(r["filings_current"] for r in rows_),
        "filings_previous": sum(r["filings_previous"] for r in rows_),
        "retained": data["counts"].get("retained", 0),
    }
    counts = data["counts"]
    top = max(counts.values(), default=0) or 1
    signup_keys = {key for key, _column in SIGNUP_STAGES}
    bars: List[Dict[str, Any]] = []
    previous: Optional[int] = None
    for key in data["stages"]:
        count = counts[key]
        if key in signup_keys and count == 0:
            continue  # self sign-up is off: do not show two empty rows
        width = round(100 * count / top)
        bars.append(
            {
                "key": key,
                "count": count,
                "width": max(width, 2) if count else 0,
                "of_previous": round(100 * count / previous) if previous else None,
            }
        )
        previous = count
    return {"cards": cards, "bars": bars}


def _monday(day: date) -> date:
    return day - timedelta(days=day.weekday())


def weekly(now: Optional[datetime] = None) -> Dict[str, List[Dict[str, Any]]]:
    """New host accounts and filings per week for the last WEEKS weeks (UTC)."""
    today = (now or datetime.now(timezone.utc)).date()
    first = _monday(today) - timedelta(weeks=WEEKS - 1)
    starts = [first + timedelta(weeks=i) for i in range(WEEKS)]
    since = first.isoformat()

    def bucket(sql: str, params: Tuple[Any, ...]) -> List[Dict[str, Any]]:
        totals = {start: 0 for start in starts}
        for row in db.query(sql, params):
            try:
                day = date.fromisoformat(row["day"])
            except (TypeError, ValueError):
                continue
            start = _monday(day)
            if start in totals:
                totals[start] += row["n"]
        peak = max(totals.values(), default=0) or 1
        return [
            {
                "label": start.strftime("%d.%m."),
                "value": totals[start],
                "height": max(round(100 * totals[start] / peak), 3) if totals[start] else 0,
            }
            for start in starts
        ]

    return {
        "hosts": bucket(
            "SELECT SUBSTR(created_at, 1, 10) AS day, COUNT(*) AS n FROM user_account "
            "WHERE role = 'host' AND created_at >= ? GROUP BY SUBSTR(created_at, 1, 10)",
            (since,),
        ),
        "filings": bucket(
            "SELECT SUBSTR(created_at, 1, 10) AS day, COUNT(*) AS n FROM submission "
            f"WHERE state IN ({_FILED}) AND created_at >= ? GROUP BY SUBSTR(created_at, 1, 10)",
            (*FILED_STATES, since),
        ),
    }
