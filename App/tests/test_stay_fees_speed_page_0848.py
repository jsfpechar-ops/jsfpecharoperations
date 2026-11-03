"""0848: bulk confirm and PDF box, plus the copy-setup card on /stay-fees."""
from __future__ import annotations

import re
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app import auth, claim, db, stay_fee_filing
from app.main import app
from tests.conftest import login_as

SIGNATURE = "data:image/png;base64,AAAA"
PREFIX = "stay-fee-speed-%"
LIST_PATH = "/stay-fees?month=2026-08"


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
    owner_id = auth.create_account("stay-fee-speed-owner@example.test", "Speed Demo", role="host",
                                   username="stay-fee-speed-owner")
    entity_id = db.insert("legal_entity", {
        "name": "Speed Demo s.r.o.",
        "owner_user_id": owner_id,
        "created_at": db.utcnow(),
    })
    client = TestClient(app)
    assert login_as(client, "stay-fee-speed-owner", url="/login?lang=en",
                    follow_redirects=False).status_code == 303
    try:
        yield client, owner_id, entity_id
    finally:
        _cleanup()


def _property(owner_id, entity_id, name, rate=50, obec=None):
    apartment_id = db.insert("apartment", {
        "internal_name": name,
        "owner_user_id": owner_id,
        "legal_entity_id": entity_id,
        "stay_fee_rate_czk": rate,
        "stay_fee_vs": "123456" if rate else None,
        "stay_fee_authority_name": "Městský úřad" if rate else None,
        "stay_fee_council_account": "19-2000781379/0800" if rate else None,
        "stay_fee_council_iban": "CZ3008000000192000781379" if rate else None,
        "created_at": db.utcnow(),
    })
    if obec:
        db.execute("UPDATE apartment SET addr_obec = ? WHERE id = ?", (obec, apartment_id))
    return apartment_id


def _stay(apartment_id, uid):
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
        "signature_png": SIGNATURE,
        "created_at": now,
        "updated_at": now,
    })


def _csrf(client, path: str) -> str:
    page = client.get(path)
    assert page.status_code == 200
    return page.text.split('name="csrf-token" content="')[1].split('"')[0]


def test_two_ready_show_one_confirm_all(host):
    client, owner_id, entity_id = host
    a = _property(owner_id, entity_id, "Speed A")
    b = _property(owner_id, entity_id, "Speed B")
    _stay(a, "speed-a")
    _stay(b, "speed-b")
    page = client.get(LIST_PATH)
    assert page.status_code == 200
    html = page.text
    assert html.count('action="/stay-fees/confirm-ready"') == 1
    ids = re.findall(r'name="apartment_id" value="(\d+)"', html)
    assert sorted(ids) == sorted([str(a), str(b)])
    assert "Confirm all ready (2)" in html
    assert "data-confirm" in html
    assert "/stay-fees/pdfs.zip" not in html


def test_one_ready_shows_no_bulk_box(host):
    client, owner_id, entity_id = host
    a = _property(owner_id, entity_id, "Speed A")
    _property(owner_id, entity_id, "Speed B", rate=0)
    _stay(a, "speed-one")
    page = client.get(LIST_PATH)
    assert page.status_code == 200
    assert "fee-bulk" not in page.text


def test_two_saved_show_download_all(host):
    client, owner_id, entity_id = host
    a = _property(owner_id, entity_id, "Speed A")
    b = _property(owner_id, entity_id, "Speed B")
    _stay(a, "speed-sa")
    _stay(b, "speed-sb")
    token = _csrf(client, LIST_PATH)
    sealed = client.post(
        "/stay-fees/confirm-ready",
        data={"_csrf": token, "month": "2026-08", "return_to": LIST_PATH,
              "apartment_id": [str(a), str(b)]},
        follow_redirects=False,
    )
    assert sealed.status_code == 303
    page = client.get(LIST_PATH)
    assert page.status_code == 200
    html = page.text
    assert 'href="/stay-fees/pdfs.zip?month=2026-08"' in html
    assert "Download all PDFs (2)" in html
    assert 'action="/stay-fees/confirm-ready"' not in html


def test_unset_sibling_shows_the_copy_card(host):
    client, owner_id, entity_id = host
    source = _property(owner_id, entity_id, "Speed Source", rate=50, obec="Praha 3")
    target = _property(owner_id, entity_id, "Speed Target", rate=0, obec="Praha 3")
    far = _property(owner_id, entity_id, "Speed Far", rate=0, obec="Brno")
    page = client.get(LIST_PATH)
    assert page.status_code == 200
    html = page.text
    assert f'id="fee-copy-{target}"' in html
    assert "123456" in html
    assert "Use this setup" in html
    assert f'id="fee-copy-{far}"' not in html
    assert f'id="fee-copy-{source}"' not in html


def test_bulk_box_posts_end_to_end(host):
    client, owner_id, entity_id = host
    a = _property(owner_id, entity_id, "Speed A")
    b = _property(owner_id, entity_id, "Speed B")
    _stay(a, "speed-e2e-a")
    _stay(b, "speed-e2e-b")
    page = client.get(LIST_PATH)
    assert page.status_code == 200
    ids = re.findall(r'name="apartment_id" value="(\d+)"', page.text)
    token = _csrf(client, LIST_PATH)
    posted = client.post(
        "/stay-fees/confirm-ready",
        data={"_csrf": token, "month": "2026-08", "return_to": LIST_PATH,
              "apartment_id": ids},
        follow_redirects=False,
    )
    assert posted.status_code == 303
    assert stay_fee_filing.latest(a, "2026-08") is not None
    assert stay_fee_filing.latest(b, "2026-08") is not None
