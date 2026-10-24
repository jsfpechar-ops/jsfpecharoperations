"""0295: the guide's QR code for the host."""
from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import auth, config, db, guide_token
from app.main import app
from tests.conftest import login_as


@pytest.fixture
def ws(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "qr.sqlite3")
    monkeypatch.setattr(auth, "staging_no_login", lambda: False)
    db.init_db()
    owner = auth.create_account("qr-owner@example.test", "QR owner", username="qr-owner", role="host")
    other = auth.create_account("qr-other@example.test", "Other owner", username="qr-other", role="host")
    now = db.utcnow()

    def home(name, user):
        return db.insert("apartment", {
            "owner_user_id": user, "internal_name": name, "active": 1, "created_at": now,
            "automation_mode": "manual",
        })
    mine, foreign = home("Vivus / 3", owner), home("Other workspace", other)
    client = TestClient(app)
    assert login_as(client, "qr-owner", url="/login?lang=en", follow_redirects=False).status_code == 303
    yield {"home": mine, "foreign": foreign, "client": client}


def test_qr_page_shows_the_code_and_the_guest_link(ws):
    response = ws["client"].get(f"/apartments/{ws['home']}/guide/qr")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    token = guide_token.current(ws["home"])
    assert token
    assert f"{config.PUBLIC_BASE_URL}/g/{token}" in response.text
    assert 'src="data:image/png;base64,' in response.text
    assert "not ready yet" in response.text  # guide not live
    assert "guest_guide." not in response.text


def test_guide_page_links_to_the_qr_page(ws):
    body = ws["client"].get(f"/apartments/{ws['home']}/guide").text
    assert f'href="/apartments/{ws["home"]}/guide/qr"' in body


def test_png_download_is_a_print_sized_image(ws):
    response = ws["client"].get(f"/apartments/{ws['home']}/guide/qr.png")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert "attachment" in response.headers["content-disposition"]
    with Image.open(io.BytesIO(response.content)) as image:
        assert min(image.size) >= 600


def test_new_link_stops_the_old_code(ws):
    client = ws["client"]
    client.get(f"/apartments/{ws['home']}/guide/qr")
    old = guide_token.current(ws["home"])
    response = client.post(f"/apartments/{ws['home']}/guide/qr/rotate", follow_redirects=False)
    assert response.status_code == 303 and "msg=" in response.headers["location"]
    new = guide_token.current(ws["home"])
    assert new and new != old
    assert client.get(f"/g/{old}").status_code == 404
    assert client.get(f"/g/{new}").status_code == 200


def test_another_hosts_property_is_out_of_reach(ws):
    client = ws["client"]
    assert client.get(f"/apartments/{ws['foreign']}/guide/qr").status_code == 404
    assert client.get(f"/apartments/{ws['foreign']}/guide/qr.png").status_code == 404
    assert client.post(f"/apartments/{ws['foreign']}/guide/qr/rotate").status_code == 404
    assert guide_token.current(ws["foreign"]) is None


def test_czech_qr_page(ws):
    body = ws["client"].get(f"/apartments/{ws['home']}/guide/qr?lang=cs").text
    assert "QR kód pro hosty" in body and "Stáhnout pro tisk" in body
