"""Archive redirects keep the host on the page they were on (task 0017)."""
from __future__ import annotations

from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient

from app import auth, db
from app.main import app
from app.routes.admin import _with_undo
from tests.conftest import login_as

_PREFIX = "archive-stay-0017"


def _account() -> int:
    return auth.create_account(
        f"{_PREFIX}@example.test",
        "Archive Host",
        role="host",
        username=_PREFIX,
    )


def _apartment(owner_id: int) -> int:
    entity_id = db.insert(
        "legal_entity",
        {
            "name": "Archive entity",
            "owner_user_id": owner_id,
            "created_at": db.utcnow(),
        },
    )
    return db.insert(
        "apartment",
        {
            "legal_entity_id": entity_id,
            "owner_user_id": owner_id,
            "internal_name": "Archive flat",
            "permalink_token": "archive-flat-0017",
            "permalink_pin": "1234",
            "automation_mode": "manual",
            "submit_after_hours": 24,
            "permalink_window_days": 3,
            "default_purpose": "10",
            "active": 1,
            "created_at": db.utcnow(),
        },
    )


def _reservation(apartment_id: int) -> int:
    return db.insert(
        "reservation",
        {
            "apartment_id": apartment_id,
            "source": "manual",
            "uid": "archive-stay-0017",
            "date_from": "2026-09-20",
            "date_to": "2026-09-22",
            "status": "active",
            "created_at": db.utcnow(),
            "updated_at": db.utcnow(),
        },
    )


def _clean() -> None:
    row = db.query_one("SELECT id FROM user_account WHERE username = ?", (_PREFIX,))
    if not row:
        return
    owner_id = row["id"]
    db.execute("DELETE FROM alert WHERE owner_user_id = ?", (owner_id,))
    db.execute("DELETE FROM audit WHERE owner_user_id = ?", (owner_id,))
    db.execute("DELETE FROM reservation WHERE apartment_id IN (SELECT id FROM apartment WHERE owner_user_id = ?)", (owner_id,))
    db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (owner_id,))
    db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (owner_id,))
    db.execute("DELETE FROM user_account WHERE id = ?", (owner_id,))


def _client() -> TestClient:
    client = TestClient(app)
    response = login_as(client, _PREFIX, url="/login?lang=en", follow_redirects=False)
    assert response.status_code == 303
    return client


def _expect_redirect(response) -> str:
    assert response.status_code == 303
    return response.headers["location"]


def test_stay_archive_keeps_list_range():
    db.init_db()
    _clean()
    owner = _account()
    apartment_id = _apartment(owner)
    stay_id = _reservation(apartment_id)
    client = _client()
    try:
        location = _expect_redirect(
            client.post(
                f"/reservations/{stay_id}/archive",
                data={"return_to": "/reservations?range=upcoming"},
                follow_redirects=False,
            )
        )
        assert location.startswith(f"/reservations?range=upcoming&undo_stay={stay_id}")
        assert "range=archive" not in location
    finally:
        _clean()


def test_stay_archive_keeps_dashboard():
    db.init_db()
    _clean()
    owner = _account()
    apartment_id = _apartment(owner)
    stay_id = _reservation(apartment_id)
    client = _client()
    try:
        location = _expect_redirect(
            client.post(
                f"/reservations/{stay_id}/archive",
                data={"return_to": "/"},
                follow_redirects=False,
            )
        )
        assert location.startswith(f"/?undo_stay={stay_id}")
    finally:
        _clean()


def test_stay_archive_keeps_stay_detail_page():
    db.init_db()
    _clean()
    owner = _account()
    apartment_id = _apartment(owner)
    stay_id = _reservation(apartment_id)
    client = _client()
    try:
        return_to = f"/reservations/{stay_id}?return_to=%2Freservations"
        location = _expect_redirect(
            client.post(
                f"/reservations/{stay_id}/archive",
                data={"return_to": return_to},
                follow_redirects=False,
            )
        )
        assert location.startswith(
            f"/reservations/{stay_id}?return_to=%2Freservations&undo_stay={stay_id}"
        )
    finally:
        _clean()


def test_with_undo_replaces_stale_undo_and_flash_query():
    result = _with_undo("/reservations?undo_stay=9&undo_return=x&msg=old", 5)
    qs = parse_qs(urlparse(result).query)
    assert list(qs.get("undo_stay", [])) == ["5"]
    assert "msg" not in qs


def test_property_archive_honours_return_to():
    db.init_db()
    _clean()
    owner = _account()
    apartment_id = _apartment(owner)
    client = _client()
    try:
        location = _expect_redirect(
            client.post(
                f"/apartments/{apartment_id}/archive",
                data={"return_to": f"/apartments/{apartment_id}"},
                follow_redirects=False,
            )
        )
        assert urlparse(location).path == f"/apartments/{apartment_id}"
    finally:
        _clean()


def test_property_archive_defaults_to_list():
    db.init_db()
    _clean()
    owner = _account()
    apartment_id = _apartment(owner)
    client = _client()
    try:
        location = _expect_redirect(
            client.post(
                f"/apartments/{apartment_id}/archive",
                data={},
                follow_redirects=False,
            )
        )
        assert urlparse(location).path == "/apartments"
    finally:
        _clean()


def test_evil_return_to_falls_back_to_default():
    db.init_db()
    _clean()
    owner = _account()
    apartment_id = _apartment(owner)
    client = _client()
    try:
        location = _expect_redirect(
            client.post(
                f"/apartments/{apartment_id}/archive",
                data={"return_to": "https://evil.example/"},
                follow_redirects=False,
            )
        )
        assert urlparse(location).path == "/apartments"
    finally:
        _clean()
