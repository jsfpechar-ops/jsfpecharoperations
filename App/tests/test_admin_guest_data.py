"""WP04: admin workspace preview — audit, optional reason, full support access.

Admins see full guest identity and all exports while previewing a host workspace.
Opening still writes impersonation_started; reason is optional (defaults to support).
"""
from __future__ import annotations

import base64
import time
from urllib.parse import unquote

import pytest
from fastapi.testclient import TestClient

from app import access, auth, db, demo, host_i18n, passport_photos
from app.main import app
from tests.conftest import login_as

PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVR4nGMAAQAABQAB"
    "DQottAAAAABJRU5ErkJggg=="
)
DOC_A = "PA1234567"
VISA_A = "VZ7654321"
DOC_B = "PB9876543"
REASON = "Host ticket 42: check the stay"


def _cleanup():
    for row in db.query("SELECT id FROM user_account WHERE username LIKE 'wp04-%'"):
        user_id = row["id"]
        db.execute("DELETE FROM alert WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM audit WHERE owner_user_id = ?", (user_id,))
        for apartment in db.query("SELECT id FROM apartment WHERE owner_user_id = ?", (user_id,)):
            apartment_id = apartment["id"]
            for reservation in db.query(
                "SELECT id FROM reservation WHERE apartment_id = ?", (apartment_id,)
            ):
                for guest in db.query(
                    "SELECT id FROM guest WHERE reservation_id = ?", (reservation["id"],)
                ):
                    passport_photos.delete_photo(guest["id"])
                db.execute("DELETE FROM guest WHERE reservation_id = ?", (reservation["id"],))
            db.execute("DELETE FROM submission WHERE apartment_id = ?", (apartment_id,))
            db.execute("DELETE FROM reservation WHERE apartment_id = ?", (apartment_id,))
            db.execute("DELETE FROM apartment WHERE id = ?", (apartment_id,))
        db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM user_account WHERE id = ?", (user_id,))


@pytest.fixture()
def seeded():
    db.init_db()
    _cleanup()
    owner = auth.create_account("wp04-host@example.test", "WP04 Host", username="wp04-host")
    admin = auth.create_account("wp04-admin@example.test", "WP04 Admin", role="admin", username="wp04-admin")
    now = db.utcnow()
    entity = db.insert(
        "legal_entity", {"name": "WP04 entity", "owner_user_id": owner, "created_at": now}
    )
    apartment = db.insert(
        "apartment",
        {
            "legal_entity_id": entity,
            "owner_user_id": owner,
            "internal_name": "WP04 flat",
            "permalink_token": "wp04tok",
            "automation_mode": "manual",
            "default_purpose": "10",
            "active": 1,
            "created_at": now,
        },
    )
    reservation = db.insert(
        "reservation",
        {
            "apartment_id": apartment,
            "uid": "wp04-stay",
            "date_from": "2026-01-01",
            "date_to": "2026-01-03",
            "status": "active",
            "created_at": now,
            "updated_at": now,
        },
    )

    def guest(surname, doc, visa=None):
        return db.insert(
            "guest",
            {
                "reservation_id": reservation,
                "surname": surname,
                "first_name": "Jane",
                "birth_date": "01011990",
                "nationality": "GBR",
                "doc_number": doc,
                "visa_number": visa,
                "purpose": "10",
                "entered_by": "guest",
                "signature_png": demo.DEMO_SIGNATURE,
                "signed_at": now,
                "passport_photo_at": now,
                "created_at": now,
                "updated_at": now,
            },
        )

    guest_a = guest("Alpha", DOC_A, VISA_A)
    guest_b = guest("Bravo", DOC_B)
    passport_photos.save_photo(guest_a, PNG_BYTES, "image/png")
    passport_photos.save_photo(guest_b, PNG_BYTES, "image/png")
    submission = db.insert(
        "submission",
        {
            "apartment_id": apartment,
            "created_at": now,
            "state": "ok",
            "guest_ids": f"[{guest_a}, {guest_b}]",
            "receipt_pdf": base64.b64encode(b"%PDF-1.4 receipt").decode(),
            "error_pdf": base64.b64encode(b"%PDF-1.4 errors").decode(),
            "request_xml": f"<request><doc>{DOC_A}</doc></request>",
            "response_xml": "<response>ok</response>",
            "pseudo_stamp": "STAMP",
        },
    )
    # The host's own ZIP is offered only while deletion is scheduled.
    db.update("user_account", owner, {"deletion_due_at": "2099-01-01T00:00:00+00:00"})
    yield {
        "owner": owner,
        "admin": admin,
        "apartment": apartment,
        "reservation": reservation,
        "guest_a": guest_a,
        "guest_b": guest_b,
        "submission": submission,
    }
    _cleanup()


