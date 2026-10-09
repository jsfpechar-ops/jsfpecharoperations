"""WP23: the filing watchdog.

Every run of the deadline job finds the stays that may miss their police
deadline, warns the host once per stay, sends the operator a digest at most
every six hours and pings an external dead-man switch: ``<url>`` when nothing
is at risk, ``<url>/fail`` when something is. Time is frozen by passing
``now`` explicitly, as the deadline code itself does.
"""
from __future__ import annotations

import json

from datetime import date, datetime, timedelta, timezone

import pytest
from markupsafe import escape

from app import auth, config, db, filing_watchdog, host_i18n, mail, mail_notify, scheduler
from tests.test_submission_retry_cap import host as host  # noqa: F401

USERNAME = "filing-watchdog-host"
TOKEN_PREFIX = "filingwatchdog"
CONTACT = "watchdog-host@example.invalid"
GUEST_SURNAME = "WATCHDOGSURNAME"

# Friday 25.09.2026. Monday 28.09. is a public holiday (Den české státnosti),
# so the three working days are Fri 25, Tue 29 and Wed 30: the deadline is
# Wednesday 30.09.2026 23:59:59, one day later than without the holiday.
FRIDAY = date(2026, 9, 25)
DEADLINE = datetime(2026, 9, 30, 23, 59, 59)


def _cleanup() -> None:
    apartments = db.query(
        "SELECT id, legal_entity_id FROM apartment WHERE permalink_token LIKE ?",
        (f"{TOKEN_PREFIX}%",),
    )
    for apartment in apartments:
        db.execute(
            "DELETE FROM email_outbox WHERE reservation_id IN "
            "(SELECT id FROM reservation WHERE apartment_id = ?)",
            (apartment["id"],),
        )
        db.execute(
            "DELETE FROM guest WHERE reservation_id IN "
            "(SELECT id FROM reservation WHERE apartment_id = ?)",
            (apartment["id"],),
        )
        db.execute("DELETE FROM reservation WHERE apartment_id = ?", (apartment["id"],))
        db.execute("DELETE FROM submission WHERE apartment_id = ?", (apartment["id"],))
        db.execute("DELETE FROM apartment WHERE id = ?", (apartment["id"],))
        if apartment["legal_entity_id"]:
            db.execute("DELETE FROM legal_entity WHERE id = ?", (apartment["legal_entity_id"],))
    db.execute("DELETE FROM email_outbox WHERE kind = 'deadline_digest'")
    db.set_setting(filing_watchdog.DIGEST_SETTING, None)


@pytest.fixture
def world():
    """One host, one property, and a helper that adds a stay with guests."""
    db.init_db()
    _cleanup()
    now = db.utcnow()
    existing = db.query_one("SELECT id FROM user_account WHERE username = ?", (USERNAME,))
    user_id = (
        existing["id"]
        if existing
        else auth.create_account(f"{USERNAME}@example.test", "Watchdog Host", username=USERNAME)
    )
    entity_id = db.insert(
        "legal_entity",
        {"name": "Watchdog s.r.o.", "owner_user_id": user_id, "contact_email": CONTACT,
         "created_at": now},
    )
    apartment_id = db.insert(
        "apartment",
        {
            "legal_entity_id": entity_id,
            "owner_user_id": user_id,
            "internal_name": "Watchdog Loft",
            "permalink_token": f"{TOKEN_PREFIX}1",
            "automation_mode": "manual",
            "active": 1,
            "created_at": now,
        },
    )
    counter = {"n": 0}

    def add_stay(guests, *, arrival=FRIDAY, status="active"):
        counter["n"] += 1
        reservation_id = db.insert(
            "reservation",
            {
                "apartment_id": apartment_id,
                "source": "airbnb",
                "uid": f"watchdog-{counter['n']}",
                "date_from": arrival.isoformat(),
                "date_to": (arrival + timedelta(days=3)).isoformat(),
                "status": status,
                "created_at": now,
                "updated_at": now,
            },
        )
        for nationality, state in guests:
            db.insert(
                "guest",
                {
                    "reservation_id": reservation_id,
                    "surname": GUEST_SURNAME,
                    "first_name": "ANNA",
                    "nationality": nationality,
                    "stay_from": arrival.isoformat(),
                    "stay_to": (arrival + timedelta(days=3)).isoformat(),
                    "submit_state": state,
                    "created_at": now,
                    "updated_at": now,
                },
            )
        return reservation_id

    yield {"add_stay": add_stay, "user_id": user_id, "apartment_id": apartment_id}
    _cleanup()


