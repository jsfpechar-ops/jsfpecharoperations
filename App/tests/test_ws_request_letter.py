"""UbyPort web-service credential request letter on the property form."""
from __future__ import annotations

import secrets

import pytest
from fastapi.testclient import TestClient

from app import auth, db
from app.main import app
from tests.conftest import login_as

SUMMARY_EN = "I don&#39;t have web-service credentials yet"
IDUB = "20998877665544"
ENTITY_NAME = "Pension U Karla"


@pytest.fixture()
def letter_world():
    db.init_db()
    owner_a = "ws-letter-owner-a"
    owner_b = "ws-letter-owner-b"
    users = {}
    for username in (owner_a, owner_b):
        row = db.query_one("SELECT id FROM user_account WHERE username = ?", (username,))
        if row:
            users[username] = row["id"]
        else:
            users[username] = auth.create_account(
                f"{username}@example.test",
                username,
                role="host",
                username=username,
            )
    entity_id = db.insert(
        "legal_entity",
        {"name": ENTITY_NAME, "owner_user_id": users[owner_a], "created_at": db.utcnow()},
    )
    apartment_id = db.insert(
        "apartment",
        {
            "legal_entity_id": entity_id,
            "owner_user_id": users[owner_a],
            "internal_name": "Letter flat",
            "permalink_token": f"wsletter{secrets.token_hex(4)}",
            "permalink_pin": "123456",
            "automation_mode": "manual",
            "default_purpose": "10",
            "uby_idub": IDUB,
            "active": 1,
            "created_at": db.utcnow(),
        },
    )
    other_apartment_id = db.insert(
        "apartment",
        {
            "owner_user_id": users[owner_b],
            "internal_name": "Other flat",
            "permalink_token": f"wsletteroth{secrets.token_hex(4)}",
            "permalink_pin": "654321",
            "automation_mode": "manual",
            "default_purpose": "10",
            "active": 1,
            "created_at": db.utcnow(),
        },
    )
    client_a = TestClient(app)
    client_b = TestClient(app)
    assert login_as(client_a, owner_a, url="/login?lang=en", follow_redirects=False).status_code == 303
    assert login_as(client_b, owner_b, url="/login?lang=en", follow_redirects=False).status_code == 303
    yield {
        "client_a": client_a,
        "client_b": client_b,
        "apartment_id": apartment_id,
        "other_apartment_id": other_apartment_id,
        "users": users,
        "entity_id": entity_id,
    }
    db.execute("DELETE FROM apartment WHERE id IN (?, ?)", (apartment_id, other_apartment_id))
    db.execute("DELETE FROM legal_entity WHERE id = ?", (entity_id,))
    for user_id in users.values():
        db.execute("DELETE FROM audit WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM alert WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM user_account WHERE id = ?", (user_id,))


def test_download_contains_idub_and_operator(letter_world):
    client = letter_world["client_a"]
    apartment_id = letter_world["apartment_id"]
    response = client.get(f"/apartments/{apartment_id}/ws-request.txt")
    assert response.status_code == 200
    assert response.headers.get("content-type", "").startswith("text/plain")
    assert 'filename="ubyport-ws-zadost.txt"' in response.headers.get("content-disposition", "")
    text = response.content.decode("utf-8")
    assert IDUB in text
    assert ENTITY_NAME in text
    assert "robotické zasílání" in text
    assert "ybndqw9" in text
    assert "Olšanská 2" in text
    assert "130 51 Praha 3" in text


def test_download_uses_idub_placeholder_when_empty(letter_world):
    client = letter_world["client_a"]
    apartment_id = letter_world["apartment_id"]
    db.update("apartment", apartment_id, {"uby_idub": ""})
    response = client.get(f"/apartments/{apartment_id}/ws-request.txt")
    assert response.status_code == 200
    text = response.content.decode("utf-8")
    assert "[doplňte IDUB]" in text
    assert IDUB not in text
    db.update("apartment", apartment_id, {"uby_idub": IDUB})


def test_download_forbidden_for_other_owner(letter_world):
    client = letter_world["client_b"]
    apartment_id = letter_world["apartment_id"]
    assert client.get(f"/apartments/{apartment_id}/ws-request.txt").status_code == 404


def test_form_block_open_without_ws_user(letter_world):
    client = letter_world["client_a"]
    apartment_id = letter_world["apartment_id"]
    db.update("apartment", apartment_id, {"uby_ws_user": ""})
    page = client.get(f"/apartments/{apartment_id}?lang=en")
    assert page.status_code == 200
    assert "ws-request-letter" in page.text
    assert SUMMARY_EN in page.text
    # 0094: a visible sub-section (no fold) while the login is still missing.
    assert '<section class="property-subsection" id="ws-request-letter">' in page.text
    assert 'id="ws-request-body"' in page.text
    assert f"/apartments/{apartment_id}/ws-request.txt" in page.text
    assert "ybndqw9" in page.text
    assert "Olšanská 2" in page.text


def test_form_block_closed_when_ws_user_set(letter_world):
    client = letter_world["client_a"]
    apartment_id = letter_world["apartment_id"]
    db.update("apartment", apartment_id, {"uby_ws_user": "UBY-WS_demo12"})
    page = client.get(f"/apartments/{apartment_id}?lang=en")
    assert page.status_code == 200
    assert "ws-request-letter" in page.text, "ws-request block missing from apartment form"
    assert SUMMARY_EN in page.text
    # 0094: with a saved login only the download link stays; nothing is folded.
    block = page.text.split('id="ws-request-letter"', 1)[1].split("</section>", 1)[0]
    assert "<details" not in block
    assert 'id="ws-request-body"' not in block
    assert f"/apartments/{apartment_id}/ws-request.txt" in block
    db.update("apartment", apartment_id, {"uby_ws_user": ""})
