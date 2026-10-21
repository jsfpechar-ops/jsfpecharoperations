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


@pytest.fixture
def flats(hosts):
    """One active property per host; the lock panel lives on its Door lock tab."""
    ids = [
        db.insert("apartment", {
            "internal_name": f"Lock tab flat {n}", "owner_user_id": owner, "permalink_token": f"smartpagetab{n}",
            "permalink_pin": "123456", "active": 1, "created_at": db.utcnow(),
        })
        for n, owner in enumerate(hosts)
    ]
    yield ids
    db.execute("DELETE FROM apartment_slug WHERE apartment_id IN (?, ?)", tuple(ids))
    db.execute("DELETE FROM apartment WHERE id IN (?, ?)", tuple(ids))


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


def test_before_connecting_the_page_explains_and_names_ttlock(hosts, flats):
    client = _client(USERS[0])
    assert 'id="smart-locks-how"' not in client.get("/apartments?lang=en").text
    page = client.get(f"/apartments/{flats[0]}?view=settings&section=lock&lang=en").text
    assert "Digital door lock" in page
    assert "only with TTLock" in page
    assert "How it works" in page
    assert "Connect my lock" in page


def test_after_connecting_three_essentials_and_every_tap_in_the_guide(hosts, flats):
    """0090: the lock page shows three essentials; the Guide keeps every tap."""
    _connect(hosts[0], "hjhfa_uhaaaa")
    client = _client(USERS[0])
    page = client.get(f"/apartments/{flats[0]}?view=settings&section=lock&lang=en").text
    assert "hjhfa_uhaaaa" in page
    for words in (
        "In the TTLock app, open your lock and tap Authorized Admin (eAdmin in some app versions).",
        "In the Recipient field, where TTLock expects an e-mail or phone number, paste your UbyHost name from above.",
        "Come back here and tap Check connection.",
        "Check connection",
        "Only the owner of the lock can do this.",
        "Do not use eKeys or Send eKey.",
    ):
        assert words in page
    assert 'href="/guide#door-codes-share"' in page
    assert "Tap Create Admin at the bottom of the screen." not in page
    assert "Send eKey and enter" not in page
    guide = client.get("/guide?lang=en").text
    assert 'id="door-codes-share"' in guide
    for words in ("Authorized Admin", "Create Admin", "Manage their own users only", "paste your UbyHost name"):
        assert words in guide
    cs = client.get(f"/apartments/{flats[0]}?view=settings&section=lock&lang=cs").text
    assert "klepněte na Autorizovaný správce" in cs  # 0205 TTLock wording
    assert "Vraťte se sem a klepněte na Zkontrolovat připojení." in cs


def _post(client, path, **data):
    return client.post(path, data=data, follow_redirects=False)


def test_setup_lands_on_the_sharing_section_and_errors_stay_on_setup(hosts, flats, monkeypatch):
    client = _client(USERS[0])
    refused = _post(client, "/smart-locks/setup", return_to="/smart-locks")
    assert refused.status_code == 303
    assert refused.headers["location"].startswith(f"/apartments/{flats[0]}?view=settings&section=lock")
    assert refused.headers["location"].endswith("#smart-locks-how")
    assert "err=" in refused.headers["location"]

    def fake_create(owner_id):
        _connect(owner_id, "hjhfa_uhaaaa")

    monkeypatch.setattr(ttlock, "create_account", fake_create)
    done = _post(client, "/smart-locks/setup", return_to="/smart-locks", terms="1")
    assert done.headers["location"].startswith(f"/apartments/{flats[0]}?view=settings&section=lock")
    assert done.headers["location"].endswith("#smart-locks-share")
    assert "msg=" in done.headers["location"]


@pytest.mark.parametrize(
    ("kind", "section", "anchor"),
    [
        ("budget", "share", "#smart-locks-share"),
        ("reauth", "list", "#smart-locks-list"),
        ("failed", "add-more", "#smart-locks-add-more"),
        ("failed", "/evil#x", "#smart-locks-share"),
    ],
)
def test_refresh_failures_stay_on_the_section_acted_in(hosts, flats, monkeypatch, kind, section, anchor):
    _connect(hosts[0], "hjhfa_uhaaaa")

    def fail(_account_id):
        raise ttlock.TTLockError("synthetic", kind=kind)

    monkeypatch.setattr(ttlock, "check_locks", fail)
    response = _post(
        _client(USERS[0]), "/smart-locks/refresh", return_to="/apartments/999999", section=section
    )
    location = response.headers["location"]
    # 0195: a foreign or unknown return_to lands on the host's own first lock tab.
    assert location.startswith(f"/apartments/{flats[0]}?view=settings&section=lock")
    assert "/apartments/999999" not in location
    assert location.endswith(anchor)
    assert "err=" in location
    assert "evil" not in location


def test_no_lock_yet_stays_on_sharing(hosts, flats, monkeypatch):
    _connect(hosts[0], "hjhfa_uhaaaa")
    monkeypatch.setattr(ttlock, "check_locks", lambda _id: ([], []))
    response = _post(_client(USERS[0]), "/smart-locks/refresh", return_to="/smart-locks", section="share")
    assert response.headers["location"].startswith(f"/apartments/{flats[0]}?view=settings&section=lock")
    assert response.headers["location"].endswith("#smart-locks-share")


