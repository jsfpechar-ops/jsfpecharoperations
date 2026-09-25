"""The notification stack is capped, merged and out of the header's way.

An uncapped fixed stack covered every page's top-right primary action, and two
alerts about the same stay made the host read and dismiss that stay twice.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import alerts, auth, db
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


def test_the_stack_stops_at_two_and_counts_the_rest(host):
    for index, reservation_id in enumerate((9001, 9002, 9003, 9004)):
        _alert("cancelled_after_report", "warning", reservation_id, f"stay {index}")

    page = host.get("/?lang=en")

    assert _bubbles(page) == 2
    assert "2 more alerts — see Overview" in page.text


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

    assert 'class="notification-more" href="/#needs-action"' in page.text


def test_the_summary_is_in_czech(host):
    for reservation_id in (9401, 9402, 9403):
        _alert("cancelled_after_report", "warning", reservation_id, "pobyt")

    page = host.get("/?lang=cs")

    assert "Další upozornění: 1 — zobrazit v Přehledu" in page.text


def test_the_stack_keeps_clear_of_the_page_header():
    css = (Path(__file__).resolve().parents[1] / "app" / "static" / "app.css").read_text(
        encoding="utf-8"
    )
    stack = css.split(".notification-stack {", 1)[1].split("}", 1)[0]

    assert "bottom: 20px" in stack
    assert "top:" not in stack, "the stack is back in the header zone"


def test_the_stack_rides_under_the_app_bar_on_a_phone():
    css = (Path(__file__).resolve().parents[1] / "app" / "static" / "app.css").read_text(
        encoding="utf-8"
    )

    assert ".notification-stack {\n    top: 59px;" in css
