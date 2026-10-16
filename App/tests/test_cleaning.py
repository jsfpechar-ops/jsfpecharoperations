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
    assert item["displayStart"] == "2026-10-16T11:00"
    assert item["displayEnd"] == "2026-10-16T15:00"
    assert item["nextArrival"] == "2026-12-01"
    assert item["checkinTime"] == "15:00"
    assert db.query_one("SELECT COUNT(*) AS n FROM cleaning_event WHERE source_reservation_id = ?", (booking,))["n"] == 1
    assert "Private guest" not in str(data)
    assert "private internal note" not in str(data)


def test_checkout_turnover_uses_same_day_property_hours_and_keeps_next_arrival_context(workspace):
    ws = workspace
    db.update("apartment", ws["home"], {"checkin_hour": 15, "checkout_hour": 11})
    booking = stay(ws["home"], "2026-10-15", "2026-10-17")
    stay(ws["home"], "2026-10-20", "2026-10-22")
    data = payload(ws).json()
    reservation = next(item for item in data["events"] if item["id"] == f"reservation:{booking}")
    turnover = next(item for item in data["cleanings"] if item["checkout"] == "2026-10-17")
    assert reservation["start"] == "2026-10-15" and reservation["end"] == "2026-10-17"
    assert reservation["displayStart"] == "2026-10-15T15:00"
    assert reservation["displayEnd"] == "2026-10-17T11:00"
    assert turnover["date"] == "2026-10-17"
    assert turnover["displayStart"] == "2026-10-17T11:00"
    assert turnover["displayEnd"] == "2026-10-17T15:00"
    assert turnover["nextArrival"] == "2026-10-20"
    assert db.query_one("SELECT scheduled_date FROM cleaning_event WHERE source_reservation_id = ?", (booking,))["scheduled_date"] == "2026-10-17"


def test_invalid_property_window_is_flagged_without_persisting_visual_fallback(workspace):
    ws = workspace
    db.update("apartment", ws["home"], {"checkin_hour": 11, "checkout_hour": 11})
    booking = stay(ws["home"], "2026-10-15", "2026-10-17")
    item = next(x for x in payload(ws).json()["cleanings"] if x["checkout"] == "2026-10-17")
    assert item["timingUnavailable"] is True and item["conflict"] is False
    assert item["displayStart"] == "2026-10-17T12:00"
    assert item["displayEnd"] == "2026-10-17T13:00"
    assert item["checkoutTime"] == "11:00" and item["checkinTime"] == "11:00"
    row = db.query_one("SELECT start_time, end_time FROM cleaning_event WHERE source_reservation_id = ?", (booking,))
    assert row["start_time"] is None and row["end_time"] is None


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


def test_notes_edit_preserves_legacy_explicit_times_and_auto_property_defaults(workspace):
    ws = workspace
    manual = cleaning.save_event(ws["home"], {"scheduled_date": "2026-10-19", "start_time": "12:30", "end_time": "14:00", "notes": "Legacy override"})
    row = dict(db.query_one("SELECT * FROM cleaning_event WHERE id = ?", (manual,)))
    cleaning.save_event(ws["home"], {"scheduled_date": "2026-10-19", "revision": row["revision"], "notes": "Notes only"}, row)
    saved = db.query_one("SELECT start_time, end_time FROM cleaning_event WHERE id = ?", (manual,))
    assert saved["start_time"] == "12:30" and saved["end_time"] == "14:00"
    item = next(x for x in payload(ws).json()["cleanings"] if x["eventId"] == manual)
    assert item["displayStart"] == "2026-10-19T12:30" and item["displayEnd"] == "2026-10-19T14:00"
    db.update("cleaning_event", manual, {"start_time": "nonsense", "end_time": "26:99"})
    malformed = dict(db.query_one("SELECT * FROM cleaning_event WHERE id = ?", (manual,)))
    cleaning.save_event(ws["home"], {"scheduled_date": malformed["scheduled_date"], "revision": malformed["revision"],
                                     "notes": "Still safe"}, malformed)
    retained = db.query_one("SELECT start_time, end_time FROM cleaning_event WHERE id = ?", (manual,))
    assert (retained["start_time"], retained["end_time"]) == ("nonsense", "26:99")


