"""Persistent alerts.

Appendix 5 section 10.4(2) requires an application that reports automatically
to inform the host "without delay" and "by an effective means" when a record
was not accepted - it explicitly suggests a prominent warning on every screen.
These rows drive the banner rendered in the base template.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from . import db, deadlines, host_i18n, validation

LEVEL_ORDER = {"critical": 0, "warning": 1, "info": 2}

# Stay-related kinds get short i18n titles/reasons at render time so EN/CS
# hosts see the same compact card regardless of the English log text stored.
_STAY_ALERT_KINDS = frozenset({"deadline", "guest_incomplete_checkin"})

# These kinds store English text only as a log/fallback copy; their card is
# rebuilt from i18n at render time so a Czech host never reads English.
_TRANSLATED_ALERT_KINDS = frozenset(
    {"dates_changed_resign", "headcount_mismatch", "feed_incomplete", "job_failed"}
)


def _fmt_date(value: Optional[str]) -> str:
    parsed = validation.parse_iso_date(value)
    return parsed.strftime("%d.%m.%Y") if parsed else (value or "")


def _stay_dates(reservation: Any) -> str:
    start = _fmt_date(reservation["date_from"])
    end = _fmt_date(reservation["date_to"])
    if start and end:
        return f"{start} – {end}"
    return start or end


def _plural_key(base: str, n: int) -> str:
    if n == 1:
        return f"{base}.one"
    if 2 <= n <= 4:
        return f"{base}.few"
    return base


def _forms_count(progress: Dict[str, Any]) -> tuple[str, str]:
    filled = str(progress.get("filled") or 0)
    expected = progress.get("expected")
    return filled, str(expected if expected is not None else "?")


def stay_title(lang: str, property_name: str, reservation: Any) -> str:
    return host_i18n.translate(
        lang,
        "notification.stay_title",
        property=property_name,
        dates=_stay_dates(reservation),
    )


def deadline_reason(lang: str, check_in, progress: Dict[str, Any], now=None) -> str:
    filled, expected = _forms_count(progress)
    kind, amount = deadlines.time_left_parts(check_in, now)
    if kind == "overdue_days":
        key = _plural_key("notification.reason.overdue_forms", amount)
        return host_i18n.translate(
            lang, key, n=amount, filled=filled, expected=expected
        )
    if kind == "overdue_hours":
        return host_i18n.translate(
            lang,
            "notification.reason.overdue_hours_forms",
            n=amount,
            filled=filled,
            expected=expected,
        )
    return host_i18n.translate(
        lang,
        "notification.reason.urgent_forms",
        filled=filled,
        expected=expected,
    )


def checkin_incomplete_reason(lang: str) -> str:
    return host_i18n.translate(lang, "notification.reason.checkin_incomplete")


def _reservation_row(reservation_id: Any) -> Any:
    return db.query_one(
        "SELECT r.*, a.internal_name FROM reservation r "
        "JOIN apartment a ON a.id = r.apartment_id WHERE r.id = ?",
        (reservation_id,),
    )


def _present_translated(row: Dict[str, Any], kind: str, lang: str) -> Dict[str, Any]:
    """Rebuild the card text of an alert whose stored copy is English-only."""
    if kind == "job_failed":
        job_id = (row.get("dedupe_key") or "").split(":", 1)[-1]
        row["display_title"] = host_i18n.translate(
            lang,
            "notification.job_failed.title",
            job=host_i18n.translate(lang, f"notification.job_name.{job_id}") if job_id else "",
        )
        row["display_detail"] = host_i18n.translate(lang, "notification.job_failed.detail")
        return row
    if kind == "feed_incomplete":
        apartment = db.query_one(
            "SELECT internal_name FROM apartment WHERE id = ?", (row.get("apartment_id"),)
        )
        row["display_title"] = host_i18n.translate(
            lang,
            "notification.feed_incomplete.title",
            property=(apartment["internal_name"] if apartment else "") or "",
        )
        row["display_detail"] = host_i18n.translate(
            lang, "notification.reason.feed_incomplete"
        )
        return row
    reservation = _reservation_row(row["reservation_id"]) if row.get("reservation_id") else None
    if not reservation:
        return row
    row["display_title"] = stay_title(lang, reservation["internal_name"] or "", reservation)
    if kind == "dates_changed_resign":
        row["display_detail"] = host_i18n.translate(
            lang, "notification.reason.dates_changed_resign"
        )
        return row
    from . import reporting

    filled, expected = _forms_count(reporting.reservation_progress(reservation))
    row["display_detail"] = host_i18n.translate(
        lang, "notification.reason.headcount_mismatch", filled=filled, expected=expected
    )
    return row


def present(alert: Any, lang: str) -> Dict[str, Any]:
    """Compact title + reason for the notification card.

    Known stay alerts are rebuilt from the reservation so hosts see short
    EN/CS copy with Czech-style dates. Other kinds keep the stored text.
    """
    row = dict(alert)
    kind = row.get("kind") or ""
    if kind in _TRANSLATED_ALERT_KINDS:
        return _present_translated(row, kind, lang)
    if kind not in _STAY_ALERT_KINDS or not row.get("reservation_id"):
        row["display_title"] = row.get("message") or ""
        row["display_detail"] = row.get("detail") or ""
        return row

    reservation = _reservation_row(row["reservation_id"])
    if not reservation:
        row["display_title"] = row.get("message") or ""
        row["display_detail"] = row.get("detail") or ""
        return row

    property_name = reservation["internal_name"] or ""
    row["display_title"] = stay_title(lang, property_name, reservation)
    if kind == "guest_incomplete_checkin":
        row["display_detail"] = checkin_incomplete_reason(lang)
        return row

    from . import reporting

    start = reporting.reservation_deadline_anchor(reservation)
    progress = reporting.reservation_progress(reservation)
    if start:
        row["display_detail"] = deadline_reason(lang, start, progress)
    else:
        filled, expected = _forms_count(progress)
        row["display_detail"] = host_i18n.translate(
            lang,
            "notification.reason.urgent_forms",
            filled=filled,
            expected=expected,
        )
    return row


def present_many(alerts: List[Any], lang: str) -> List[Dict[str, Any]]:
    return [present(alert, lang) for alert in alerts]


def raise_alert(
    level: str,
    kind: str,
    message: str,
    detail: str = "",
    dedupe_key: Optional[str] = None,
    apartment_id: Optional[int] = None,
    reservation_id: Optional[int] = None,
    owner_user_id: Optional[int] = None,
) -> None:
    """Record an alert, refreshing the message if the same one is already open."""
    if owner_user_id is None and apartment_id:
        apartment = db.query_one("SELECT owner_user_id FROM apartment WHERE id = ?", (apartment_id,))
        owner_user_id = apartment["owner_user_id"] if apartment else None
    if owner_user_id is None and reservation_id:
        reservation = db.query_one(
            "SELECT a.owner_user_id FROM reservation r "
            "JOIN apartment a ON a.id = r.apartment_id WHERE r.id = ?",
            (reservation_id,),
        )
        owner_user_id = reservation["owner_user_id"] if reservation else None
    key = dedupe_key or f"{kind}:{apartment_id}:{reservation_id}:{message}"
    existing = db.query_one(
        "SELECT id FROM alert WHERE dedupe_key = ? AND resolved_at IS NULL", (key,)
    )
    if existing:
        db.update(
            "alert",
            existing["id"],
            {"level": level, "message": message, "detail": detail, "created_at": db.utcnow()},
        )
        return
    db.insert(
        "alert",
        {
            "level": level,
            "kind": kind,
            "apartment_id": apartment_id,
            "reservation_id": reservation_id,
            "owner_user_id": owner_user_id,
            "dedupe_key": key,
            "message": message,
            "detail": detail,
            "created_at": db.utcnow(),
        },
    )


def resolve(dedupe_key: str) -> None:
    db.execute(
        "UPDATE alert SET resolved_at = ? WHERE dedupe_key = ? AND resolved_at IS NULL",
        (db.utcnow(), dedupe_key),
    )


def resolve_by_id(alert_id: int, user_dismissed: bool = False) -> None:
    db.execute(
        "UPDATE alert SET resolved_at = ?, user_dismissed = ? WHERE id = ?",
        (db.utcnow(), 1 if user_dismissed else 0, alert_id),
    )


def resolve_kind(kind: str, apartment_id: Optional[int] = None) -> None:
    if apartment_id is None:
        db.execute(
            "UPDATE alert SET resolved_at = ? WHERE kind = ? AND resolved_at IS NULL",
            (db.utcnow(), kind),
        )
    else:
        db.execute(
            "UPDATE alert SET resolved_at = ? WHERE kind = ? AND apartment_id = ? "
            "AND resolved_at IS NULL",
            (db.utcnow(), kind, apartment_id),
        )


def open_alerts(owner_user_id: Optional[int] = None) -> List:
    rows = db.query(
        "SELECT * FROM alert WHERE resolved_at IS NULL AND (? IS NULL OR owner_user_id = ?) "
        "ORDER BY created_at DESC",
        (owner_user_id, owner_user_id),
    )
    return sorted(rows, key=lambda r: LEVEL_ORDER.get(r["level"], 9))


def count_critical() -> int:
    row = db.query_one(
        "SELECT COUNT(*) AS n FROM alert WHERE resolved_at IS NULL AND level = 'critical'"
    )
    return row["n"] if row else 0
