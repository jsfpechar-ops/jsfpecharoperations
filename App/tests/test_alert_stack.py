"""The notification stack is capped, merged and out of the header's way.

An uncapped fixed stack covered every page's top-right primary action, and two
alerts about the same stay made the host read and dismiss that stay twice.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import host_i18n, alerts, auth, db
from app.main import app

PASSWORD = "Secure-Password-123"
USERNAME = "alert-stack-host"


@pytest.fixture(autouse=True)
def _database():
    db.init_db()


def _cleanup():
    ids = [
        row["id"]
        for row in db.query("SELECT id FROM user_account WHERE username = ?", (USERNAME,))
    ]
    for user_id in ids:
        db.execute("DELETE FROM alert WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM audit WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM user_account WHERE id = ?", (user_id,))


@pytest.fixture
def host():
    db.init_db()
    _cleanup()
    auth.create_account(USERNAME, PASSWORD, "Alert Host", must_change_password=False)
    client = TestClient(app)
    response = client.post(
        "/login?lang=en",
        data={"username": USERNAME, "password": PASSWORD},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    try:
        yield client
    finally:
        _cleanup()


def _alert(kind: str, level: str, reservation_id: int, message: str):
    owner_id = db.query_one("SELECT id FROM user_account WHERE username = ?", (USERNAME,))["id"]
    alerts.raise_alert(
        level,
        kind,
        message,
        reservation_id=reservation_id,
        owner_user_id=owner_id,
        dedupe_key=f"{kind}:{reservation_id}",
    )


def _bubbles(page) -> int:
    return page.text.count("data-notification>")


def _row(alert_id: int, kind: str, level: str, reservation_id):
    return {
        "id": alert_id,
        "kind": kind,
        "level": level,
        "reservation_id": reservation_id,
        "apartment_id": None,
        "message": f"{kind} message",
        "detail": "",
        "params": None,
    }


def test_two_alerts_for_one_stay_collapse_into_the_more_severe():
    cards = alerts.present_many(
        [
            _row(1, "guest_incomplete_checkin", "warning", 7),
            _row(2, "dates_changed_resign", "critical", 7),
        ],
        "en",
    )

    assert len(cards) == 1
    assert cards[0]["id"] == 2


def test_a_less_severe_alert_never_replaces_the_one_already_shown():
    cards = alerts.present_many(
        [
            _row(1, "dates_changed_resign", "critical", 7),
            _row(2, "guest_incomplete_checkin", "warning", 7),
        ],
        "en",
    )

    assert len(cards) == 1
    assert cards[0]["id"] == 1


def test_alerts_that_belong_to_no_stay_are_left_alone():
    cards = alerts.present_many(
        [
            _row(1, "feed_incomplete", "warning", None),
            _row(2, "feed_duplicate_uid", "warning", None),
        ],
        "en",
    )

    assert [card["id"] for card in cards] == [1, 2]


def test_notification_panel_keeps_every_action_reachable(host):
    for index, reservation_id in enumerate((9001, 9002, 9003, 9004)):
        _alert("cancelled_after_report", "warning", reservation_id, f"stay {index}")

    page = host.get("/?lang=en")

    assert _bubbles(page) == 4
    assert 'data-host-alert-count>4</span>' in page.text


def test_the_stack_shows_no_summary_when_everything_fits(host):
    _alert("cancelled_after_report", "warning", 9101, "one")
    _alert("cancelled_after_report", "warning", 9102, "two")

    page = host.get("/?lang=en")

    assert _bubbles(page) == 2
    assert "more alerts" not in page.text


def test_two_alerts_on_one_stay_do_not_use_up_the_stack(host):
    _alert("dates_changed_resign", "critical", 9201, "moved")
    _alert("guest_incomplete_checkin", "warning", 9201, "waiting")
    _alert("cancelled_after_report", "warning", 9202, "cancelled")

    page = host.get("/?lang=en")

    assert _bubbles(page) == 2
    assert "more alerts" not in page.text


def test_the_summary_opens_the_overview_queue(host):
    for reservation_id in (9301, 9302, 9303):
        _alert("cancelled_after_report", "warning", reservation_id, "stay")

    page = host.get("/?lang=en")

    assert 'data-host-alert-count>3</span>' in page.text
    assert _bubbles(page) == 3


def test_the_summary_is_in_czech(host):
    for reservation_id in (9401, 9402, 9403):
        _alert("cancelled_after_report", "warning", reservation_id, "pobyt")

    page = host.get("/?lang=cs")

    assert host_i18n.translate('cs', 'a11y.notifications') in page.text
    assert 'data-host-alert-count>3</span>' in page.text


def test_notification_panel_stays_in_document_flow():
    css = (Path(__file__).resolve().parents[1] / "app" / "static" / "host.css").read_text()
    stack = css.split('.host-workspace .host-alerts .notification-stack {', 1)[1].split('}', 1)[0]
    assert 'position: static' in stack
    assert 'max-height: 360px' in stack


def test_critical_notifications_open_without_an_extra_click(host):
    _alert('dates_changed_resign', 'critical', 9501, 'Dates changed')
    page = host.get('/?lang=en')
    assert 'data-host-alerts open' in page.text
    assert 'data-notification' in page.text


def test_a_lost_raise_race_refreshes_the_alert_instead_of_raising(monkeypatch):
    """AR-23: the dedupe SELECT misses and the INSERT collides with the row.

    Two threads raising the same open alert must end with one row carrying the
    later message, not an IntegrityError escaping to the caller.
    """
    key = "ar23-race-key"
    db.execute("DELETE FROM alert WHERE dedupe_key = ?", (key,))
    alerts.raise_alert("warning", "job_failed", "old message", dedupe_key=key)

    real_query_one = alerts.db.query_one
    calls = {"n": 0}

    def racy_query_one(sql, params=()):
        calls["n"] += 1
        # The first call is the dedupe check; pretend the row was not there yet
        # so the INSERT below meets the open alert a sibling thread wrote.
        if calls["n"] == 1:
            return None
        return real_query_one(sql, params)

    monkeypatch.setattr(alerts.db, "query_one", racy_query_one)
    alerts.raise_alert("warning", "job_failed", "new message", dedupe_key=key)
    monkeypatch.setattr(alerts.db, "query_one", real_query_one)

    rows = db.query(
        "SELECT * FROM alert WHERE dedupe_key = ? AND resolved_at IS NULL", (key,)
    )
    assert len(rows) == 1
    assert rows[0]["message"] == "new message"
    db.execute("DELETE FROM alert WHERE dedupe_key = ?", (key,))


def test_a_turnstile_outage_is_shown_to_every_host(host):
    """AR-48: ``turnstile_unavailable`` is installation-wide, like ``job_failed``.

    It is raised with no owner when Cloudflare is unreachable, so a host only
    sees it if ``open_alerts`` treats the kind as belonging to the installation.
    """
    owner_id = db.query_one(
        "SELECT id FROM user_account WHERE username = ?", (USERNAME,)
    )["id"]
    key = "turnstile_unavailable:ar48"
    db.execute("DELETE FROM alert WHERE dedupe_key = ?", (key,))
    alerts.raise_alert(
        "warning",
        "turnstile_unavailable",
        "Security check unavailable",
        dedupe_key=key,
    )
    try:
        shown = alerts.open_alerts(owner_user_id=owner_id)
        assert any(row["kind"] == "turnstile_unavailable" for row in shown)
    finally:
        db.execute("DELETE FROM alert WHERE dedupe_key = ?", (key,))


def test_the_resign_card_cannot_be_dismissed(host):
    """AR-39/OD-6: this card is the filing gate, so dismiss must not clear it."""
    _alert("dates_changed_resign", "critical", 9501, "the dates moved")
    alert = db.query_one(
        "SELECT id FROM alert WHERE kind = 'dates_changed_resign' AND reservation_id = 9501"
    )

    fetched = host.post(
        f"/alerts/{alert['id']}/dismiss",
        headers={"X-Requested-With": "fetch"},
        follow_redirects=False,
    )
    assert fetched.status_code == 409
    assert db.query_one(
        "SELECT resolved_at FROM alert WHERE id = ?", (alert["id"],)
    )["resolved_at"] is None

    plain = host.post(f"/alerts/{alert['id']}/dismiss", follow_redirects=False)
    assert plain.status_code == 303
    assert db.query_one(
        "SELECT resolved_at FROM alert WHERE id = ?", (alert["id"],)
    )["resolved_at"] is None