def _mine(stays, ids):
    return {stay["reservation_id"]: stay for stay in stays if stay["reservation_id"] in ids}


# --- at-risk detection ----------------------------------------------------------


def test_a_friday_arrival_before_a_public_holiday_gets_the_extra_day(world):
    rid = world["add_stay"]([("DEU", "pending")])

    # Tuesday noon: without the holiday the deadline would be tonight, so the
    # stay would be at risk. With it, 36 hours are left.
    assert rid not in _mine(filing_watchdog.at_risk_stays(datetime(2026, 9, 29, 12, 0)), {rid})

    stays = _mine(filing_watchdog.at_risk_stays(datetime(2026, 9, 30, 8, 0)), {rid})
    assert rid in stays
    assert stays[rid]["deadline"] == DEADLINE
    assert stays[rid]["arrival"] == FRIDAY
    assert stays[rid]["overdue"] is False

    late = _mine(filing_watchdog.at_risk_stays(datetime(2026, 10, 2, 9, 0)), {rid})
    assert late[rid]["overdue"] is True


def test_the_window_opens_exactly_24_hours_before_the_deadline(world):
    rid = world["add_stay"]([("DEU", "pending")])
    edge = DEADLINE - timedelta(hours=24)
    assert rid in _mine(filing_watchdog.at_risk_stays(edge), {rid})
    assert rid not in _mine(filing_watchdog.at_risk_stays(edge - timedelta(seconds=1)), {rid})


def test_an_eu_guest_is_reportable(world):
    rid = world["add_stay"]([("SVK", "pending"), ("CZE", "not_required")])
    stays = _mine(filing_watchdog.at_risk_stays(datetime(2026, 9, 30, 8, 0)), {rid})
    assert stays[rid]["unfiled"] == 1


def test_a_czech_only_stay_is_not_at_risk(world):
    rid = world["add_stay"]([("CZE", "pending"), ("cze", "not_required")])
    assert rid not in _mine(filing_watchdog.at_risk_stays(datetime(2026, 10, 5, 8, 0)), {rid})


def test_a_cancelled_stay_is_not_at_risk(world):
    cancelled = world["add_stay"]([("DEU", "pending")], status="cancelled")
    ignored = world["add_stay"]([("DEU", "pending")], status="ignored")
    found = _mine(filing_watchdog.at_risk_stays(datetime(2026, 10, 5, 8, 0)), {cancelled, ignored})
    assert found == {}


def test_a_filed_stay_is_not_at_risk_and_a_partly_filed_one_counts_the_rest(world):
    filed = world["add_stay"]([("DEU", "sent"), ("USA", "sent"), ("CZE", "not_required")])
    partly = world["add_stay"]([("DEU", "sent"), ("USA", "error"), ("UKR", "blocked")])
    found = _mine(filing_watchdog.at_risk_stays(datetime(2026, 10, 5, 8, 0)), {filed, partly})
    assert filed not in found
    assert found[partly]["unfiled"] == 2


def test_a_stay_with_a_far_deadline_is_not_at_risk(world):
    rid = world["add_stay"]([("DEU", "pending")], arrival=date(2026, 10, 12))
    assert rid not in _mine(filing_watchdog.at_risk_stays(datetime(2026, 10, 12, 9, 0)), {rid})


# --- host mail ------------------------------------------------------------------


def _outbox(kind, reservation_id=None):
    if reservation_id is None:
        return db.query("SELECT * FROM email_outbox WHERE kind = ? ORDER BY id", (kind,))
    return db.query(
        "SELECT * FROM email_outbox WHERE kind = ? AND reservation_id = ? ORDER BY id",
        (kind, reservation_id),
    )


def test_the_host_is_mailed_once_per_stay(world, monkeypatch):
    monkeypatch.setattr(mail, "mail_enabled", lambda: True)
    rid = world["add_stay"]([("DEU", "pending"), ("FRA", "pending")])
    now = datetime(2026, 9, 30, 8, 0)

    stays = list(_mine(filing_watchdog.at_risk_stays(now), {rid}).values())
    assert filing_watchdog.notify_hosts(stays, now) == 1
    # The next runs, half an hour apart, and a day later: still one mail.
    for later in (now + timedelta(minutes=30), now + timedelta(days=1)):
        stays = list(_mine(filing_watchdog.at_risk_stays(later), {rid}).values())
        assert stays and stays[0]["mailed_at"]
        assert filing_watchdog.notify_hosts(stays, later) == 0

    rows = _outbox("deadline_at_risk", rid)
    assert len(rows) == 1
    row = rows[0]
    assert row["to_email"] == CONTACT
    assert db.query_one(
        "SELECT at_risk_mailed_at FROM reservation WHERE id = ?", (rid,)
    )["at_risk_mailed_at"]
    payload = json.loads(row["payload"])
    text = payload["text"]
    assert "Watchdog Loft" in row["subject"] and "30.09.2026 23:59" in row["subject"]
    assert "25.09.2026" in text
    assert "Guests not filed yet: 2" in text
    assert f"{config.PUBLIC_BASE_URL.rstrip('/')}/reservations/{rid}" in text
    assert host_i18n.translate("en", "mail.deadline_at_risk.manual") in text
    assert "UbyPort web application" in text
    assert GUEST_SURNAME not in text and GUEST_SURNAME not in payload["html"]


