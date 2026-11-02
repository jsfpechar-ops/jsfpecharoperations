"""0845: one POST seals every ready stay-fee period the host sees."""
from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient

from app import auth, claim, db, stay_fee_auto, stay_fee_filing
from app.main import app
from tests.conftest import login_as

SIGNATURE = "data:image/png;base64,AAAA"
PREFIX = "stay-fee-bulk-%"


def _cleanup():
    for user in db.query("SELECT id FROM user_account WHERE username LIKE ?", (PREFIX,)):
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
    owner_id = auth.create_account("stay-fee-bulk-owner@example.test", "Bulk Demo", role="host",
                                   username="stay-fee-bulk-owner")
    entity_id = db.insert("legal_entity", {
        "name": "Bulk Demo s.r.o.",
        "owner_user_id": owner_id,
        "created_at": db.utcnow(),
    })
    client = TestClient(app)
    assert login_as(client, "stay-fee-bulk-owner", url="/login?lang=en",
                    follow_redirects=False).status_code == 303
    try:
        yield client, owner_id, entity_id
    finally:
        _cleanup()


def _property(owner_id, entity_id, name="Bulk Flat"):
    return db.insert("apartment", {
        "internal_name": name,
        "owner_user_id": owner_id,
        "legal_entity_id": entity_id,
        "stay_fee_rate_czk": 50,
        "stay_fee_vs": "123456",
        "stay_fee_authority_name": "Městský úřad",
        "stay_fee_council_account": "19-2000781379/0800",
        "stay_fee_council_iban": "CZ3008000000192000781379",
        "created_at": db.utcnow(),
    })


def _stay(apartment_id, uid, signed=True):
    now = db.utcnow()
    rid = db.insert("reservation", {
        "apartment_id": apartment_id,
        "uid": uid,
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
        "signature_png": SIGNATURE if signed else None,
        "created_at": now,
        "updated_at": now,
    })


def _csrf(client, path: str) -> str:
    page = client.get(path)
    assert page.status_code == 200
    return page.text.split('name="csrf-token" content="')[1].split('"')[0]


def _row(apartment_id):
    return db.query_one("SELECT * FROM apartment WHERE id = ?", (apartment_id,))


LIST_PATH = "/stay-fees?month=2026-08"


def test_bulk_seals_the_same_amounts_as_the_single_button(host):
    client, owner_id, entity_id = host
    a = _property(owner_id, entity_id, "Bulk A")
    b = _property(owner_id, entity_id, "Bulk B")
    _stay(a, "bulk-a")
    _stay(b, "bulk-b")
    expected = stay_fee_auto.check(_row(a), date(2026, 8, 1), date(2026, 9, 30))["group"]["total_czk"]
    token = _csrf(client, LIST_PATH)
    single = client.post(
        f"/stay-fees/{a}/finalize",
        data={"_csrf": token, "month": "2026-08", "confirm_collected": "1",
              "return_to": "/stay-fees?month=2026-08"},
        follow_redirects=False,
    )
    assert single.status_code == 303
    bulk = client.post(
        "/stay-fees/confirm-ready",
        data={"_csrf": token, "month": "2026-08", "return_to": "/stay-fees?month=2026-08",
              "apartment_id": [str(b)]},
        follow_redirects=False,
    )
    assert bulk.status_code == 303
    ra = stay_fee_filing.latest(a, "2026-08")
    rb = stay_fee_filing.latest(b, "2026-08")
    assert ra is not None and rb is not None
    assert ra["total_due_czk"] == rb["total_due_czk"] == expected
    assert ra["rate_czk"] == rb["rate_czk"]
    pa, pb = stay_fee_filing.payload(ra), stay_fee_filing.payload(rb)
    if "collected" in pa and "collected" in pb:
        assert sorted(pa["collected"].values()) == sorted(pb["collected"].values())
    else:
        assert stay_fee_filing.frozen_summary(ra, _row(a))["total_czk"] == \
            stay_fee_filing.frozen_summary(rb, _row(b))["total_czk"]


def test_bulk_skips_blocked_and_saved_periods(host):
    client, owner_id, entity_id = host
    a = _property(owner_id, entity_id, "Bulk A")
    b = _property(owner_id, entity_id, "Bulk B")
    c = _property(owner_id, entity_id, "Bulk C")
    _stay(a, "bulk-a")
    _stay(b, "bulk-b", signed=False)
    _stay(c, "bulk-c")
    token = _csrf(client, LIST_PATH)
    client.post(
        f"/stay-fees/{c}/finalize",
        data={"_csrf": token, "month": "2026-08", "confirm_collected": "1",
              "return_to": "/stay-fees?month=2026-08"},
        follow_redirects=False,
    )
    c_before = stay_fee_filing.latest(c, "2026-08")
    assert c_before is not None
    bulk = client.post(
        "/stay-fees/confirm-ready",
        data={"_csrf": token, "month": "2026-08", "return_to": "/stay-fees?month=2026-08",
              "apartment_id": [str(a), str(b), str(c)]},
        follow_redirects=False,
    )
    assert bulk.status_code == 303
    assert stay_fee_filing.latest(a, "2026-08") is not None
    assert stay_fee_filing.latest(b, "2026-08") is None
    assert stay_fee_filing.latest(c, "2026-08")["id"] == c_before["id"]
    page = client.get(bulk.headers["location"])
    assert page.status_code == 200
    assert "Periods saved: 1" in page.text


