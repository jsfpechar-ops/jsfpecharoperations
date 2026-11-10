"""Brief 1082 (S5, decision 7b): the server draft of an unfinished guest form.

Storage, encryption, isolation between devices, the filing pin, deletion on
send, the stale-draft guard, the purge (owner rule), throttle and CSRF.
Synthetic data only.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import auth, claim, config, db, guest_draft, mail, reporting, retention, scheduler
from app.main import app
from app.routes import guest
from tests.conftest import login_as
from tests.test_guest_child_document import SIGNATURE

TOKEN = "draft1082tok"
ENTITY = "Draft 1082"
HOST = "draft1082-host"
APP_DIR = Path(__file__).resolve().parents[1] / "app"
DEVICE_A = guest_draft.key_hash("A" * 43)
DEVICE_B = guest_draft.key_hash("B" * 43)


def _account(username: str) -> int:
    row = db.query_one("SELECT id FROM user_account WHERE username = ?", (username,))
    if row:
        return int(row["id"])
    return auth.create_account(
        f"{username}@example.test", username.title(), role="host", username=username
    )


def _cleanup():
    apartment = db.query_one("SELECT * FROM apartment WHERE permalink_token = ?", (TOKEN,))
    db.execute("DELETE FROM rate_limit_event WHERE scope IN ('guest_draft', 'guest_save')")
    if not apartment:
        return
    stays = "(SELECT id FROM reservation WHERE apartment_id = ?)"
    db.execute(f"DELETE FROM guest_form_draft WHERE reservation_id IN {stays}", (apartment["id"],))
    db.execute(f"DELETE FROM guest WHERE reservation_id IN {stays}", (apartment["id"],))
    db.execute("DELETE FROM submission WHERE apartment_id = ?", (apartment["id"],))
    db.execute("DELETE FROM reservation WHERE apartment_id = ?", (apartment["id"],))
    db.execute("DELETE FROM apartment WHERE id = ?", (apartment["id"],))
    db.execute(
        "DELETE FROM legal_entity WHERE name = ? AND id NOT IN "
        "(SELECT legal_entity_id FROM apartment WHERE legal_entity_id IS NOT NULL)",
        (ENTITY,),
    )


def _stay(apartment_id: int, uid: str, days_to_end: int = 3, status: str = "active") -> int:
    now = db.utcnow()
    today = claim.prague_today()
    return db.insert(
        "reservation",
        {
            "apartment_id": apartment_id,
            "source": "airbnb",
            "uid": uid,
            "date_from": (today + timedelta(days=min(0, days_to_end - 1))).isoformat(),
            "date_to": (today + timedelta(days=days_to_end)).isoformat(),
            "status": status,
            "created_at": now,
            "updated_at": now,
        },
    )


def _seed(owner: str = HOST):
    db.init_db()
    _cleanup()
    owner_id = _account(owner)
    now = db.utcnow()
    entity_id = db.insert(
        "legal_entity", {"name": ENTITY, "owner_user_id": owner_id, "created_at": now}
    )
    apartment_id = db.insert(
        "apartment",
        {
            "legal_entity_id": entity_id,
            "owner_user_id": owner_id,
            "internal_name": "Draft flat",
            "uby_name": "Draft Facility",
            "permalink_token": TOKEN,
            "permalink_window_days": 14,
            "default_purpose": "10",
            "passport_photo_policy": "off",
            "automation_mode": "manual",
            "active": 1,
            "created_at": now,
        },
    )
    return apartment_id, _stay(apartment_id, "draft-1082-stay")


def _payload(**overrides):
    data = {
        "surname": "Smith",
        "first_name": "John Paul",
        "birth_date": "1.1.1990",
        "nationality": "GBR",
        "doc_number": "SYN1082P1",
        "res_street": "Baker Street 221B",
        "res_city": "London",
        "res_country": "GBR",
        "purpose": "10",
        "party_size": "2",
        "signature": SIGNATURE,
        "legal_ack": "1",
    }
    data.update(overrides)
    return data


def _count(reservation_id=None) -> int:
    if reservation_id is None:
        return int(db.query_one("SELECT COUNT(*) AS n FROM guest_form_draft")["n"])
    return int(
        db.query_one(
            "SELECT COUNT(*) AS n FROM guest_form_draft WHERE reservation_id = ?", (reservation_id,)
        )["n"]
    )


def _row(reservation_id: int):
    return db.query_one("SELECT * FROM guest_form_draft WHERE reservation_id = ?", (reservation_id,))


def _stored(reservation_id: int) -> dict:
    return json.loads(db.decrypt_field(_row(reservation_id)["fields_enc"]))


def _age(reservation_id: int, days: int) -> None:
    stamp = (datetime.now(timezone.utc) - timedelta(days=days)).replace(microsecond=0).isoformat()
    db.execute("UPDATE guest_form_draft SET updated_at = ? WHERE reservation_id = ?", (stamp, reservation_id))


def _draft(client, reservation_id: int, **data):
    data.setdefault("draft_owned", "0")
    return client.post(f"/l/{TOKEN}/{reservation_id}/draft?lang=en", data=data)


def _new(client, reservation_id: int):
    return client.get(f"/l/{TOKEN}/{reservation_id}/new?lang=en")


def _save(client, reservation_id: int, **overrides):
    return client.post(
        f"/l/{TOKEN}/{reservation_id}/save?lang=en", data=_payload(**overrides), follow_redirects=False
    )


@pytest.fixture
def stay(monkeypatch):
    monkeypatch.setattr(mail, "mail_enabled", lambda: False)
    apartment_id, reservation_id = _seed()
    try:
        yield apartment_id, reservation_id
    finally:
        _cleanup()


@pytest.fixture
def contexts(monkeypatch):
    seen = []
    original = guest.render_guest

    def render(request, template, context, *args, **kwargs):
        seen.append(context)
        return original(request, template, context, *args, **kwargs)

    monkeypatch.setattr(guest, "render_guest", render)
    return seen


# --- a: save and load -------------------------------------------------------

def test_save_then_load_returns_the_cleaned_fields(stay):
    _apartment_id, rid = stay
    assert guest_draft.save(rid, DEVICE_A, 0, 0, {"surname": "  Zzdraft ", "doc_number": "SYN1082A"})
    assert guest_draft.load(rid, DEVICE_A, 0, 0) == {"surname": "Zzdraft", "doc_number": "SYN1082A"}


def test_a_second_save_updates_the_same_row(stay):
    _apartment_id, rid = stay
    guest_draft.save(rid, DEVICE_A, 0, 0, {"surname": "Zzone"})
    _age(rid, 1)
    before = _row(rid)
    guest_draft.save(rid, DEVICE_A, 0, 0, {"surname": "Zztwo"})
    after = _row(rid)
    assert _count(rid) == 1
    assert after["id"] == before["id"] and after["created_at"] == before["created_at"]
    assert after["updated_at"] > before["updated_at"]
    assert _stored(rid) == {"surname": "Zztwo"}


def test_only_allowlisted_fields_are_kept_and_values_are_cut(stay):
    _apartment_id, rid = stay
    guest_draft.save(
        rid,
        DEVICE_A,
        0,
        0,
        {
            "surname": "Z" * 200,
            "passport_photo": "photo",
            "signature": SIGNATURE,
            "legal_ack": "1",
            "stay_from": "2026-01-01",
            "guest_id": "7",
            "_csrf": "token",
        },
    )
    assert _stored(rid) == {"surname": "Z" * 60}
    assert guest_draft.load(rid, DEVICE_A, 0, 0) == {"surname": "Z" * 60}


def test_party_size_and_nationality_alone_store_nothing(stay):
    _apartment_id, rid = stay
    assert guest_draft.save(rid, DEVICE_A, 0, 0, {"party_size": "2", "nationality": "GBR"}) is False
    assert _count(rid) == 0
    guest_draft.save(rid, DEVICE_A, 0, 0, {"surname": "Zzdraft"})
    assert guest_draft.save(rid, DEVICE_A, 0, 0, {"party_size": "2"}) is False
    assert _count(rid) == 0


# --- b: encrypted at rest ---------------------------------------------------

def test_the_draft_is_encrypted_at_rest(stay):
    _apartment_id, rid = stay
    guest_draft.save(rid, DEVICE_A, 0, 0, {"doc_number": "SYN1082X", "surname": "Zzdraft"})
    row = _row(rid)
    for column in row.keys():
        assert "SYN1082X" not in str(row[column]), column
        assert "Zzdraft" not in str(row[column]), column
    assert json.loads(db.decrypt_field(row["fields_enc"]))["doc_number"] == "SYN1082X"


# --- c: isolation -----------------------------------------------------------

def test_another_device_another_stay_or_another_generation_gets_nothing(stay):
    apartment_id, rid = stay
    other = _stay(apartment_id, "draft-1082-other")
    guest_draft.save(rid, DEVICE_A, 3, 0, {"surname": "Zzdraft"})
    assert guest_draft.load(rid, DEVICE_B, 3, 0) is None
    assert guest_draft.load(other, DEVICE_A, 3, 0) is None
    assert _count(rid) == 1
    assert guest_draft.load(rid, DEVICE_A, 4, 0) is None
    assert _count(rid) == 0


def test_a_draft_is_restored_only_on_the_device_that_wrote_it(stay, contexts):
    _apartment_id, rid = stay
    device_a, device_b = TestClient(app), TestClient(app)
    posted = _draft(device_a, rid, surname="Zzdraftsur", first_name="Zzdraftfirst", doc_number="SYN1082C")
    assert posted.status_code == 204, posted.text
    header = posted.headers["set-cookie"].lower()
    assert "ubyhost_draft=" in header and "httponly" in header and "samesite=lax" in header
    key = device_a.cookies.get(guest.DRAFT_COOKIE)
    row = _row(rid)
    assert row["device_key_hash"] == guest_draft.key_hash(key)
    assert all(key not in str(row[column]) for column in row.keys())

    theirs = _new(device_b, rid)
    assert theirs.status_code == 200
    for value in ("Zzdraftsur", "Zzdraftfirst", "SYN1082C"):
        assert value not in theirs.text
    assert contexts[-1]["draft_restored"] is False
    assert device_b.cookies.get(guest.DRAFT_COOKIE) is None

    mine = _new(device_a, rid)
    for value in ("Zzdraftsur", "Zzdraftfirst", "SYN1082C"):
        assert f'value="{value}"' in mine.text
    assert contexts[-1]["draft_restored"] is True
    assert contexts[-1]["draft_url"].startswith(f"/l/{TOKEN}/{rid}/draft")
    assert contexts[-1]["draft_owned"] == 0
    # Every save renews the same key for 7 more days (review item 3).
    again = _draft(device_a, rid, surname="Zzdraftsur")
    renewed = again.headers.get("set-cookie", "")
    assert f"ubyhost_draft={key}" in renewed
    assert f"max-age={guest.DRAFT_COOKIE_MAX_AGE}" in renewed.lower()
    assert device_a.cookies.get(guest.DRAFT_COOKIE) == key
    # Nothing stored: no cookie.
    empty = _draft(TestClient(app), rid, party_size="2")
    assert empty.status_code == 204 and "ubyhost_draft" not in empty.headers.get("set-cookie", "")


# --- d: filing never reads drafts ------------------------------------------

def test_only_the_draft_files_name_the_table_or_the_module():
    allowed = {
        "guest_draft.py",
        "routes/guest.py",
        "retention.py",
        "scheduler.py",
        "migrations/0042_guest_form_draft.sql",
    }
    naming = set()
    for path in APP_DIR.rglob("*"):
        if not path.is_file() or "__pycache__" in path.parts:
            continue
        body = path.read_bytes()
        if b"guest_form_draft" in body or b"guest_draft" in body:
            naming.add(path.relative_to(APP_DIR).as_posix())
    assert naming == allowed
    for name in ("reporting.py", "worker.py", "housebook.py", "deadlines.py", "filing_watchdog.py", "stay_fee_filing.py"):
        assert name not in naming
    assert not any(name.startswith("ubyport/") for name in naming)


def test_a_stay_with_only_a_draft_files_nothing(stay):
    apartment_id, rid = stay
    fields = {name: value for name, value in _payload().items() if name in guest_draft.DRAFT_FIELDS}
    assert guest_draft.save(rid, DEVICE_A, 0, 0, fields)
    reservation = db.query_one("SELECT * FROM reservation WHERE id = ?", (rid,))
    assert reporting.reservation_progress(reservation)["filled"] == 0
    reporting.submit_stay_if_complete(apartment_id, rid)
    assert db.query_one("SELECT COUNT(*) AS n FROM submission WHERE apartment_id = ?", (apartment_id,))["n"] == 0
    assert db.query_one("SELECT COUNT(*) AS n FROM guest WHERE reservation_id = ?", (rid,))["n"] == 0
    assert _count(rid) == 1


# --- e: a sent form deletes the draft --------------------------------------

def test_sending_the_form_deletes_the_draft(stay, contexts):
    _apartment_id, rid = stay
    device = TestClient(app)
    assert _draft(device, rid, surname="Zzdraftsur", visa_number="SYNVISA1082").status_code == 204
    assert _count(rid) == 1
    saved = _save(device, rid)
    assert saved.status_code == 303, saved.text
    assert _count(rid) == 0
    page = _new(device, rid)
    assert "Zzdraftsur" not in page.text and "SYNVISA1082" not in page.text
    assert contexts[-1]["draft_restored"] is False

    # A draft written after the save that is the sent guest again: dropped.
    assert _draft(device, rid, surname="Zzagain", doc_number="syn1082p1", draft_owned="1").status_code == 204
    assert _count(rid) == 0
    # The read guard still holds for a row that got in some other way.
    guest_draft.save(
        rid, guest_draft.key_hash(device.cookies.get(guest.DRAFT_COOKIE)), 0, 1,
        {"surname": "Zzagain", "doc_number": "syn1082p1"},
    )
    assert _count(rid) == 1
    page = _new(device, rid)
    assert "Zzagain" not in page.text
    assert contexts[-1]["draft_restored"] is False
    assert _count(rid) == 0


# --- f: a late autosave never fills the next person's form ------------------

def test_a_late_autosave_of_the_sent_page_is_not_restored(stay, contexts):
    _apartment_id, rid = stay
    device = TestClient(app)
    person = {name: value for name, value in _payload().items() if name in guest_draft.DRAFT_FIELDS}
    assert _draft(device, rid, **person).status_code == 204
    assert _save(device, rid).status_code == 303
    assert _count(rid) == 0

    late = _draft(device, rid, surname="Zzlatesur", doc_number="SYN1082LATE", draft_owned="0")
    assert late.status_code == 204
    assert _row(rid)["owned_count"] == 0
    page = _new(device, rid)
    assert "Zzlatesur" not in page.text and "SYN1082LATE" not in page.text
    assert contexts[-1]["draft_restored"] is False
    assert contexts[-1]["draft_owned"] == 1
    assert _count(rid) == 0

    assert _draft(device, rid, surname="Zznextsur", draft_owned="1").status_code == 204
    page = _new(device, rid)
    assert 'value="Zznextsur"' in page.text
    assert contexts[-1]["draft_restored"] is True


@pytest.mark.parametrize("posted, stored", [("-5", 0), ("abc", 0), ("999", 999)])
def test_the_posted_owned_count_is_clamped(stay, posted, stored):
    _apartment_id, rid = stay
    assert _draft(TestClient(app), rid, surname="Zzdraftsur", draft_owned=posted).status_code == 204
    assert _row(rid)["owned_count"] == stored


# --- g: purge (owner rule) --------------------------------------------------

def _purge_fixture(apartment_id: int) -> dict:
    stays = {
        "old": _stay(apartment_id, "draft-1082-old", days_to_end=3),
        "recent_ends_tomorrow": _stay(apartment_id, "draft-1082-recent", days_to_end=1),
        "ended_yesterday": _stay(apartment_id, "draft-1082-ended", days_to_end=-1),
        "ends_today": _stay(apartment_id, "draft-1082-today", days_to_end=0),
        "cancelled": _stay(apartment_id, "draft-1082-cancelled", days_to_end=3, status="cancelled"),
    }
    for reservation_id in stays.values():
        guest_draft.save(reservation_id, DEVICE_A, 0, 0, {"surname": "Zzdraft"})
    _age(stays["old"], 8)
    _age(stays["recent_ends_tomorrow"], 6)
    return stays


def test_purge_applies_the_owner_rule_with_autopurge_off(stay, monkeypatch):
    apartment_id, rid = stay
    monkeypatch.setattr(config, "RETENTION_AUTOPURGE", False)
    stays = _purge_fixture(apartment_id)
    guest_draft.save(rid, DEVICE_A, 0, 0, {"surname": "Zzdraft"})
    assert guest_draft.purge(claim.prague_today()) == 3
    left = {name: _count(reservation_id) for name, reservation_id in stays.items()}
    assert left == {
        "old": 0,
        "recent_ends_tomorrow": 1,
        "ended_yesterday": 0,
        "ends_today": 1,
        "cancelled": 0,
    }
    assert _count(rid) == 1


def test_the_photo_sweep_runs_the_purge(stay, monkeypatch):
    _apartment_id, rid = stay
    monkeypatch.setattr(config, "RETENTION_AUTOPURGE", False)
    guest_draft.save(rid, DEVICE_A, 0, 0, {"surname": "Zzdraft"})
    _age(rid, 8)
    scheduler._job_photo_sweep()
    assert _count(rid) == 0


def test_workspace_deletion_removes_its_drafts(monkeypatch):
    monkeypatch.setattr(mail, "mail_enabled", lambda: False)
    apartment_id, rid = _seed(owner="draft1082-gone")
    try:
        guest_draft.save(rid, DEVICE_A, 0, 0, {"surname": "Zzdraft"})
        owner_id = db.query_one("SELECT owner_user_id FROM apartment WHERE id = ?", (apartment_id,))["owner_user_id"]
        retention._delete_workspace(int(owner_id))
        assert _count(rid) == 0
        assert db.query_one("SELECT id FROM reservation WHERE id = ?", (rid,)) is None
    finally:
        _cleanup()


def test_load_deletes_a_stale_row(stay):
    _apartment_id, rid = stay
    guest_draft.save(rid, DEVICE_A, 0, 0, {"surname": "Zzdraft"})
    _age(rid, 8)
    assert guest_draft.load(rid, DEVICE_A, 0, 0) is None
    assert _count(rid) == 0


def test_the_purge_is_not_a_retention_step():
    assert "guest_draft" not in repr(retention.STEPS)


# --- h: throttle and CSRF ---------------------------------------------------

def test_a_draft_post_without_the_csrf_token_is_refused_like_a_save(stay):
    _apartment_id, rid = stay
    device = TestClient(app)
    _new(device, rid)
    save = device.post(f"/l/{TOKEN}/{rid}/save?lang=en", data=_payload(_csrf=""), follow_redirects=False)
    draft = _draft(device, rid, surname="Zzdraftsur", _csrf="")
    assert draft.status_code == save.status_code
    assert draft.status_code not in (200, 204, 303)
    assert _count(rid) == 0


def test_the_121st_write_in_the_window_is_refused(stay):
    _apartment_id, rid = stay
    device = TestClient(app)
    for _ in range(guest.GUEST_DRAFT_MAX_WRITES):
        assert _draft(device, rid, surname="Zzkept").status_code == 204
    over = _draft(device, rid, surname="Zzrefused")
    assert over.status_code == 429
    assert over.text == ""
    assert _stored(rid) == {"surname": "Zzkept"}


def test_a_body_over_16_kb_is_refused(stay):
    _apartment_id, rid = stay
    answer = _draft(TestClient(app), rid, surname="Z" * 17000)
    assert answer.status_code == 413
    assert _count(rid) == 0


# --- i: no draft on the other surfaces --------------------------------------

def test_editing_a_saved_guest_restores_nothing(stay, contexts):
    _apartment_id, rid = stay
    device = TestClient(app)
    assert _save(device, rid).status_code == 303
    guest_id = db.query_one("SELECT id FROM guest WHERE reservation_id = ?", (rid,))["id"]
    assert _draft(device, rid, surname="Zzdraftsur", draft_owned="1").status_code == 204
    page = device.get(f"/l/{TOKEN}/{rid}/edit/{guest_id}?lang=en")
    assert page.status_code == 200
    assert "Zzdraftsur" not in page.text
    assert "draft_url" not in contexts[-1] and not contexts[-1].get("draft_restored")
    assert _count(rid) == 1


def test_a_post_with_a_guest_id_stores_nothing(stay):
    _apartment_id, rid = stay
    answer = _draft(TestClient(app), rid, surname="Zzdraftsur", guest_id="5")
    assert answer.status_code == 204
    assert "set-cookie" not in answer.headers or "ubyhost_draft" not in answer.headers["set-cookie"]
    assert _count(rid) == 0


def test_the_host_preview_has_no_draft(stay, contexts):
    _apartment_id, rid = stay
    host = TestClient(app)
    signed_in = login_as(host, HOST, url="/login?lang=en", remember=True, follow_redirects=False)
    assert signed_in.status_code == 303, signed_in.text
    answer = _draft(host, rid, surname="Zzdraftsur")
    assert answer.status_code == 204
    assert _count(rid) == 0
    assert host.cookies.get(guest.DRAFT_COOKIE) is None
    page = _new(host, rid)
    assert page.status_code == 200
    assert "draft_url" not in contexts[-1] and contexts[-1]["draft_restored"] is False


# --- review, attempt 2 ------------------------------------------------------

def test_an_undecryptable_draft_is_deleted_and_the_form_still_opens(stay, contexts):
    _apartment_id, rid = stay
    device = TestClient(app)
    assert _draft(device, rid, surname="Zzdraftsur").status_code == 204
    db.execute("UPDATE guest_form_draft SET fields_enc = ? WHERE reservation_id = ?", ("gAAAAA-not-a-token", rid))
    page = _new(device, rid)
    assert page.status_code == 200
    assert contexts[-1]["draft_restored"] is False
    assert _count(rid) == 0

    guest_draft.save(rid, DEVICE_A, 0, 0, {"surname": "Zzdraft"})
    token = _row(rid)["fields_enc"]
    db.execute(
        "UPDATE guest_form_draft SET fields_enc = ? WHERE reservation_id = ?",
        (token[:-6] + ("AAAAAA" if not token.endswith("AAAAAA") else "BBBBBB"), rid),
    )
    assert guest_draft.load(rid, DEVICE_A, 0, 0) is None
    assert _count(rid) == 0


def test_a_stay_past_check_out_takes_no_draft(stay):
    apartment_id, _rid = stay
    ended = _stay(apartment_id, "draft-1082-ended", days_to_end=-1)
    today = _stay(apartment_id, "draft-1082-today", days_to_end=0)
    answer = _draft(TestClient(app), ended, surname="Zzdraftsur")
    if answer.status_code == 204:
        assert "ubyhost_draft" not in answer.headers.get("set-cookie", "")
    else:
        # The link no longer opens an ended stay at all.
        assert answer.status_code == 404
    assert _count(ended) == 0
    assert _draft(TestClient(app), today, surname="Zzdraftsur").status_code == 204
    assert _count(today) == 1


def test_the_route_refuses_past_check_out_even_when_the_stay_resolves(stay, monkeypatch):
    apartment_id, rid = stay
    real_today = claim.prague_today()
    monkeypatch.setattr(claim, "prague_today", lambda: real_today + timedelta(days=4))
    monkeypatch.setattr(
        guest, "_reservation_for_guest",
        lambda apartment, reservation_id, request=None: db.query_one(
            "SELECT * FROM reservation WHERE id = ?", (reservation_id,)
        ),
    )
    monkeypatch.setattr(guest, "_require_claim_session", lambda *args, **kwargs: None)
    answer = _draft(TestClient(app), rid, surname="Zzdraftsur")
    assert answer.status_code == 204
    assert "ubyhost_draft" not in answer.headers.get("set-cookie", "")
    assert _count(rid) == 0


def test_a_stay_keeps_at_most_twenty_drafts_and_drops_the_oldest(stay):
    _apartment_id, rid = stay
    hashes = [guest_draft.key_hash(f"device-{n:02d}" + "x" * 40) for n in range(guest_draft.MAX_PER_RESERVATION + 3)]
    for n, device_hash in enumerate(hashes):
        guest_draft.save(rid, device_hash, 0, 0, {"surname": f"Zz{n}"})
        stamp = (datetime.now(timezone.utc) - timedelta(minutes=100 - n)).replace(microsecond=0).isoformat()
        db.execute("UPDATE guest_form_draft SET updated_at = ? WHERE device_key_hash = ?", (stamp, device_hash))
    guest_draft.save(rid, hashes[-1], 0, 0, {"surname": "Zzlast"})
    assert _count(rid) == guest_draft.MAX_PER_RESERVATION
    for gone in hashes[:3]:
        assert guest_draft.load(rid, gone, 0, 0) is None
    assert guest_draft.load(rid, hashes[3], 0, 0) == {"surname": "Zz3"}
    assert guest_draft.load(rid, hashes[-1], 0, 0) == {"surname": "Zzlast"}
    # Posts without a cookie cannot grow the table past the cap.
    for n in range(5):
        assert _draft(TestClient(app), rid, surname=f"Zzorphan{n}").status_code == 204
    assert _count(rid) == guest_draft.MAX_PER_RESERVATION


def test_sending_a_guest_on_another_stay_keeps_this_stays_draft(stay, contexts):
    apartment_id, rid = stay
    other = _stay(apartment_id, "draft-1082-other")
    device = TestClient(app)
    assert _draft(device, rid, surname="Zzkeepsur", draft_owned="0").status_code == 204
    assert _save(device, other, doc_number="SYN1082OTH", surname="Otherstay").status_code == 303
    assert _count(rid) == 1
    page = _new(device, rid)
    assert 'value="Zzkeepsur"' in page.text
    assert contexts[-1]["draft_restored"] is True
    assert contexts[-1]["draft_owned"] == 0
    _new(device, other)
    assert contexts[-1]["draft_owned"] == 1


def test_the_owned_count_has_no_limit_of_forty(stay):
    _apartment_id, rid = stay
    assert not hasattr(guest_draft, "MAX_OWNED")
    assert guest_draft.clamp_owned(41) == 41
    guest_draft.save(rid, DEVICE_A, 0, 41, {"surname": "Zzdraft"})
    assert guest_draft.load(rid, DEVICE_A, 0, 40) is None
    guest_draft.save(rid, DEVICE_A, 0, 41, {"surname": "Zzdraft"})
    assert guest_draft.load(rid, DEVICE_A, 0, 41) == {"surname": "Zzdraft"}
    assert guest_draft.clamp_owned("9" * 40) == 2**31 - 1


# --- review, attempt 3 ------------------------------------------------------

def test_an_autosave_landing_after_the_save_stores_nothing(stay):
    _apartment_id, rid = stay
    device = TestClient(app)
    person = {name: value for name, value in _payload().items() if name in guest_draft.DRAFT_FIELDS}
    assert _draft(device, rid, **person).status_code == 204
    assert _count(rid) == 1
    assert _save(device, rid).status_code == 303
    assert _count(rid) == 0
    # The late autosave of the sent page: same person, old count.
    late = _draft(device, rid, **person)
    assert late.status_code == 204
    assert "ubyhost_draft" not in late.headers.get("set-cookie", "")
    assert _count(rid) == 0
    # Same name and birth date without the document number: also nothing.
    partial = {name: person[name] for name in ("first_name", "surname", "birth_date")}
    assert _draft(device, rid, **partial).status_code == 204
    assert _count(rid) == 0
    # A device without the cookie cannot store the sent person either.
    assert _draft(TestClient(app), rid, doc_number=person["doc_number"].lower()).status_code == 204
    assert _count(rid) == 0
    # The next person on the same phone is still saved.
    assert _draft(device, rid, surname="Zznextsur", draft_owned="1").status_code == 204
    assert _stored(rid) == {"surname": "Zznextsur"}
    # ... and a match replaces nothing: the older row of this device goes.
    assert _draft(device, rid, **person).status_code == 204
    assert _count(rid) == 0


def test_the_cap_evicts_the_oldest_row_but_never_the_current_device(stay):
    _apartment_id, rid = stay
    cap = guest_draft.MAX_PER_RESERVATION
    others = [guest_draft.key_hash(f"other-{n:02d}" + "y" * 40) for n in range(cap)]
    future = datetime.now(timezone.utc) + timedelta(hours=1)
    for n, device_hash in enumerate(others):
        guest_draft.save(rid, device_hash, 0, 0, {"surname": f"Zz{n}"})
        stamp = (future + timedelta(minutes=n)).replace(microsecond=0).isoformat()
        db.execute("UPDATE guest_form_draft SET updated_at = ? WHERE device_key_hash = ?", (stamp, device_hash))
    assert _count(rid) == cap
    # The current device's row is now the oldest by updated_at, and it stays.
    guest_draft.save(rid, DEVICE_A, 0, 0, {"surname": "Zzcurrent"})
    assert _count(rid) == cap
    assert guest_draft.load(rid, DEVICE_A, 0, 0) == {"surname": "Zzcurrent"}
    # The row that went is the oldest of the others.
    assert db.query_one(
        "SELECT id FROM guest_form_draft WHERE reservation_id = ? AND device_key_hash = ?", (rid, others[0])
    ) is None
    for kept in others[1:]:
        assert db.query_one(
            "SELECT id FROM guest_form_draft WHERE reservation_id = ? AND device_key_hash = ?", (rid, kept)
        ) is not None
