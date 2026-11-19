"""1863: POST /reservations/{id} served by Go equals Python.

Same form, same session, two identical stays: one saved by Python, one by Go.
The redirect, the stored stay, the claim, the outbox and the open alerts must
match, and Go must ask for the submit sweep exactly when Python files.
Run with UBYHOST_GO_PATHS=/__go_test__ (starts the Go stack; POSTs go to Go directly).
"""
from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient

from app import alerts, auth, db, reporting
from app.main import app
from tests.conftest import csrf_token_for, login_as, mark_security_prompt_seen
from tests.go_stack import ensure_go_running, go_paths_enabled, seed_go_host_gate

pytestmark = pytest.mark.skipif(
    not go_paths_enabled(),
    reason="set UBYHOST_GO_PATHS=/__go_test__ to start the Go stack",
)

USERNAME = "stay-save-1863"
OPEN_SUBMIT = "SELECT COUNT(*) AS n FROM job WHERE kind = 'submit' AND done_at IS NULL AND dead_at IS NULL"
SNAPSHOT = (
    "SELECT guest_email, host_note, summary, expected_guests_override, status, "
    "lead_reduced_guests, lead_reduced_from, lead_reduced_at, "
    "registration_completed_at IS NOT NULL AS completed FROM reservation WHERE id = ?"
)
SAVE = {"guest_email": "", "host_note": "", "status": "active"}

# name, automation mode, expected guests, filed, blank, extra stay columns, form, open alert, files
CASES = [
    ("note", "manual", None, 0, 0, {},
     {"guest_email": " a@example.test ", "host_note": " Late ", "summary": "x" * 170, "status": "bogus"}, None, False),
    ("complete_immediate", "immediate", 1, 1, 0, {}, SAVE, None, True),
    ("incomplete_immediate", "immediate", 2, 1, 1, {}, SAVE, None, False),
    ("complete_scheduled", "scheduled", 1, 1, 0, {}, SAVE, None, False),
    ("police_login_refused", "immediate", 1, 1, 0, {}, SAVE, "ubyport_auth_failed:{apt}", False),
    ("cancel", "immediate", 1, 1, 0, {}, dict(SAVE, status="cancelled"), None, False),
    ("reactivate", "manual", None, 0, 0, {"status": "cancelled"}, SAVE, "cancelled_with_guests:{res}", False),
    ("count_61", "manual", None, 0, 0, {}, {"host_note": "x", "expected_guests_override": "61"}, None, False),
    ("lead_same", "manual", None, 0, 0, {"declared_guests": 3, "lead_reduced_guests": 2, "lead_reduced_from": 3},
     {"expected_guests_override": "2"}, None, False),
    ("lead_new", "manual", None, 0, 0, {"declared_guests": 3, "lead_reduced_guests": 2, "lead_reduced_from": 3},
     {"expected_guests_override": "3"}, None, False),
]


def _cleanup() -> None:
    db.execute(
        "DELETE FROM job WHERE kind = 'submit' AND done_at IS NULL AND dead_at IS NULL AND locked_at IS NULL"
    )
    for row in db.query("SELECT id FROM user_account WHERE username = ?", (USERNAME,)):
        uid = row["id"]
        stays = "SELECT id FROM reservation WHERE apartment_id IN (SELECT id FROM apartment WHERE owner_user_id = ?)"
        db.execute(f"DELETE FROM email_outbox WHERE reservation_id IN ({stays})", (uid,))
        db.execute(f"DELETE FROM reservation_claim WHERE reservation_id IN ({stays})", (uid,))
        db.execute(f"DELETE FROM guest WHERE reservation_id IN ({stays})", (uid,))
        db.execute("DELETE FROM alert WHERE owner_user_id = ?", (uid,))
        db.execute("DELETE FROM reservation WHERE apartment_id IN (SELECT id FROM apartment WHERE owner_user_id = ?)", (uid,))
        db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (uid,))
        db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (uid,))
        db.execute("DELETE FROM audit WHERE owner_user_id = ?", (uid,))
        db.execute("DELETE FROM legal_acceptance WHERE user_account_id = ?", (uid,))
        db.execute("DELETE FROM user_account WHERE id = ?", (uid,))


@pytest.fixture
def save_host():
    db.init_db()
    _cleanup()
    owner_id = mark_security_prompt_seen(
        auth.create_account(f"{USERNAME}@example.test", "Stay Save", username=USERNAME)
    )
    seed_go_host_gate(owner_id)
    entity = db.insert(
        "legal_entity",
        {"name": "Save s.r.o.", "seat": "Praha", "ico": "18630001", "contact_email": "s@example.test",
         "owner_user_id": owner_id, "created_at": db.utcnow()},
    )
    client = TestClient(app)
    login_as(client, USERNAME, url="/login?lang=en", follow_redirects=False)
    try:
        yield client, owner_id, entity
    finally:
        _cleanup()