def test_no_mail_is_marked_sent_while_mail_is_off(world, monkeypatch):
    monkeypatch.setattr(mail, "mail_enabled", lambda: False)
    rid = world["add_stay"]([("DEU", "pending")])
    now = datetime(2026, 9, 30, 8, 0)
    stays = list(_mine(filing_watchdog.at_risk_stays(now), {rid}).values())
    assert filing_watchdog.notify_hosts(stays, now) == 0
    assert db.query_one(
        "SELECT at_risk_mailed_at FROM reservation WHERE id = ?", (rid,)
    )["at_risk_mailed_at"] is None


@pytest.mark.parametrize("lang", ["en", "cs"])
def test_the_host_mail_is_translated(lang):
    content = mail_notify.build_deadline_at_risk(
        property_name="Loft", arrival="25.09.2026", deadline=DEADLINE, unfiled=2,
        stay_url="https://example.invalid/reservations/1", lang=lang,
    )
    assert "mail.deadline_at_risk" not in content["text"] + content["subject"] + content["html"]
    if lang == "cs":
        assert "UbyPort" in content["text"] and "doručenku" in content["text"]


# --- operator digest ------------------------------------------------------------


def test_the_operator_digest_is_throttled_to_one_per_six_hours(world, monkeypatch):
    monkeypatch.setattr(mail, "mail_enabled", lambda: True)
    monkeypatch.setattr(config, "OPERATOR_EMAIL", "operator@example.invalid")
    rid = world["add_stay"]([("DEU", "pending")])
    start = datetime(2026, 9, 30, 8, 0)
    stays = list(_mine(filing_watchdog.at_risk_stays(start), {rid}).values())

    assert filing_watchdog.send_operator_digest(stays, start) is True
    for minutes in (30, 60, 5 * 60 + 59):
        assert filing_watchdog.send_operator_digest(stays, start + timedelta(minutes=minutes)) is False
    assert filing_watchdog.send_operator_digest(stays, start + timedelta(hours=6)) is True

    rows = _outbox("deadline_digest")
    assert len(rows) == 2
    assert {row["to_email"] for row in rows} == {"operator@example.invalid"}
    text = json.loads(rows[0]["payload"])["text"]
    assert USERNAME in text and "Watchdog Loft" in text
    assert "25.09.2026" in text and "30.09.2026 23:59" in text
    assert GUEST_SURNAME not in text and "ANNA" not in text


def test_no_digest_without_stays_at_risk(world, monkeypatch):
    monkeypatch.setattr(mail, "mail_enabled", lambda: True)
    assert filing_watchdog.send_operator_digest([], datetime(2026, 9, 30, 8, 0)) is False
    assert _outbox("deadline_digest") == []


def test_the_digest_stamp_is_utc(world, monkeypatch):
    monkeypatch.setattr(mail, "mail_enabled", lambda: True)
    rid = world["add_stay"]([("DEU", "pending")])
    now = datetime(2026, 9, 30, 8, 0)
    stays = list(_mine(filing_watchdog.at_risk_stays(now), {rid}).values())
    filing_watchdog.send_operator_digest(stays, now)
    stamp = datetime.fromisoformat(db.get_setting(filing_watchdog.DIGEST_SETTING))
    assert stamp == datetime(2026, 9, 30, 6, 0, tzinfo=timezone.utc)  # CEST is UTC+2


# --- heartbeat ------------------------------------------------------------------


@pytest.fixture
def pings(monkeypatch):
    calls = []
    monkeypatch.setattr(scheduler.requests, "get", lambda url, timeout: calls.append(url))
    monkeypatch.setattr(scheduler.reporting, "check_deadlines", lambda: 0)
    monkeypatch.setattr(scheduler.dsr, "raise_due_alerts", lambda: 0)
    return calls


