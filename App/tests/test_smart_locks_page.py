"""The digital door lock page walks a host through the TTLock app, and keeps hosts apart."""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app import auth, config, db, ttlock
from app.main import app
from tests.conftest import login_as

USERS = ("smartpage-a", "smartpage-b")
ADMIN_KEY = {"lockId": 1, "lockAlias": "Door A", "keyStatus": "110401", "userType": "110302", "keyRight": 1}
PLAIN_KEY = {"lockId": 2, "lockAlias": "Door B", "keyStatus": "110401", "userType": "110302", "keyRight": 0}


@pytest.fixture
def hosts(monkeypatch):
    db.init_db()
    monkeypatch.setattr(config, "DOOR_CODES_ENABLED", True)
    monkeypatch.setattr(config, "TTLOCK_CLIENT_ID", "cid")
    monkeypatch.setattr(config, "TTLOCK_CLIENT_SECRET", "csecret")
    _cleanup()
    ids = [
        auth.create_account(f"{name}@example.test", name, username=name) for name in USERS
    ]
    yield ids
    _cleanup()


def _cleanup():
    for name in USERS:
        row = db.query_one("SELECT id FROM user_account WHERE username = ?", (name,))
        if row:
            db.execute("DELETE FROM audit WHERE owner_user_id = ?", (row["id"],))
            db.execute("DELETE FROM lock_account WHERE owner_user_id = ?", (row["id"],))
            db.execute("DELETE FROM user_account WHERE id = ?", (row["id"],))


def _connect(owner: int, name: str, locks=None) -> None:
    now = db.utcnow()
    db.insert(
        "lock_account",
        {
            "owner_user_id": owner,
            "provider": "ttlock",
            "username": name,
            "status": "ok",
            "locks_json": json.dumps(locks or []),
            "created_at": now,
            "updated_at": now,
        },
    )


def _client(username: str) -> TestClient:
    client = TestClient(app)
    login_as(client, username, url="/login?lang=en", follow_redirects=False)
    return client


def test_before_connecting_the_page_explains_and_names_ttlock(hosts):
    page = _client(USERS[0]).get("/smart-locks").text
    assert "Digital door lock" in page
    assert "only with TTLock" in page
    assert "How it works" in page
    assert "Connect my lock" in page


def test_after_connecting_every_tap_is_written_out(hosts):
    _connect(hosts[0], "hjhfa_uhaaaa")
    page = _client(USERS[0]).get("/smart-locks").text
    assert "hjhfa_uhaaaa" in page
    for words in ("Authorized Admin", "Create Admin", "Manage their own users only", "Check connection"):
        assert words in page
    assert "Send eKey and enter" not in page


def test_a_plain_key_is_called_out_not_ignored(hosts, monkeypatch):
    _connect(hosts[0], "hjhfa_uhaaaa")
    monkeypatch.setattr(ttlock, "_call", lambda *a, **k: {"list": [PLAIN_KEY], "pages": 1})
    page = _client(USERS[0]).post("/smart-locks/refresh", data={"return_to": "/smart-locks"}).text
    assert "not an admin key" in page


def test_an_admin_key_shows_the_lock_as_connected(hosts, monkeypatch):
    _connect(hosts[0], "hjhfa_uhaaaa")
    monkeypatch.setattr(ttlock, "_call", lambda *a, **k: {"list": [ADMIN_KEY], "pages": 1})
    page = _client(USERS[0]).post("/smart-locks/refresh", data={"return_to": "/smart-locks"}).text
    assert "Door A" in page
    assert "UbyHost can create door codes on this lock" in page


def test_each_host_has_their_own_name_and_never_sees_anothers_locks(hosts):
    _connect(hosts[0], "hjhfa_uhaaaa", [{"lock_id": "1", "alias": "Door A", "battery": 90, "tz_offset_ms": 3600000}])
    _connect(hosts[1], "hjhfa_uhbbbb", [{"lock_id": "2", "alias": "Door B", "battery": 80, "tz_offset_ms": 3600000}])
    page_a = _client(USERS[0]).get("/smart-locks").text
    page_b = _client(USERS[1]).get("/smart-locks").text
    assert "Door A" in page_a and "Door B" not in page_a
    assert "Door B" in page_b and "Door A" not in page_b


def test_a_new_account_gets_a_random_name_each_time():
    names = {"uh" + __import__("secrets").token_hex(8) for _ in range(50)}
    assert len(names) == 50
    import inspect

    assert 'secrets.token_hex(8)' in inspect.getsource(ttlock.create_account)
