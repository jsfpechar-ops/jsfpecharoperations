"""Cleaning operations, token boundaries and permanent-code retry contracts."""
from __future__ import annotations

import secrets
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app import auth, cleaning, cleaning_codes, cleaning_i18n, config, db, ttlock
from app.main import app
from tests.conftest import login_as


@pytest.fixture
def workspace(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "cleaning.sqlite3")
    monkeypatch.setattr(cleaning, "today", lambda: date(2026, 10, 16))
    monkeypatch.setattr(auth, "staging_no_login", lambda: False)
    db.init_db()
    owner = auth.create_account("cleaner-owner@example.test", "Schedule owner", username="cleaner-owner", role="host")
    other = auth.create_account("cleaner-other@example.test", "Other owner", username="cleaner-other", role="host")
    now = db.utcnow()

    def home(name, user):
        return db.insert("apartment", {
            "owner_user_id": user, "internal_name": name, "active": 1, "created_at": now,
            "automation_mode": "manual", "checkin_hour": 15, "checkout_hour": 11,
        })
    homes = [home("Riverside / 4", owner), home("Garden / 2", owner)]
    foreign = home("Other workspace", other)
    client = TestClient(app)
    assert login_as(client, "cleaner-owner", url="/login?lang=en", follow_redirects=False).status_code == 303
    yield {"owner": owner, "other": other, "homes": homes, "home": homes[0], "foreign": foreign, "client": client}


def stay(home, start="2026-10-17", end="2026-10-20", **extra):
    return db.insert("reservation", {
        "apartment_id": home, "uid": secrets.token_hex(16),
        "date_from": start, "date_to": end, "status": "active", "source": "manual",
        "created_at": db.utcnow(), "updated_at": db.utcnow(), **extra,
    })


def payload(ws, **params):
    return ws["client"].get("/cleaning/schedule", params={
        "from": "2026-10-16", "to": "2026-11-15", **params,
    })


def event(ws, reservation_id):
    cleaning.reconcile(ws["owner"])
    return dict(db.query_one("SELECT * FROM cleaning_event WHERE source_reservation_id = ?", (reservation_id,)))


def lock_setup(ws, monkeypatch):
    monkeypatch.setattr(ttlock, "enabled", lambda: True)
    monkeypatch.setattr(ttlock, "allowed_for", lambda owner: owner == ws["owner"])
    account_id = db.insert("lock_account", {
        "owner_user_id": ws["owner"], "provider": "ttlock", "username": "fictional-api-user",
        "status": "ok", "locks_json": '[{"lock_id":"123"}]', "created_at": db.utcnow(), "updated_at": db.utcnow(),
    })
    db.update("apartment", ws["home"], {"lock_provider": "ttlock", "lock_id": "123"})
    return account_id, dict(db.query_one("SELECT * FROM apartment WHERE id = ?", (ws["home"],)))


def test_auto_checkout_is_persisted_once_and_has_next_arrival_beyond_loaded_range(workspace):
    ws = workspace
    booking = stay(ws["home"], "2026-10-10", "2026-10-16", summary="Private guest", host_note="private internal note")
    stay(ws["home"], "2026-12-01", "2026-12-04")
    assert payload(ws).status_code == 200
    data = payload(ws).json()
    item = next(x for x in data["cleanings"] if x["date"] == "2026-10-16")
    assert item["checkoutTime"] == "11:00"
    assert item["nextArrival"] == "2026-12-01"
    assert item["checkinTime"] == "15:00"
    assert db.query_one("SELECT COUNT(*) AS n FROM cleaning_event WHERE source_reservation_id = ?", (booking,))["n"] == 1
    assert "Private guest" not in str(data)
    assert "private internal note" not in str(data)


def test_booking_changes_follow_until_host_moves_date_and_stale_edits_fail(workspace):
    ws = workspace
    booking = stay(ws["home"])
    original = event(ws, booking)
    db.update("reservation", booking, {"date_to": "2026-10-21"})
    changed = event(ws, booking)
    assert changed["scheduled_date"] == "2026-10-21"
    with pytest.raises(ValueError, match="changed"):
        cleaning.save_event(ws["home"], {**original, "notes": "stale"}, original)
    cleaning.save_event(ws["home"], {**changed, "scheduled_date": "2026-10-22", "notes": "Fresh towels"}, changed)
    db.update("reservation", booking, {"date_to": "2026-10-23"})
    moved = event(ws, booking)
    assert moved["scheduled_date"] == "2026-10-22"
    assert payload(ws).json()["cleanings"][0]["conflict"]
    assert db.decrypt_field(moved["notes_enc"]) == "Fresh towels"
    assert "Fresh towels" not in moved["notes_enc"]


