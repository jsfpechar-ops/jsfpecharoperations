"""0847: a property with no stay fee takes over the setup of a sibling in the same municipality."""
from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient

from app import auth, claim, db
from app.main import app
from app.routes import stay_fees as stay_fee_routes
from tests.conftest import login_as

SIGNATURE = "data:image/png;base64,AAAA"
REFUSED = "This setup cannot be copied here."


def _cleanup():
    for user in db.query("SELECT id FROM user_account WHERE username LIKE 'stay-fee-copy-%'"):
        owner_id = user["id"]
        db.execute(
            "DELETE FROM stay_fee_filing WHERE apartment_id IN "
            "(SELECT id FROM apartment WHERE owner_user_id = ?)",
            (owner_id,),
        )
        db.execute(
            "DELETE FROM guest WHERE reservation_id IN (SELECT id FROM reservation "
            "WHERE apartment_id IN (SELECT id FROM apartment WHERE owner_user_id = ?))",
            (owner_id,),
        )
        db.execute(
            "DELETE FROM reservation WHERE apartment_id IN "
            "(SELECT id FROM apartment WHERE owner_user_id = ?)",
            (owner_id,),
        )
        db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (owner_id,))
        db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (owner_id,))
        db.execute("DELETE FROM audit WHERE owner_user_id = ?", (owner_id,))
        db.execute("DELETE FROM user_account WHERE id = ?", (owner_id,))


@pytest.fixture
def host(monkeypatch):
    db.init_db()
    _cleanup()
    monkeypatch.setattr(claim, "prague_today", lambda: date(2026, 9, 30))
    owner_id = auth.create_account("stay-fee-copy-owner@example.test", "Copy Demo", role="host", username="stay-fee-copy-owner")
    entity_id = db.insert("legal_entity", {
        "name": "Copy Demo s.r.o.",
        "owner_user_id": owner_id,
        "created_at": db.utcnow(),
    })
    client = TestClient(app)
    assert login_as(client, "stay-fee-copy-owner", url="/login?lang=en", follow_redirects=False).status_code == 303
    try:
        yield client, owner_id, entity_id
    finally:
        _cleanup()


def _flat(owner_id, entity_id, name, city, **fee):
    values = {
        "internal_name": name,
        "addr_obec": city,
        "active": 1,
        "owner_user_id": owner_id,
        "legal_entity_id": entity_id,
        "created_at": db.utcnow(),
    }
    values.update(fee)
    return db.insert("apartment", values)


def _source(owner_id, entity_id, city="Praha 3"):
    return _flat(
        owner_id, entity_id, "Source", city,
        stay_fee_rate_czk=50,
        stay_fee_vs="123456",
        stay_fee_authority_name="Městský úřad",
        stay_fee_council_account="19-2000781379/0800",
        stay_fee_council_iban="CZ3008000000192000781379",
        stay_fee_cadence="quarterly",
        stay_fee_authority_databox="abc1234",
    )


def _csrf(client, path: str) -> str:
    page = client.get(path)
    assert page.status_code == 200
    return page.text.split('name="csrf-token" content="')[1].split('"')[0]


def _copy(client, target_id, source_id):
    token = _csrf(client, "/stay-fees")
    return client.post(
        f"/stay-fees/{target_id}/copy-setup",
        data={"_csrf": token, "source_id": str(source_id), "return_to": "/stay-fees"},
        follow_redirects=False,
    )


def _stay(apartment_id):
    now = db.utcnow()
    rid = db.insert("reservation", {
        "apartment_id": apartment_id,
        "uid": "copy-stay-1",
        "date_from": "2026-08-10",
        "date_to": "2026-08-14",
        "status": "active",
        "created_at": now,
        "updated_at": now,
    })
    db.insert("guest", {
        "reservation_id": rid,
        "first_name": "Ada",
        "surname": "Guest",
        "birth_date": "01011990",
        "nationality": "DEU",
        "signature_png": SIGNATURE,
        "created_at": now,
        "updated_at": now,
    })


FEE_FIELDS = stay_fee_routes.FEE_COPY_FIELDS


def test_copy_takes_every_fee_field(host):
    client, owner_id, entity_id = host
    source_id = _source(owner_id, entity_id)
    target_id = _flat(owner_id, entity_id, "Target", "praha 3", stay_fee_rate_czk=0)
    source = db.query_one("SELECT * FROM apartment WHERE id = ?", (source_id,))
    resp = _copy(client, target_id, source_id)
    assert resp.status_code == 303
    target = db.query_one("SELECT * FROM apartment WHERE id = ?", (target_id,))
    for key in FEE_FIELDS:
        assert target[key] == source[key], key


