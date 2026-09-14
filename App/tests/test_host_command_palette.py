"""Command palette and inline stay edits added in the host UX overhaul.

Both endpoints are JSON-capable and keyed by numeric stay id, so they need the
same workspace boundary as every other admin route.
"""
from __future__ import annotations

from datetime import date, timedelta

from fastapi.testclient import TestClient

from app import db, host_i18n
from app.main import app
from tests.test_accounts import PASSWORD, _account, _apartment, _clean_accounts, _login


def _reservation(apartment_id: int, uid: str) -> int:
    today = date.today()
    return db.insert(
        "reservation",
        {
            "apartment_id": apartment_id,
            "source": "manual",
            "uid": uid,
            "summary": f"Stay {uid}",
            "date_from": today.isoformat(),
            "date_to": (today + timedelta(days=2)).isoformat(),
            "status": "active",
            "created_at": db.utcnow(),
            "updated_at": db.utcnow(),
        },
    )


def test_command_palette_requires_a_session():
    db.init_db()
    _clean_accounts()
    _account("boundary-palette")
    try:
        response = TestClient(app).get("/api/command-palette")
        assert response.status_code == 401
        assert response.json() == {"items": []}
    finally:
        _clean_accounts()


def test_command_palette_lists_only_the_signed_in_workspace():
    db.init_db()
    _clean_accounts()
    first_id = _account("boundary-palette-first")
    second_id = _account("boundary-palette-second")
    first_flat = _apartment(first_id, "Palette One", "paletteone")
    second_flat = _apartment(second_id, "Palette Two", "palettetwo")
    first_stay = _reservation(first_flat, "palette-stay-one")
    _reservation(second_flat, "palette-stay-two")
    try:
        client = _login("boundary-palette-first")
        payload = client.get("/api/command-palette").json()
        labels = {item["label"] for item in payload["items"]}
        urls = {item.get("url") for item in payload["items"]}

        assert "Palette One" in labels
        assert "Palette Two" not in labels
        assert f"/reservations/{first_stay}" in urls
        assert all(
            f"/apartments/{second_flat}" not in (item.get("url") or "")
            for item in payload["items"]
        )
        assert any(item.get("copy", "").endswith("/l/paletteone") for item in payload["items"])
    finally:
        _clean_accounts()


def test_command_palette_uses_the_host_language():
    db.init_db()
    _clean_accounts()
    owner = _account("boundary-palette-lang")
    _apartment(owner, "Lang flat", "palettelang")
    try:
        client = _login("boundary-palette-lang")
        client.cookies.set(host_i18n.LANG_COOKIE, "cs")
        labels = {item["label"] for item in client.get("/api/command-palette").json()["items"]}
        assert host_i18n.translate("cs", "nav.overview") in labels
        assert host_i18n.translate("en", "nav.overview") not in labels
    finally:
        _clean_accounts()


def test_quick_edit_rejects_out_of_range_party_size():
    db.init_db()
    _clean_accounts()
    owner = _account("boundary-quickedit-host")
    apartment = _apartment(owner, "Quick flat", "quickedit")
    stay = _reservation(apartment, "quick-stay")
    try:
        client = _login("boundary-quickedit-host")
        for bad in ("0", "61", "999"):
            response = client.post(
                f"/reservations/{stay}/quick-edit",
                data={"expected_guests_override": bad},
                headers={"X-Requested-With": "fetch"},
            )
            assert response.status_code == 422
            assert response.json() == {"ok": False}
        assert db.query_one(
            "SELECT expected_guests_override FROM reservation WHERE id = ?", (stay,)
        )["expected_guests_override"] is None
    finally:
        _clean_accounts()


def test_quick_edit_updates_fields_for_fetch_clients():
    db.init_db()
    _clean_accounts()
    owner = _account("boundary-quickedit-save")
    apartment = _apartment(owner, "Save flat", "quicksave")
    stay = _reservation(apartment, "quick-save")
    long_summary = "S" * 200
    try:
        client = _login("boundary-quickedit-save")
        response = client.post(
            f"/reservations/{stay}/quick-edit",
            data={
                "summary": long_summary,
                "expected_guests_override": "4",
            },
            headers={"X-Requested-With": "fetch"},
        )
        assert response.status_code == 200
        assert response.json() == {"ok": True}
        row = db.query_one("SELECT summary, expected_guests_override FROM reservation WHERE id = ?", (stay,))
        assert row["summary"] == long_summary[:160]
        assert row["expected_guests_override"] == 4
    finally:
        _clean_accounts()


def test_quick_edit_cannot_touch_another_workspace_stay():
    db.init_db()
    _clean_accounts()
    first_id = _account("boundary-quickedit-first")
    second_id = _account("boundary-quickedit-second")
    second_flat = _apartment(second_id, "Other flat", "quickother")
    foreign_stay = _reservation(second_flat, "foreign-stay")
    try:
        client = _login("boundary-quickedit-first")
        response = client.post(
            f"/reservations/{foreign_stay}/quick-edit",
            data={"summary": "Hijacked"},
            headers={"X-Requested-With": "fetch"},
        )
        assert response.status_code == 404
        assert db.query_one("SELECT summary FROM reservation WHERE id = ?", (foreign_stay,))["summary"] == "Stay foreign-stay"
    finally:
        _clean_accounts()


def test_archiving_a_stay_offers_undo_and_localises_the_flash():
    db.init_db()
    _clean_accounts()
    owner = _account("boundary-archive-undo")
    apartment = _apartment(owner, "Archive flat", "archiveflat")
    stay = _reservation(apartment, "archive-stay")
    try:
        client = _login("boundary-archive-undo")
        client.cookies.set(host_i18n.LANG_COOKIE, "cs")
        response = client.post(
            f"/reservations/{stay}/archive",
            data={"return_to": "/reservations"},
            follow_redirects=False,
        )
        assert response.status_code == 303
        location = response.headers["location"]
        assert f"undo_stay={stay}" in location
        assert "undo_return=" in location
        assert db.query_one("SELECT archived_at FROM reservation WHERE id = ?", (stay,))["archived_at"]

        archive_page = client.get(location, follow_redirects=True)
        assert host_i18n.translate("cs", "archive.stay_moved") in archive_page.text
        assert f'action="/reservations/{stay}/unarchive"' in archive_page.text
    finally:
        _clean_accounts()