def test_notes_edit_preserves_automatic_date_following(workspace):
    ws = workspace
    booking = stay(ws["home"])
    row = event(ws, booking)
    cleaning.save_event(ws["home"], {**row, "notes": "Only notes changed"}, row)
    db.update("reservation", booking, {"date_to": "2026-10-22"})
    assert event(ws, booking)["scheduled_date"] == "2026-10-22"


def test_dismissal_survives_reimport_cancel_and_restore_without_changing_booking(workspace):
    ws = workspace
    booking = stay(ws["home"])
    before = dict(db.query_one("SELECT * FROM reservation WHERE id = ?", (booking,)))
    row = event(ws, booking)
    response = ws["client"].post(f"/cleaning/events/{row['id']}/delete", data={"revision": row["revision"]})
    assert response.status_code == 200
    assert dict(db.query_one("SELECT * FROM reservation WHERE id = ?", (booking,))) == before
    for status in ("cancelled", "active", "active"):
        db.update("reservation", booking, {"status": status})
        cleaning.reconcile(ws["owner"])
    assert event(ws, booking)["state"] == "dismissed"
    assert payload(ws).json()["cleanings"] == []


def test_cancelled_and_archived_stays_disappear_but_manual_cleaning_remains(workspace):
    ws = workspace
    booking = stay(ws["home"])
    event(ws, booking)
    cleaning.save_event(ws["home"], {"scheduled_date": "2026-10-19", "notes": "Intermediate cleaning"})
    db.update("reservation", booking, {"status": "cancelled"})
    assert len(payload(ws).json()["cleanings"]) == 1
    assert payload(ws).json()["cleanings"][0]["origin"] == "manual"
    db.update("reservation", booking, {"status": "active"})
    assert len(payload(ws).json()["cleanings"]) == 2
    db.update("reservation", booking, {"archived_at": db.utcnow()})
    assert len(payload(ws).json()["cleanings"]) == 1


def test_readable_list_and_settings_escape_host_text_and_show_leading_zero_code(workspace):
    ws = workspace
    stay(ws["home"])
    stay(ws["home"], "2026-10-23", "2026-10-25")
    cleaning.save_settings(ws["home"], {"instructions": "1. Linen\n2. <script>alert(1)</script>",
                                       "checkout_time": "10:30", "checkin_time": "15:30"})
    cleaning_codes.save_manual(ws["home"], "001234")
    response = ws["client"].get("/cleaning?lang=en")
    assert response.status_code == 200
    assert 'href="/cleaning"' in response.text
    assert "001234" in response.text
    assert "&lt;script&gt;" in response.text
    assert "<script>alert(1)</script>" not in response.text
    assert "10:30" in response.text and "15:30" in response.text
    data = payload(ws).json()
    assert "type=\"checkbox\"" not in data["listHtml"]
    for lang in ("en", "cs"):
        for path in ("/cleaning/new", f"/cleaning/properties/{ws['home']}", "/cleaning/properties", "/cleaning/shares"):
            assert ws["client"].get(path, params={"lang": lang}).status_code == 200


@pytest.mark.parametrize("values", [
    {"scheduled_date": "2026-02-30"}, {"scheduled_date": "20261020"},
    {"scheduled_date": "2026-10-20", "start_time": "12:00"},
    {"scheduled_date": "2026-10-20", "start_time": "13:00", "end_time": "12:00"},
    {"scheduled_date": "2026-10-20", "start_time": "25:00", "end_time": "26:00"},
    {"scheduled_date": "2026-10-20", "notes": "x" * 5001},
])
def test_invalid_cleaning_input_is_rejected(workspace, values):
    response = workspace["client"].post("/cleaning/events", data={"apartment_id": workspace["home"], **values})
    assert response.status_code == 422


