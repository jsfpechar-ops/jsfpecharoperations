"""Brief 0421: payment_request and stripe_account models (migration 0026)."""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from app import db, payment_request

OWNER = "requestmodel"
TODAY = date(2026, 10, 27)


def _cleanup():
    row = db.query_one("SELECT id FROM user_account WHERE username = ?", (OWNER,))
    if not row:
        return
    oid = row["id"]
    db.execute("DELETE FROM payment_request WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM stripe_account WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM audit WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM user_account WHERE id = ?", (oid,))


@pytest.fixture
def owner():
    db.init_db()
    _cleanup()
    oid = db.insert("user_account", {"username": OWNER, "password_hash": "x",
                                     "display_name": "Requests", "created_at": db.utcnow()})
    try:
        yield oid
    finally:
        _cleanup()


def _entity(oid, **kw):
    values = {"name": "Testovaci s.r.o.", "seat": "Ukazkova 1, Praha",
              "owner_user_id": oid, "created_at": db.utcnow()}
    values.update(kw)
    return db.insert("legal_entity", values)


def _create(owner, **kw):
    values = {"reason": "repair", "amount_czk": 1500, "rail": "qr",
              "expires_at": (TODAY + timedelta(days=7)).isoformat()}
    values.update(kw)
    return payment_request.create(owner, today=TODAY, **values)


def test_migration_0026_tables_exist(owner):
    tables = {r["name"] for r in db.query(
        "SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert {"payment_request", "stripe_account"} <= tables
    version = db.query_one("SELECT MAX(version) AS v FROM schema_migrations")["v"]
    assert version >= 26


def test_create_and_get(owner):
    rid = _create(owner, reason="damage", amount_czk=2000, guest_email="guest@example.com")
    row = payment_request.get(rid)
    assert row["status"] == "draft"
    assert row["reason"] == "damage"
    assert row["currency"] == "CZK"
    assert row["guest_email"] == "guest@example.com"


def test_card_rail_has_no_variable_symbol(owner):
    rid = _create(owner, rail="card")
    assert payment_request.get(rid)["variable_symbol"] is None


def test_variable_symbol_unique_and_from_id(owner):
    first = _create(owner)
    second = _create(owner, reason="cleaning")
    vs1 = payment_request.get(first)["variable_symbol"]
    vs2 = payment_request.get(second)["variable_symbol"]
    assert vs1 != vs2
    assert vs1 == f"{first:010d}"
    assert vs2 == f"{second:010d}"


def test_invalid_reason_rail_amount_raise(owner):
    with pytest.raises(ValueError):
        _create(owner, reason="party")
    with pytest.raises(ValueError):
        _create(owner, rail="wire")
    with pytest.raises(ValueError):
        _create(owner, amount_czk=0)


def test_status_lifecycle(owner):
    rid = _create(owner)
    assert payment_request.set_status(rid, "sent", today=TODAY)
    assert payment_request.set_status(rid, "awaiting_payment", today=TODAY)
    assert payment_request.mark_paid(rid, today=TODAY, via="qr")
    row = payment_request.get(rid)
    assert row["status"] == "paid"
    assert row["paid_at"]


def test_illegal_transitions_raise(owner):
    rid = _create(owner)
    with pytest.raises(ValueError):
        payment_request.set_status(rid, "paid", today=TODAY)
    assert payment_request.set_status(rid, "sent", today=TODAY)
    with pytest.raises(ValueError):
        payment_request.set_status(rid, "draft", today=TODAY)
    assert payment_request.set_status(rid, "cancelled", today=TODAY)
    with pytest.raises(ValueError):
        payment_request.set_status(rid, "sent", today=TODAY)


def test_for_owner_scopes_and_orders(owner):
    other = db.insert("user_account", {"username": "otherowner", "password_hash": "x",
                                       "display_name": "Other", "created_at": db.utcnow()})
    try:
        _create(owner, reason="cleaning")
        _create(owner, reason="custom")
        _create(other, reason="repair")
        rows = payment_request.for_owner(owner)
        assert len(rows) == 2
        assert all(r["owner_user_id"] == owner for r in rows)
        assert {r["reason"] for r in rows} == {"cleaning", "custom"}
    finally:
        db.execute("DELETE FROM payment_request WHERE owner_user_id = ?", (other,))
        db.execute("DELETE FROM user_account WHERE id = ?", (other,))


def test_expire_sweep_only_past_due(owner):
    fresh = _create(owner, reason="repair")
    stale = _create(owner, reason="custom",
                    expires_at=(TODAY - timedelta(days=1)).isoformat())
    payment_request.set_status(fresh, "sent", today=TODAY)
    payment_request.set_status(stale, "sent", today=TODAY)
    assert payment_request.expire_sweep(TODAY) == 1
    assert payment_request.get(fresh)["status"] == "sent"
    assert payment_request.get(stale)["status"] == "expired"


def test_qr_payload_uses_entity_iban(owner):
    _entity(owner, iban="CZ6508000000001921239563")
    rid = _create(owner)
    payload, png = payment_request.qr_payload(payment_request.get(rid))
    assert payload.startswith("SPD*1.0*ACC:CZ6508000000001921239563")
    assert "X-VS:" in payload
    assert png[:4] == b"\x89PNG"


def test_qr_payload_from_czech_account(owner):
    _entity(owner, bank_account="19-2000145399/0800")
    rid = _create(owner)
    payload, _png = payment_request.qr_payload(payment_request.get(rid))
    assert "ACC:CZ" in payload


def test_qr_payload_without_bank_account_raises(owner):
    _entity(owner)
    rid = _create(owner)
    with pytest.raises(ValueError):
        payment_request.qr_payload(payment_request.get(rid))


def test_qr_payload_rejects_card_rail(owner):
    _entity(owner, iban="CZ6508000000001921239563")
    rid = _create(owner, rail="card")
    with pytest.raises(ValueError):
        payment_request.qr_payload(payment_request.get(rid))
