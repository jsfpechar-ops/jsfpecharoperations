"""Log out ends the account's sessions on every device, not only this browser."""
from __future__ import annotations

import secrets

from fastapi.testclient import TestClient

from app import auth, db
from app.main import app

PASSWORD = f"Logout-everywhere-{secrets.token_urlsafe(12)}-7"


def _signed_in(username: str) -> TestClient:
    client = TestClient(app)
    response = client.post(
        "/login?lang=en", data={"username": username, "password": PASSWORD},
        follow_redirects=False,
    )
    assert response.status_code == 303
    return client


def test_logging_out_on_one_device_signs_out_the_other():
    db.init_db()
    username = f"logout-{secrets.token_hex(4)}"
    auth.create_account(username, PASSWORD, "Logout Host", role="host", must_change_password=False)
    laptop, phone = _signed_in(username), _signed_in(username)
    copied = dict(phone.cookies)
    assert phone.get("/reservations", follow_redirects=False).status_code == 200

    assert laptop.post("/logout", follow_redirects=False).status_code == 303

    assert phone.get("/reservations", follow_redirects=False).status_code in (302, 303)
    replay = TestClient(app, cookies=copied)
    assert replay.get("/reservations", follow_redirects=False).status_code in (302, 303)
