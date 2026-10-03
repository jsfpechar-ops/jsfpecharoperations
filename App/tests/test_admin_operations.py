"""WP10: the admin Operations page is admin only and never shows a guest.

The page reads filings, calendars, jobs, mail and alerts across every
workspace. The rendered HTML is checked against the demo seed's guest
surnames and document numbers, with every seeded guest pushed into a failed
filing state so the filings section really lists their stays.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app import admin_ops, auth, config, db, demo, reporting, scheduler
from app.main import app

PASSWORD = "Secure-Password-123"
PREFIX = "wp10-ops-"


def _cleanup() -> None:
    for row in db.query("SELECT id FROM user_account WHERE username LIKE ?", (PREFIX + "%",)):
        demo.clear(row["id"])
        db.execute("DELETE FROM alert WHERE owner_user_id = ?", (row["id"],))
        db.execute("DELETE FROM audit WHERE owner_user_id = ?", (row["id"],))
        db.execute("DELETE FROM legal_acceptance WHERE user_account_id = ?", (row["id"],))
        db.execute("DELETE FROM user_account WHERE id = ?", (row["id"],))
    db.execute("DELETE FROM email_outbox WHERE idempotency_key LIKE ?", (PREFIX + "%",))
    db.execute("DELETE FROM settings WHERE key LIKE ?", (scheduler.JOB_LAST_OK_PREFIX + "%",))
    db.execute("DELETE FROM alert WHERE dedupe_key LIKE 'job_failed:%'")


@pytest.fixture(autouse=True)
def _database():
    db.init_db()
    _cleanup()
    yield
    _cleanup()


def _account(name: str, role: str) -> int:
    return auth.create_account(
        PREFIX + name, PASSWORD, name.title(), role=role, must_change_password=False
    )


def _login(name: str) -> TestClient:
    client = TestClient(app)
    response = client.post(
        "/login?lang=en",
        data={"username": PREFIX + name, "password": PASSWORD},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    return client


def test_a_host_cannot_open_the_operations_page():
    _account("host", "host")
    client = _login("host")
    assert client.get("/admin/operations", follow_redirects=False).status_code == 403


def test_signed_out_visitor_is_sent_to_login():
    _account("admin", "admin")
    response = TestClient(app).get("/admin/operations", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"].startswith("/login")


def test_admin_sees_every_section_and_no_guest_identity(monkeypatch):
    monkeypatch.setattr(config, "UBYPORT_ENV", "mock")
    host_id = _account("seeded", "host")
    _account("admin", "admin")
    assert demo.seed(host_id)
    guests = db.query(
        "SELECT g.id, g.surname, g.doc_number_enc, g.doc_number FROM guest g "
        "JOIN reservation r ON r.id = g.reservation_id "
        "JOIN apartment a ON a.id = r.apartment_id WHERE a.owner_user_id = ?",
        (host_id,),
    )
    assert guests, "the demo seed should create guests"
    identities = set()
    for index, guest in enumerate(guests):
        row = db.query_one("SELECT * FROM guest WHERE id = ?", (guest["id"],))
        for value in (row["surname"], row["doc_number"], row["first_name"]):
            if value and len(value) > 3:
                identities.add(value)
        state = reporting.BLOCKED if index % 2 else reporting.ERROR
        db.execute(
            "UPDATE guest SET submit_state = ?, submit_attempts = ? WHERE id = ?",
            (state, index % 4, guest["id"]),
        )
    assert "P1234567" in identities

    client = _login("admin")
    response = client.get("/admin/operations?lang=en")
    assert response.status_code == 200
    html = response.text
    for section in ("ops-filings", "ops-feeds", "ops-jobs", "ops-mail", "ops-alerts"):
        assert f'id="{section}"' in html
    assert demo.DEMO_APARTMENT in html  # the filings list names the property
    assert "ops." not in html  # every label resolved from the catalogue
    for value in identities:
        assert value not in html, value
    # And the Czech page reads its own catalogue.
    czech = client.get("/admin/operations?lang=cs").text
    assert "Hlášení vyžadující pozornost" in czech


def test_filings_are_one_row_per_stay_with_the_worst_state():
    host_id = _account("filings", "host")
    now = db.utcnow()
    apartment_id = db.insert(
        "apartment",
        {"internal_name": "Ops Flat", "owner_user_id": host_id, "created_at": now},
    )
    reservation_id = db.insert(
        "reservation",
        {
            "apartment_id": apartment_id, "uid": "wp10-ops-1", "date_from": "2026-01-01",
            "date_to": "2026-01-03", "created_at": now, "updated_at": now,
        },
    )
    submission_id = db.insert(
        "submission",
        {"apartment_id": apartment_id, "created_at": now, "state": "outcome_unknown"},
    )
    for state, sub in (("error", None), ("pending", submission_id)):
        db.insert(
            "guest",
            {
                "reservation_id": reservation_id, "surname": "Hidden", "submit_state": state,
                "submission_id": sub, "created_at": now, "updated_at": now,
            },
        )
    result = admin_ops.filings_needing_attention()
    mine = [row for row in result["rows"] if row["stay_id"] == reservation_id]
    assert len(mine) == 1
    assert mine[0]["state"] == "outcome_unknown"
    assert mine[0]["workspace"] == PREFIX + "filings"
    assert "Hidden" not in repr(result)
    db.execute("DELETE FROM guest WHERE reservation_id = ?", (reservation_id,))
    db.execute("DELETE FROM submission WHERE id = ?", (submission_id,))
    db.execute("DELETE FROM reservation WHERE id = ?", (reservation_id,))
    db.execute("DELETE FROM apartment WHERE id = ?", (apartment_id,))


def test_job_ok_records_the_last_success_and_late_jobs_show():
    scheduler._job_ok("mail")
    stored = db.get_setting(scheduler.JOB_LAST_OK_PREFIX + "mail")
    assert stored and admin_ops.age_minutes(stored) == 0
    old = (datetime.now(timezone.utc) - timedelta(minutes=11)).replace(microsecond=0).isoformat()
    db.set_setting(scheduler.JOB_LAST_OK_PREFIX + "mail", old)
    rows = {row["job_id"]: row for row in admin_ops.job_health()["rows"]}
    assert rows["mail"]["late"] is True  # 11 min > 2 x 5 min
    assert rows["ical"]["late"] is True  # never recorded
    scheduler._job_ok("ical")
    rows = {row["job_id"]: row for row in admin_ops.job_health()["rows"]}
    assert rows["ical"]["late"] is False


def test_failed_mail_is_listed_without_the_recipient():
    now = db.utcnow()
    db.insert(
        "email_outbox",
        {
            "idempotency_key": PREFIX + "mail", "kind": "submission_problem",
            "to_email": "secret.recipient@example.test", "subject": "x", "payload": "{}",
            "state": "failed", "attempts": 8, "next_attempt_at": now,
            "created_at": now, "updated_at": now,
        },
    )
    result = admin_ops.mail_problems()
    assert any(row["kind"] == "submission_problem" and row["attempts"] == 8 for row in result["rows"])
    assert "secret.recipient" not in repr(result)
