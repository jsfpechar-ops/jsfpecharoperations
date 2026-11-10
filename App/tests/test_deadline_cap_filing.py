"""Brief 1070: registered guests are filed by the deadline cap.

A stay short of its declared count, or with no count at all, completes only
after 12 quiet hours. The deadline cap (6 h before the legal deadline) must
file the people already registered without waiting for that, and nothing
else about filing may change.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from app import alerts, config, db, reporting
from app.ubyport.client import SubmissionResult
from tests.test_send_controls import SIGNATURE

# Check-in Mon 9 Nov 2026. Legal deadline in code: Wed 11 Nov 23:59:59 Prague
# (CET, UTC+1) = 22:59:59 UTC. Cap: 17:59:59 Prague = 16:59:59 UTC.
CHECK_IN = "2026-11-09"
LAST_WRITE = "2026-11-11T13:00:00+00:00"  # 14:00 Prague on the deadline day
BEFORE_CAP = datetime(2026, 11, 11, 16, 59, tzinfo=timezone.utc)
AFTER_CAP = datetime(2026, 11, 11, 17, 0, tzinfo=timezone.utc)
DEADLINE_UTC = datetime(2026, 11, 11, 22, 59, 59, tzinfo=timezone.utc)


def _fresh_db(monkeypatch, tmp_path, name):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / name)
    db.init_db()


def _stay(mode, *, date_from, expected, guests, updated_at=None, token="tok-1070"):
    """One apartment, one stay, ``guests`` complete guest forms."""
    now = db.utcnow()
    touched = updated_at or now
    entity_id = db.insert(
        "legal_entity",
        {"name": "Test", "seat": "Praha", "ico": "12345678", "created_at": now},
    )
    apartment_id = db.insert(
        "apartment",
        {
            "legal_entity_id": entity_id,
            "internal_name": "Flat",
            "city_en": "Prague",
            "permalink_token": token,
            "automation_mode": mode,
            "submit_after_hours": 24,
            "default_purpose": "10",
            "active": 1,
            "created_at": now,
        },
    )
    start = date.fromisoformat(date_from)
    reservation_id = db.insert(
        "reservation",
        {
            "apartment_id": apartment_id,
            "source": "manual",
            "uid": f"stay-{token}",
            "date_from": date_from,
            "date_to": (start + timedelta(days=30)).isoformat(),
            "status": "active",
            "expected_guests_override": expected,
            "created_at": now,
            "updated_at": now,
        },
    )
    guest_ids = [_add_guest(reservation_id, i, touched) for i in range(guests)]
    return apartment_id, reservation_id, guest_ids


def _add_guest(reservation_id, index, touched):
    return db.insert(
        "guest",
        {
            "reservation_id": reservation_id,
            "surname": f"Smith{chr(65 + index)}",
            "first_name": "John",
            "birth_date": "01011990",
            "nationality": "GBR",
            "doc_number": f"P123456{index}",
            "res_street": "Street 1",
            "res_city": "London",
            "res_country": "GBR",
            "purpose": "10",
            "is_lead": 1 if index == 0 else 0,
            "entered_by": "host",
            "signature_png": SIGNATURE,
            "signed_at": touched,
            "identity_verified_at": touched,
            "submit_state": reporting.PENDING,
            "created_at": touched,
            "updated_at": touched,
        },
    )


def _reservation(reservation_id):
    return db.query_one("SELECT * FROM reservation WHERE id = ?", (reservation_id,))


def _states(guest_ids):
    return [
        db.query_one("SELECT submit_state FROM guest WHERE id = ?", (gid,))["submit_state"]
        for gid in guest_ids
    ]


class _FakeClient:
    """Accepts every record and remembers the size of each batch."""

    def __init__(self):
        self.batches = []

    def submit(self, _header, guests):
        self.batches.append(len(guests))
        return SubmissionResult(
            endpoint="test",
            request_xml="<request/>",
            response_xml="<response/>",
            record_errors=["" for _ in guests],
        )


def _fake_register(monkeypatch):
    client = _FakeClient()
    monkeypatch.setattr(reporting, "client_for", lambda *_a, **_k: client)
    monkeypatch.setattr(reporting.validation, "validate_apartment", lambda _a: [])
    return client


def _past_check_in():
    # Ten days ago: the cap and the deadline have long passed on the real clock.
    return (date.today() - timedelta(days=10)).isoformat()


def _an_hour_ago():
    # Well inside the 12 quiet hours, so the stay cannot complete quietly.
    return (datetime.now(timezone.utc) - timedelta(hours=1)).replace(microsecond=0).isoformat()


# --- the decision itself, on a frozen clock (now=) ---------------------------


def test_a_short_stay_is_due_at_the_cap_before_the_deadline(monkeypatch, tmp_path):
    """(a) 2 of 3 registered, last write 14:00 on the deadline day."""
    _fresh_db(monkeypatch, tmp_path, "cap-a.db")
    apartment_id, reservation_id, _ids = _stay(
        "scheduled", date_from=CHECK_IN, expected=3, guests=2, updated_at=LAST_WRITE
    )
    apartment = db.query_one("SELECT * FROM apartment WHERE id = ?", (apartment_id,))
    reservation = _reservation(reservation_id)
    assert not reservation["registration_completed_at"]

    assert reporting.due_for_automatic_send(apartment, reservation, now=BEFORE_CAP) is False
    assert reporting.due_for_automatic_send(apartment, reservation, now=AFTER_CAP) is True
    assert AFTER_CAP < DEADLINE_UTC


def test_a_stay_with_no_expected_count_is_due_at_the_cap(monkeypatch, tmp_path):
    """(b) The host entered the stay; no count was ever declared."""
    _fresh_db(monkeypatch, tmp_path, "cap-b.db")
    apartment_id, reservation_id, _ids = _stay(
        "immediate", date_from=CHECK_IN, expected=None, guests=1, updated_at=LAST_WRITE
    )
    apartment = db.query_one("SELECT * FROM apartment WHERE id = ?", (apartment_id,))
    reservation = _reservation(reservation_id)
    assert reporting.expected_guest_count(reservation) is None

    assert reporting.due_for_automatic_send(apartment, reservation, now=BEFORE_CAP) is False
    assert reporting.due_for_automatic_send(apartment, reservation, now=AFTER_CAP) is True


def test_a_completed_stay_keeps_its_schedule(monkeypatch, tmp_path):
    """(c) Completion plus delay, capped as before."""
    _fresh_db(monkeypatch, tmp_path, "cap-c.db")
    apartment = {"automation_mode": "scheduled", "submit_after_hours": 24}
    reservation = {
        "id": -1,
        "date_from": CHECK_IN,
        "registration_completed_at": "2026-11-10T08:00:00+00:00",
    }
    # 24 h after completion is Wed 08:00 UTC, earlier than the cap.
    assert reporting.due_for_automatic_send(
        apartment, reservation, now=datetime(2026, 11, 11, 7, 59, tzinfo=timezone.utc)
    ) is False
    assert reporting.due_for_automatic_send(
        apartment, reservation, now=datetime(2026, 11, 11, 8, 0, tzinfo=timezone.utc)
    ) is True
    # 48 h after completion is later than the cap, so the cap wins.
    apartment["submit_after_hours"] = 48
    assert reporting.due_for_automatic_send(apartment, reservation, now=BEFORE_CAP) is False
    assert reporting.due_for_automatic_send(apartment, reservation, now=AFTER_CAP) is True
    # Immediate sends at completion.
    immediate = {"automation_mode": "immediate", "submit_after_hours": 24}
    assert reporting.due_for_automatic_send(
        immediate, reservation, now=datetime(2026, 11, 10, 8, 0, tzinfo=timezone.utc)
    ) is True


def test_a_manual_property_is_never_due(monkeypatch, tmp_path):
    """(d) manual stays manual, before and after the cap and the deadline."""
    _fresh_db(monkeypatch, tmp_path, "cap-d.db")
    apartment = {"automation_mode": "manual", "submit_after_hours": 24}
    reservation = {"id": -1, "date_from": CHECK_IN, "registration_completed_at": None}
    for moment in (AFTER_CAP, DEADLINE_UTC + timedelta(days=3)):
        assert reporting.due_for_automatic_send(apartment, reservation, now=moment) is False


def test_a_stay_without_a_deadline_anchor_still_waits_for_completion(monkeypatch, tmp_path):
    _fresh_db(monkeypatch, tmp_path, "cap-anchor.db")
    apartment = {"automation_mode": "immediate", "submit_after_hours": 24}
    reservation = {"id": -1, "date_from": None, "registration_completed_at": None}
    assert reporting.due_for_automatic_send(apartment, reservation, now=AFTER_CAP) is False


# --- the sweep, on the real clock (stays anchored in the past) ---------------


def test_the_sweep_files_a_short_stay_past_the_cap(monkeypatch, tmp_path):
    """(a) end to end: filed without waiting for the quiet hours."""
    _fresh_db(monkeypatch, tmp_path, "sweep-a.db")
    client = _fake_register(monkeypatch)
    _apartment_id, reservation_id, guest_ids = _stay(
        "scheduled", date_from=_past_check_in(), expected=3, guests=2,
        updated_at=_an_hour_ago(),
    )

    summary = reporting.sweep()

    assert summary["failed"] == 0
    assert client.batches == [2]
    assert _states(guest_ids) == [reporting.SENT, reporting.SENT]
    # The 12-quiet-hours rule is unchanged: the stay is still not complete.
    assert not _reservation(reservation_id)["registration_completed_at"]


def test_the_sweep_files_a_stay_with_no_expected_count_past_the_cap(monkeypatch, tmp_path):
    """(b) end to end."""
    _fresh_db(monkeypatch, tmp_path, "sweep-b.db")
    client = _fake_register(monkeypatch)
    _apartment_id, reservation_id, guest_ids = _stay(
        "immediate", date_from=_past_check_in(), expected=None, guests=1,
        updated_at=_an_hour_ago(),
    )

    reporting.sweep()

    assert client.batches == [1]
    assert _states(guest_ids) == [reporting.SENT]
    assert not _reservation(reservation_id)["registration_completed_at"]


def test_the_sweep_does_not_file_a_short_stay_before_the_cap(monkeypatch, tmp_path):
    """(c) Before the cap nothing changes: the short stay still waits."""
    _fresh_db(monkeypatch, tmp_path, "sweep-c.db")
    client = _fake_register(monkeypatch)
    _apartment_id, _reservation_id, guest_ids = _stay(
        "immediate", date_from=date.today().isoformat(), expected=3, guests=2,
        updated_at=_an_hour_ago(),
    )

    reporting.sweep()

    assert client.batches == []
    assert _states(guest_ids) == [reporting.PENDING, reporting.PENDING]


def test_the_sweep_leaves_manual_and_auth_failed_properties_alone(monkeypatch, tmp_path):
    """(d) No automatic filing for manual, or while the login is refused."""
    _fresh_db(monkeypatch, tmp_path, "sweep-d.db")
    client = _fake_register(monkeypatch)
    _m_apartment, _m_res, manual_ids = _stay(
        "manual", date_from=_past_check_in(), expected=3, guests=2,
        updated_at=_an_hour_ago(), token="tok-1070-manual",
    )
    locked_apartment, _l_res, locked_ids = _stay(
        "immediate", date_from=_past_check_in(), expected=3, guests=2,
        updated_at=_an_hour_ago(), token="tok-1070-locked",
    )
    alerts.raise_alert(
        "critical",
        "ubyport_auth_failed",
        "Flat: login refused.",
        dedupe_key=f"ubyport_auth_failed:{locked_apartment}",
        apartment_id=locked_apartment,
    )

    reporting.sweep()

    assert client.batches == []
    assert _states(manual_ids + locked_ids) == [reporting.PENDING] * 4


def test_a_later_completion_does_not_file_twice(monkeypatch, tmp_path):
    """(e) Filed at the cap, then the stay completes: nothing is sent again."""
    _fresh_db(monkeypatch, tmp_path, "sweep-e.db")
    client = _fake_register(monkeypatch)
    apartment_id, reservation_id, guest_ids = _stay(
        "immediate", date_from=_past_check_in(), expected=3, guests=2,
        updated_at=_an_hour_ago(),
    )
    reporting.sweep()
    assert client.batches == [2]

    # The host lowers the count: the stay completes now.
    db.update("reservation", reservation_id, {"expected_guests_override": 2})
    reporting.submit_stay_if_complete(apartment_id, reservation_id)
    reporting.sweep()

    assert _reservation(reservation_id)["registration_completed_at"]
    assert client.batches == [2]
    assert _states(guest_ids) == [reporting.SENT, reporting.SENT]


def test_a_person_who_registers_after_the_cap_filing_is_filed(monkeypatch, tmp_path):
    """(f) The late person goes alone; the filed two are not sent again."""
    _fresh_db(monkeypatch, tmp_path, "sweep-f.db")
    client = _fake_register(monkeypatch)
    _apartment_id, reservation_id, guest_ids = _stay(
        "scheduled", date_from=_past_check_in(), expected=3, guests=2,
        updated_at=_an_hour_ago(),
    )
    reporting.sweep()
    assert client.batches == [2]

    late_id = _add_guest(reservation_id, 2, db.utcnow())
    reporting.sweep()

    assert client.batches == [2, 1]
    assert _states(guest_ids + [late_id]) == [reporting.SENT] * 3


def test_valid_co_guests_are_filed_at_the_cap_while_one_form_is_unsigned(monkeypatch, tmp_path):
    """The main new behaviour: the valid person goes, the unsigned one waits."""
    _fresh_db(monkeypatch, tmp_path, "sweep-mixed.db")
    client = _fake_register(monkeypatch)
    _apartment_id, reservation_id, (valid_id, unsigned_id) = _stay(
        "immediate", date_from=_past_check_in(), expected=2, guests=2,
        updated_at=_an_hour_ago(),
    )
    db.update("guest", unsigned_id, {"signature_png": None, "signed_at": None})

    reporting.sweep()

    assert client.batches == [1]
    assert _states([valid_id, unsigned_id]) == [reporting.SENT, reporting.PENDING]
    assert not _reservation(reservation_id)["registration_completed_at"]

    reporting.sweep()

    assert client.batches == [1]
    assert _states([valid_id, unsigned_id]) == [reporting.SENT, reporting.PENDING]