def test_normal_cleaning_editor_has_no_duplicate_time_fields(workspace):
    ws = workspace
    booking = stay(ws["home"])
    item = event(ws, booking)
    response = ws["client"].get(f"/cleaning/events/{item['id']}/edit")
    assert response.status_code == 200
    assert 'name="start_time"' not in response.text
    assert 'name="end_time"' not in response.text
    assert "Edit timing in Properties" in response.text
    new_response = ws["client"].get("/cleaning/new")
    assert new_response.status_code == 200
    assert 'href="/apartments/"' in new_response.text


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
    cleaning.ensure_property(ws["home"])
    db.update("cleaning_property", ws["home"], {"checkout_time": "10:30", "checkin_time": "15:30"})
    cleaning.save_settings(ws["home"], {"instructions": "1. Linen\n2. <script>alert(1)</script>"})
    cleaning_codes.save_manual(ws["home"], "001234")
    response = ws["client"].get("/cleaning?lang=en")
    assert response.status_code == 200
    assert 'href="/cleaning"' in response.text
    assert "001234" in response.text
    assert "&lt;script&gt;" in response.text
    assert "<script>alert(1)</script>" not in response.text
    assert "11:00" in response.text and "15:00" in response.text
    legacy = db.query_one("SELECT checkout_time, checkin_time FROM cleaning_property WHERE apartment_id = ?", (ws["home"],))
    assert legacy["checkout_time"] == "10:30" and legacy["checkin_time"] == "15:30"
    home = cleaning.properties(ws["owner"], [ws["home"]])[0]
    assert cleaning._hour(home, "checkout") == "11:00"
    assert cleaning._hour(home, "checkin") == "15:00"
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



def test_calendar_json_creation_contract_and_validation(workspace):
    ws = workspace
    response = ws["client"].post("/cleaning/events", headers={"Accept": "application/json"}, data={
        "apartment_id": ws["home"], "scheduled_date": "2026-10-26", "notes": "popup only",
    })
    assert response.status_code == 201
    assert response.headers["cache-control"] == "no-store"
    created = response.json()
    assert created["id"] > 0
    assert created["url"].startswith("/cleaning?cal_date=2026-10-26&property=")
    row = db.query_one("SELECT scheduled_date, start_time, end_time FROM cleaning_event WHERE id = ?", (created["id"],))
    assert row["scheduled_date"] == "2026-10-26"
    assert row["start_time"] is None and row["end_time"] is None

    invalid = ws["client"].post("/cleaning/events", headers={"Accept": "application/json"}, data={
        "apartment_id": ws["home"], "scheduled_date": "", "notes": "must not save",
    })
    assert invalid.status_code == 422
    assert invalid.json()["errors"]["scheduled_date"]
    assert db.query_one("SELECT COUNT(*) AS n FROM cleaning_event WHERE apartment_id = ? AND notes_enc IS NOT NULL",
                        (ws["home"],))["n"] == 1


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
    cleaning_codes.save_manual(ws["home"], "001234")
    monkeypatch.setattr(auth, "staging_no_login", lambda: True)
    assert ws["client"].post("/cleaning/shares", data={"properties": [ws["home"]]}).status_code == 422
    with pytest.raises(ValueError, match="login_required"):
        cleaning_codes.save_manual(ws["home"], "998877")
    prop = next(p for p in cleaning.properties(ws["owner"]) if p["id"] == ws["home"])
    assert cleaning._code(prop)["value"] == ""
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


def test_shared_booking_fractional_display_is_clipped_to_requested_dates(workspace):
    ws = workspace
    stay_id = stay(ws["home"], "2026-10-15", "2026-10-22")
    _, token = cleaning.new_share(ws["owner"], [ws["home"]])
    response = ws["client"].get(f"/cleaning/shared/{token}/schedule",
                                params={"from": "2026-10-17", "to": "2026-10-20"})
    assert response.status_code == 200
    booking = next(item for item in response.json()["events"] if item["id"] == f"reservation:{stay_id}")
    assert booking["start"] == "2026-10-17" and booking["end"] == "2026-10-20"
    assert booking["displayStart"] == "2026-10-17T00:00"
    assert booking["displayEnd"] == "2026-10-20T00:00"
    assert "2026-10-15" not in str(booking) and "2026-10-22" not in str(booking)


def test_shared_link_uses_canonical_https_origin_behind_a_proxy(workspace, monkeypatch):
    monkeypatch.setattr(config, "PUBLIC_BASE_URL", "https://cleaning.example.test")
    response = workspace["client"].post("/cleaning/shares", data={"properties": [workspace["home"]]})
    assert response.status_code == 200
    assert "https://cleaning.example.test/cleaning/shared/" in response.text
    assert "http://testserver/cleaning/shared/" not in response.text


