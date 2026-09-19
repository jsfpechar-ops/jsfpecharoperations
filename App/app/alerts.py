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


def present(alert: Any, lang: str) -> Dict[str, Any]:
    """Compact title + reason for the notification card.

    Known stay alerts are rebuilt from the reservation so hosts see short
    EN/CS copy with Czech-style dates. Other kinds keep the stored text.
    """
    row = dict(alert)
    kind = row.get("kind") or ""
    if kind not in _STAY_ALERT_KINDS or not row.get("reservation_id"):
        row["display_title"] = row.get("message") or ""
        row["display_detail"] = row.get("detail") or ""
        return row

    reservation = db.query_one(
        "SELECT r.*, a.internal_name FROM reservation r "
        "JOIN apartment a ON a.id = r.apartment_id WHERE r.id = ?",
        (row["reservation_id"],),
    )
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

    start = validation.parse_iso_date(reservation["date_from"])
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
