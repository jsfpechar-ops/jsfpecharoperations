"""BE-10: workspace export and termination deletion (LEGAL-GATED, G-D11)."""
from __future__ import annotations

import io
import json
import zipfile
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app import auth, db, retention
from app.main import app

PASSWORD = "Secure-Password-123"


def _unlock(value: str) -> None:
    db.execute(
        "INSERT INTO settings (key, value) VALUES ('invoice_purge_unlock', ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (value,),
    )


def _cleanup():
    for row in db.query("SELECT id FROM user_account WHERE username LIKE 'ws-%'"):
        user_id = row["id"]
        for apartment in db.query(
            "SELECT id FROM apartment WHERE owner_user_id = ?", (user_id,)
        ):
            apartment_id = apartment["id"]
            db.execute(
                "DELETE FROM guest WHERE reservation_id IN "
                "(SELECT id FROM reservation WHERE apartment_id = ?)",
                (apartment_id,),
            )
            db.execute("DELETE FROM submission WHERE apartment_id = ?", (apartment_id,))
            db.execute("DELETE FROM reservation WHERE apartment_id = ?", (apartment_id,))
            db.execute("DELETE FROM apartment WHERE id = ?", (apartment_id,))
        _unlock("1")
        db.execute("DELETE FROM invoice_item WHERE invoice_id IN "
                   "(SELECT id FROM invoice WHERE owner_user_id = ?)", (user_id,))
        db.execute("DELETE FROM invoice WHERE owner_user_id = ?", (user_id,))
        _unlock("")
        db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM data_subject_request WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM alert WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM legal_acceptance WHERE user_account_id = ?", (user_id,))
        db.execute("DELETE FROM audit WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM user_account WHERE id = ?", (user_id,))


def _seed(username: str):
    owner = auth.create_account(
        username, PASSWORD, username, must_change_password=False
    )
    now = db.utcnow()
    entity = db.insert(
        "legal_entity", {"name": f"{username} entity", "owner_user_id": owner, "created_at": now}
    )
    apartment = db.insert(
        "apartment",
        {
            "legal_entity_id": entity,
            "owner_user_id": owner,
            "internal_name": f"{username} flat",
            "created_at": now,
        },
    )
    reservation = db.insert(
        "reservation",
        {
            "apartment_id": apartment,
            "uid": f"ws-{username}",
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
            "surname": "Ws",
            "first_name": "Test",
            "nationality": "GBR",
            "purpose": "10",
            "entered_by": "guest",
            "created_at": now,
            "updated_at": now,
        },
    )
    return owner, entity, apartment, reservation, guest


def _admin(username: str) -> int:
    return auth.create_account(
        username, PASSWORD, username, role="admin", must_change_password=False
    )


def _login(username: str) -> TestClient:
    client = TestClient(app)
    response = client.post(
        "/login?lang=en",
        data={"username": username, "password": PASSWORD},
        follow_redirects=False,
    )
    assert response.status_code == 303
    return client


@pytest.fixture(autouse=True)
def _database():
    db.init_db()
    _cleanup()
    yield
    _cleanup()


def test_the_workspace_export_streams_a_zip_with_a_manifest():
    owner, *_rest = _seed("ws-host")
    _admin("ws-admin")
    response = _login("ws-admin").post(
        f"/admin/users/{owner}/export", follow_redirects=False
    )
    assert response.status_code == 200, response.text
    archive = zipfile.ZipFile(io.BytesIO(response.content))
    names = archive.namelist()
    assert "manifest.json" in names
    assert "housebook.csv" in names
    manifest = json.loads(archive.read("manifest.json"))
    assert manifest["owner_user_id"] == owner
    assert db.query_one(
        "SELECT id FROM audit WHERE action = 'workspace_exported' AND owner_user_id = ?",
        (owner,),
    )


def test_scheduling_deletion_requires_the_username_and_disables_the_account():
    owner, *_rest = _seed("ws-del")
    _admin("ws-admin")
    client = _login("ws-admin")
    bad = client.post(
        f"/admin/users/{owner}/schedule-deletion",
        data={"confirm": "wrong"},
        follow_redirects=False,
    )
    assert bad.status_code == 303
    assert db.query_one(
        "SELECT deletion_due_at FROM user_account WHERE id = ?", (owner,)
    )["deletion_due_at"] is None

    ok = client.post(
        f"/admin/users/{owner}/schedule-deletion",
        data={"confirm": "ws-del"},
        follow_redirects=False,
    )
    assert ok.status_code == 303
    row = db.query_one(
        "SELECT deletion_due_at, active FROM user_account WHERE id = ?", (owner,)
    )
    assert row["deletion_due_at"]
    assert row["active"] == 0


