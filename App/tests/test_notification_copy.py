"""Host notification cards stay short: property + dates, one reason line."""
from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from app import alerts, host_i18n


def test_notification_copy_keys_exist_in_en_and_cs():
    keys = [
        "notification.stay_title",
        "notification.reason.overdue_forms",
        "notification.reason.overdue_forms.one",
        "notification.reason.overdue_forms.few",
        "notification.reason.overdue_hours_forms",
        "notification.reason.urgent_forms",
        "notification.reason.checkin_incomplete",
        "notification.open_stay",
        "notification.feed_duplicate_uid.title",
        "notification.reason.feed_duplicate_uid",
        "notification.feed_recurring_event.title",
        "notification.reason.feed_recurring_event",
        "notification.reason.moved_after_report",
    ]
    for key in keys:
        for lang in ("en", "cs"):
            text = host_i18n.translate(
                lang,
                key,
                n=2,
                filled=1,
                expected=2,
                property="Loft",
                dates="11.09.2026",
            )
            assert text and text != key, (lang, key)


def test_deadline_reason_is_one_compact_line():
    progress = {"filled": 0, "expected": 2}
    check_in = date(2026, 9, 1)
    now = datetime(2026, 9, 15, 12, 0)
    en = alerts.deadline_reason("en", check_in, progress, now=now)
    cs = alerts.deadline_reason("cs", check_in, progress, now=now)
    assert " · " in en and "0/2" in en
    assert "Overdue" in en
    assert " · " in cs and "0/2" in cs
    assert "Po termínu" in cs
    assert "guest form" not in en.lower()
    assert "Status:" not in en


def test_checkin_reason_drops_masked_email():
    en = alerts.checkin_incomplete_reason("en")
    cs = alerts.checkin_incomplete_reason("cs")
    assert en == "Check-in today · forms incomplete"
    assert cs == "Příjezd dnes · formuláře neúplné"
    assert "@" not in en and "@" not in cs
    assert "Claimed" not in en
    assert "registration link" not in en


def test_present_rebuilds_stay_title_with_czech_dates(monkeypatch):
    """Presentation ignores verbose stored English and uses CZ-style dates."""
    reservation = {
        "id": 42,
        "date_from": "2026-09-11",
        "date_to": "2026-09-13",
        "internal_name": "Karlín Loft (demo)",
        "expected_guests": 2,
        "apartment_id": 1,
    }

    monkeypatch.setattr(
        alerts.db,
        "query_one",
        lambda sql, params=(): reservation,
    )
    monkeypatch.setattr(
        "app.reporting.reservation_progress",
        lambda _res: {"filled": 0, "expected": 2, "status": "awaiting_guest", "incomplete": True},
    )

    alert = {
        "kind": "deadline",
        "reservation_id": 42,
        "message": (
            "Karlín Loft (demo): stay from 2026-09-11 is overdue by 2 days "
            "and is not fully reported."
        ),
        "detail": "Status: Waiting for guest. 0 of ? guest form(s) complete.",
    }
    shown = alerts.present(alert, "en")
    assert shown["display_title"] == "Karlín Loft (demo) · 11.09.2026 – 13.09.2026"
    assert "stay from" not in shown["display_title"]
    assert "Status:" not in shown["display_detail"]
    assert "guest form" not in shown["display_detail"].lower()
    assert "0/2" in shown["display_detail"]

    shown_cs = alerts.present(alert, "cs")
    assert "Karlín Loft (demo)" in shown_cs["display_title"]
    assert "11.09.2026" in shown_cs["display_title"]
    assert (
        "Po termínu" in shown_cs["display_detail"]
        or "Termín teď" in shown_cs["display_detail"]
    )


def test_present_checkin_omits_email(monkeypatch):
    reservation = {
        "id": 7,
        "date_from": "2026-09-19",
        "date_to": "2026-09-21",
        "internal_name": "Vinohrady Studio (demo)",
    }
    monkeypatch.setattr(
        alerts.db,
        "query_one",
        lambda sql, params=(): reservation,
    )
    alert = {
        "kind": "guest_incomplete_checkin",
        "reservation_id": 7,
        "message": "old verbose title",
        "detail": "Claimed as m********@d***.ubyhost.test. The guest can still complete…",
    }
    shown = alerts.present(alert, "en")
    assert shown["display_title"] == (
        "Vinohrady Studio (demo) · 19.09.2026 – 21.09.2026"
    )
    assert shown["display_detail"] == "Check-in today · forms incomplete"
    assert "@" not in shown["display_detail"]


