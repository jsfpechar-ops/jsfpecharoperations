from __future__ import annotations

import re
import secrets
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app import auth, cleaning, config, db
from app.main import app
from tests.conftest import login_as


@pytest.fixture
def workspace(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "cleaning.sqlite3")
    monkeypatch.setattr(cleaning, "today", lambda: date(2026, 10, 16))
    monkeypatch.setattr(auth, "staging_no_login", lambda: False)
    db.init_db()
    owner = auth.create_account("cleaner-owner@example.test", "Schedule owner", username="cleaner-owner", role="host")
    now = db.utcnow()

    def home(name, user):
        return db.insert("apartment", {
            "owner_user_id": user, "internal_name": name, "active": 1, "created_at": now,
            "automation_mode": "manual", "checkin_hour": 15, "checkout_hour": 11,
        })
    homes = [home("Riverside / 4", owner), home("Garden / 2", owner)]
    client = TestClient(app)
    assert login_as(client, "cleaner-owner", url="/login?lang=en", follow_redirects=False).status_code == 303
    yield {"owner": owner, "homes": homes, "home": homes[0], "client": client}


def stay(home, start="2026-10-17", end="2026-10-20", **extra):
    return db.insert("reservation", {
        "apartment_id": home, "uid": secrets.token_hex(16),
        "date_from": start, "date_to": end, "status": "active", "source": "manual",
        "created_at": db.utcnow(), "updated_at": db.utcnow(), **extra,
    })


def test_header_has_one_primary_share_button_in_czech(workspace):
    response = workspace["client"].get("/cleaning?lang=cs")
    assert response.status_code == 200
    assert response.text.count("ui-btn-primary") == 1
    tag = re.search(r"<a\b[^>]*ui-btn-primary[^>]*>.*?</a>", response.text, re.S)
    assert tag is not None
    assert 'href="/cleaning/shares"' in tag.group(0)
    assert "Sdílet rozpis s uklízečkou" in tag.group(0)


def test_header_has_no_add_stay_link(workspace):
    response = workspace["client"].get("/cleaning?lang=cs")
    assert "/reservations?new=1" not in response.text


def test_host_page_shows_tables_before_calendar(workspace):
    stay(workspace["home"])
    response = workspace["client"].get("/cleaning?lang=en")
    assert response.status_code == 200
    assert 'class="cleaning-skip"' not in response.text
    assert response.text.index("cleaning-section") < response.text.index('id="calendar"')


def test_shared_view_shows_calendar_before_list_with_skip_link(workspace):
    client = workspace["client"]
    created = client.post("/cleaning/shares", data={"properties": [workspace["home"]]})
    assert created.status_code == 200
    token = re.search(r"/cleaning/shared/([\w-]+)", created.text).group(1)
    shared = TestClient(app).get(f"/cleaning/shared/{token}")
    assert shared.status_code == 200
    assert 'class="cleaning-skip"' in shared.text
    assert shared.text.index('id="calendar"') < shared.text.index('id="cleaning-list"')
