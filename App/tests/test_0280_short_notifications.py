"""0280: notifications are one short line plus the link to the fix."""
from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from app import alerts, auth, db, host_i18n
from app.main import app
from tests.conftest import login_as

USERNAME = "short-notify-host"


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
    auth.create_account(f"{USERNAME}@example.test", "Short Notify Host", username=USERNAME)
    client = TestClient(app)
    response = login_as(client, USERNAME, url="/login?lang=en", follow_redirects=False)
    assert response.status_code == 303, response.text
    try:
        yield client
    finally:
        _cleanup()


def _owner_id():
    return db.query_one("SELECT id FROM user_account WHERE username = ?", (USERNAME,))["id"]


def _alert(kind: str, level: str, reservation_id: int, message: str):
    alerts.raise_alert(
        level,
        kind,
        message,
        reservation_id=reservation_id,
        owner_user_id=_owner_id(),
        dedupe_key=f"{kind}:{reservation_id}",
    )


def _bubbles(page) -> int:
    return page.text.count("data-notification>")


def test_setup_alert_never_lists_fields(host):
    alerts.raise_alert(
        "warning",
        "apartment_setup",
        "Apartment setup is incomplete",
        detail="uby_idub: IDUB is required",
        dedupe_key="apartment_setup:0280",
        owner_user_id=_owner_id(),
    )

    for path in ("/?lang=en", "/reservations?lang=en"):
        page = host.get(path)
        assert page.status_code == 200, path
        assert "uby_idub" not in page.text, path


def test_titles_and_push_bodies_are_short():
    pattern = re.compile(r"^(notification\.[a-z_]+\.title|push\.msg\.)")
    checked = 0
    for lang in ("en", "cs", "vi"):
        for key, value in host_i18n.STRINGS[lang].items():
            if not pattern.search(key):
                continue
            checked += 1
            text = re.sub(r"%\([a-z_]+\)s|%%", "", value)
            assert len(text) <= 60, f"{lang} {key}: {len(text)} characters"
    assert checked > 0


def test_reason_only_for_stay_kinds():
    alert = {
        "id": 1,
        "kind": "mail_failed",
        "level": "warning",
        "reservation_id": None,
        "apartment_id": None,
        "message": "Mail failed",
        "detail": "x",
        "params": None,
    }
    assert alerts.present(alert, "en")["display_reason"] == ""


def test_red_alert_keeps_its_own_line(host):
    _alert("dates_changed_resign", "critical", 9701, "moved")
    for reservation_id in (9702, 9703, 9704):
        _alert("cancelled_after_report", "warning", reservation_id, "stay")

    page = host.get("/reservations?lang=en")

    assert _bubbles(page) == 1
    assert "3 more alerts" in page.text