def _watchdog_returns(monkeypatch, at_risk):
    monkeypatch.setattr(
        filing_watchdog, "run",
        lambda now=None: {"at_risk": at_risk, "host_mails": 0, "digest": 0},
    )


def test_the_heartbeat_reports_success_when_nothing_is_at_risk(pings, monkeypatch):
    monkeypatch.setattr(config, "HEARTBEAT_FILING_URL", "https://hc-ping.example.invalid/abc/")
    _watchdog_returns(monkeypatch, 0)
    scheduler._job_deadlines()
    assert pings == ["https://hc-ping.example.invalid/abc"]


def test_the_heartbeat_reports_fail_when_a_stay_is_at_risk(pings, monkeypatch):
    monkeypatch.setattr(config, "HEARTBEAT_FILING_URL", "https://hc-ping.example.invalid/abc")
    _watchdog_returns(monkeypatch, 2)
    scheduler._job_deadlines()
    assert pings == ["https://hc-ping.example.invalid/abc/fail"]


def test_the_heartbeat_reports_fail_when_the_deadline_watch_breaks(pings, monkeypatch):
    monkeypatch.setattr(config, "HEARTBEAT_FILING_URL", "https://hc-ping.example.invalid/abc")
    _watchdog_returns(monkeypatch, 0)

    def boom():
        raise RuntimeError("deadline watch broke")

    monkeypatch.setattr(scheduler.reporting, "check_deadlines", boom)
    monkeypatch.setattr(scheduler, "_job_failed", lambda job_id: None)
    scheduler._job_deadlines()
    assert pings == ["https://hc-ping.example.invalid/abc/fail"]


def test_no_ping_when_the_watchdog_itself_fails(pings, monkeypatch):
    monkeypatch.setattr(config, "HEARTBEAT_FILING_URL", "https://hc-ping.example.invalid/abc")

    def boom(now=None):
        raise RuntimeError("watchdog broke")

    monkeypatch.setattr(filing_watchdog, "run", boom)
    failed = []
    monkeypatch.setattr(scheduler, "_job_failed", failed.append)
    scheduler._job_deadlines()
    assert pings == []
    assert failed == ["deadlines"]


def test_nothing_is_sent_when_the_url_is_empty(pings, monkeypatch):
    monkeypatch.setattr(config, "HEARTBEAT_FILING_URL", "")
    for at_risk in (0, 3):
        _watchdog_returns(monkeypatch, at_risk)
        scheduler._job_deadlines()
    assert pings == []


def test_the_real_watchdog_runs_inside_the_deadline_job(world, pings, monkeypatch):
    """No stub for run(): the job computes the answer and pings with it."""
    monkeypatch.setattr(config, "HEARTBEAT_FILING_URL", "https://hc-ping.example.invalid/abc")
    rid = world["add_stay"]([("DEU", "pending")], arrival=date.today() - timedelta(days=10))
    scheduler._job_deadlines()
    assert pings == ["https://hc-ping.example.invalid/abc/fail"]
    assert rid in _mine(filing_watchdog.at_risk_stays(), {rid})


# --- stays with no guest on file ("unknown risk") --------------------------------


def test_a_stay_without_guests_is_unknown_risk_once_the_guests_have_arrived(world):
    rid = world["add_stay"]([])

    def unknown(now):
        return _mine(filing_watchdog.unknown_risk_stays(now), {rid})

    # Before the arrival nothing is due yet, whatever the deadline.
    assert rid not in unknown(datetime(2026, 9, 24, 23, 0))
    # Tuesday noon: 36 hours left (holiday on Monday), not yet.
    assert rid not in unknown(datetime(2026, 9, 29, 12, 0))
    found = unknown(datetime(2026, 9, 30, 8, 0))
    assert found[rid]["deadline"] == DEADLINE and found[rid]["no_guests"] is True
    assert found[rid]["overdue"] is False
    assert unknown(datetime(2026, 10, 2, 9, 0))[rid]["overdue"] is True
    # A week after the deadline an empty stay drops off.
    assert rid not in unknown(DEADLINE + timedelta(days=7, hours=1))
    # It is never a known risk: there is no guest to call reportable.
    assert rid not in _mine(filing_watchdog.at_risk_stays(datetime(2026, 9, 30, 8, 0)), {rid})


