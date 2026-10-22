"""0275: one welcome-back line after 14 days away (idea S). Dates only."""
from __future__ import annotations

from datetime import date
from typing import Any, Dict, Optional

from . import db, reporting

AWAY_DAYS = 14
SHOW_DAYS = 7


def _seen_key(user_id: int) -> str:
    return f"last_seen_{int(user_id)}"


def _line_key(user_id: int) -> str:
    return f"welcome_back_{int(user_id)}"


def _parse(value: Optional[str]) -> Optional[date]:
    try:
        return date.fromisoformat((value or "")[:10])
    except ValueError:
        return None


def keys_for(user_id: int) -> tuple:
    """The settings check() reads, so a page can fetch them with others in one query."""
    return (_seen_key(user_id), _line_key(user_id))


def check(user_id: Optional[int], owner_user_id: Optional[int], today: date, settings: Optional[Dict[str, Optional[str]]] = None) -> Optional[Dict[str, Any]]:
    """Record today's visit; return the line to show, or None."""
    if not user_id:
        return None
    if settings is None:
        settings = db.get_settings(keys_for(user_id))
    last_seen = _parse(settings.get(_seen_key(user_id)))
    if last_seen != today:
        db.set_setting(_seen_key(user_id), today.isoformat())
    if last_seen and (today - last_seen).days >= AWAY_DAYS:
        db.set_setting(_line_key(user_id), f"{last_seen.isoformat()}|{today.isoformat()}")
    if last_seen and (today - last_seen).days >= AWAY_DAYS:
        raw = f"{last_seen.isoformat()}|{today.isoformat()}"
    else:
        raw = settings.get(_line_key(user_id)) or ""
    since_raw, _, shown_raw = raw.partition("|")
    since, shown = _parse(since_raw), _parse(shown_raw)
    if not since or not shown:
        return None
    if (today - shown).days > SHOW_DAYS:
        dismiss(user_id)
        return None
    scope = db.null_safe_eq("a.owner_user_id")
    stays = db.query_one(
        "SELECT COUNT(*) AS n FROM reservation r JOIN apartment a ON a.id = r.apartment_id "
        f"WHERE {scope} AND COALESCE(r.source, '') != 'demo' AND r.created_at >= ?",
        (owner_user_id, since.isoformat()),
    )["n"]
    reported = db.query_one(
        "SELECT COUNT(*) AS n FROM guest g JOIN reservation r ON r.id = g.reservation_id "
        "JOIN apartment a ON a.id = r.apartment_id "
        f"WHERE {scope} AND COALESCE(r.source, '') != 'demo' "
        "AND g.submit_state = ? AND g.submitted_at >= ?",
        (owner_user_id, reporting.SENT, since.isoformat()),
    )["n"]
    return {"since": since.isoformat(), "stays": int(stays), "reported": int(reported)}


def dismiss(user_id: Optional[int]) -> None:
    if user_id:
        db.set_setting(_line_key(user_id), "")


def forget(cur, user_id: int) -> None:
    """Retention: drop both rows with the account's workspace."""
    cur.execute(
        "DELETE FROM settings WHERE key IN (?, ?)", (_seen_key(user_id), _line_key(user_id))
    )
