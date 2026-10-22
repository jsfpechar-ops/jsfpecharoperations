"""0240 (idea N): "What needs you", the one card at the top of the dashboard.

Each line is a bold subject, one plain sentence and one button that lands on
the exact fix. It gathers what used to be separate blocks on the dashboard:
the alert stack, the stays that need the host, unfinished police setup and
the paste reminder (0233). It reads only what the dashboard already loaded.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, Iterable, List, Optional

from . import host_i18n, validation

_TONE_RANK = {"red": 0, "amber": 1, "grey": 2}
_ALERT_TONE = {"critical": "red", "warning": "amber", "info": "grey"}
_FINISHED = ("reported", "not_required")
_SEND = ("ready", "awaiting_verification")
_GUEST = ("awaiting_guest", "incomplete")
# The settings part of the page that holds each missing police field.
_SETUP_QUERY = {
    "basics": "view=settings&section=property",
    "address": "view=settings&section=property",
    "ubyport": "view=settings&section=reporting",
    "calendars": "view=bookings",
}


def _get(row, key: str, default=None):
    try:
        value = row[key]
    except (KeyError, IndexError, TypeError):
        return default
    return default if value is None else value


def _line(kind: str, tone: str, subject: str, text: str, action: str, href: str, **extra) -> Dict[str, Any]:
    return {
        "kind": kind,
        "tone": tone,
        "subject": subject,
        "text": text,
        "action": action,
        "href": href,
        "dismiss_id": extra.get("dismiss_id"),
        "stay_id": extra.get("stay_id"),
        "apartment_id": extra.get("apartment_id"),
    }


def _stay_name(reservation) -> str:
    """The same name the stay list uses: the typed label of a hand-made stay."""
    label = _get(reservation, "summary", "")
    if _get(reservation, "source", "") != "manual" or not str(label).strip():
        label = _get(reservation, "internal_name", "")
    dates = validation.fmt_date_range(_get(reservation, "date_from"), _get(reservation, "date_to"))
    return f"{label} · {dates}"


def stay_line(row: Dict[str, Any], lang: str, today: date) -> Optional[Dict[str, Any]]:
    """The line for one stay, or None while the stay is on track."""
    from . import demo  # local: demo imports many modules

    def t(key: str, **kwargs) -> str:
        return host_i18n.translate(lang, key, **kwargs)

    reservation = row["reservation"]
    status = row["progress"]["status"]
    if status in _FINISHED:
        return None
    stay_id = reservation["id"]
    subject = _stay_name(reservation)
    base = f"/reservations/{stay_id}?return_to=/"
    if status == "failed":
        return _line("stay", "red", subject, t("needs_you.stay.failed"), t("needs_you.action.fix"), base + "#guests", stay_id=stay_id)
    if row.get("urgency") == "overdue":
        if status in _SEND:
            return _line("stay", "red", subject, t("needs_you.stay.overdue"), t("needs_you.action.send"), base + "#now", stay_id=stay_id)
        return _line("stay", "red", subject, t("needs_you.stay.overdue"), t("needs_you.action.open"), base, stay_id=stay_id)
    if demo.is_demo_stay(reservation):
        return None
    if status in _SEND:
        # Automatic and scheduled reporting send by themselves: on track.
        if _get(reservation, "automation_mode", "manual") != "manual":
            return None
        return _line("stay", "amber", subject, t("needs_you.stay.ready"), t("needs_you.action.send"), base + "#now", stay_id=stay_id)
    arrival = validation.parse_iso_date(_get(reservation, "date_from", ""))
    if status in _GUEST and arrival is not None and arrival <= today + timedelta(days=1):
        if arrival < today:
            when = t("needs_you.when.arrived")
        elif arrival == today:
            when = t("needs_you.when.today")
        else:
            when = t("needs_you.when.tomorrow")
        started = bool(row["progress"].get("guests"))
        key = "needs_you.stay.forms_missing" if started else "needs_you.stay.no_form"
        return _line("stay", "amber", subject, t(key, when=when), t("needs_you.action.send_link"), base + "#now", stay_id=stay_id)
    return None


def build(
    rows: Iterable[Dict[str, Any]],
    queue: Dict[str, List[Dict[str, Any]]],
    cards: Iterable[Dict[str, Any]],
    missing_rows: Iterable[Dict[str, Any]],
    link_unused: Iterable[Any],
    lang: str,
    today: date,
) -> Dict[str, Any]:
    """{"lines": [...], "on_track": n}: red first, then amber, then grey."""

    def t(key: str, **kwargs) -> str:
        return host_i18n.translate(lang, key, **kwargs)

    lines: List[Dict[str, Any]] = []
    covered = set()
    for bucket in ("needs_action", "waiting", "upcoming"):
        for row in (queue or {}).get(bucket, []):
            stay_id = row["reservation"]["id"]
            if stay_id in covered:
                continue
            line = stay_line(row, lang, today)
            if line:
                covered.add(stay_id)
                lines.append(line)
    setup_alerts = set()
    pin_cards = [card for card in cards or [] if card.get("kind") == "guest_pin_rotated"]
    for card in cards or []:
        kind = card.get("kind") or ""
        if card.get("reservation_id") and card["reservation_id"] in covered:
            continue  # the stay's own line says it, with live numbers
        if kind == "apartment_setup" and card.get("apartment_id"):
            setup_alerts.add(card["apartment_id"])
        href = card.get("action_href") or ""
        action = t(card["action_label_key"]) if card.get("action_label_key") else ""
        if kind == "guest_pin_rotated":
            if card is not pin_cards[0]:
                continue
            if len(pin_cards) > 1:
                href, action = "/apartments", t("dashboard.setup.view_properties")
        lines.append(_line(
            "alert",
            _ALERT_TONE.get(card.get("level") or "", "amber"),
            card.get("display_title") or card.get("message") or "",
            card.get("display_detail") or card.get("detail") or "",
            action,
            href,
            dismiss_id=None if kind == "dates_changed_resign" else card.get("id"),
            stay_id=card.get("reservation_id"),
            apartment_id=card.get("apartment_id"),
        ))
    from . import demo  # local: demo imports many modules

    for row in missing_rows or []:
        apartment = row["apartment"]
        if apartment["id"] in setup_alerts or not row.get("missing"):
            continue
        if demo.is_demo_apartment(apartment):
            continue  # the sample property never reports to the police
        # One short line, never the field-by-field list (owner, 2026-10-22):
        # the button opens the first missing field.
        first = row["missing"][0]["anchor"]
        lines.append(_line(
            "setup", "amber", apartment["internal_name"] or "",
            t("needs_you.setup"), t("needs_you.action.setup"),
            f"/apartments/{apartment['id']}?{_SETUP_QUERY.get(first, 'view=settings')}#{first}",
            apartment_id=apartment["id"],
        ))
    for apartment in link_unused or []:
        lines.append(_line(
            "paste", "amber", apartment["internal_name"] or "",
            t("needs_you.paste"), t("workflow.paste.open"),
            f"/apartments/{apartment['id']}?view=settings&section=guests#communication",
            apartment_id=apartment["id"],
        ))
    lines.sort(key=lambda line: _TONE_RANK.get(line["tone"], 1))
    on_track = sum(
        1 for row in rows or []
        if row["progress"]["status"] not in _FINISHED and row["reservation"]["id"] not in covered
    )
    return {"lines": lines, "on_track": on_track}