def _login(username: str) -> TestClient:
    client = TestClient(app)
    response = login_as(client, username, url="/login?lang=en", follow_redirects=False)
    assert response.status_code == 303
    return client


def _impersonate(client: TestClient, owner: int, reason: str = REASON):
    return client.post(
        f"/admin/users/{owner}/impersonate",
        data={"reason": reason},
        follow_redirects=False,
    )


def _supporting(seeded) -> TestClient:
    client = _login("wp04-admin")
    assert _impersonate(client, seeded["owner"]).status_code == 303
    assert "Previewing workspace" in client.get("/").text
    return client


def _audit(owner: int, action: str):
    return db.query(
        "SELECT * FROM audit WHERE owner_user_id = ? AND action = ? ORDER BY id",
        (owner, action),
    )


def _pages(seeded):
    return [
        f"/reservations/{seeded['reservation']}",
        "/housebook",
        f"/submissions/{seeded['submission']}",
        f"/guests/{seeded['guest_a']}",
        f"/guests/{seeded['guest_b']}",
    ]


def _downloads(seeded):
    a, s = seeded["guest_a"], seeded["submission"]
    return [
        ("get", f"/guests/{a}/form.pdf"),
        ("get", f"/guests/{a}/export.json"),
        ("get", f"/guests/{a}/passport-photo"),
        ("get", "/housebook.csv"),
        ("get", "/housebook/pdfs.zip"),
        ("get", "/submissions/receipts.zip"),
        ("get", f"/submissions/{s}/receipt.pdf"),
        ("get", f"/submissions/{s}/errors.pdf"),
        ("get", f"/submissions/{s}/request.xml"),
        ("get", f"/submissions/{s}/response.xml"),
        ("post", "/settings/workspace-export"),
    ]


# --- starting, the reason ---------------------------------------------------

def test_opening_a_workspace_without_a_reason_uses_support_in_audit(seeded):
    client = _login("wp04-admin")
    assert _impersonate(client, seeded["owner"], "").status_code == 303
    assert "Previewing workspace" in client.get("/").text
    rows = _audit(seeded["owner"], "impersonation_started")
    assert rows[-1]["detail"] == "admin=wp04-admin reason=support"

    client.post("/admin/stop-impersonating", follow_redirects=False)
    assert _impersonate(client, seeded["owner"], "  Host   ticket\n42  ").status_code == 303
    rows = _audit(seeded["owner"], "impersonation_started")
    assert rows[-1]["detail"] == "admin=wp04-admin reason=Host ticket 42"


def test_the_bar_shows_the_minutes_left(seeded):
    client = _supporting(seeded)
    page = client.get("/").text
    if auth.IMPERSONATION_MAX_AGE <= 0:
        assert "data-impersonation-minutes" not in page
        return
    assert "data-impersonation-minutes=" in page
    assert "minutes left" in page


def test_a_session_without_a_start_time_is_treated_as_expired(seeded):
    payload = {"as": seeded["owner"]}
    assert auth.impersonation_expired(payload)
    assert not auth.impersonation_expired({"as": seeded["owner"], "ast": int(time.time())})
    assert not auth.impersonation_expired({})


# --- the 60-minute limit and the stop row -------------------------------------

def test_after_sixty_minutes_the_next_request_ends_the_impersonation(seeded, monkeypatch):
    monkeypatch.setattr(auth, "IMPERSONATION_MAX_AGE", 3600)
    client = _supporting(seeded)
    started = time.time()
    monkeypatch.setattr(
        auth.time, "time", lambda: started + auth.IMPERSONATION_MAX_AGE + 1
    )
    response = client.get(f"/reservations/{seeded['reservation']}", follow_redirects=False)
    assert response.status_code == 303
    location = unquote(response.headers["location"])
    assert location.startswith("/admin/users?msg=")
    assert host_i18n.translate("en", "impersonation.expired") in location

    host_rows = _audit(seeded["owner"], "impersonation_stopped")
    admin_rows = _audit(seeded["admin"], "impersonation_stopped")
    assert [row["detail"] for row in host_rows] == ["expired"]
    assert [row["detail"] for row in admin_rows] == ["expired"]
    assert host_rows[0]["actor"] == "wp04-admin"

    # The replaced cookie is the admin's own: no preview, no second stop row.
    page = client.get("/")
    assert "Previewing workspace" not in page.text
    assert DOC_A not in client.get("/housebook").text
    assert len(_audit(seeded["owner"], "impersonation_stopped")) == 1


