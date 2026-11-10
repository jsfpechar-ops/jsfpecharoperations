"""1075: prefills from data we already hold, the invoice fold, share-text order (rendered pages)."""
from __future__ import annotations

import json
import re
import secrets

import pytest
from fastapi.testclient import TestClient

from app import auth, config, db
from app.main import app
from tests.conftest import login_as

OWNER = "prefill1075"
FOLD = re.compile(r'<details class="ui-details-box invoice-more"( open)?>')


def _cleanup():
    row = db.query_one("SELECT id FROM user_account WHERE username = ?", (OWNER,))
    if not row:
        return
    oid = row["id"]
    db.execute("DELETE FROM lock_account WHERE owner_user_id = ?", (oid,))
    for apt in db.query("SELECT id FROM apartment WHERE owner_user_id = ?", (oid,)):
        db.execute("DELETE FROM settings WHERE key = ?", (f"property_setup:{apt['id']}",))
    db.execute("DELETE FROM reservation WHERE apartment_id IN (SELECT id FROM apartment WHERE owner_user_id = ?)", (oid,))
    db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM audit WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM user_account WHERE id = ?", (oid,))


@pytest.fixture
def owner():
    db.init_db()
    _cleanup()
    auth.create_account(f"{OWNER}@example.test", "Prefill Host", username=OWNER)
    oid = db.query_one("SELECT id FROM user_account WHERE username = ?", (OWNER,))["id"]
    try:
        yield oid
    finally:
        _cleanup()


@pytest.fixture
def client(owner):
    client = TestClient(app)
    assert login_as(client, OWNER, url="/login?lang=en", follow_redirects=False).status_code == 303
    return client


def _entity(owner_id, **extra):
    return db.insert("legal_entity", {
        "name": "Prefill 1075 s.r.o.", "seat": "Praha", "ico": "12345678", "contact_email": "biz@example.test",
        "vat_status": "non_payer", "invoice_due_days": 14, "owner_user_id": owner_id, "created_at": db.utcnow(),
        **extra,
    })


def _flat(user, **extra):
    return db.insert("apartment", {
        "owner_user_id": user, "internal_name": "Home 1075", "active": 1, "created_at": db.utcnow(),
        "automation_mode": "manual", "permalink_token": auth.new_permalink_token(), **extra,
    })


def _stay(user, email):
    now = db.utcnow()
    home = _flat(user, checkin_hour=15, checkout_hour=11)
    return db.insert("reservation", {
        "apartment_id": home, "uid": secrets.token_hex(16), "date_from": "2026-12-01",
        "date_to": "2026-12-03", "status": "active", "source": "manual",
        "guest_email": email, "created_at": now, "updated_at": now,
    })


def test_new_business_form_prefills_the_account_email(client):
    html = client.get("/entities?lang=en").text
    field = re.search(r'<input[^>]*id="new_contact_email"[^>]*>', html).group(0)
    assert f'value="{OWNER}@example.test"' in field


def test_edit_form_of_a_business_without_email_stays_empty(client, owner):
    entity = _entity(owner, contact_email="")
    html = client.get(f"/entities?edit={entity}&lang=en").text
    fields = [f for f in re.findall(r'<input[^>]*name="contact_email"[^>]*>', html) if 'id="new_contact_email"' not in f]
    assert fields
    for field in fields:
        assert 'value=""' in field and f"{OWNER}@example.test" not in field


def test_payment_form_prefills_guest_email_only_from_own_stay(client, owner):
    own = _stay(owner, "guest@example.test")
    other = auth.create_account("prefill1075-other@example.test", "Other", username="prefill1075-other", role="host")
    foreign = _stay(other, "secret@example.test")
    try:
        assert 'value="guest@example.test"' in client.get(f"/payments/new?reservation_id={own}&lang=en").text
        page = client.get(f"/payments/new?reservation_id={foreign}&lang=en").text
        assert "secret@example.test" not in page
        assert 'value="guest@example.test"' not in client.get("/payments/new?lang=en").text
    finally:
        db.execute("DELETE FROM reservation WHERE apartment_id IN (SELECT id FROM apartment WHERE owner_user_id = ?)", (other,))
        db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (other,))
        db.execute("DELETE FROM user_account WHERE id = ?", (other,))


def test_wizard_hours_default_to_15_and_10_and_keep_saved_hours(client, owner):
    empty = client.get(f"/apartments/{_flat(owner)}/setup/property?lang=en").text
    assert 'value="15" selected' in empty and 'value="10" selected' in empty
    saved = client.get(f"/apartments/{_flat(owner, checkin_hour=16, checkout_hour=11)}/setup/property?lang=en").text
    assert 'value="16" selected' in saved and 'value="11" selected' in saved
    assert 'value="15" selected' not in saved and 'value="10" selected' not in saved


def test_invoice_fold_is_closed_when_empty_and_open_when_a_prefix_is_set(client, owner):
    plain = client.get(f"/entities?edit={_entity(owner)}&lang=en").text
    assert [m.group(1) for m in FOLD.finditer(plain)] == [None]
    numbered = client.get(f"/entities?edit={_entity(owner, invoice_prefix='UB')}&lang=en").text
    assert [m.group(1) for m in FOLD.finditer(numbered)] == [" open"]
    fold = numbered[numbered.index('class="ui-details-box invoice-more"'):]
    fold = fold[:fold.index("</details>")]
    assert 'id="invoice_prefix"' in fold and 'id="invoice_next_number"' in fold
    assert 'id="registry_entry"' not in fold and 'id="invoice_due_days"' not in fold


def test_share_block_lists_steps_before_warnings(client, owner, monkeypatch):
    monkeypatch.setattr(config, "DOOR_CODES_ENABLED", True)
    monkeypatch.setattr(config, "TTLOCK_CLIENT_ID", "cid")
    monkeypatch.setattr(config, "TTLOCK_CLIENT_SECRET", "csecret")
    now = db.utcnow()
    db.insert("lock_account", {"owner_user_id": owner, "provider": "ttlock", "username": "x_prefill1075",
                               "status": "ok", "locks_json": json.dumps([]), "created_at": now, "updated_at": now})
    html = client.get(f"/apartments/{_flat(owner)}?view=settings&section=lock&lang=en").text
    start = html.index('id="smart-locks-share"')
    steps = html.index("In the TTLock app, add UbyHost as eAdmin", start)
    owner_warning = html.index("Only the owner of the lock can do this.", start)
    assert html.index("x_prefill1075", start) < steps < owner_warning < html.index("Do not use eKeys", start)
