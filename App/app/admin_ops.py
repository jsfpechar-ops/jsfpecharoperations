"""Read-only numbers for the admin Operations page (WP10, review 4.2).

One question per section: what needs the operator's attention across every
workspace right now. Everything here is aggregate SQL over indexed columns with
a ``LIMIT``; nothing is decrypted and no guest field is selected, so the page
cannot show a guest's name, document or address even by accident. Feed URLs
and mail recipients are left out too: a calendar URL carries the channel's
secret token and an address is personal data the page does not need.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from . import db, reporting, scheduler

ROW_LIMIT = 50
FEED_STALE_HOURS = 3
# A batch is 'running' only while it is on the wire; the stale-batch recovery
# (reporting) takes over after the send claim lapses, so anything older than
# this is stuck rather than slow.
RUNNING_STUCK_MINUTES = 30
# A queued mail the drain should have picked up long ago.
MAIL_STUCK_MINUTES = 30

# The per-stay filing states, worst first. ``retry_cap`` is an ``error`` whose
# automatic retries are used up (reporting.SUBMISSION_MAX_AUTO_ATTEMPTS), so it
# waits for a person like the others.
FILING_STATES = ("outcome_unknown", "rejected", "retry_cap", "error")


def _iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def parse_time(value: Optional[str]) -> Optional[datetime]:
    """Read the ISO timestamps the app writes, with or without an offset."""
    if not value:
        return None
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def age_minutes(value: Optional[str], now: Optional[datetime] = None) -> Optional[int]:
    parsed = parse_time(value)
    if parsed is None:
        return None
    return max(0, int(((now or _now()) - parsed).total_seconds() // 60))


# --- filings ------------------------------------------------------------------

_FILING_FROM = (
    "FROM guest g "
    "JOIN reservation r ON r.id = g.reservation_id "
    "JOIN apartment a ON a.id = r.apartment_id "
    "LEFT JOIN submission s ON s.id = g.submission_id "
    "WHERE g.archived_at IS NULL AND r.archived_at IS NULL "
    "AND (g.submit_state IN (?, ?) "
    "OR (s.state = 'outcome_unknown' AND g.submit_state <> ?))"
)


def _filing_params() -> tuple:
    return (reporting.ERROR, reporting.BLOCKED, reporting.SENT)


def filings_needing_attention(limit: int = ROW_LIMIT) -> Dict[str, Any]:
    """Stays with a guest the register refused, could not take, or may hold.

    One row per stay. The severity is folded in SQL so the list is one query:
    3 outcome unknown, 2 rejected (blocked), 1 retry budget used up, 0 error.
    """
    count_row = db.query_one(
        f"SELECT COUNT(DISTINCT r.id) AS n {_FILING_FROM}", _filing_params()
    )
    rows = db.query(
        "SELECT r.id AS stay_id, a.id AS apartment_id, a.internal_name, "
        "a.owner_user_id, u.username AS workspace, "
        "MAX(CASE WHEN s.state = 'outcome_unknown' THEN 3 "
        "WHEN g.submit_state = ? THEN 2 "
        "WHEN g.submit_attempts >= ? THEN 1 ELSE 0 END) AS severity, "
        "MIN(COALESCE(s.finished_at, s.created_at, g.updated_at)) AS since "
        + _FILING_FROM.replace(
            "JOIN apartment a ON a.id = r.apartment_id ",
            "JOIN apartment a ON a.id = r.apartment_id "
            "LEFT JOIN user_account u ON u.id = a.owner_user_id ",
        )
        + " GROUP BY r.id, a.id, a.internal_name, a.owner_user_id, u.username "
        "ORDER BY severity DESC, since ASC LIMIT ?",
        (
            reporting.BLOCKED,
            reporting.SUBMISSION_MAX_AUTO_ATTEMPTS,
            *_filing_params(),
            limit,
        ),
    )
    now = _now()
    states = {3: "outcome_unknown", 2: "rejected", 1: "retry_cap", 0: "error"}
    items = [
        {
            "stay_id": row["stay_id"],
            "apartment_id": row["apartment_id"],
            "property": row["internal_name"],
            "owner_user_id": row["owner_user_id"],
            "workspace": row["workspace"] or "",
            "state": states.get(int(row["severity"] or 0), "error"),
            "age_minutes": age_minutes(row["since"], now),
        }
        for row in rows
    ]
    return {"count": int(count_row["n"] if count_row else 0), "rows": items}


def stuck_submissions(limit: int = ROW_LIMIT) -> Dict[str, Any]:
    """Batches still marked as on the wire long after any send could last."""
    cutoff = _iso(_now() - timedelta(minutes=RUNNING_STUCK_MINUTES))
    count_row = db.query_one(
        "SELECT COUNT(*) AS n FROM submission WHERE state = 'running' AND created_at < ?",
        (cutoff,),
    )
    rows = db.query(
        "SELECT s.id, s.created_at, a.id AS apartment_id, a.internal_name, "
        "a.owner_user_id, u.username AS workspace "
        "FROM submission s JOIN apartment a ON a.id = s.apartment_id "
        "LEFT JOIN user_account u ON u.id = a.owner_user_id "
        "WHERE s.state = 'running' AND s.created_at < ? ORDER BY s.created_at LIMIT ?",
        (cutoff, limit),
    )
    now = _now()
    return {
        "count": int(count_row["n"] if count_row else 0),
        "rows": [
            {
                "submission_id": row["id"],
                "property": row["internal_name"],
                "owner_user_id": row["owner_user_id"],
                "workspace": row["workspace"] or "",
                "age_minutes": age_minutes(row["created_at"], now),
            }
            for row in rows
        ],
    }


# --- calendars ----------------------------------------------------------------

def feeds_needing_attention(limit: int = ROW_LIMIT) -> Dict[str, Any]:
    """Active feeds whose last sync failed, looked suspect, or is too old.

    Since WP15 an unchanged calendar is not read again, so ``last_sync_at``
    stays old for a quiet feed. ``last_checked_at`` moves on every check; for a
    feed whose status is ``ok`` it is the last successful check. Feeds not yet
    checked since WP15 fall back to ``last_sync_at``. Any status other than
    ``ok`` is listed anyway.
    """
    cutoff = _iso(_now() - timedelta(hours=FEED_STALE_HOURS))
    where = (
        "FROM ical_feed f JOIN apartment a ON a.id = f.apartment_id "
        "WHERE f.active = 1 AND a.active = 1 AND a.archived_at IS NULL "
        "AND (f.last_status IS NULL OR f.last_status <> 'ok' "
        "OR COALESCE(f.last_checked_at, f.last_sync_at) IS NULL "
        "OR COALESCE(f.last_checked_at, f.last_sync_at) < ?)"
    )
    count_row = db.query_one(f"SELECT COUNT(*) AS n {where}", (cutoff,))
    rows = db.query(
        "SELECT f.id, f.label, f.last_status, "
        "COALESCE(f.last_checked_at, f.last_sync_at) AS last_checked, a.internal_name, "
        "a.owner_user_id, (SELECT username FROM user_account u WHERE u.id = a.owner_user_id) "
        f"AS workspace {where} ORDER BY last_checked LIMIT ?",
        (cutoff, limit),
    )
    now = _now()
    return {
        "count": int(count_row["n"] if count_row else 0),
        "rows": [
            {
                "feed_id": row["id"],
                "label": row["label"] or "",
                "status": row["last_status"] or "never",
                "property": row["internal_name"],
                "owner_user_id": row["owner_user_id"],
                "workspace": row["workspace"] or "",
                "age_minutes": age_minutes(row["last_checked"], now),
            }
            for row in rows
        ],
    }


# --- scheduler ----------------------------------------------------------------

def job_health() -> Dict[str, Any]:
    """Last success per job, late when older than twice the job's interval."""
    intervals = scheduler.job_intervals()
    keys = [f"{scheduler.JOB_LAST_OK_PREFIX}{job_id}" for job_id in intervals]
    marks = ", ".join("?" for _ in keys)
    stored = {
        row["key"]: row["value"]
        for row in db.query(f"SELECT key, value FROM settings WHERE key IN ({marks})", keys)
    }
    failed = {
        row["dedupe_key"]: row["created_at"]
        for row in db.query(
            "SELECT dedupe_key, created_at FROM alert "
            "WHERE kind = 'job_failed' AND resolved_at IS NULL LIMIT ?",
            (ROW_LIMIT,),
        )
    }
    now = _now()
    rows = []
    for job_id, minutes in intervals.items():
        last_ok = stored.get(f"{scheduler.JOB_LAST_OK_PREFIX}{job_id}")
        age = age_minutes(last_ok, now)
        failed_at = failed.get(f"job_failed:{job_id}")
        rows.append(
            {
                "job_id": job_id,
                "interval_minutes": minutes,
                "last_ok": last_ok,
                "age_minutes": age,
                "late": age is None or age > 2 * minutes,
                "failed": failed_at is not None,
                "failed_age_minutes": age_minutes(failed_at, now),
            }
        )
    return {"count": sum(1 for row in rows if row["late"] or row["failed"]), "rows": rows}