def test_an_arrival_today_counts_when_the_deadline_is_near(world):
    # An ordinary Wednesday arrival: the window opens 24 hours before its
    # deadline, by then the guests have long arrived.
    wednesday = date(2026, 10, 7)
    rid = world["add_stay"]([], arrival=wednesday)
    due = filing_watchdog.deadlines.reporting_deadline(wednesday)
    assert rid in _mine(filing_watchdog.unknown_risk_stays(due - timedelta(hours=23)), {rid})
    assert rid not in _mine(filing_watchdog.unknown_risk_stays(due - timedelta(hours=25)), {rid})


def test_a_cancelled_or_filled_stay_is_not_unknown_risk(world):
    cancelled = world["add_stay"]([], status="cancelled")
    ignored = world["add_stay"]([], status="ignored")
    czech = world["add_stay"]([("CZE", "not_required")])
    now = datetime(2026, 9, 30, 8, 0)
    assert _mine(filing_watchdog.unknown_risk_stays(now), {cancelled, ignored, czech}) == {}


def test_the_host_gets_the_no_guest_details_mail_once(world, monkeypatch):
    monkeypatch.setattr(mail, "mail_enabled", lambda: True)
    rid = world["add_stay"]([])
    now = datetime(2026, 9, 30, 8, 0)
    stays = list(_mine(filing_watchdog.unknown_risk_stays(now), {rid}).values())
    assert filing_watchdog.notify_hosts(stays, now) == 1
    later = now + timedelta(minutes=30)
    stays = list(_mine(filing_watchdog.unknown_risk_stays(later), {rid}).values())
    assert stays[0]["mailed_at"] and filing_watchdog.notify_hosts(stays, later) == 0

    rows = _outbox("deadline_at_risk", rid)
    assert len(rows) == 1
    text = json.loads(rows[0]["payload"])["text"]
    expected_subject = host_i18n.translate(
        mail_notify.HOST_MAIL_LANGUAGE, "mail.deadline_at_risk.no_guests.subject",
        property="Watchdog Loft", deadline="30.09.2026 23:59",
    )
    assert rows[0]["subject"] == expected_subject
    assert host_i18n.translate(
        mail_notify.HOST_MAIL_LANGUAGE, "mail.deadline_at_risk.no_guests.next_steps"
    ) in text

    # Guests are entered later and are not filed: the stay is now a known
    # risk, but the host was already warned for it.
    db.insert("guest", {"reservation_id": rid, "nationality": "DEU", "submit_state": "pending",
                        "created_at": db.utcnow(), "updated_at": db.utcnow()})
    stays = list(_mine(filing_watchdog.at_risk_stays(later), {rid}).values())
    assert stays and filing_watchdog.notify_hosts(stays, later) == 0
    assert len(_outbox("deadline_at_risk", rid)) == 1


@pytest.mark.parametrize("lang", ["en", "cs"])
def test_the_no_guest_details_mail_is_translated(lang):
    content = mail_notify.build_deadline_at_risk(
        property_name="Loft", arrival="25.09.2026", deadline=DEADLINE, unfiled=0,
        stay_url="https://example.invalid/reservations/1", lang=lang, no_guests=True,
    )
    blob = content["text"] + content["subject"] + content["html"]
    assert "mail.deadline_at_risk" not in blob
    # No "guests not filed: 0" line in this variant.
    label = host_i18n.translate(lang, "mail.deadline_at_risk.unfiled_label")
    assert label not in content["text"]
    if lang == "cs":
        assert "občanem České republiky" in content["text"]


def test_the_digest_lists_stays_without_guests_in_their_own_section(world, monkeypatch):
    monkeypatch.setattr(mail, "mail_enabled", lambda: True)
    monkeypatch.setattr(config, "OPERATOR_EMAIL", "operator@example.invalid")
    known = world["add_stay"]([("DEU", "pending")])
    empty = world["add_stay"]([])
    now = datetime(2026, 9, 30, 8, 0)
    stays = list(_mine(filing_watchdog.at_risk_stays(now), {known}).values())
    unknown = list(_mine(filing_watchdog.unknown_risk_stays(now), {empty}).values())
    assert filing_watchdog.send_operator_digest(stays, now, unknown=unknown) is True

    row = _outbox("deadline_digest")[0]
    lang = mail_notify.HOST_MAIL_LANGUAGE
    assert row["subject"] == host_i18n.translate(
        lang, "mail.deadline_digest.subject_unknown", count=1, unknown=1
    )
    text = json.loads(row["payload"])["text"]
    heading = host_i18n.translate(lang, "mail.deadline_digest.unknown_heading")
    assert heading in text
    known_part, unknown_part = text.split(heading)
    assert "Watchdog Loft" in known_part and "Watchdog Loft" in unknown_part
    assert GUEST_SURNAME not in text