def test_host_create_update_delete_json_and_concurrent_change(workspace):
    ws = workspace
    response = ws["client"].post("/cleaning/events", data={
        "apartment_id": ws["home"], "scheduled_date": "2026-10-20", "notes": "Extra towels",
    })
    assert response.status_code == 200
    item = payload(ws).json()["cleanings"][0]
    endpoint = f"/cleaning/events/{item['eventId']}"
    data = {"scheduled_date": "2026-10-21", "revision": item["revision"], "notes": "Extra towels"}
    assert ws["client"].post(endpoint, data=data, headers={"Accept": "application/json"}).status_code == 200
    assert ws["client"].post(endpoint, data=data, headers={"Accept": "application/json"}).status_code == 409
    assert ws["client"].get(endpoint + "/edit").status_code == 200
    current = payload(ws).json()["cleanings"][0]
    assert current["date"] == "2026-10-21"
    assert ws["client"].post(endpoint + "/delete", data={"revision": current["revision"]}).status_code == 200


def test_owner_isolation_and_authentication(workspace):
    ws = workspace
    foreign_stay = stay(ws["foreign"])
    cleaning.reconcile(ws["other"])
    foreign_event = db.query_one("SELECT id FROM cleaning_event WHERE source_reservation_id = ?", (foreign_stay,))["id"]
    for path in (f"/cleaning/events/{foreign_event}/edit", f"/cleaning/properties/{ws['foreign']}"):
        assert ws["client"].get(path).status_code == 404
    assert payload(ws, property=ws["foreign"]).status_code == 404
    assert ws["client"].post(f"/cleaning/events/{foreign_event}", data={}).status_code == 404
    for path in ("/cleaning", "/cleaning/schedule?from=2026-10-16&to=2026-11-15", "/cleaning/shares"):
        assert TestClient(app).get(path, follow_redirects=False).status_code == 303


def test_tokens_are_hashed_scoped_bounded_read_only_and_revocable(workspace):
    ws = workspace
    stay(ws["home"])
    stay(ws["homes"][1])
    stay(ws["foreign"])
    cleaning_codes.save_manual(ws["home"], "001234")
    cleaning_codes.save_manual(ws["homes"][1], "998877")
    share_id, token = cleaning.new_share(ws["owner"], [ws["home"]])
    row = db.query_one("SELECT * FROM cleaning_share WHERE id = ?", (share_id,))
    assert token not in str(dict(row)) and len(row["token_hash"]) == 64
    anonymous = TestClient(app)
    url = f"/cleaning/shared/{token}"
    page = anonymous.get(url)
    assert page.status_code == 200
    assert "001234" in page.text and "998877" not in page.text
    assert "Other workspace" not in page.text and "Garden / 2" not in page.text
    assert 'href="/settings"' not in page.text
    assert page.headers["referrer-policy"] == "no-referrer"
    assert page.headers["cache-control"] == "no-store"
    assert "noindex" in page.headers["x-robots-tag"]
    wide = anonymous.get(url + "/schedule?from=2026-01-01&to=2027-01-01").json()
    assert wide["from"] == "2026-10-16" and wide["to"] == "2026-11-15"
    assert anonymous.get(url + f"/schedule?from=2026-10-16&to=2026-11-15&property={ws['homes'][1]}").status_code == 404
    assert anonymous.post(url + "/events", data={}).status_code in (404, 405)
    assert anonymous.post("/cleaning/events", data={}, follow_redirects=False).status_code == 303
    assert ws["client"].post(f"/cleaning/shares/{share_id}/revoke").status_code == 200
    assert anonymous.get(url).status_code == 404
    assert anonymous.get(url + "/schedule").status_code == 404


def test_expired_and_malformed_shares_fail_and_other_owner_cannot_create(workspace):
    ws = workspace
    with pytest.raises(ValueError):
        cleaning.new_share(ws["owner"], [ws["foreign"]])
    share_id, token = cleaning.new_share(ws["owner"], [ws["home"]])
    db.update("cleaning_share", share_id, {"expires_at": "2000-01-01T00:00:00+00:00"})
    assert cleaning.shared(token) is None
    for token in ("", "x", "../admin", "x" * 100):
        assert cleaning.shared(token) is None


def test_share_creation_and_safe_staging_gate(workspace, monkeypatch):
    ws = workspace
    response = ws["client"].post("/cleaning/shares", data={"properties": [ws["home"]]})
    assert response.status_code == 200 and "/cleaning/shared/" in response.text
    monkeypatch.setattr(auth, "staging_no_login", lambda: True)
    assert ws["client"].post("/cleaning/shares", data={"properties": [ws["home"]]}).status_code == 422
    with pytest.raises(ValueError, match="login_required"):
        cleaning_codes.queue_permanent(dict(db.query_one("SELECT * FROM apartment WHERE id = ?", (ws["home"],))), ws["owner"])


