"""Once a stay is reported, its deadline records the filing instead of counting down.

The badge used to be computed from the arrival date alone, so a stay the
police register had already accepted read "overdue by 42 h" on the stays list
and the stay page for ever. These tests pin the four cases: filed on time,
filed late, not filed yet and past the deadline (still red), and Czech guests
only (no deadline at all).
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from app import auth, config, db, deadlines, host_i18n, reporting
from app.main import app
from tests.conftest import login_as

USERNAME = "deadline-filed-host"
TOKEN = "deadlinefiledtoken"

_ENTITY_ID: int | None = None

DEADLINE_SPAN = re.compile(r'class="deadline(?: [a-z-]+)* ([a-z]+)"[^>]*>([^<]*)<')


# --- the cell itself -------------------------------------------------------

def _utc_iso(local: datetime) -> str:
    """A naive Prague time, stored the way submit_batch stores it (UTC)."""
    aware = local.replace(tzinfo=ZoneInfo(config.TIMEZONE))
    return aware.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def _progress(status: str, submitted: list[str | None]) -> dict:
    return {
        "status": status,
        "reportable": [{"submitted_at": stamp} for stamp in submitted],
    }


CHECK_IN = date(2026, 5, 11)  # a Monday; the deadline is Wednesday 13.05. 23:59:59


def test_filed_at_is_the_latest_reportable_filing_in_prague_time():
    early = _utc_iso(datetime(2026, 5, 12, 9, 0))
    late = _utc_iso(datetime(2026, 5, 12, 14, 32))
    progress = _progress("reported", [late, early, None])

    assert reporting.filed_at(progress) == datetime(2026, 5, 12, 14, 32)


def test_a_stay_filed_before_the_deadline_records_the_filing_time():
    progress = _progress("reported", [_utc_iso(datetime(2026, 5, 12, 14, 32))])

    cell = reporting.deadline_cell(progress, CHECK_IN)

    assert cell["state"] == "filed_on_time"
    assert cell["level"] == "done"
    assert cell["filed_at"] == datetime(2026, 5, 12, 14, 32)


def test_a_stay_filed_after_the_deadline_is_late_by_whole_hours():
    due = deadlines.reporting_deadline(CHECK_IN)
    progress = _progress("reported", [_utc_iso(due + timedelta(hours=6, minutes=10))])

    cell = reporting.deadline_cell(progress, CHECK_IN)

    assert cell["state"] == "filed_late"
    assert cell["level"] == "neutral"
    assert cell["late_hours"] == 6


def test_a_filing_minutes_after_the_deadline_is_never_zero_hours_late():
    due = deadlines.reporting_deadline(CHECK_IN)
    progress = _progress("reported", [_utc_iso(due + timedelta(minutes=5))])

    assert reporting.deadline_cell(progress, CHECK_IN)["late_hours"] == 1


def test_a_stay_still_to_be_filed_keeps_its_countdown():
    for status in ("awaiting_guest", "incomplete", "ready", "failed", "awaiting_verification"):
        cell = reporting.deadline_cell(_progress(status, []), CHECK_IN)
        assert cell["state"] == "countdown"
        assert cell["level"] == deadlines.urgency(CHECK_IN)


def test_a_stay_with_only_czech_guests_has_no_deadline():
    cell = reporting.deadline_cell(_progress("not_required", []), CHECK_IN)

    assert cell["state"] == "none"


@pytest.mark.parametrize("lang", ["en", "cs"])
def test_the_late_wording_counts_hours_then_days(lang):
    hours = host_i18n.translate(lang, "deadline.filed_late_hours", n=6)
    two_days = host_i18n.translate_plural(lang, "deadline.filed_late_days", 2)
    five_days = host_i18n.translate_plural(lang, "deadline.filed_late_days", 5)
    assert "6" in hours and "2" in two_days and "5" in five_days
    if lang == "en":
        assert hours == "Reported 6 h late"
        assert two_days == "Reported 2 days late"
    else:
        assert hours == "Nahlášeno 6 h po termínu"
        assert two_days == "Nahlášeno 2 dny po termínu"
        assert five_days == "Nahlášeno 5 dní po termínu"


# --- the three pages -------------------------------------------------------

def _cleanup():
    apartment = db.query_one("SELECT * FROM apartment WHERE permalink_token = ?", (TOKEN,))
    if apartment:
        db.execute(
            "DELETE FROM guest WHERE reservation_id IN "
            "(SELECT id FROM reservation WHERE apartment_id = ?)",
            (apartment["id"],),
        )
        db.execute("DELETE FROM reservation WHERE apartment_id = ?", (apartment["id"],))
        db.execute("DELETE FROM apartment WHERE id = ?", (apartment["id"],))
    global _ENTITY_ID
    if _ENTITY_ID is not None:
        db.execute("DELETE FROM legal_entity WHERE id = ?", (_ENTITY_ID,))
        _ENTITY_ID = None


def _recent_past_deadline_arrival() -> date:
    """An arrival the dashboard still lists whose (one-day) deadline has passed.

    The dashboard drops a finished stay three days after arrival, so the test
    shortens the window to one working day and picks the latest arrival in
    the last three days that is already past it.
    """
    now = deadlines.local_now()
    for back in (1, 2, 3):
        candidate = date.today() - timedelta(days=back)
        if deadlines.reporting_deadline(candidate) < now:
            return candidate
    pytest.skip("no working day in the last three days (holiday cluster)")


def _seed(*, nationality: str, sent: bool, filed: datetime | None):
    db.init_db()
    _cleanup()
    now = db.utcnow()
    check_in = _recent_past_deadline_arrival()
    existing = db.query_one("SELECT id FROM user_account WHERE username = ?", (USERNAME,))
    user_id = (
        existing["id"]
        if existing
        else auth.create_account(f"{USERNAME}@example.test", "Deadline Host", username=USERNAME)
    )
    global _ENTITY_ID
    _ENTITY_ID = db.insert(
        "legal_entity",
        {"name": "Deadline s.r.o.", "owner_user_id": user_id, "created_at": now},
    )
    apartment_id = db.insert(
        "apartment",
        {
            "legal_entity_id": _ENTITY_ID,
            "owner_user_id": user_id,
            "internal_name": "Deadline 1",
            "permalink_token": TOKEN,
            "automation_mode": "manual",
            "default_purpose": "10",
            "uby_mark": "DEMO1",
            "active": 1,
            "created_at": now,
        },
    )
    reservation_id = db.insert(
        "reservation",
        {
            "apartment_id": apartment_id,
            "source": "airbnb",
            "uid": "deadline-stay",
            "date_from": check_in.isoformat(),
            "date_to": (date.today() + timedelta(days=2)).isoformat(),
            "status": "active",
            "expected_guests_override": 1,
            "created_at": now,
            "updated_at": now,
        },
    )
    db.insert(
        "guest",
        {
            "reservation_id": reservation_id,
            "surname": "NGUYEN",
            "first_name": "MINH",
            "birth_date": "01011990",
            "nationality": nationality,
            "doc_number": "P9988771",
            "res_street": "Le Loi 5",
            "res_city": "Hanoi",
            "res_country": nationality,
            "purpose": "10",
            "is_lead": 1,
            "entered_by": "guest",
            "signature_png": "imported",
            "signed_at": now,
            "passport_photo_at": now,
            "identity_verified_at": now,
            "submit_state": reporting.SENT if sent else reporting.PENDING,
            "submitted_at": _utc_iso(filed) if filed else None,
            "created_at": now,
            "updated_at": now,
        },
    )
    client = TestClient(app)
    login_as(client, USERNAME, follow_redirects=False)
    client.cookies.set(host_i18n.LANG_COOKIE, "en")
    return client, reservation_id, check_in


@pytest.fixture
def one_day_window(monkeypatch):
    monkeypatch.setattr(deadlines, "REPORTING_WORKING_DAYS", 1)
    yield
    _cleanup()


def _pages(client, reservation_id):
    return {
        "dashboard": client.get("/").text,
        "stays list": client.get("/reservations?range=all").text,
        "stay page": client.get(f"/reservations/{reservation_id}").text,
    }


def _badges(page: str) -> list[tuple[str, str]]:
    return [(level, text.strip()) for level, text in DEADLINE_SPAN.findall(page)]


def test_a_reported_stay_past_its_deadline_shows_no_overdue(one_day_window):
    check_in = _recent_past_deadline_arrival()
    filed = deadlines.reporting_deadline(check_in) - timedelta(hours=3)
    client, reservation_id, _ = _seed(nationality="VNM", sent=True, filed=filed)
    expected = f"Reported {filed.strftime('%d.%m. %H:%M')}"

    for name, page in _pages(client, reservation_id).items():
        badges = _badges(page)
        assert ("done", expected) in badges, f"{name}: {badges}"
        assert not any(level == "overdue" for level, _ in badges), name
        assert "overdue by" not in page, name


def test_a_stay_filed_after_its_deadline_reads_late(one_day_window):
    check_in = _recent_past_deadline_arrival()
    filed = deadlines.reporting_deadline(check_in) + timedelta(hours=6, minutes=30)
    if filed > deadlines.local_now():
        pytest.skip("the deadline passed less than seven hours ago")
    client, reservation_id, _ = _seed(nationality="VNM", sent=True, filed=filed)

    for name, page in _pages(client, reservation_id).items():
        badges = _badges(page)
        assert ("neutral", "Reported 6 h late") in badges, f"{name}: {badges}"
        assert "overdue by" not in page, name


def test_a_stay_not_reported_past_its_deadline_is_still_critical(one_day_window):
    client, reservation_id, _ = _seed(nationality="VNM", sent=False, filed=None)

    for name, page in _pages(client, reservation_id).items():
        badges = _badges(page)
        assert any(level == "overdue" and "overdue by" in text for level, text in badges), (
            f"{name}: {badges}"
        )


def test_a_czech_only_stay_shows_no_deadline(one_day_window):
    client, reservation_id, _ = _seed(nationality="CZE", sent=False, filed=None)
    progress = reporting.reservation_progress(
        db.query_one("SELECT * FROM reservation WHERE id = ?", (reservation_id,))
    )
    assert progress["status"] == "not_required"

    pages = _pages(client, reservation_id)
    assert _badges(pages["stays list"]) == []
    assert _badges(pages["stay page"]) == []
    assert _badges(pages["dashboard"]) == []