@pytest.mark.parametrize("keypad_suffix", ["", "#"])
def test_manual_takeover_of_same_ttlock_pin_keeps_the_physical_code(workspace, monkeypatch, keypad_suffix):
    ws = workspace
    _, home = lock_setup(ws, monkeypatch)
    job = cleaning_codes.queue_permanent(home, ws["owner"])
    monkeypatch.setattr(ttlock, "add_permanent_code", lambda *args: "12345")
    cleaning_codes.process_queue()
    pin = db.decrypt_field(db.query_one("SELECT pin_enc FROM cleaning_code WHERE id = ?", (job,))["pin_enc"])
    cleaning_codes.save_manual(ws["home"], pin + keypad_suffix)
    monkeypatch.setattr(ttlock, "delete_code", lambda *args: pytest.fail("The manual code is the same physical PIN"))
    assert cleaning_codes.process_queue() == 0
    prop = next(p for p in cleaning.properties(ws["owner"]) if p["id"] == ws["home"])
    assert cleaning._code(prop)["value"] == pin + keypad_suffix
    assert cleaning._code(prop)["source"] == "manual"
    previous = db.query_one("SELECT * FROM cleaning_code WHERE id = ?", (job,))
    assert previous["state"] == "detached" and previous["pin_enc"] is None



def test_cleaning_availability_uses_property_hours_and_preserves_manual_override(workspace):
    ws = workspace
    home_id = ws["home"]
    cleaning.ensure_property(home_id)
    db.update("cleaning_property", home_id, {"checkout_time": "09:30", "checkin_time": "18:00"})
    first = stay(home_id, "2026-10-17", "2026-10-20")
    stay(home_id, "2026-10-22", "2026-10-24")
    payload_value = cleaning.schedule(ws["owner"], date(2026, 10, 16), date(2026, 10, 24), [home_id])
    assert payload_value["properties"][0]["id"] == home_id
    generated = next(item for item in payload_value["cleanings"] if item["checkout"] == "2026-10-20")
    assert generated["nextArrival"] == "2026-10-22"
    assert generated["checkoutTime"] == "11:00" and generated["checkinTime"] == "15:00"
    home = cleaning.properties(ws["owner"], [home_id])[0]
    assert cleaning._hour(home, "checkout") == "11:00"
    assert cleaning._hour(home, "checkin") == "15:00"
    event = db.query_one("SELECT * FROM cleaning_event WHERE source_reservation_id = ?", (db.query_one("SELECT id FROM reservation WHERE id = ?", (first,))["id"],))
    assert event is not None
    manual_day = "2026-10-21"
    db.update("apartment", home_id, {"checkout_hour": 12, "checkin_hour": 16})
    refreshed = cleaning.schedule(ws["owner"], date(2026, 10, 16), date(2026, 10, 24), [home_id])
    updated_generated = next(item for item in refreshed["cleanings"] if item["checkout"] == "2026-10-20")
    assert updated_generated["checkoutTime"] == "12:00" and updated_generated["checkinTime"] == "16:00"
    cleaning.save_event(home_id, {"scheduled_date": manual_day, "start_time": "12:00", "end_time": "14:00", "notes": "", "revision": event["revision"]}, existing=dict(event))
    moved = db.query_one("SELECT scheduled_date, start_time, end_time, overridden FROM cleaning_event WHERE id = ?", (event["id"],))
    assert (moved["scheduled_date"], moved["start_time"], moved["end_time"], moved["overridden"]) == (manual_day, "12:00", "14:00", 1)
    legacy = db.query_one("SELECT checkout_time, checkin_time FROM cleaning_property WHERE apartment_id = ?", (home_id,))
    assert (legacy["checkout_time"], legacy["checkin_time"]) == ("09:30", "18:00")
    db.update("apartment", home_id, {"checkout_hour": 30, "checkin_hour": -1})
    invalid_home = cleaning.properties(ws["owner"], [home_id])[0]
    assert cleaning._hour(invalid_home, "checkout") is None
    assert cleaning._hour(invalid_home, "checkin") is None
    response = ws["client"].get(f"/cleaning/properties/{home_id}")
    assert response.status_code == 200
    assert 'id="cleaning-property-times"' in response.text
    summary = response.text.split('id="cleaning-property-times"', 1)[1].split("</section>", 1)[0]
    assert "/apartments/" in summary
    assert "30:00" not in summary and "-1:00" not in summary