def test_a_digest_goes_out_for_stays_without_guests_alone(world, monkeypatch):
    monkeypatch.setattr(mail, "mail_enabled", lambda: True)
    monkeypatch.setattr(config, "OPERATOR_EMAIL", "operator@example.invalid")
    empty = world["add_stay"]([])
    now = datetime(2026, 9, 30, 8, 0)
    unknown = list(_mine(filing_watchdog.unknown_risk_stays(now), {empty}).values())
    assert filing_watchdog.send_operator_digest([], now, unknown=unknown) is True
    text = json.loads(_outbox("deadline_digest")[0]["payload"])["text"]
    assert host_i18n.translate(
        mail_notify.HOST_MAIL_LANGUAGE, "mail.deadline_digest.intro"
    ) not in text


def test_stays_without_guests_never_fail_the_heartbeat(world, pings, monkeypatch):
    """Czech guests owe no report, so an empty stay is no reason to page anyone."""
    monkeypatch.setattr(config, "HEARTBEAT_FILING_URL", "https://hc-ping.example.invalid/abc")
    # Only this test's stays: the shared database may hold other tests' stays.
    monkeypatch.setattr(filing_watchdog, "at_risk_stays", lambda now=None, **_kwargs: [])
    # The latest arrival whose deadline is in the window (the real clock runs here).
    local = filing_watchdog.deadlines.local_now()
    arrival = next(
        date.today() - timedelta(days=back)
        for back in range(0, 14)
        if filing_watchdog.deadlines.reporting_deadline(date.today() - timedelta(days=back))
        - local <= filing_watchdog.AT_RISK_WINDOW
    )
    rid = world["add_stay"]([], arrival=arrival)
    result = filing_watchdog.run()
    assert result["at_risk"] == 0 and result["unknown_risk"] >= 1
    assert rid in _mine(filing_watchdog.unknown_risk_stays(), {rid})
    scheduler._job_deadlines()
    assert pings == ["https://hc-ping.example.invalid/abc"]


def test_a_broken_unknown_risk_query_does_not_silence_the_watchdog(world, monkeypatch):
    def boom(now=None):
        raise RuntimeError("unknown-risk query broke")

    monkeypatch.setattr(filing_watchdog, "unknown_risk_stays", boom)
    rid = world["add_stay"]([("DEU", "pending")], arrival=date.today() - timedelta(days=10))
    result = filing_watchdog.run()
    assert result["at_risk"] >= 1 and result["unknown_risk"] == 0
    assert rid in _mine(filing_watchdog.at_risk_stays(), {rid})


# --- guide ----------------------------------------------------------------------


def test_the_guide_explains_filing_by_hand():
    from app.guide_i18n import GUIDE_STRINGS

    en, cs = GUIDE_STRINGS["en"], GUIDE_STRINGS["cs"]
    assert en["guide.reporting.manual_filing_title"] == "If UbyHost cannot file in time"
    assert "UbyPort web application" in en["guide.reporting.manual_filing_step1"]
    assert "receipt" in en["guide.reporting.manual_filing_step3"]
    assert "duty" in en["guide.reporting.manual_filing_duty"]
    assert "webové aplikace UbyPort" in cs["guide.reporting.manual_filing_step1"]
    assert "doručenku" in cs["guide.reporting.manual_filing_step3"]
    assert "povinnost" in cs["guide.reporting.manual_filing_duty"]


def test_the_guide_page_shows_the_manual_filing_section(host):
    for lang in ("en", "cs"):
        page = host.get(f"/guide?lang={lang}").text
        assert 'id="manual-filing"' in page
        for key in ("title", "step1", "step2", "step3"):
            text = str(escape(host_i18n.translate(lang, f"guide.reporting.manual_filing_{key}")))
            assert text[:40] in page, (lang, key)


# --- a stay waiting for PR 230's one automatic resend ---------------------------

# Wednesday 30.09.2026 08:00 Prague (06:00 UTC): the deadline is tonight.
WEDNESDAY_MORNING = datetime(2026, 9, 30, 8, 0)
WEDNESDAY_MORNING_UTC = datetime(2026, 9, 30, 6, 0, tzinfo=timezone.utc)


