"""Persistent alerts.

Appendix 5 section 10.4(2) requires an application that reports automatically
to inform the host "without delay" and "by an effective means" when a record
was not accepted - it explicitly suggests a prominent warning on every screen.
These rows drive the banner rendered in the base template.

Language: the ``message``/``detail`` columns hold English prose and are the log
copy, the mail copy and the fallback. The card a host *reads* is rebuilt at
render time from ``notification.*`` keys, so a Czech host never meets English.
An alert that interpolates values (a property name, a count, a UbyPort error)
stores them as JSON in ``params`` when it is raised; the render formats them.
Two kinds of detail stay English on purpose, because there is nothing to
translate: an exception message from a remote server, and the code list UbyPort
itself returns.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from . import db, deadlines, host_i18n, validation

LEVEL_ORDER = {"critical": 0, "warning": 1, "info": 2}

# Kinds whose card is computed from the live reservation rather than rendered
# from what was stored: the numbers move as time passes (a deadline gets more
# overdue), so rendering them from a snapshot taken at raise time would lie.
_COMPUTED_ALERT_KINDS = frozenset(
    {
        "deadline",
        "guest_incomplete_checkin",
        "headcount_mismatch",
        "dates_changed_resign",
        "moved_after_report",
        "submission_stuck",
        "job_failed",
        "feed_incomplete",
        "feed_duplicate_uid",
        "feed_recurring_event",
    }
)

# Kinds that belong to a calendar feed rather than to one stay. Their card is
# rebuilt from the property name, so they are handled before the reservation
# lookup below.
_FEED_ALERT_KINDS = frozenset({"feed_incomplete", "feed_duplicate_uid", "feed_recurring_event"})


# One date format for the whole app: an alert, an e-mail and a page must never
# print the same stay differently.
_fmt_date = validation.fmt_date


def _stay_dates(reservation: Any) -> str:
    return validation.fmt_date_range(reservation["date_from"], reservation["date_to"])


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
        key = host_i18n.plural_key("notification.reason.overdue_forms", amount)
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


def stored_params(row: Any) -> Dict[str, Any]:
    """The interpolation values an alert stored, or ``{}`` if it stored none."""
    raw = row.get("params") if hasattr(row, "get") else None
    if not raw:
        return {}
    try:
        values = json.loads(raw)
    except (TypeError, ValueError):
        return {}
    return values if isinstance(values, dict) else {}


def _localised(lang: str, key: str, stored: str, params: Dict[str, Any]) -> str:
    """The translated twin of a stored string, or the stored string itself.

    Falling back is deliberate and not only for a missing key: an alert raised
    before this release carries no ``params``, and a card that interpolates
    values cannot be rebuilt without them - showing ``%(property)s`` to a host
    would be worse than showing English.
    """
    table = host_i18n.STRINGS[host_i18n.normalise_language(lang)]
    text = table.get(key)
    if text is None:
        return stored or ""
    if "%(" in text and not params:
        return stored or ""
    return host_i18n.lookup(table, table, key, **params)


def _reservation_row(reservation_id: Any) -> Any:
    return db.query_one(
        "SELECT r.*, a.internal_name FROM reservation r "
        "JOIN apartment a ON a.id = r.apartment_id WHERE r.id = ?",
        (reservation_id,),
    )


def _title_key(kind: str, params: Dict[str, Any], lang: str) -> str:
    """The title key for a kind, allowing a ``variant`` to pick a wording.

    One kind can describe two different events - a stay cancelled in the
    calendar and a stay that vanished from it are both
    ``cancelled_after_report`` - so the variant names the wording. A variant
    with no key of its own falls back to the plain kind.
    """
    base = f"notification.{kind}.title"
    variant = params.get("variant")
    if not variant:
        return base
    table = host_i18n.STRINGS[host_i18n.normalise_language(lang)]
    return f"{base}.{variant}" if f"{base}.{variant}" in table else base


def _present_stored(row: Dict[str, Any], kind: str, lang: str) -> Dict[str, Any]:
    """Render an alert from its stored parameters and the ``notification.*`` copy.

    A detail that is assembled from more than one sentence uses a leading
    clause under ``notification.<kind>.header``; it is rendered only when the
    ``header`` value it interpolates is non-empty, which is how an optional
    sentence stays optional without a branch at the call site.
    """
    params = stored_params(row)
    row["display_title"] = _localised(
        lang, _title_key(kind, params, lang), row.get("message"), params
    )
    detail = _localised(lang, f"notification.{kind}.detail", row.get("detail"), params)
    if params.get("header"):
        leading = _localised(lang, f"notification.{kind}.header", "", params)
        if leading:
            detail = f"{leading} {detail}".strip()
    row["display_detail"] = detail
    return row


def _present_computed(row: Dict[str, Any], kind: str, lang: str) -> Dict[str, Any]:
    """Rebuild the card of an alert whose text is derived from live data."""
    if kind == "job_failed":
        job_id = (row.get("dedupe_key") or "").split(":", 1)[-1]
        row["display_title"] = host_i18n.translate(
            lang,
            "notification.job_failed.title",
            job=host_i18n.translate(lang, f"notification.job_name.{job_id}") if job_id else "",
        )
        row["display_detail"] = host_i18n.translate(lang, "notification.job_failed.detail")
        return row
    if kind in _FEED_ALERT_KINDS:
        apartment = db.query_one(
            "SELECT internal_name FROM apartment WHERE id = ?", (row.get("apartment_id"),)
        )
        row["display_title"] = host_i18n.translate(
            lang,
            f"notification.{kind}.title",
            property=(apartment["internal_name"] if apartment else "") or "",
        )
        row["display_detail"] = host_i18n.translate(lang, f"notification.reason.{kind}")
        return row
    reservation = _reservation_row(row["reservation_id"]) if row.get("reservation_id") else None
    if not reservation:
        row["display_title"] = row.get("message") or ""
        row["display_detail"] = row.get("detail") or ""
        return row
    row["display_title"] = stay_title(lang, reservation["internal_name"] or "", reservation)
    if kind in ("dates_changed_resign", "moved_after_report", "submission_stuck"):
        row["display_detail"] = host_i18n.translate(lang, f"notification.reason.{kind}")
        return row
    if kind == "guest_incomplete_checkin":
        row["display_detail"] = checkin_incomplete_reason(lang)
        return row
    from . import reporting

    progress = reporting.reservation_progress(reservation)
    if kind == "headcount_mismatch":
        filled, expected = _forms_count(progress)
        row["display_detail"] = host_i18n.translate(
            lang, "notification.reason.headcount_mismatch", filled=filled, expected=expected
        )
        return row
    start = reporting.reservation_deadline_anchor(reservation)
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


def present(alert: Any, lang: str) -> Dict[str, Any]:
    """Compact title + reason for the notification card.

    Stay alerts are rebuilt from the reservation so hosts see short EN/CS copy
    with Czech-style dates. Every other kind is rebuilt from the parameters it
    stored, and falls back to its English log copy when it stored none.
    """
    row = dict(alert)
    kind = row.get("kind") or ""
    if kind in _COMPUTED_ALERT_KINDS:
        return _present_computed(row, kind, lang)
    return _present_stored(row, kind, lang)


def present_many(alerts: List[Any], lang: str) -> List[Dict[str, Any]]:
    """One card per stay, most severe first.

    A deadline and an incomplete guest list are raised for the same booking, so
    the host used to read the same stay twice and dismiss it twice. Rows that
    share a reservation collapse into the most severe of them, at the position
    the first one held; the list arrives already ordered by level.
    """
    cards: List[Dict[str, Any]] = []
    seen: Dict[Any, int] = {}
    for alert in alerts:
        card = present(alert, lang)
        reservation_id = card.get("reservation_id")
        if not reservation_id:
            cards.append(card)
            continue
        index = seen.get(reservation_id)
        if index is None:
            seen[reservation_id] = len(cards)
            cards.append(card)
            continue
        if LEVEL_ORDER.get(card.get("level"), 9) < LEVEL_ORDER.get(cards[index].get("level"), 9):
            cards[index] = card
    return cards


def raise_alert(
    level: str,
    kind: str,
    message: str,
    detail: str = "",
    dedupe_key: Optional[str] = None,
    apartment_id: Optional[int] = None,
    reservation_id: Optional[int] = None,
    owner_user_id: Optional[int] = None,
    params: Optional[Dict[str, Any]] = None,
) -> None:
    """Record an alert, refreshing the message if the same one is already open.

    ``message`` and ``detail`` are the English log copy and the fallback; the
    card a host reads is built from ``params`` at render time. Passing the
    values rather than pre-formatted prose is what lets a Czech host read the
    card in Czech.
    """
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
    stored = json.dumps(params, ensure_ascii=False, sort_keys=True) if params else None
    existing = db.query_one(
        "SELECT id FROM alert WHERE dedupe_key = ? AND resolved_at IS NULL", (key,)
    )
    if existing:
        db.update(
            "alert",
            existing["id"],
            {
                "level": level,
                "message": message,
                "detail": detail,
                "params": stored,
                "created_at": db.utcnow(),
            },
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
            "params": stored,
            "created_at": db.utcnow(),
        },
    )


def open_alert(dedupe_key: str) -> Optional[Any]:
    """The alert still standing for ``dedupe_key``, if any.

    Callers that gate work on a warning - filing a stay whose signatures the
    calendar invalidated - need to ask about one key rather than scan the
    dashboard list.
    """
    return db.query_one(
        "SELECT * FROM alert WHERE dedupe_key = ? AND resolved_at IS NULL",
        (dedupe_key,),
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


# Kinds that belong to the installation rather than to one host. A dead
# background job stops the sweep, the deadline watch and the calendar sync for
# every workspace at once, so it is stored with no owner and shown to all of
# them: a host who is never told cannot act on it.
SYSTEM_ALERT_KINDS = frozenset({"job_failed"})


def open_alerts(owner_user_id: Optional[int] = None) -> List:
    marks = ", ".join("?" for _ in SYSTEM_ALERT_KINDS)
    rows = db.query(
        f"SELECT * FROM alert WHERE resolved_at IS NULL AND ("
        f"? IS NULL OR owner_user_id = ? OR kind IN ({marks})) "
        "ORDER BY created_at DESC",
        (owner_user_id, owner_user_id, *SYSTEM_ALERT_KINDS),
    )
    return sorted(rows, key=lambda r: LEVEL_ORDER.get(r["level"], 9))