def _seed(owner_id, entity, tag, mode, expected, filed, blank, extra, alert):
    now = db.utcnow()
    apt = db.insert(
        "apartment",
        {"legal_entity_id": entity, "owner_user_id": owner_id, "internal_name": "Save Flat",
         "addr_obec": "Praha", "addr_house_no": "1", "addr_zip": "11000",
         "permalink_token": f"save{tag}", "permalink_pin": "123456",
         "automation_mode": mode, "active": 1, "created_at": now},
    )
    res = db.insert(
        "reservation",
        {"apartment_id": apt, "uid": f"1863-{tag}", "source": "manual", "date_from": "2026-12-01",
         "date_to": "2026-12-03", "status": "active", "expected_guests_override": expected,
         "created_at": now, "updated_at": now, **extra},
    )
    for _ in range(filed):
        db.insert("guest", {"reservation_id": res, "submit_state": "sent", "manual_filed_at": now,
                            "created_at": now, "updated_at": now})
    for _ in range(blank):
        db.insert("guest", {"reservation_id": res, "created_at": now, "updated_at": now})
    db.insert("reservation_claim", {"reservation_id": res, "state": "claimed", "token_hash": "hash",
                                    "token_version": 0, "created_at": now, "updated_at": now})
    db.insert("email_outbox", {"idempotency_key": f"1863-{tag}", "kind": "claim", "reservation_id": res,
                               "state": "queued", "created_at": now, "updated_at": now})
    if alert:
        key = alert.format(apt=apt, res=res)
        alerts.raise_alert("critical", key.split(":")[0], "seeded", dedupe_key=key, apartment_id=apt)
    return apt, res


def _snapshot(apt, res):
    row = dict(db.query_one(SNAPSHOT, (res,)))
    claim_row = db.query_one(
        "SELECT token_hash IS NULL AS cleared, guest_access_locked_at IS NOT NULL AS locked "
        "FROM reservation_claim WHERE reservation_id = ?", (res,))
    row["claim"] = dict(claim_row)
    row["outbox"] = [r["state"] for r in db.query("SELECT state FROM email_outbox WHERE reservation_id = ?", (res,))]
    row["open_alerts"] = sorted(
        r["kind"] for r in db.query("SELECT kind FROM alert WHERE apartment_id = ? AND resolved_at IS NULL", (apt,))
    )
    return row


def _go_post(client, path, form):
    go = ensure_go_running("http://testserver")
    token = csrf_token_for(client)  # first: it may set the ubyhost_csrf cookie
    cookies = {c.name: c.value for c in client.cookies.jar}
    return httpx.post(go + path, data=dict(form, _csrf=token), cookies=cookies,
                      follow_redirects=False, timeout=15)


def _same_location(resp, res):
    return resp.headers.get("location", "").replace(f"/reservations/{res}", "/reservations/<id>")


@pytest.mark.parametrize("case", CASES, ids=[c[0] for c in CASES])
def test_save_matches_python(save_host, monkeypatch, case):
    client, owner_id, entity = save_host
    name, mode, expected, filed, blank, extra, form, alert, files = case
    calls = []
    monkeypatch.setattr(reporting, "submit_for_apartment", lambda apartment_id, **kw: calls.append(apartment_id))

    py_apt, py_res = _seed(owner_id, entity, f"{name}-py", mode, expected, filed, blank, extra, alert)
    go_apt, go_res = _seed(owner_id, entity, f"{name}-go", mode, expected, filed, blank, extra, alert)

    py = client.post(f"/reservations/{py_res}", data=form, follow_redirects=False)
    db.execute("DELETE FROM job WHERE kind = 'submit' AND done_at IS NULL AND dead_at IS NULL AND locked_at IS NULL")
    go = _go_post(client, f"/reservations/{go_res}", form)
    go_jobs = db.query_one(OPEN_SUBMIT)["n"]

    assert go.status_code == py.status_code, name
    assert _same_location(go, go_res) == _same_location(py, py_res), name
    if py.status_code == 422:
        assert go.json() == py.json() == {"ok": False}
    assert _snapshot(go_apt, go_res) == _snapshot(py_apt, py_res), name
    assert (py_apt in calls) is files, f"{name}: Python filing call {calls}"
    assert (go_jobs == 1) is files, f"{name}: Go open submit jobs {go_jobs}"


def test_unknown_stay_matches_python(save_host):
    client, _owner_id, _entity = save_host
    py = client.post("/reservations/999999999", data=SAVE, follow_redirects=False)
    go = _go_post(client, "/reservations/999999999", SAVE)
    assert (go.status_code, go.headers.get("location")) == (py.status_code, py.headers.get("location"))
