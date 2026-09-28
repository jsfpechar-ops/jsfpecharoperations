"""BE-13/LD-5: the security incident register is platform-admin only.

The register is the Art 33(5) record; the notification draft is shown as text to
copy and is never sent automatically.
"""
from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app import auth, config, db, incidents
from app.main import app

PASSWORD = "Secure-Password-123"


def _cleanup():
    for row in db.query("SELECT id FROM user_account WHERE username LIKE 'incident-%'"):
        user_id = row["id"]
        db.execute("DELETE FROM alert WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM audit WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM user_account WHERE id = ?", (user_id,))
    db.execute("DELETE FROM security_incident")
    db.execute("DELETE FROM alert WHERE kind = 'incident_review'")


def _login(username: str) -> TestClient:
    client = TestClient(app)
    response = client.post(
        "/login?lang=en",
        data={"username": username, "password": PASSWORD},
        follow_redirects=False,
    )
    assert response.status_code == 303
    return client


def _account(username: str, role: str) -> int:
    return auth.create_account(
        username, PASSWORD, username.title(), role=role, must_change_password=False
    )


def test_the_register_is_platform_admin_only():
    db.init_db()
    _cleanup()
    _account("incident-host", "host")
    try:
        client = _login("incident-host")
        assert client.get("/admin/incidents").status_code == 403
        assert client.post(
            "/admin/incidents", data={"summary": "x"}, follow_redirects=False
        ).status_code == 403
    finally:
        _cleanup()


def test_an_admin_records_and_updates_an_incident():
    db.init_db()
    _cleanup()
    _account("incident-admin", "admin")
    first = _account("incident-a", "host")
    second = _account("incident-b", "host")
    try:
        client = _login("incident-admin")
        created = client.post(
            "/admin/incidents",
            data={
                "summary": "Mailbox credential leaked",
                "detected_at": "2026-01-01T00:00:00+00:00",
                "data_categories": "guest e-mail addresses",
                "approx_subjects": "3",
                "risk_level": "high",
                "owner_ids": [str(first), str(second)],
            },
            follow_redirects=False,
        )
        assert created.status_code == 303, created.text

        row = db.query_one("SELECT * FROM security_incident ORDER BY id DESC LIMIT 1")
        assert row["summary"] == "Mailbox credential leaked"
        assert row["risk_level"] == "high"
        assert json.loads(row["affected_owner_ids"]) == [first, second]
        assert row["approx_subjects"] == 3

        marked = client.post(
            f"/admin/incidents/{row['id']}",
            data={"action": "contained_at"},
            follow_redirects=False,
        )
        assert marked.status_code == 303
        assert db.query_one(
            "SELECT contained_at FROM security_incident WHERE id = ?", (row["id"],)
        )["contained_at"]

        # The notification draft names the contact and the 72-hour reminder.
        refreshed = incidents.get(row["id"])
        draft = incidents.controller_notification_draft(refreshed)
        assert "72 hours" in draft
        assert "Art 33(2)" in draft
    finally:
        _cleanup()


def test_frequent_pin_failures_suggest_a_review(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "incidents.sqlite3")
    db.init_db()
    now = db.utcnow()
    for _ in range(incidents.REVIEW_THRESHOLD):
        db.execute(
            "INSERT INTO audit (at, actor, action, detail) VALUES (?,?,?,?)",
            (now, "anonymous", "guest_pin_rate_limited", ""),
        )

    assert incidents.suggest_review_if_frequent() is True
    alert = db.query_one("SELECT * FROM alert WHERE kind = 'incident_review'")
    assert alert is not None
    assert alert["resolved_at"] is None
    # Same day: the card is refreshed, not duplicated.
    assert incidents.suggest_review_if_frequent() is True
    assert len(db.query("SELECT id FROM alert WHERE kind = 'incident_review'")) == 1
