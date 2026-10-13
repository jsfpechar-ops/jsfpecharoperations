"""0097: the web-service request-letter generator is replaced by one line of fine print.

The property Police reporting section links the official Foreign Police page
instead of drafting a letter; the old download URL lands on that section.
"""
from __future__ import annotations

import secrets

import pytest
from fastapi.testclient import TestClient

from app import auth, db
from app.host_i18n import STRINGS
from app.main import app
from tests.conftest import login_as

SUMMARY_EN = "I don&#39;t have web-service credentials yet"
POLICE_PAGE = (
    "https://policie.gov.cz/reditelstvi-sluzby-cizinecke-policie/"
    "jake-jsou-moznosti-zasilani-dat-aplikaci-ubyport"
)
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


def test_old_download_url_lands_on_police_reporting(letter_world):
    client = letter_world["client_a"]
    apartment_id = letter_world["apartment_id"]
    response = client.get(f"/apartments/{apartment_id}/ws-request.txt", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == (
        f"/apartments/{apartment_id}?view=settings&section=reporting#ubyport"
    )


def test_old_download_url_is_not_found_for_other_owner(letter_world):
    client = letter_world["client_b"]
    apartment_id = letter_world["apartment_id"]
    response = client.get(f"/apartments/{apartment_id}/ws-request.txt", follow_redirects=False)
    assert response.status_code == 404


@pytest.mark.parametrize("ws_user", ["", "UBY-WS_demo12"])
@pytest.mark.parametrize("lang", ["en", "cs"])
def test_section_has_one_fine_print_line_and_no_letter(letter_world, ws_user, lang):
    client = letter_world["client_a"]
    apartment_id = letter_world["apartment_id"]
    db.update("apartment", apartment_id, {"uby_ws_user": ws_user})
    page = client.get(f"/apartments/{apartment_id}?lang={lang}")
    assert page.status_code == 200
    text = page.text
    section = text.split('id="ubyport"', 1)[1].split("</section>", 1)[0]
    # The generator is gone in every state: no summary, recipient, body or download.
    assert SUMMARY_EN not in text
    for gone in ('id="ws-request-body"', "ws-request.txt", "ybndqw9", "Olšanská 2", "robotické zasílání"):
        assert gone not in text, gone
    # One fine-print line under the credential fields, linking the police page.
    assert section.count(POLICE_PAGE) == 1
    line = section.split('id="ws-request-letter"', 1)[1].split("</p>", 1)[0]
    assert POLICE_PAGE in line and 'target="_blank"' in line and 'rel="noopener"' in line
    assert STRINGS[lang]["apartment.form.ubyport.no_credentials"] in line
    # It sits after the password field and before the abbreviation.
    assert section.index('id="uby_ws_password"') < section.index('id="ws-request-letter"') < section.index('id="uby_mark"')
    db.update("apartment", apartment_id, {"uby_ws_user": ""})


def test_letter_strings_are_gone():
    for lang in ("en", "cs"):
        assert not [key for key in STRINGS[lang] if ".ws_request." in key]