def test_base_template_keeps_compact_notification_structure():
    base = Path(__file__).resolve().parents[1] / "app" / "templates" / "base.html"
    text = base.read_text(encoding="utf-8")
    assert 'include "_host_alerts.html"' in text
    text = base.with_name("_host_alerts.html").read_text(encoding="utf-8")
    assert "display_title" in text
    assert "display_detail" in text
    assert "notification-action" in text
    assert "data-notification-dismiss" in text
    assert "notification.open_stay" in text


# --- W4.6: the new calendar cards must read in the host's language [F5, F6, F12]

def _feed_card(kind, monkeypatch, property_name="Karlín Loft (demo)"):
    monkeypatch.setattr(
        alerts.db, "query_one", lambda sql, params=(): {"internal_name": property_name}
    )
    alert = {
        "kind": kind,
        "apartment_id": 1,
        "message": "english log copy",
        "detail": "english log copy",
    }
    return alerts.present(alert, "en"), alerts.present(alert, "cs")


def test_a_duplicate_booking_card_is_rebuilt_in_both_languages(monkeypatch):
    en, cs = _feed_card("feed_duplicate_uid", monkeypatch)
    assert en["display_title"] == "Karlín Loft (demo): one booking is listed twice."
    assert en["display_detail"] == (
        "The calendar returns the same booking ID more than once. Only the first "
        "entry of each was imported – check the portal, because one of the two "
        "stays may be missing."
    )
    assert cs["display_title"] == "Karlín Loft (demo): jedna rezervace je uvedena dvakrát."
    assert cs["display_detail"] == (
        "Kalendář vrací stejné ID rezervace vícekrát. Importoval se vždy jen první "
        "záznam – zkontrolujte portál, jeden z pobytů může chybět."
    )
    assert "english log copy" not in (cs["display_title"] + cs["display_detail"])


def test_a_repeating_booking_card_is_rebuilt_in_both_languages(monkeypatch):
    en, cs = _feed_card("feed_recurring_event", monkeypatch)
    assert en["display_title"] == "Karlín Loft (demo): a booking repeats."
    assert en["display_detail"] == (
        "The calendar repeats a booking, but only the first occurrence was "
        "imported. Add the other stays by hand."
    )
    assert cs["display_title"] == "Karlín Loft (demo): rezervace se opakuje."
    assert cs["display_detail"] == (
        "Kalendář opakuje rezervaci, ale importoval se jen první výskyt. Ostatní "
        "pobyty zadejte ručně."
    )
    assert "english log copy" not in (cs["display_title"] + cs["display_detail"])


def test_a_stay_moved_after_reporting_gets_a_reason_line(monkeypatch):
    reservation = {
        "id": 7,
        "date_from": "2026-09-19",
        "date_to": "2026-09-21",
        "internal_name": "Vinohrady Studio (demo)",
    }
    monkeypatch.setattr(alerts.db, "query_one", lambda sql, params=(): reservation)
    alert = {
        "kind": "moved_after_report",
        "reservation_id": 7,
        "message": "english log copy",
        "detail": "english log copy",
    }
    en = alerts.present(alert, "en")
    assert en["display_title"] == "Vinohrady Studio (demo) · 19.09.2026 – 21.09.2026"
    assert en["display_detail"] == (
        "The calendar moved this stay after it was reported to the police. The "
        "filed record names the old dates – check the new dates with the guests "
        "and resend."
    )
    cs = alerts.present(alert, "cs")
    assert "Vinohrady Studio (demo)" in cs["display_title"]
    assert cs["display_detail"] == (
        "Kalendář posunul tento pobyt poté, co byl nahlášen policii. Odeslaný "
        "záznam uvádí původní termíny – zkontrolujte s hosty nové termíny a "
        "odešlete znovu."
    )
    assert "english log copy" not in (cs["display_title"] + cs["display_detail"])