def test_manual_fallback_and_removal_do_not_call_provider(workspace, monkeypatch):
    ws = workspace
    monkeypatch.setattr(ttlock, "_call", lambda *args: pytest.fail("Manual code must not call TTLock"))
    path = f"/cleaning/properties/{ws['home']}/code/"
    assert ws["client"].post(path + "manual", data={"code": "001234"}).status_code == 200
    assert ws["client"].post(path + "manual", data={"code": "bad code"}).status_code == 422
    assert ws["client"].post(path + "remove").status_code == 200
    home = next(p for p in cleaning.properties(ws["owner"]) if p["id"] == ws["home"])
    assert not cleaning._code(home)["value"]


def test_permanent_payload_has_type_two_and_no_dates(monkeypatch):
    calls = []
    monkeypatch.setattr(ttlock, "_call", lambda *args: calls.append(args) or {"keyboardPwdId": 42})
    assert ttlock.add_permanent_code(7, "123", "7654321", "UH Cleaning operation") == "42"
    body = calls[0][2]
    assert body["keyboardPwdType"] == 2 and body["addType"] == 2
    assert body["keyboardPwd"] == "7654321"
    assert "startDate" not in body and "endDate" not in body
    with pytest.raises(ValueError):
        ttlock.add_permanent_code(7, "123", "bad", "UH Cleaning")


def test_permanent_queue_confirms_before_display_and_replaces_old_code(workspace, monkeypatch):
    ws = workspace
    _, home = lock_setup(ws, monkeypatch)
    cleaning_codes.save_manual(ws["home"], "001234")
    job = cleaning_codes.queue_permanent(home, ws["owner"])
    assert cleaning_codes.queue_permanent(home, ws["owner"]) == job
    assert cleaning._code(next(p for p in cleaning.properties(ws["owner"]) if p["id"] == ws["home"]))["value"] == "001234"
    monkeypatch.setattr(ttlock, "add_permanent_code", lambda *args: "provider-42")
    assert cleaning_codes.process_queue() == 1
    row = db.query_one("SELECT * FROM cleaning_code WHERE id = ?", (job,))
    assert row["state"] == "active" and row["provider_code_id"] == "provider-42"
    assert db.decrypt_field(row["pin_enc"]) != "001234"
    cleaning_codes.remove(ws["home"])
    deleted = []
    monkeypatch.setattr(ttlock, "delete_code", lambda *args: deleted.append(args))
    assert cleaning_codes.process_queue() == 1
    assert deleted and db.query_one("SELECT pin_enc FROM cleaning_code WHERE id = ?", (job,))["pin_enc"] is None


def test_timeout_reconciles_exact_operation_without_duplicate_add(workspace, monkeypatch):
    ws = workspace
    _, home = lock_setup(ws, monkeypatch)
    job = cleaning_codes.queue_permanent(home, ws["owner"])
    def timeout(*args):
        raise ttlock.TTLockError("connection lost", kind="network")
    monkeypatch.setattr(ttlock, "add_permanent_code", timeout)
    cleaning_codes.process_queue()
    row = dict(db.query_one("SELECT * FROM cleaning_code WHERE id = ?", (job,)))
    assert row["state"] == "retrying"
    monkeypatch.setattr(ttlock, "add_permanent_code", lambda *args: pytest.fail("Must adopt the existing permanent code"))
    monkeypatch.setattr(ttlock, "_call", lambda *args: {"list": [{
        "keyboardPwdName": row["operation_ref"], "keyboardPwdType": 2,
        "keyboardPwd": db.decrypt_field(row["pin_enc"]), "keyboardPwdId": 43,
    }]})
    db.update("cleaning_code", job, {"next_attempt_at": "2000-01-01T00:00:00+00:00"})
    assert cleaning_codes.process_queue() == 1
    assert db.query_one("SELECT provider_code_id FROM cleaning_code WHERE id = ?", (job,))["provider_code_id"] == "43"


def test_failed_provider_can_fall_back_without_losing_uncertain_operation(workspace, monkeypatch):
    ws = workspace
    _, home = lock_setup(ws, monkeypatch)
    job = cleaning_codes.queue_permanent(home, ws["owner"])
    db.update("cleaning_code", job, {"state": "failed", "last_error": "permission"})
    cleaning_codes.save_manual(ws["home"], "000123")
    old = db.query_one("SELECT * FROM cleaning_code WHERE id = ?", (job,))
    assert old["state"] == "revoke_pending"
    monkeypatch.setattr(ttlock, "_call", lambda *args: {"list": []})
    assert cleaning_codes.process_queue() == 1
    assert db.query_one("SELECT state FROM cleaning_code WHERE id = ?", (job,))["state"] == "revoked"


