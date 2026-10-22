"""0240 (idea N): the lines of the "What needs you" card."""

from __future__ import annotations

from datetime import date, timedelta

from app import needs_you

TODAY = date(2026, 10, 22)


def _row(stay_id, status, *, days=0, urgency="future", mode="manual", source="airbnb"):
    start = TODAY + timedelta(days=days)
    return {
        "reservation": {
            "id": stay_id, "internal_name": "Loft", "summary": "", "source": source,
            "date_from": start.isoformat(), "date_to": (start + timedelta(days=2)).isoformat(),
            "automation_mode": mode,
        },
        "progress": {"status": status},
        "urgency": urgency,
    }


def _build(rows, cards=(), missing=(), unused=(), lang="en"):
    queue = {"needs_action": list(rows), "waiting": [], "upcoming": []}
    return needs_you.build(rows, queue, list(cards), list(missing), list(unused), lang, TODAY)


def test_calm_when_nothing_needs_the_host():
    result = _build([_row(1, "awaiting_guest", days=10), _row(2, "ready", days=3, mode="scheduled")])
    assert result["lines"] == []
    assert result["on_track"] == 2


def test_each_stay_gets_one_plain_line_with_the_exact_button():
    rows = [
        _row(1, "failed", days=-2),
        _row(2, "ready", days=2),
        _row(3, "awaiting_guest", days=1),
        _row(4, "incomplete", days=-1, urgency="overdue"),
    ]
    lines = {line["stay_id"]: line for line in _build(rows)["lines"]}
    assert lines[1]["text"] == "The police did not accept the report." and lines[1]["href"].endswith("#guests")
    assert lines[2]["action"] == "Send the report" and lines[2]["href"].endswith("#now")
    assert lines[3]["text"] == "The guest arrives tomorrow and has not filled in the guest form."
    assert lines[3]["href"] == "/reservations/3?return_to=/#stay-link"
    assert lines[4]["tone"] == "red" and lines[4]["text"] == "The police deadline has passed."


def test_red_lines_come_first():
    rows = [_row(2, "ready", days=2), _row(1, "failed", days=-2)]
    tones = [line["tone"] for line in _build(rows)["lines"]]
    assert tones == sorted(tones, key=lambda tone: {"red": 0, "amber": 1, "grey": 2}[tone])


def test_an_alert_for_a_stay_with_its_own_line_is_not_repeated():
    rows = [_row(1, "failed", days=-2)]
    cards = [
        {"id": 7, "kind": "submission_stuck", "level": "warning", "reservation_id": 1, "display_title": "x",
         "display_detail": "y", "action_label_key": "notification.action.guests", "action_href": "/reservations/1#guests"},
        {"id": 8, "kind": "feed_error", "level": "warning", "apartment_id": 5, "display_title": "Calendar 'A' could not be read.",
         "display_detail": "d", "action_label_key": "notification.action.calendar", "action_href": "/apartments/5?view=bookings#calendars"},
    ]
    lines = _build(rows, cards)["lines"]
    assert [line["kind"] for line in lines] == ["stay", "alert"]
    assert lines[1]["action"] == "Check the calendar" and lines[1]["dismiss_id"] == 8


def test_setup_and_paste_lines_name_the_property():
    missing = [{"apartment": {"id": 5, "internal_name": "Loft"}, "missing": [{"key": "ubyport", "anchor": "ubyport"}]}]
    unused = [{"id": 6, "internal_name": "Studio"}]
    lines = _build([], missing=missing, unused=unused, lang="cs")["lines"]
    assert lines[0]["subject"] == "Loft" and lines[0]["href"] == "/apartments/5?view=settings&section=reporting#ubyport"
    assert lines[0]["text"] == "Chybí údaje pro policii, takže zatím nemůže odejít žádné hlášení."
    assert lines[1]["subject"] == "Studio" and lines[1]["href"].endswith("#communication")


def test_demo_stays_never_ask_to_send():
    assert _build([_row(1, "ready", days=2, source="demo")])["lines"] == []