def test_list_offers_the_source_only_in_the_same_place(host):
    _client, owner_id, entity_id = host
    source_id = _source(owner_id, entity_id, city="Praha 3")
    source_row = db.query_one("SELECT * FROM apartment WHERE id = ?", (source_id,))
    zero_id = _flat(owner_id, entity_id, "Zero", "Praha 3", stay_fee_rate_czk=0)
    zero_row = db.query_one("SELECT * FROM apartment WHERE id = ?", (zero_id,))
    same = db.query_one("SELECT * FROM apartment WHERE id = ?", (_flat(owner_id, entity_id, "Same", "praha 3"),))
    brno = db.query_one("SELECT * FROM apartment WHERE id = ?", (_flat(owner_id, entity_id, "Brno", "Brno"),))
    empty = db.query_one("SELECT * FROM apartment WHERE id = ?", (_flat(owner_id, entity_id, "Empty", ""),))
    assert stay_fee_routes.fee_copy_source(same, [source_row])["id"] == source_id
    assert stay_fee_routes.fee_copy_source(brno, [source_row]) is None
    assert stay_fee_routes.fee_copy_source(empty, [source_row]) is None
    assert stay_fee_routes.fee_copy_source(same, [zero_row]) is None


def test_copy_refuses_other_place_active_target_foreign_source(host):
    client, owner_id, entity_id = host
    source_id = _source(owner_id, entity_id, city="Praha 3")

    brno_id = _flat(owner_id, entity_id, "Brno flat", "Brno", stay_fee_rate_czk=0)
    resp = _copy(client, brno_id, source_id)
    assert resp.status_code == 303
    assert REFUSED in client.get(resp.headers["location"]).text
    assert db.query_one("SELECT stay_fee_rate_czk FROM apartment WHERE id = ?", (brno_id,))["stay_fee_rate_czk"] == 0

    active_id = _flat(owner_id, entity_id, "Active", "Praha 3", stay_fee_rate_czk=50, stay_fee_vs="999999")
    resp = _copy(client, active_id, source_id)
    assert resp.status_code == 303
    assert REFUSED in client.get(resp.headers["location"]).text
    active = db.query_one("SELECT stay_fee_rate_czk, stay_fee_vs FROM apartment WHERE id = ?", (active_id,))
    assert active["stay_fee_rate_czk"] == 50
    assert active["stay_fee_vs"] == "999999"

    other = auth.create_account("stay-fee-copy-other@example.test", "Other Demo", role="host", username="stay-fee-copy-other")
    other_entity = db.insert("legal_entity", {"name": "Other s.r.o.", "owner_user_id": other, "created_at": db.utcnow()})
    foreign_source = _source(other, other_entity, city="Praha 3")
    target_id = _flat(owner_id, entity_id, "Foreign target", "Praha 3", stay_fee_rate_czk=0)
    resp = _copy(client, target_id, foreign_source)
    assert resp.status_code == 303
    assert REFUSED in client.get(resp.headers["location"]).text
    assert db.query_one("SELECT stay_fee_rate_czk FROM apartment WHERE id = ?", (target_id,))["stay_fee_rate_czk"] == 0


def test_copy_refuses_when_target_has_a_filing(host):
    client, owner_id, entity_id = host
    source_id = _source(owner_id, entity_id, city="Praha 3")
    target_id = _flat(
        owner_id, entity_id, "Filed", "Praha 3",
        stay_fee_rate_czk=50,
        stay_fee_vs="123456",
        stay_fee_authority_name="Městský úřad",
        stay_fee_council_account="19-2000781379/0800",
        stay_fee_council_iban="CZ3008000000192000781379",
    )
    _stay(target_id)
    token = _csrf(client, f"/stay-fees/{target_id}?month=2026-08")
    saved = client.post(
        f"/stay-fees/{target_id}/finalize",
        data={
            "_csrf": token,
            "month": "2026-08",
            "rate_czk": "50",
            "confirm_collected": "1",
            f"collected_{db.query_one('SELECT id FROM guest ORDER BY id DESC')['id']}": "200",
        },
        follow_redirects=False,
    )
    assert saved.status_code == 303
    assert db.query_one("SELECT id FROM stay_fee_filing WHERE apartment_id = ?", (target_id,)) is not None
    db.update("apartment", target_id, {"stay_fee_rate_czk": 0})
    resp = _copy(client, target_id, source_id)
    assert resp.status_code == 303
    assert REFUSED in client.get(resp.headers["location"]).text
    assert db.query_one("SELECT stay_fee_rate_czk FROM apartment WHERE id = ?", (target_id,))["stay_fee_rate_czk"] == 0