def test_before_sixty_minutes_the_impersonation_holds(seeded, monkeypatch):
    monkeypatch.setattr(auth, "IMPERSONATION_MAX_AGE", 3600)
    client = _supporting(seeded)
    started = time.time()
    monkeypatch.setattr(auth.time, "time", lambda: started + auth.IMPERSONATION_MAX_AGE - 120)
    page = client.get("/")
    assert "Previewing workspace" in page.text
    assert 'data-impersonation-minutes="2"' in page.text
    assert _audit(seeded["owner"], "impersonation_stopped") == []


def test_exiting_writes_the_stop_row_to_the_host_and_the_admin(seeded):
    client = _supporting(seeded)
    response = client.post("/admin/stop-impersonating", follow_redirects=False)
    assert response.status_code == 303
    assert [row["detail"] for row in _audit(seeded["owner"], "impersonation_stopped")] == ["exit"]
    assert [row["detail"] for row in _audit(seeded["admin"], "impersonation_stopped")] == ["exit"]


# --- masking ------------------------------------------------------------------

def test_the_host_sees_full_identity_data(seeded):
    client = _login("wp04-host")
    for path in _pages(seeded):
        assert client.get(path).status_code == 200, path
    assert DOC_A in client.get(f"/reservations/{seeded['reservation']}").text
    assert VISA_A in client.get("/housebook").text
    assert DOC_B in client.get(f"/submissions/{seeded['submission']}").text
    form = client.get(f"/guests/{seeded['guest_a']}").text
    assert DOC_A in form and VISA_A in form
    assert demo.DEMO_SIGNATURE in form
    assert f"/guests/{seeded['guest_a']}/passport-photo" in form
    assert host_i18n.translate("en", "identity.hidden") not in form
    for method, path in _downloads(seeded):
        response = getattr(client, method)(path, follow_redirects=False)
        assert response.status_code == 200, (path, response.status_code)


def test_the_admin_sees_full_identity_data_while_supporting(seeded):
    client = _supporting(seeded)
    for path in _pages(seeded):
        assert client.get(path).status_code == 200, path
    assert DOC_A in client.get(f"/reservations/{seeded['reservation']}").text
    assert VISA_A in client.get("/housebook").text
    assert DOC_B in client.get(f"/submissions/{seeded['submission']}").text
    form = client.get(f"/guests/{seeded['guest_a']}").text
    assert DOC_A in form and VISA_A in form
    assert demo.DEMO_SIGNATURE in form
    assert f"/guests/{seeded['guest_a']}/passport-photo" in form
    assert host_i18n.translate("en", "identity.hidden") not in form
    for method, path in _downloads(seeded):
        response = getattr(client, method)(path, follow_redirects=False)
        assert response.status_code == 200, (path, response.status_code)
    admin_zip = client.post(f"/admin/users/{seeded['owner']}/export", follow_redirects=False)
    assert admin_zip.status_code == 200
    assert _audit(seeded["owner"], "workspace_exported")


def test_supporting_can_download_a_stored_dorucenka_and_it_is_audited(seeded):
    client = _supporting(seeded)
    submission_id = seeded["submission"]
    response = client.get(f"/submissions/{submission_id}/receipt.pdf", follow_redirects=False)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/pdf")
    rows = _audit(seeded["owner"], "export_submission_pdf")
    assert rows, "download must be audited for the host workspace"
    assert f"submission_id={submission_id} which=receipt" in rows[-1]["detail"]
    assert "while_supporting=1" in rows[-1]["detail"]

    errors = client.get(f"/submissions/{submission_id}/errors.pdf", follow_redirects=False)
    assert errors.status_code == 200
    error_rows = _audit(seeded["owner"], "export_submission_pdf")
    assert "which=errors" in error_rows[-1]["detail"]
    assert "while_supporting=1" in error_rows[-1]["detail"]