def test_retention_wipes_old_notes_but_keeps_suppression(workspace):
    ws = workspace
    booking = stay(ws["home"], "2026-09-01", "2026-09-02")
    # Historical row supplied explicitly; normal reconciliation only seeds recent/future events.
    row_id = db.insert("cleaning_event", {
        "apartment_id": ws["home"], "source_reservation_id": booking, "source_date": "2026-09-02",
        "scheduled_date": "2026-09-02", "notes_enc": db.encrypt_field("Temporary operational note"),
        "state": "dismissed", "created_at": db.utcnow(), "updated_at": db.utcnow(),
    })
    assert cleaning.purge(date(2026, 10, 16), True, ws["owner"]) == 1
    assert db.query_one("SELECT notes_enc FROM cleaning_event WHERE id = ?", (row_id,))["notes_enc"]
    assert cleaning.purge(date(2026, 10, 16), False, ws["owner"]) == 1
    row = db.query_one("SELECT * FROM cleaning_event WHERE id = ?", (row_id,))
    assert row["notes_enc"] is None and row["state"] == "dismissed"


def test_date_only_dst_and_catalog_parity():
    first, last = cleaning.parse_range("2026-10-24", "2026-10-27")
    assert last - first == timedelta(days=3)
    assert cleaning.parse_date("2028-02-29").day == 29
    assert all(len(pair) == 2 and all(pair) for pair in cleaning_i18n.WORDS.values())


def test_lock_change_during_creation_never_publishes_a_code_for_the_old_lock(workspace, monkeypatch):
    ws = workspace
    _, home = lock_setup(ws, monkeypatch)
    job = cleaning_codes.queue_permanent(home, ws["owner"])
    def provider_success(*args):
        db.update("apartment", ws["home"], {"lock_id": "456"})
        return "old-lock-code"
    monkeypatch.setattr(ttlock, "add_permanent_code", provider_success)
    assert cleaning_codes.process_queue() == 1
    row = db.query_one("SELECT * FROM cleaning_code WHERE id = ?", (job,))
    assert row["state"] == "revoke_pending" and row["provider_code_id"] == "old-lock-code"
    prop = next(p for p in cleaning.properties(ws["owner"]) if p["id"] == ws["home"])
    assert not cleaning._code(prop)["value"]


def test_active_permanent_code_is_hidden_and_revoked_after_lock_mapping_changes(workspace, monkeypatch):
    ws = workspace
    _, home = lock_setup(ws, monkeypatch)
    job = cleaning_codes.queue_permanent(home, ws["owner"])
    monkeypatch.setattr(ttlock, "add_permanent_code", lambda *args: "12345")
    cleaning_codes.process_queue()
    db.update("apartment", ws["home"], {"lock_id": "456"})
    prop = next(p for p in cleaning.properties(ws["owner"]) if p["id"] == ws["home"])
    assert not cleaning._code(prop)["value"]
    deleted = []
    monkeypatch.setattr(ttlock, "delete_code", lambda *args: deleted.append(args))
    assert cleaning_codes.process_queue() == 1
    assert deleted[0][1] == "123"
    assert db.query_one("SELECT state FROM cleaning_code WHERE id = ?", (job,))["state"] == "revoked"


def test_pending_code_is_not_programmed_after_property_lock_is_changed(workspace, monkeypatch):
    ws = workspace
    _, home = lock_setup(ws, monkeypatch)
    job = cleaning_codes.queue_permanent(home, ws["owner"])
    db.update("apartment", ws["home"], {"lock_id": "456"})
    monkeypatch.setattr(ttlock, "add_permanent_code", lambda *args: pytest.fail("Old lock must not be programmed"))
    assert cleaning_codes.process_queue() == 1
    row = db.query_one("SELECT * FROM cleaning_code WHERE id = ?", (job,))
    assert row["state"] == "revoked" and row["pin_enc"] is None


def test_shared_link_uses_canonical_https_origin_behind_a_proxy(workspace, monkeypatch):
    monkeypatch.setattr(config, "PUBLIC_BASE_URL", "https://cleaning.example.test")
    response = workspace["client"].post("/cleaning/shares", data={"properties": [workspace["home"]]})
    assert response.status_code == 200
    assert "https://cleaning.example.test/cleaning/shared/" in response.text
    assert "http://testserver/cleaning/shared/" not in response.text