def test_bulk_ignores_other_owners_and_garbage_ids(host):
    client, owner_id, entity_id = host
    other_id = auth.create_account("stay-fee-bulk-other@example.test", "Other Demo", role="host",
                                   username="stay-fee-bulk-other")
    other_entity = db.insert("legal_entity", {
        "name": "Other Demo s.r.o.",
        "owner_user_id": other_id,
        "created_at": db.utcnow(),
    })
    foreign = _property(other_id, other_entity, "Foreign Flat")
    _stay(foreign, "bulk-foreign")
    token = _csrf(client, LIST_PATH)
    bulk = client.post(
        "/stay-fees/confirm-ready",
        data={"_csrf": token, "month": "2026-08", "return_to": "/stay-fees?month=2026-08",
              "apartment_id": [str(foreign), "x", "-1"]},
        follow_redirects=False,
    )
    assert bulk.status_code == 303
    assert stay_fee_filing.latest(foreign, "2026-08") is None
    page = client.get(bulk.headers["location"])
    assert "No period was ready to save." in page.text


def test_bulk_future_month_falls_back(host):
    client, owner_id, entity_id = host
    a = _property(owner_id, entity_id, "Bulk A")
    _stay(a, "bulk-a")
    token = _csrf(client, LIST_PATH)
    bulk = client.post(
        "/stay-fees/confirm-ready",
        data={"_csrf": token, "month": "2027-01", "return_to": "/stay-fees",
              "apartment_id": [str(a)]},
        follow_redirects=False,
    )
    assert bulk.status_code == 303


def test_job_audit_name_is_unchanged(host):
    client, owner_id, entity_id = host
    a = _property(owner_id, entity_id, "Bulk A")
    _stay(a, "bulk-a")
    filing_id = stay_fee_auto.confirm(_row(a), date(2026, 8, 1), date(2026, 9, 30))
    assert filing_id is not None
    hit = db.query_one("SELECT id FROM audit WHERE action = ? AND detail LIKE ?",
                       ("stay_fee_auto_finalize", f"apartment_id={a} %"))
    assert hit is not None
    db.execute("DELETE FROM audit WHERE id = ?", (hit["id"],))


def test_zip_holds_each_saved_pdf_byte_for_byte(host):
    import io
    import zipfile

    client, owner_id, entity_id = host
    a = _property(owner_id, entity_id, "Bulk A")
    b = _property(owner_id, entity_id, "Bulk B")
    _stay(a, "bulk-a")
    _stay(b, "bulk-b")
    token = _csrf(client, LIST_PATH)
    bulk = client.post(
        "/stay-fees/confirm-ready",
        data={"_csrf": token, "month": "2026-08", "return_to": "/stay-fees?month=2026-08",
              "apartment_id": [str(a), str(b)]},
        follow_redirects=False,
    )
    assert bulk.status_code == 303
    resp = client.get("/stay-fees/pdfs.zip?month=2026-08")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/zip")
    archive = zipfile.ZipFile(io.BytesIO(resp.content))
    names = archive.namelist()
    assert len(names) == 2
    for apartment_id in (a, b):
        member = next(name for name in names if name.endswith(f"-{apartment_id}.pdf"))
        single = client.get(f"/stay-fees/{apartment_id}/pdf?month=2026-08")
        assert single.status_code == 200
        assert archive.read(member) == single.content


def test_zip_without_saved_period_goes_back_to_the_list(host):
    client, owner_id, entity_id = host
    other_id = auth.create_account("stay-fee-bulk-other@example.test", "Other Demo", role="host",
                                   username="stay-fee-bulk-other")
    other_entity = db.insert("legal_entity", {
        "name": "Other Demo s.r.o.",
        "owner_user_id": other_id,
        "created_at": db.utcnow(),
    })
    foreign = _property(other_id, other_entity, "Foreign Flat")
    _stay(foreign, "bulk-foreign")
    assert stay_fee_auto.confirm(_row(foreign), date(2026, 8, 1), date(2026, 9, 30)) is not None
    a = _property(owner_id, entity_id, "Bulk A")
    _stay(a, "bulk-a")
    resp = client.get("/stay-fees/pdfs.zip?month=2026-08", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"].startswith("/stay-fees?month=2026-08")