def test_saving_a_guest_while_supporting_persists_identity(seeded):
    client = _supporting(seeded)
    guest_id = seeded["guest_a"]
    response = client.post(
        f"/guests/{guest_id}",
        data={
            "surname": "Alpha",
            "first_name": "Janet",
            "birth_date": "01011990",
            "nationality": "GBR",
            "doc_type": "pas",
            "doc_number": DOC_A,
            "visa_number": VISA_A,
            "purpose": "10",
            "res_street": "Baker Street 1",
            "res_city": "London",
            "res_country": "GBR",
            "signature": demo.DEMO_SIGNATURE,
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    row = db.query_one("SELECT * FROM guest WHERE id = ?", (guest_id,))
    assert row["doc_number"] == DOC_A
    assert row["visa_number"] == VISA_A
    assert row["signature_png"] == demo.DEMO_SIGNATURE


# --- reveal -------------------------------------------------------------------

def test_reveal_still_writes_audit_and_admin_already_sees_full_identity(seeded):
    client = _supporting(seeded)
    a, b = seeded["guest_a"], seeded["guest_b"]
    assert DOC_A in client.get(f"/guests/{a}").text
    assert DOC_B in client.get(f"/guests/{b}").text

    revealed = client.post(
        f"/guests/{a}/reveal-identity",
        data={"reason": "Guest says the passport number is wrong"},
        follow_redirects=False,
    )
    assert revealed.status_code == 303
    rows = _audit(seeded["owner"], "guest_identity_revealed")
    assert rows[-1]["detail"] == f"guest_id={a} reason=Guest says the passport number is wrong"
    assert client.get("/housebook.csv", follow_redirects=False).status_code == 200


def test_reveal_ends_with_the_impersonation(seeded):
    client = _supporting(seeded)
    a = seeded["guest_a"]
    client.post(f"/guests/{a}/reveal-identity", data={"reason": REASON}, follow_redirects=False)
    client.post("/admin/stop-impersonating", follow_redirects=False)
    assert _impersonate(client, seeded["owner"]).status_code == 303
    assert DOC_A in client.get(f"/guests/{a}").text


def test_the_reveal_keeps_the_original_start_time(seeded, monkeypatch):
    monkeypatch.setattr(auth, "IMPERSONATION_MAX_AGE", 3600)
    client = _supporting(seeded)
    started = time.time()
    monkeypatch.setattr(auth.time, "time", lambda: started + 50 * 60)
    client.post(
        f"/guests/{seeded['guest_a']}/reveal-identity",
        data={"reason": REASON},
        follow_redirects=False,
    )
    monkeypatch.setattr(auth.time, "time", lambda: started + auth.IMPERSONATION_MAX_AGE + 1)
    assert client.get("/", follow_redirects=False).status_code == 303
    assert [r["detail"] for r in _audit(seeded["owner"], "impersonation_stopped")] == ["expired"]


def test_identity_helpers():
    assert access.mask_identifier("") == ""
    assert access.mask_identifier(None) == ""
    assert access.mask_identifier("AB") == "•••"
    assert access.mask_identifier("123456789") == "•••789"
    assert auth.support_reason("abcd") is None
    assert auth.support_reason("abcde") == "abcde"
    assert auth.support_reason("x" * 300) == "x" * 300
    assert auth.support_reason("x" * 301) is None
    assert auth.impersonation_audit_reason("") == "support"
    assert auth.impersonation_audit_reason("abcde") == "abcde"


# --- the host's Settings ------------------------------------------------------

def test_the_host_sees_start_stop_and_reveal_in_settings(seeded):
    admin = _supporting(seeded)
    admin.post(
        f"/guests/{seeded['guest_a']}/reveal-identity",
        data={"reason": "Checking the visa number"},
        follow_redirects=False,
    )
    admin.post("/admin/stop-impersonating", follow_redirects=False)
    db.audit("apartment_updated", "id=1", actor="wp04-host", owner_user_id=seeded["owner"])

    host = _login("wp04-host")
    page = host.get("/settings").text
    for text in (
        "impersonation_started",
        f"reason={REASON}",
        "impersonation_stopped",
        "guest_identity_revealed",
        "reason=Checking the visa number",
        "as admin wp04-admin",
        "apartment_updated",
        "Support sessions",
    ):
        assert text in page, text

    support = host.get("/settings?audit=support").text
    assert "impersonation_started" in support
    assert "impersonation_stopped" in support
    assert "guest_identity_revealed" in support
    assert "apartment_updated" not in support
