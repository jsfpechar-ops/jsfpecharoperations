"""BE-6: sensitive reads are audited, and the row names the real human.

G-D10: passport-image views and every export/download are audited, ordinary page
views are not. The audit detail carries ids and counts only (Rule 8).
"""
from __future__ import annotations

import base64

from fastapi.testclient import TestClient

from app import auth, db, passport_photos
from app.main import app

PASSWORD = "Secure-Password-123"
PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVR4nGMAAQAABQAB"
    "DQottAAAAABJRU5ErkJggg=="
)
SECRET_NAME = "Secretname"
SECRET_DOC = "P9999999"


def _cleanup():
    for row in db.query("SELECT id FROM user_account WHERE username LIKE 'audit-%'"):
        user_id = row["id"]
        db.execute("DELETE FROM alert WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM audit WHERE owner_user_id = ?", (user_id,))
        for apartment in db.query(
            "SELECT id FROM apartment WHERE owner_user_id = ?", (user_id,)
        ):
            apartment_id = apartment["id"]
            for reservation in db.query(
                "SELECT id FROM reservation WHERE apartment_id = ?", (apartment_id,)
            ):
                for guest in db.query(
                    "SELECT id FROM guest WHERE reservation_id = ?",
                    (reservation["id"],),
                ):
                    passport_photos.delete_photo(guest["id"])
                db.execute("DELETE FROM guest WHERE reservation_id = ?", (reservation["id"],))
            db.execute("DELETE FROM submission WHERE apartment_id = ?", (apartment_id,))
            db.execute("DELETE FROM reservation WHERE apartment_id = ?", (apartment_id,))
            db.execute("DELETE FROM apartment WHERE id = ?", (apartment_id,))
        db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (user_id,))
        db.execute(
            "DELETE FROM legal_entity WHERE name = 'Audit entity' AND id NOT IN "
            "(SELECT legal_entity_id FROM apartment WHERE legal_entity_id IS NOT NULL)"
        )
        db.execute("DELETE FROM user_account WHERE id = ?", (user_id,))


def _seed():
    db.init_db()
    _cleanup()
    owner = auth.create_account(
        "audit-host", PASSWORD, "Audit", must_change_password=False
    )
    now = db.utcnow()
    entity = db.insert(
        "legal_entity", {"name": "Audit entity", "owner_user_id": owner, "created_at": now}
    )
    apartment = db.insert(
        "apartment",
        {
            "legal_entity_id": entity,
            "owner_user_id": owner,
            "internal_name": "Audit flat",
            "permalink_token": "audittok",
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
            "uid": "audit-stay",
            "date_from": "2026-01-01",
            "date_to": "2026-01-03",
            "status": "active",
            "created_at": now,
            "updated_at": now,
        },
    )
    guest = db.insert(
        "guest",
        {
            "reservation_id": reservation,
            "surname": SECRET_NAME,
            "first_name": "Jane",
            "birth_date": "01011990",
            "nationality": "GBR",
            "doc_number": SECRET_DOC,
            "purpose": "10",
            "entered_by": "guest",
            "passport_photo_at": now,
            "created_at": now,
            "updated_at": now,
        },
    )
    passport_photos.save_photo(guest, PNG_BYTES, "image/png")
    submission = db.insert(
        "submission",
        {
            "apartment_id": apartment,
            "created_at": now,
            "state": "ok",
            "receipt_pdf": base64.b64encode(b"%PDF-1.4 receipt").decode(),
            "error_pdf": base64.b64encode(b"%PDF-1.4 errors").decode(),
            "request_xml": f"<request><doc>{SECRET_DOC}</doc></request>",
            "response_xml": "<response>ok</response>",
            "pseudo_stamp": "STAMP",
        },
    )
    db.update("guest", guest, {"submission_id": submission, "receipt_submission_id": submission})
    return owner, apartment, reservation, guest, submission


def _login(username: str) -> TestClient:
    client = TestClient(app)
    response = client.post(
        "/login?lang=en",
        data={"username": username, "password": PASSWORD},
        follow_redirects=False,
    )
    assert response.status_code == 303
    return client


def test_every_sensitive_read_writes_one_audit_row_for_the_actor():
    owner, _apartment, _reservation, guest, submission = _seed()
    try:
        client = _login("audit-host")
        calls = {
            "export_reservations_csv": "/reservations.csv?from=2026-01-01&to=2026-01-03",
            "export_registration_pdf": f"/guests/{guest}/form.pdf",
            "export_receipts_zip": "/submissions/receipts.zip",
            "export_submission_pdf": f"/submissions/{submission}/receipt.pdf",
            "export_submission_xml": f"/submissions/{submission}/response.xml",
            "export_housebook_csv": "/housebook.csv",
            "export_housebook_pdfs": "/housebook/pdfs.zip",
            "passport_photo_viewed": f"/guests/{guest}/passport-photo",
        }
        for action, path in calls.items():
            response = client.get(path)
            assert response.status_code == 200, (action, response.status_code)
            rows = db.query(
                "SELECT * FROM audit WHERE owner_user_id = ? AND action = ?",
                (owner, action),
            )
            assert len(rows) == 1, (action, len(rows))
            assert rows[0]["actor"] == "audit-host"
            assert rows[0]["actor_user_id"] == owner
            assert rows[0]["impersonator_user_id"] is None

        # The detail carries ids/counts only, never the guest's data.
        for row in db.query(
            "SELECT detail FROM audit WHERE owner_user_id = ?", (owner,)
        ):
            detail = row["detail"] or ""
            assert SECRET_NAME not in detail
            assert SECRET_DOC not in detail
    finally:
        _cleanup()


def test_an_impersonated_export_names_the_admin_and_the_workspace():
    owner, _apartment, _reservation, _guest, submission = _seed()
    admin = auth.create_account(
        "audit-admin", PASSWORD, "Audit Admin", role="admin", must_change_password=False
    )
    try:
        client = _login("audit-admin")
        started = client.post(
            f"/admin/users/{owner}/impersonate", follow_redirects=False
        )
        assert started.status_code == 303
        response = client.get(f"/submissions/{submission}/receipt.pdf")
        assert response.status_code == 200

        row = db.query_one(
            "SELECT * FROM audit WHERE action = 'export_submission_pdf' "
            "AND owner_user_id = ? ORDER BY id DESC LIMIT 1",
            (owner,),
        )
        assert row is not None
        assert row["actor"] == "audit-admin"
        assert row["actor_user_id"] == admin
        assert row["impersonator_user_id"] == admin
    finally:
        _cleanup()