def _unclear_batch(world, reservation_id, *, finished_ago, retried=False):
    """Put every guest of the stay on an outcome_unknown batch."""
    guest_ids = [
        row["id"]
        for row in db.query("SELECT id FROM guest WHERE reservation_id = ?", (reservation_id,))
    ]
    finished = (WEDNESDAY_MORNING_UTC - finished_ago).replace(microsecond=0).isoformat()
    submission_id = db.insert(
        "submission",
        {
            "apartment_id": world["apartment_id"],
            "created_at": finished,
            "finished_at": finished,
            "mode": "auto",
            "state": "outcome_unknown",
            "guest_ids": json.dumps(guest_ids),
            "error_text": "no answer",
            "retried_at": finished if retried else None,
        },
    )
    for guest_id in guest_ids:
        db.update("guest", guest_id, {"submission_id": submission_id})
    return submission_id


def test_a_stay_awaiting_its_one_automatic_resend_is_not_at_risk_yet(world):
    rid = world["add_stay"]([("DEU", "pending")])
    _unclear_batch(world, rid, finished_ago=timedelta(minutes=5))

    assert rid not in _mine(filing_watchdog.at_risk_stays(WEDNESDAY_MORNING), {rid})
    waiting = _mine(
        filing_watchdog.at_risk_stays(WEDNESDAY_MORNING, include_awaiting_retry=True), {rid}
    )
    assert waiting[rid]["awaiting_retry"] is True
    assert waiting[rid]["awaiting_retry_guests"] == 1


def test_the_resend_wait_is_bounded_by_the_grace(world):
    rid = world["add_stay"]([("DEU", "pending")])
    _unclear_batch(
        world, rid, finished_ago=filing_watchdog.RETRY_GRACE + timedelta(minutes=1)
    )
    stays = _mine(filing_watchdog.at_risk_stays(WEDNESDAY_MORNING), {rid})
    assert stays[rid]["awaiting_retry"] is False


def test_a_batch_already_resent_is_at_risk(world):
    """The sweep resends a batch once; after that it is the host's to settle."""
    rid = world["add_stay"]([("DEU", "pending")])
    _unclear_batch(world, rid, finished_ago=timedelta(minutes=5), retried=True)
    assert rid in _mine(filing_watchdog.at_risk_stays(WEDNESDAY_MORNING), {rid})


def test_a_missed_deadline_is_at_risk_even_while_a_resend_is_due(world):
    rid = world["add_stay"]([("DEU", "pending")])
    _unclear_batch(world, rid, finished_ago=timedelta(minutes=5))
    thursday = WEDNESDAY_MORNING + timedelta(days=1)
    # The batch finished five minutes before Wednesday morning; move it along.
    db.execute(
        "UPDATE submission SET finished_at = ? WHERE apartment_id = ?",
        (
            (WEDNESDAY_MORNING_UTC + timedelta(days=1) - timedelta(minutes=5)).isoformat(),
            world["apartment_id"],
        ),
    )
    stays = _mine(filing_watchdog.at_risk_stays(thursday), {rid})
    assert stays[rid]["overdue"] is True
    assert stays[rid]["awaiting_retry"] is False


def test_a_stay_with_one_guest_waiting_and_one_refused_is_at_risk(world):
    rid = world["add_stay"]([("DEU", "pending"), ("FRA", "error")])
    guest_ids = [
        row["id"]
        for row in db.query(
            "SELECT id FROM guest WHERE reservation_id = ? ORDER BY id", (rid,)
        )
    ]
    _unclear_batch(world, rid, finished_ago=timedelta(minutes=5))
    db.update("guest", guest_ids[1], {"submission_id": None})
    stays = _mine(filing_watchdog.at_risk_stays(WEDNESDAY_MORNING), {rid})
    assert stays[rid]["awaiting_retry"] is False
    assert stays[rid]["unfiled"] == 2


def test_the_run_neither_mails_nor_fails_while_the_resend_is_due(world, monkeypatch):
    monkeypatch.setattr(mail, "mail_enabled", lambda: True)
    monkeypatch.setattr(config, "OPERATOR_EMAIL", "operator@example.invalid")
    rid = world["add_stay"]([("DEU", "pending")])
    _unclear_batch(world, rid, finished_ago=timedelta(minutes=5))

    result = filing_watchdog.run(WEDNESDAY_MORNING)
    assert result["awaiting_retry"] >= 1
    assert not db.query_one(
        "SELECT 1 AS x FROM email_outbox WHERE kind = 'deadline_at_risk' AND reservation_id = ?",
        (rid,),
    )
    assert db.query_one(
        "SELECT at_risk_mailed_at FROM reservation WHERE id = ?", (rid,)
    )["at_risk_mailed_at"] is None

    # Once the grace is over the same stay is mailed like any other.
    later = WEDNESDAY_MORNING + filing_watchdog.RETRY_GRACE + timedelta(minutes=1)
    result = filing_watchdog.run(later)
    assert result["at_risk"] >= 1
    assert db.query_one(
        "SELECT 1 AS x FROM email_outbox WHERE kind = 'deadline_at_risk' AND reservation_id = ?",
        (rid,),
    )