# --- mail ---------------------------------------------------------------------

def mail_problems(limit: int = ROW_LIMIT) -> Dict[str, Any]:
    """Failed mail, and mail that should have left by now. No recipients."""
    cutoff = _iso(_now() - timedelta(minutes=MAIL_STUCK_MINUTES))
    where = (
        "FROM email_outbox WHERE state IN ('failed', 'bounced', 'complained') "
        "OR (state = 'queued' AND created_at < ?) "
        "OR (state = 'sending' AND updated_at < ?)"
    )
    params = (cutoff, cutoff)
    count_row = db.query_one(f"SELECT COUNT(*) AS n {where}", params)
    rows = db.query(
        f"SELECT id, kind, state, attempts, created_at {where} ORDER BY created_at LIMIT ?",
        (*params, limit),
    )
    now = _now()
    return {
        "count": int(count_row["n"] if count_row else 0),
        "rows": [
            {
                "outbox_id": row["id"],
                "kind": row["kind"],
                "state": row["state"],
                "attempts": int(row["attempts"] or 0),
                "age_minutes": age_minutes(row["created_at"], now),
            }
            for row in rows
        ],
    }


# --- alerts -------------------------------------------------------------------

def open_alerts(limit: int = ROW_LIMIT) -> Dict[str, Any]:
    """Unresolved alerts grouped by kind and level, with the oldest one's age."""
    rows = db.query(
        "SELECT kind, level, COUNT(*) AS n, MIN(created_at) AS oldest "
        "FROM alert WHERE resolved_at IS NULL "
        "GROUP BY kind, level ORDER BY n DESC, kind LIMIT ?",
        (limit,),
    )
    now = _now()
    items = [
        {
            "kind": row["kind"],
            "level": row["level"],
            "count": int(row["n"] or 0),
            "age_minutes": age_minutes(row["oldest"], now),
        }
        for row in rows
    ]
    return {"count": sum(item["count"] for item in items), "rows": items}


def overview() -> Dict[str, Any]:
    """Everything the page shows, in the order it shows it."""
    return {
        "filings": filings_needing_attention(),
        "stuck": stuck_submissions(),
        "feeds": feeds_needing_attention(),
        "jobs": job_health(),
        "mail": mail_problems(),
        "alerts": open_alerts(),
    }