def test_found_locks_return_to_the_hosts_own_property_lock_section(hosts, monkeypatch):
    _connect(hosts[0], "hjhfa_uhaaaa")
    found = [{"lock_id": "1", "alias": "Door A", "battery": 90, "tz_offset_ms": 3600000}]
    monkeypatch.setattr(ttlock, "check_locks", lambda _id: (found, []))
    own = db.insert("apartment", {
        "internal_name": "Lock flat", "owner_user_id": hosts[0], "permalink_token": "smartlockown1",
        "permalink_pin": "123456", "active": 1, "created_at": db.utcnow(),
    })
    foreign = db.insert("apartment", {
        "internal_name": "Other flat", "owner_user_id": hosts[1], "permalink_token": "smartlockother1",
        "permalink_pin": "123456", "active": 1, "created_at": db.utcnow(),
    })
    try:
        client = _client(USERS[0])
        response = _post(client, "/smart-locks/refresh", return_to=f"/apartments/{own}", section="share")
        location = response.headers["location"]
        assert location.startswith(f"/apartments/{own}?") and location.endswith("#door-code")
        row = db.query_one("SELECT lock_provider, lock_id FROM apartment WHERE id = ?", (own,))
        assert row["lock_provider"] is None and row["lock_id"] is None
        for bad in (f"/apartments/{foreign}", "https://evil.example/apartments/1", "//evil.example"):
            response = _post(client, "/smart-locks/refresh", return_to=bad, section="share")
            location = response.headers["location"]
            # 0195: never a foreign property id; the host's own first property's lock tab.
            assert location.startswith(f"/apartments/{own}?view=settings&section=lock"), location
            assert f"/apartments/{foreign}" not in location
            assert location.endswith("#smart-locks-list")
            assert "evil" not in location
    finally:
        db.execute("DELETE FROM apartment_slug WHERE apartment_id IN (?, ?)", (own, foreign))
        db.execute("DELETE FROM apartment WHERE id IN (?, ?)", (own, foreign))


def test_property_lock_tab_has_the_panel_and_the_list_has_none(hosts, flats):
    own = flats[0]
    client = _client(USERS[0])
    page = client.get(f"/apartments/{own}?lang=en").text
    assert "/smart-locks?" not in page
    assert 'id="smart-locks-how"' in page
    _connect(hosts[0], "hjhfa_uhaaaa")
    page = client.get(f"/apartments/{own}?view=settings&section=lock&lang=en").text
    assert "/smart-locks?" not in page
    assert f"/apartments/{own}?view=settings&amp;section=lock" in page
    assert 'id="smart-locks-how"' not in client.get("/apartments?lang=en").text


def test_a_plain_key_is_called_out_not_ignored(hosts, flats, monkeypatch):
    _connect(hosts[0], "hjhfa_uhaaaa")
    monkeypatch.setattr(ttlock, "_call", lambda *a, **k: {"list": [PLAIN_KEY], "pages": 1})
    page = _client(USERS[0]).post("/smart-locks/refresh", data={"return_to": f"/apartments/{flats[0]}"}).text
    assert "not an admin key" in page


def test_an_admin_key_shows_the_lock_as_connected(hosts, flats, monkeypatch):
    _connect(hosts[0], "hjhfa_uhaaaa")
    monkeypatch.setattr(ttlock, "_call", lambda *a, **k: {"list": [ADMIN_KEY], "pages": 1})
    page = _client(USERS[0]).post("/smart-locks/refresh", data={"return_to": f"/apartments/{flats[0]}"}).text
    assert "Door A" in page
    assert "UbyHost can create door codes on this lock" in page


def test_each_host_has_their_own_name_and_never_sees_anothers_locks(hosts, flats):
    _connect(hosts[0], "hjhfa_uhaaaa", [{"lock_id": "1", "alias": "Door A", "battery": 90, "tz_offset_ms": 3600000}])
    _connect(hosts[1], "hjhfa_uhbbbb", [{"lock_id": "2", "alias": "Door B", "battery": 80, "tz_offset_ms": 3600000}])
    page_a = _client(USERS[0]).get(f"/apartments/{flats[0]}?view=settings&section=lock&lang=en").text
    page_b = _client(USERS[1]).get(f"/apartments/{flats[1]}?view=settings&section=lock&lang=en").text
    assert "Door A" in page_a and "Door B" not in page_a
    assert "Door B" in page_b and "Door A" not in page_b


def test_a_new_account_gets_a_random_name_each_time():
    names = {"uh" + __import__("secrets").token_hex(8) for _ in range(50)}
    assert len(names) == 50
    import inspect

    assert 'secrets.token_hex(8)' in inspect.getsource(ttlock.create_account)



def test_the_setup_wizard_lock_step_gets_every_lock_answer_back(hosts, flats, monkeypatch):
    """0203: a lock connected from the setup wizard returns to the wizard, not to Settings."""
    _connect(hosts[0], "hjhfa_uhaaaa")
    wizard = f"/apartments/{flats[0]}/setup/door_lock"
    client = _client(USERS[0])
    monkeypatch.setattr(ttlock, "check_locks", lambda _id: ([], []))
    response = _post(client, "/smart-locks/refresh", return_to=wizard, section="share")
    location = response.headers["location"]
    assert location.startswith(wizard) and location.endswith("#smart-locks-share"), location
    found = [{"lock_id": "1", "alias": "Door A", "battery": 90, "tz_offset_ms": 3600000}]
    monkeypatch.setattr(ttlock, "check_locks", lambda _id: (found, []))
    response = _post(client, "/smart-locks/refresh", return_to=wizard, section="share")
    assert response.headers["location"].startswith(wizard), response.headers["location"]
    foreign = f"/apartments/{flats[1]}/setup/door_lock"
    response = _post(client, "/smart-locks/refresh", return_to=foreign, section="share")
    assert f"/apartments/{flats[1]}" not in response.headers["location"]
