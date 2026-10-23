"""Arrival warnings follow live completion and are cleared by the next sweep."""
from __future__ import annotations

from datetime import date

import pytest

from app import alerts, claim, db, mail, reporting
from tests.test_arrival_nudge_0245 import _clock
from tests.test_claim_mail import _cleanup, _seed


@pytest.fixture
def stay(monkeypatch):
    current, past, far, apartment_id = _seed()
    arrival = db.query_one(
        "SELECT date_from FROM reservation WHERE id = ?", (current,)
    )["date_from"]
    _clock(monkeypatch, date.fromisoformat(arrival), hour=10)
    monkeypatch.setattr(mail, "drain", lambda **kwargs: 0)
    monkeypatch.setattr(claim, "expire_holds", lambda: 0)
    progress = {
        "filled": 0, "expected": 2, "incomplete": True, "status": "awaiting_guest",
    }

    def current_progress(reservation, guests=None):
        if reservation["id"] == current:
            return dict(progress)
        return {"filled": 2, "expected": 2, "incomplete": False, "status": "ready"}

    monkeypatch.setattr(reporting, "reservation_progress", current_progress)
    try:
        yield current, apartment_id, progress
    finally:
        for reservation_id in (current, past, far):
            db.execute("DELETE FROM alert WHERE reservation_id = ?", (reservation_id,))
            db.execute("DELETE FROM email_outbox WHERE reservation_id = ?", (reservation_id,))
        _cleanup()


def _raise(stay, kind="guest_incomplete_checkin", level="warning"):
    reservation_id, apartment_id, _progress = stay
    key = f"{kind}:{reservation_id}"
    alerts.raise_alert(
        level, kind, "Check-in today", "Forms incomplete",
        dedupe_key=key, apartment_id=apartment_id, reservation_id=reservation_id,
    )
    return key


def _rows(stay):
    return db.query(
        "SELECT * FROM alert WHERE reservation_id = ? AND resolved_at IS NULL",
        (stay[0],),
    )


@pytest.mark.parametrize("status", ["ready", "reported", "not_required"])
@pytest.mark.parametrize("lang", ["en", "cs"])
def test_completed_stay_hides_existing_warning_before_worker_runs(stay, status, lang):
    key = _raise(stay)
    stay[2].update(filled=2, incomplete=False, status=status)

    assert alerts.open_alert(key) is not None
    assert alerts.present_many(_rows(stay), lang) == []
    # Presentation is read-only; the worker owns persisted resolution.
    assert alerts.open_alert(key) is not None


@pytest.mark.parametrize(
    ("filled", "expected", "incomplete"),
    [(1, 2, True), (2, 2, True), (2, None, False), (1, 2, False)],
)
def test_incomplete_or_unknown_forms_keep_the_warning(stay, filled, expected, incomplete):
    _raise(stay)
    stay[2].update(filled=filled, expected=expected, incomplete=incomplete)

    cards = alerts.present_many(_rows(stay), "en")
    assert len(cards) == 1
    assert cards[0]["display_reason"] == "Check-in today · forms incomplete"


def test_hiding_completed_forms_preserves_other_warnings_for_the_stay(stay):
    _raise(stay)
    _raise(stay, "dates_changed_resign", "critical")
    stay[2].update(filled=2, incomplete=False, status="ready")

    cards = alerts.present_many(_rows(stay), "en")
    assert [card["kind"] for card in cards] == ["dates_changed_resign"]


def test_worker_resolves_completion_and_warns_again_if_forms_become_incomplete(stay):
    key = _raise(stay)
    original_id = alerts.open_alert(key)["id"]
    stay[2].update(filled=2, incomplete=False, status="ready")

    assert claim.sweep_reminders()["host"] == 0
    assert alerts.open_alert(key) is None
    resolved = db.query_one("SELECT * FROM alert WHERE id = ?", (original_id,))
    assert resolved["resolved_at"]
    assert not resolved["user_dismissed"]
    assert claim.sweep_reminders()["host"] == 0
    assert alerts.open_alert(key) is None

    stay[2].update(filled=1, incomplete=True, status="partial")
    assert claim.sweep_reminders()["host"] == 1
    assert alerts.open_alert(key)["id"] != original_id
    assert len(alerts.present_many(_rows(stay), "en")) == 1


def test_unreadable_guest_data_does_not_hide_the_warning(stay, monkeypatch):
    _raise(stay)

    def unreadable(reservation, guests=None):
        raise db.DecryptionError("unreadable test data")

    monkeypatch.setattr(reporting, "reservation_progress", unreadable)
    cards = alerts.present_many(_rows(stay), "en")
    assert len(cards) == 1
    assert cards[0]["kind"] == "guest_incomplete_checkin"