def test_due_workspaces_are_deleted_and_nothing_else():
    owner, _entity, apartment, _reservation, guest = _seed("ws-doom")
    other, *_rest = _seed("ws-keep")
    db.execute(
        "UPDATE user_account SET deletion_due_at = ? WHERE id = ?",
        ((date.today() - timedelta(days=1)).isoformat(), owner),
    )

    assert retention._workspace_deletion_step(date.today(), True, None) >= 1
    assert db.query_one("SELECT id FROM user_account WHERE id = ?", (owner,))

    assert retention._workspace_deletion_step(date.today(), False, None) >= 1
    assert db.query_one("SELECT id FROM user_account WHERE id = ?", (owner,)) is None
    assert db.query_one("SELECT id FROM guest WHERE id = ?", (guest,)) is None
    assert db.query_one("SELECT id FROM apartment WHERE id = ?", (apartment,)) is None
    assert db.query_one("SELECT id FROM user_account WHERE id = ?", (other,))


def test_an_issued_invoice_does_not_block_workspace_deletion():
    owner, entity, _apartment, _reservation, _guest = _seed("ws-inv")
    now = db.utcnow()
    invoice = db.insert(
        "invoice",
        {
            "legal_entity_id": entity,
            "kind": "invoice",
            "seq_year": 2026,
            "seq_no": 1,
            "number": "INV-1",
            "vs": "1",
            "lang": "en",
            "vat_status": "non_payer",
            "issue_date": "2026-01-01",
            "seller_name": "S",
            "seller_seat": "P",
            "buyer_name": "B",
            "total_haler": 100,
            "issued_at": now,
            "owner_user_id": owner,
            "created_at": now,
        },
    )
    db.execute(
        "UPDATE user_account SET deletion_due_at = ? WHERE id = ?",
        ((date.today() - timedelta(days=1)).isoformat(), owner),
    )
    retention._workspace_deletion_step(date.today(), False, None)
    assert db.query_one("SELECT id FROM invoice WHERE id = ?", (invoice,)) is None


def test_a_workspace_with_filed_stay_fees_and_property_invoices_is_deleted_completely():
    owner, entity, apartment, _reservation, _guest = _seed("ws-full")
    now = db.utcnow()
    db.insert("invoice_sequence", {"legal_entity_id": entity, "year": 2026, "last_no": 1})
    db.insert(
        "invoice",
        {
            "legal_entity_id": entity, "apartment_id": apartment, "kind": "invoice",
            "seq_year": 2026, "seq_no": 1, "number": "INV-2", "vs": "2", "lang": "en",
            "vat_status": "non_payer", "issue_date": "2026-01-01", "seller_name": "S",
            "seller_seat": "P", "buyer_name": "B", "total_haler": 100, "issued_at": now,
            "owner_user_id": owner, "created_at": now,
        },
    )
    filing = db.insert(
        "stay_fee_filing",
        {
            "apartment_id": apartment, "period_key": "2026-01", "cadence": "monthly",
            "rate_czk": 50, "liable_days": 1, "exempt_days": 0, "total_due_czk": 50,
            "total_collected_czk": 50, "created_at": now,
        },
    )
    db.insert(
        "stay_fee_adjustment",
        {
            "apartment_id": apartment, "period_key": "2026-01", "direction": "add",
            "mode": "bed_days", "bed_days": 1, "reason_enc": "x", "created_at": now,
            "filing_id": filing,
        },
    )
    mail = db.insert(
        "email_outbox",
        {
            "idempotency_key": "ws-full-mail", "kind": "guest_link", "apartment_id": apartment,
            "owner_user_id": owner, "to_email": "guest@example.invalid", "created_at": now,
            "updated_at": now,
        },
    )
    db.execute(
        "UPDATE user_account SET deletion_due_at = ? WHERE id = ?",
        ((date.today() - timedelta(days=1)).isoformat(), owner),
    )
    retention._workspace_deletion_step(date.today(), False, None)
    assert db.query_one("SELECT id FROM user_account WHERE id = ?", (owner,)) is None
    assert db.query_one("SELECT id FROM apartment WHERE id = ?", (apartment,)) is None
    assert db.query_one("SELECT id FROM legal_entity WHERE id = ?", (entity,)) is None
    assert db.query_one("SELECT id FROM email_outbox WHERE id = ?", (mail,)) is None