def test_a_stay_held_on_an_unclear_automatic_resend_is_at_risk_after_the_grace(world):
    """WP31: the one automatic resend came back unclear too; nothing more is due."""
    rid = world["add_stay"]([("DEU", "pending")])
    original = _unclear_batch(
        world, rid, finished_ago=timedelta(minutes=15), retried=True
    )
    guest_ids = json.loads(
        db.query_one("SELECT guest_ids FROM submission WHERE id = ?", (original,))["guest_ids"]
    )
    finished = (WEDNESDAY_MORNING_UTC - timedelta(minutes=5)).replace(microsecond=0).isoformat()
    resend = db.insert(
        "submission",
        {
            "apartment_id": world["apartment_id"],
            "created_at": finished,
            "finished_at": finished,
            "mode": "auto_resend",
            "state": "outcome_unknown",
            "guest_ids": json.dumps(guest_ids),
            "error_text": "no answer",
        },
    )
    for guest_id in guest_ids:
        db.update("guest", guest_id, {"submission_id": resend})

    after_grace = WEDNESDAY_MORNING + filing_watchdog.RETRY_GRACE
    stays = _mine(filing_watchdog.at_risk_stays(after_grace), {rid})
    assert stays[rid]["awaiting_retry"] is False
    # No later resend can move the finish time on, so it stays at risk.
    much_later = WEDNESDAY_MORNING + 5 * filing_watchdog.RETRY_GRACE
    assert rid in _mine(filing_watchdog.at_risk_stays(much_later), {rid})


def test_a_manual_property_is_warned_about_eight_hours_before_the_deadline(
    world, monkeypatch,
):
    """Wednesday afternoon is inside eight hours of Wednesday night."""
    monkeypatch.setattr(mail, "mail_enabled", lambda: True)
    rid = world["add_stay"]([("DEU", "pending")])
    now = datetime(2026, 9, 30, 16, 0)

    stays = filing_watchdog.manual_deadline_stays(now)
    assert filing_watchdog.notify_manual_hosts(stays, now) == 1
    assert filing_watchdog.notify_manual_hosts(
        filing_watchdog.manual_deadline_stays(now), now
    ) == 0

    rows = _outbox("manual_deadline", rid)
    assert len(rows) == 1
    assert rows[0]["to_email"] == CONTACT
    text = json.loads(rows[0]["payload"])["text"]
    assert "Watchdog Loft" in rows[0]["subject"]
    assert "30.09.2026 23:59" in text
    assert "press Send" in text
    assert GUEST_SURNAME not in text
    assert not _outbox("deadline_at_risk", rid)


def test_the_last_day_keeps_the_existing_warning(world):
    rid = world["add_stay"]([("DEU", "pending")])
    assert rid not in _mine(
        filing_watchdog.manual_deadline_stays(datetime(2026, 9, 30, 8, 0)), {rid}
    )


def test_a_manual_property_gets_no_early_mail_days_before_the_deadline(world):
    rid = world["add_stay"]([("DEU", "pending")])
    assert rid not in _mine(
        filing_watchdog.manual_deadline_stays(datetime(2026, 9, 29, 8, 0)), {rid}
    )


def test_a_scheduled_property_gets_no_early_manual_mail(world, monkeypatch):
    monkeypatch.setattr(mail, "mail_enabled", lambda: True)
    db.update("apartment", world["apartment_id"], {"automation_mode": "scheduled"})
    rid = world["add_stay"]([("DEU", "pending")])
    now = datetime(2026, 9, 30, 16, 0)
    assert rid not in _mine(filing_watchdog.manual_deadline_stays(now), {rid})
    assert filing_watchdog.notify_manual_hosts(
        filing_watchdog.manual_deadline_stays(now), now
    ) == 0


@pytest.mark.parametrize("lang", ["en", "cs"])
def test_the_manual_deadline_mail_is_translated(lang):
    content = mail_notify.build_manual_deadline(
        property_name="Loft",
        arrival="25.09.2026",
        deadline=DEADLINE,
        unfiled=1,
        stay_url="https://example.invalid/reservations/1",
        lang=lang,
    )
    blob = content["text"] + content["subject"] + content["html"]
    assert "mail.manual_deadline" not in blob
    assert "25.09.2026" in content["text"]
    assert "30.09.2026 23:59" in content["text"]
