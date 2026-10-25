"""0245: the host hears about an unopened guest link the day before arrival, once."""

from __future__ import annotations

from datetime import datetime, time, timedelta

from app import claim, db, mail, mail_notify
from tests.test_claim_mail import _cleanup, _seed


def _clock(monkeypatch, day, hour=10):
    monkeypatch.setattr(mail, "backend_name", lambda: "console")
    monkeypatch.setattr(mail, "mail_enabled", lambda: True)
    moment = [datetime.combine(day, time(hour, 0))]
    monkeypatch.setattr(claim.deadlines, "local_now", lambda now=None: now if now is not None else moment[0])
    monkeypatch.setattr(claim, "prague_today", lambda: moment[0].date())
    return moment


def _host_reminders(reservation_id):
    return db.query(
        "SELECT * FROM email_outbox WHERE reservation_id = ? AND kind = 'reminder_host'", (reservation_id,)
    )


def test_an_unopened_link_reminds_the_host_the_day_before_and_only_once(monkeypatch):
    current, _past, _far, _apartment_id = _seed()
    arrival = db.query_one("SELECT date_from FROM reservation WHERE id = ?", (current,))["date_from"]
    day_before = datetime.fromisoformat(arrival).date() - timedelta(days=1)
    try:
        moment = _clock(monkeypatch, day_before, hour=8)
        assert claim.sweep_reminders()["host_early"] == 0  # not before 18:00
        moment[0] = datetime.combine(day_before, time(10, 0))
        assert claim.sweep_reminders()["host_early"] == 0  # not before 18:00
        moment[0] = datetime.combine(day_before, time(18, 0))
        assert claim.sweep_reminders()["host_early"] == 1
        rows = _host_reminders(current)
        assert len(rows) == 1
        mail_log = db.query_one("SELECT * FROM console_mail_log WHERE subject LIKE 'Arriving tomorrow,%'")
        assert mail_log
        assert f"/reservations/{current}#now" in mail_log["body_text"]
        assert "check-in tomorrow" in mail_log["body_text"]
        # Check-in day: the same key, so no second host mail.
        moment[0] = datetime.combine(day_before + timedelta(days=1), time(10, 0))
        claim.sweep_reminders()
        assert len(_host_reminders(current)) == 1
    finally:
        db.execute("DELETE FROM alert WHERE reservation_id = ?", (current,))
        db.execute("DELETE FROM console_mail_log")
        db.execute("DELETE FROM email_outbox")
        _cleanup()


def test_the_reminder_and_door_code_notice_each_end_with_one_button():
    content = mail_notify.build_reminder_host(
        property_name="Flat", date="01.11.2026", assigned="", stay_url="https://example.test/reservations/5#now",
        claimed=False, tomorrow=True,
    )
    assert content["subject"].startswith("Arriving tomorrow, guest link not opened yet")
    assert content["html"].count('href="https://example.test/reservations/5#now"') >= 1
    payload = mail_notify._door_code_payload("en", "Flat: code late", "The code is late.", 5)
    assert "/reservations/5#now" in payload["text"]
    assert payload["html"].count("Open the stay") == 1
    assert "<p>The code is late.</p>" not in payload["html"]
