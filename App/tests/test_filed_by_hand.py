"""WP23: a stay the host filed by hand in the UbyPort web application.

When UbyHost cannot file a stay in time, the host files it in UbyPort and
marks it on the stay page. The guests then count as filed everywhere: status,
deadline badge, watchdog, sweep (never sent afterwards) and house book. The
mark can be taken back within 24 hours if it was a mistake. Time is frozen by
passing ``now``; the routes use the real clock and their stamps are set
relative to it.
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app import auth, db, deadlines, filing_watchdog, host_i18n, housebook, reporting
from tests.test_filing_watchdog import PASSWORD, USERNAME, world as world  # noqa: F401
from tests.test_filing_watchdog import FRIDAY, _mine

# A filing time on Wednesday 30.09.2026 at 14:32 Prague time (CEST, UTC+2).
FILED_UTC = "2026-09-30T12:32:00+00:00"
NOW = datetime(2026, 9, 30, 15, 0, tzinfo=timezone.utc)


def _states(rid):
    return {
        row["nationality"]: row
        for row in db.query(
            "SELECT * FROM guest WHERE reservation_id = ? ORDER BY id", (rid,)
        )
    }


def _reservation(rid):
    return db.query_one("SELECT * FROM reservation WHERE id = ?", (rid,))


@pytest.fixture
def client(world):
    from app.main import app

    with TestClient(app) as test_client:
        response = test_client.post(
            "/login", data={"username": USERNAME, "password": PASSWORD}, follow_redirects=False
        )
        assert response.status_code == 303 and "err=" not in response.headers["location"]
        yield test_client
    db.execute("DELETE FROM audit WHERE action LIKE 'stay_filed_manually%'")


# --- the mark itself ------------------------------------------------------------


def test_the_mark_covers_the_unfiled_reportable_guests_only(world):
    rid = world["add_stay"](
        [("DEU", "pending"), ("USA", "error"), ("UKR", "blocked"),
         ("CZE", "not_required"), ("FRA", "sent")]
    )
    result = reporting.mark_filed_by_hand(rid, FILED_UTC, "UP-123")
    assert result["marked"] == 3 and result["busy"] == 0

    guests = _states(rid)
    for nationality, previous in (("DEU", "pending"), ("USA", "error"), ("UKR", "blocked")):
        guest = guests[nationality]
        assert guest["submit_state"] == reporting.SENT
        assert guest["manual_filed_at"] == FILED_UTC
        assert guest["manual_reference"] == "UP-123"
        assert guest["manual_marked_at"]
        assert guest["manual_prev_state"] == previous
        assert reporting.guest_filed_by_hand(guest)
    assert guests["CZE"]["submit_state"] == "not_required" and not guests["CZE"]["manual_filed_at"]
    assert guests["FRA"]["submit_state"] == "sent" and not guests["FRA"]["manual_filed_at"]

    # Nothing left to mark: a second mark changes nothing.
    assert reporting.mark_filed_by_hand(rid, FILED_UTC, None)["marked"] == 0


def test_a_stay_filed_by_hand_is_reported_even_without_a_signature(world):
    # The test guests carry no signature, so UbyHost would call them incomplete.
    rid = world["add_stay"]([("DEU", "pending"), ("USA", "error")])
    assert reporting.reservation_progress(_reservation(rid))["status"] != "reported"
    reporting.mark_filed_by_hand(rid, FILED_UTC, None)
    progress = reporting.reservation_progress(_reservation(rid))
    assert progress["status"] == "reported"
    assert reporting.send_controls(_reservation(rid), db.query_one(
        "SELECT * FROM apartment WHERE id = ?", (world["apartment_id"],)
    ), progress)["send_enabled"] is False


def test_the_deadline_badge_says_filed_by_hand(world):
    rid = world["add_stay"]([("DEU", "pending")])
    reporting.mark_filed_by_hand(rid, FILED_UTC, None)
    progress = reporting.reservation_progress(_reservation(rid))
    cell = reporting.deadline_cell(progress, FRIDAY)
    assert cell["by_hand"] is True
    assert cell["state"] == "filed_on_time"
    assert cell["filed_at"] == datetime(2026, 9, 30, 14, 32)


def test_a_late_filing_by_hand_is_still_marked_by_hand(world):
    rid = world["add_stay"]([("DEU", "pending")])
    reporting.mark_filed_by_hand(rid, "2026-10-02T08:00:00+00:00", None)
    cell = reporting.deadline_cell(reporting.reservation_progress(_reservation(rid)), FRIDAY)
    assert cell["state"] == "filed_late" and cell["by_hand"] is True


def test_a_stay_filed_by_hand_is_not_at_risk(world):
    rid = world["add_stay"]([("DEU", "pending"), ("USA", "error")])
    now = datetime(2026, 10, 1, 9, 0)
    assert rid in _mine(filing_watchdog.at_risk_stays(now), {rid})
    reporting.mark_filed_by_hand(rid, FILED_UTC, None)
    assert rid not in _mine(filing_watchdog.at_risk_stays(now), {rid})
    assert rid not in _mine(filing_watchdog.unknown_risk_stays(now), {rid})


def test_the_sweep_never_sends_a_guest_filed_by_hand(world, monkeypatch):
    # Only the state may decide here, so every guest counts as complete.
    monkeypatch.setattr(reporting, "guest_is_complete", lambda guest, reservation: True)
    rid = world["add_stay"]([("DEU", "pending")])
    apartment_id = world["apartment_id"]

    def sendable(**kwargs):
        pairs = reporting.collect_sendable(apartment_id, ignore_automation=True, **kwargs)
        return [guest["id"] for guest, _reservation in pairs if guest["reservation_id"] == rid]

    assert len(sendable()) == 1
    # A list built before the mark, as a running sweep would hold it.
    stale = [
        pair for pair in reporting.collect_sendable(apartment_id, ignore_automation=True)
        if pair[0]["reservation_id"] == rid
    ]
    reporting.mark_filed_by_hand(rid, FILED_UTC, None)
    assert sendable() == []
    # Not even as a deliberate resend: the register already has the record.
    assert sendable(allow_resend=True) == []
    # And the claim, the only double-filing guard, drops the stale pair.
    token, claimed = reporting.claim_sendable(stale)
    reporting.release_sendable_claim(token)
    assert claimed == []


def test_a_guest_ubyhost_is_sending_right_now_is_not_marked(world):
    rid = world["add_stay"]([("DEU", "pending")])
    guest_id = _states(rid)["DEU"]["id"]
    db.execute(
        "INSERT INTO submission_claim (guest_id, claim_token, claimed_at) VALUES (?, ?, ?)",
        (guest_id, "watchdog-live-claim", time.time()),
    )
    try:
        result = reporting.mark_filed_by_hand(rid, FILED_UTC, None)
    finally:
        db.execute("DELETE FROM submission_claim WHERE claim_token = ?", ("watchdog-live-claim",))
    assert result == {"marked": 0, "busy": 1, "guest_ids": []}
    assert _states(rid)["DEU"]["submit_state"] == "pending"


# --- undo -----------------------------------------------------------------------


def test_undo_within_24_hours_restores_the_previous_states(world):
    rid = world["add_stay"]([("DEU", "pending"), ("USA", "error"), ("UKR", "blocked")])
    reporting.mark_filed_by_hand(rid, FILED_UTC, "UP-1")
    marked = datetime.fromisoformat(_states(rid)["DEU"]["manual_marked_at"])

    assert reporting.undo_filed_by_hand(rid, now=marked + timedelta(hours=25)) == []
    assert _states(rid)["DEU"]["submit_state"] == "sent"

    undone = reporting.undo_filed_by_hand(rid, now=marked + timedelta(hours=23, minutes=59))
    assert len(undone) == 3
    guests = _states(rid)
    assert {n: g["submit_state"] for n, g in guests.items()} == {
        "DEU": "pending", "USA": "error", "UKR": "blocked",
    }
    for guest in guests.values():
        assert guest["manual_filed_at"] is None and guest["manual_reference"] is None
        assert guest["manual_marked_at"] is None and guest["manual_prev_state"] is None


def test_undo_leaves_a_guest_ubyport_accepted_alone(world):
    rid = world["add_stay"]([("FRA", "sent"), ("DEU", "pending")])
    reporting.mark_filed_by_hand(rid, FILED_UTC, None)
    reporting.undo_filed_by_hand(rid)
    guests = _states(rid)
    assert guests["FRA"]["submit_state"] == "sent"
    assert guests["DEU"]["submit_state"] == "pending"


# --- the filing time ------------------------------------------------------------


def test_the_filing_time_is_read_as_prague_time_and_checked():
    assert reporting.parse_manual_filed_at("2026-09-30T14:32", NOW) == FILED_UTC
    assert reporting.parse_manual_filed_at("", NOW) == NOW.isoformat()
    # A few minutes ahead is clock skew; more is a typo.
    assert reporting.parse_manual_filed_at("2026-09-30T17:04", NOW)
    assert reporting.parse_manual_filed_at("2026-09-30T17:30", NOW) is None
    assert reporting.parse_manual_filed_at("2026-07-30T12:00", NOW) is None
    assert reporting.parse_manual_filed_at("yesterday", NOW) is None


def test_the_reference_is_one_short_line():
    assert reporting.clean_manual_reference("  UP\n 123 ") == "UP 123"
    assert reporting.clean_manual_reference("") is None
    assert len(reporting.clean_manual_reference("x" * 500)) == reporting.MANUAL_REFERENCE_MAX


# --- house book -----------------------------------------------------------------


def test_the_house_book_notes_a_filing_by_hand(world):
    rid = world["add_stay"]([("DEU", "pending"), ("FRA", "sent")])
    reporting.mark_filed_by_hand(rid, FILED_UTC, "UP-777")
    rows = {
        row["nationality"]: row
        for row in housebook.housebook_rows(apartment_id=world["apartment_id"])
    }
    assert rows["DEU"]["reported"] == "yes - filed by hand in UbyPort"
    assert rows["DEU"]["reported_at"] == FILED_UTC
    assert rows["DEU"]["stamp"] == "UP-777"
    assert rows["FRA"]["reported"] == "yes"
    # The registration form PDF builds with the note.
    pdf = housebook.registration_form_pdf(_states(rid)["DEU"]["id"])
    assert pdf.startswith(b"%PDF")


# --- the stay page --------------------------------------------------------------


def test_the_host_marks_the_stay_on_its_page_and_can_undo(world, client):
    rid = world["add_stay"]([("DEU", "pending")])
    page = client.get(f"/reservations/{rid}").text
    assert host_i18n.translate("cs", "stay.hand_filing.open") in page
    assert 'action="/reservations/%d/filed-by-hand"' % rid in page

    response = client.post(
        f"/reservations/{rid}/filed-by-hand",
        data={"filed_at": deadlines.local_now().strftime("%Y-%m-%dT%H:%M"),
              "reference": "UP-2026-42"},
        follow_redirects=False,
    )
    assert response.status_code == 303 and "msg=" in response.headers["location"]
    guest = _states(rid)["DEU"]
    assert guest["submit_state"] == "sent" and guest["manual_reference"] == "UP-2026-42"
    audit = db.query_one(
        "SELECT * FROM audit WHERE action = 'stay_filed_manually' AND detail LIKE ?",
        (f"reservation={rid} %",),
    )
    assert audit and "guests=1" in audit["detail"] and "UP-2026-42" in audit["detail"]

    page = client.get(f"/reservations/{rid}").text
    when = deadlines.local_now(datetime.fromisoformat(guest["manual_filed_at"]))
    assert host_i18n.translate("cs", "deadline.filed_by_hand", when=when.strftime("%d.%m. %H:%M")) in page
    assert host_i18n.translate("cs", "stay.detail.guests.filed_by_hand") in page
    assert "UP-2026-42" in page
    assert host_i18n.translate("cs", "stay.hand_filing.undo") in page
    # Nothing is left to mark, so the form is gone.
    assert 'action="/reservations/%d/filed-by-hand"' % rid not in page

    response = client.post(f"/reservations/{rid}/filed-by-hand/undo", follow_redirects=False)
    assert response.status_code == 303 and "msg=" in response.headers["location"]
    assert _states(rid)["DEU"]["submit_state"] == "pending"
    assert db.query_one(
        "SELECT 1 FROM audit WHERE action = 'stay_filed_manually_undone' AND detail = ?",
        (f"reservation={rid} guests=1",),
    )


def test_undo_after_24_hours_is_refused(world, client):
    rid = world["add_stay"]([("DEU", "pending")])
    reporting.mark_filed_by_hand(rid, FILED_UTC, None)
    old = (datetime.now(timezone.utc) - timedelta(hours=25)).replace(microsecond=0).isoformat()
    db.execute("UPDATE guest SET manual_marked_at = ? WHERE reservation_id = ?", (old, rid))

    page = client.get(f"/reservations/{rid}").text
    assert host_i18n.translate("cs", "stay.hand_filing.undo") not in page
    response = client.post(f"/reservations/{rid}/filed-by-hand/undo", follow_redirects=False)
    assert "err=" in response.headers["location"]
    assert _states(rid)["DEU"]["submit_state"] == "sent"
    assert not db.query_one(
        "SELECT 1 FROM audit WHERE action = 'stay_filed_manually_undone' AND detail LIKE ?",
        (f"reservation={rid} %",),
    )


def test_a_filing_time_in_the_future_is_refused(world, client):
    rid = world["add_stay"]([("DEU", "pending")])
    future = (deadlines.local_now() + timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M")
    response = client.post(
        f"/reservations/{rid}/filed-by-hand", data={"filed_at": future}, follow_redirects=False
    )
    assert "err=" in response.headers["location"]
    assert _states(rid)["DEU"]["submit_state"] == "pending"


def test_a_stay_of_another_workspace_cannot_be_marked(world, client):
    other_user = db.query_one("SELECT id FROM user_account WHERE username = ?", ("filed-by-hand-other",))
    other_id = other_user["id"] if other_user else auth.create_account(
        "filed-by-hand-other", PASSWORD, "Other Host", must_change_password=False
    )
    now = db.utcnow()
    apartment_id = db.insert(
        "apartment",
        {"owner_user_id": other_id, "internal_name": "Other Loft",
         "permalink_token": "filingwatchdog-other", "active": 1, "created_at": now},
    )
    rid = db.insert(
        "reservation",
        {"apartment_id": apartment_id, "source": "manual", "uid": "filed-by-hand-other",
         "date_from": FRIDAY.isoformat(), "date_to": (FRIDAY + timedelta(days=2)).isoformat(),
         "status": "active", "created_at": now, "updated_at": now},
    )
    guest_id = db.insert(
        "guest",
        {"reservation_id": rid, "nationality": "DEU", "submit_state": "pending",
         "created_at": now, "updated_at": now},
    )
    response = client.post(
        f"/reservations/{rid}/filed-by-hand", data={"filed_at": ""}, follow_redirects=False
    )
    assert "err=" in response.headers["location"]
    assert db.query_one("SELECT submit_state FROM guest WHERE id = ?", (guest_id,))["submit_state"] == "pending"


@pytest.mark.parametrize("lang", ["en", "cs"])
def test_the_new_strings_exist_in_both_languages(lang):
    keys = [
        "deadline.filed_by_hand", "stay.detail.guests.filed_by_hand",
        "stay.hand_filing.title", "stay.hand_filing.lede", "stay.hand_filing.open",
        "stay.hand_filing.filed_at", "stay.hand_filing.reference",
        "stay.hand_filing.reference_hint", "stay.hand_filing.covers",
        "stay.hand_filing.confirm", "stay.hand_filing.done",
        "stay.hand_filing.done_reference", "stay.hand_filing.undo",
        "stay.hand_filing.undo_until", "stay.hand_filing.undo_confirm",
        "flash.hand_filing.marked", "flash.hand_filing.undone",
        "flash.error.hand_filing_nothing", "flash.error.hand_filing_busy",
        "flash.error.hand_filing_time", "flash.error.hand_filing_undo_closed",
        "guest.admin.banner.filed_by_hand", "guide.reporting.manual_filing_step4",
    ]
    for key in keys:
        assert key in host_i18n.STRINGS[lang], key
    if lang == "cs":
        assert host_i18n.STRINGS["cs"]["deadline.filed_by_hand"] == "Podáno ručně %(when)s"
        assert "ručně v UbyPortu" in host_i18n.STRINGS["cs"]["stay.hand_filing.open"]
    else:
        assert host_i18n.STRINGS["en"]["stay.hand_filing.open"] == "I filed this stay by hand in UbyPort"
