"""WP11: the admin funnel is computed from existing rows, admin only, and the
CSV export carries the same rows as the page."""
from __future__ import annotations

import csv
import io
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app import admin_funnel, auth, db
from app.main import app

PASSWORD = "Secure-Password-123"
PREFIX = "wp11-funnel-"
NOW = datetime(2026, 10, 15, 12, 0, tzinfo=timezone.utc)


def _iso(moment: datetime) -> str:
    return moment.replace(microsecond=0).isoformat()


def _cleanup() -> None:
    for row in db.query("SELECT id FROM user_account WHERE username LIKE ?", (PREFIX + "%",)):
        uid = row["id"]
        apartments = [a["id"] for a in db.query("SELECT id FROM apartment WHERE owner_user_id = ?", (uid,))]
        for apartment_id in apartments:
            db.execute("DELETE FROM submission WHERE apartment_id = ?", (apartment_id,))
            db.execute("DELETE FROM reservation WHERE apartment_id = ?", (apartment_id,))
            db.execute("DELETE FROM ical_feed WHERE apartment_id = ?", (apartment_id,))
            db.execute("DELETE FROM apartment WHERE id = ?", (apartment_id,))
        db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (uid,))
        db.execute("DELETE FROM legal_acceptance WHERE user_account_id = ?", (uid,))
        db.execute("DELETE FROM audit WHERE owner_user_id = ?", (uid,))
        db.execute("DELETE FROM alert WHERE owner_user_id = ?", (uid,))
        db.execute("DELETE FROM user_account WHERE id = ?", (uid,))


@pytest.fixture(autouse=True)
def _database():
    db.init_db()
    _cleanup()
    yield
    _cleanup()


def _account(name: str, role: str = "host") -> int:
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


def _seed_host_at(level: int) -> int:
    """A host that has reached the first ``level`` + 1 core stages."""
    uid = _account(f"level{level}")
    at = _iso(NOW - timedelta(days=60))
    if level >= 1:
        db.insert("audit", {"at": at, "actor": "x", "action": "login", "owner_user_id": uid})
    if level >= 2:
        db.insert(
            "legal_acceptance",
            {"user_account_id": uid, "document": "terms", "version": "1", "accepted_at": at, "method": "clickwrap"},
        )
    if level >= 3:
        db.insert("legal_entity", {"name": "Biz", "owner_user_id": uid, "created_at": at})
    apartment_id = None
    if level >= 4:
        apartment_id = db.insert(
            "apartment", {"internal_name": f"Flat {level}", "owner_user_id": uid, "created_at": at}
        )
        # A broken calendar never counts as connected.
        db.insert(
            "ical_feed",
            {"apartment_id": apartment_id, "url": "https://example.test/a.ics", "last_status": "error", "created_at": at},
        )
    if level >= 5:
        db.insert(
            "ical_feed",
            {"apartment_id": apartment_id, "url": "https://example.test/b.ics", "last_status": "ok", "created_at": at},
        )
    if level >= 6:
        db.insert(
            "reservation",
            {
                "apartment_id": apartment_id, "uid": f"{PREFIX}{level}", "date_from": "2026-08-01",
                "date_to": "2026-08-03", "registration_completed_at": at,
                "created_at": at, "updated_at": at,
            },
        )
        # Failed filings never count.
        db.insert("submission", {"apartment_id": apartment_id, "created_at": at, "state": "error"})
    if level >= 7:
        db.insert(
            "submission",
            {"apartment_id": apartment_id, "created_at": at, "finished_at": at, "state": "ok"},
        )
    if level >= 8:
        for moment in (datetime(2026, 9, 20, tzinfo=timezone.utc), datetime(2026, 10, 2, tzinfo=timezone.utc)):
            db.insert(
                "submission",
                {"apartment_id": apartment_id, "created_at": _iso(moment), "finished_at": _iso(moment), "state": "partial"},
            )
    return uid


def _mine(data):
    return {row["username"]: row for row in data["rows"] if row["username"].startswith(PREFIX)}


def test_each_seeded_host_lands_on_its_stage():
    expected = [key for key, _column in admin_funnel.CORE_STAGES]
    ids = {level: _seed_host_at(level) for level in range(len(expected))}
    data = admin_funnel.rows(now=NOW)
    mine = _mine(data)
    assert data["previous_month"] == "2026-09" and data["current_month"] == "2026-10"
    for level, uid in ids.items():
        row = mine[f"{PREFIX}level{level}"]
        assert row["id"] == uid
        assert row["stage"] == expected[level], (level, row["stage"])
        assert row["stage_at"]
    retained = mine[f"{PREFIX}level8"]
    assert (retained["filings_previous"], retained["filings_current"]) == (1, 1)
    assert retained["last_filing_at"].startswith("2026-10-02")
    assert mine[f"{PREFIX}level7"]["filings_current"] == 0
    assert mine[f"{PREFIX}level7"]["retained_at"] is None
    # The error-state calendar and the failed filing were not counted.
    assert mine[f"{PREFIX}level4"]["first_calendar_at"] is None
    assert mine[f"{PREFIX}level6"]["first_filing_at"] is None
    # Stage counts include every stage reached; this test's hosts alone give 9..1.
    for index, key in enumerate(expected):
        assert data["counts"][key] >= len(expected) - index


def test_admins_are_not_in_the_funnel():
    _account("boss", role="admin")
    assert f"{PREFIX}boss" not in _mine(admin_funnel.rows(now=NOW))


def test_host_cannot_open_the_funnel_or_the_csv():
    _account("plainhost")
    client = _login("plainhost")
    assert client.get("/admin/funnel", follow_redirects=False).status_code == 403
    assert client.get("/admin/funnel.csv", follow_redirects=False).status_code == 403


def test_csv_has_the_same_rows_as_the_page():
    for level in (0, 4, 8):
        _seed_host_at(level)
    _account("admin", role="admin")
    client = _login("admin")
    page = client.get("/admin/funnel?lang=en")
    assert page.status_code == 200
    assert "funnel.stage." not in page.text and "funnel.col." not in page.text
    exported = client.get("/admin/funnel.csv")
    assert exported.status_code == 200
    assert exported.headers["content-type"].startswith("text/csv")
    reader = list(csv.DictReader(io.StringIO(exported.text)))
    data = admin_funnel.rows()
    assert [row["account_id"] for row in reader] == [str(row["id"]) for row in data["rows"]]
    assert [row["stage"] for row in reader] == [row["stage"] for row in data["rows"]]
    for row in data["rows"]:
        assert f'data-account="{row["id"]}"' in page.text
    by_name = {row["username"]: row for row in reader}
    assert by_name[f"{PREFIX}level4"]["stage"] == "first_property"
    assert by_name[f"{PREFIX}level8"]["stage"] == "retained"
    header = list(reader[0].keys())
    assert header[:4] == ["account_id", "username", "name", "active"]
    assert "created" in header and "first_filing" in header
    czech = client.get("/admin/funnel?lang=cs").text
    assert "Účty podle fáze" in czech


def test_wp20_hook_adds_stages_before_created(monkeypatch):
    monkeypatch.setattr(admin_funnel, "SIGNUP_STAGES", (("signed_up", "created_at"),))
    assert [key for key, _c in admin_funnel.stages()][:2] == ["signed_up", "created"]
    columns = [header for header, _key in admin_funnel.csv_columns("2026-09", "2026-10")]
    assert columns.index("signed_up") < columns.index("created")


def test_self_sign_up_stages_and_source_column():
    """WP20 filled the hook: signed up, e-mail verified, and the source flag."""
    _account("adminmade")
    tagged = _account("signedup")
    now = datetime.now(timezone.utc)
    db.execute(
        "UPDATE user_account SET signup_at = ?, email_verified_at = ?, "
        "signup_utm_source = 'google' WHERE id = ?",
        (_iso(now - timedelta(days=2)), _iso(now - timedelta(days=1)), tagged),
    )
    data = admin_funnel.rows()
    mine = _mine(data)
    assert data["stages"][:3] == ["signed_up", "email_verified", "created"]
    assert mine[PREFIX + "signedup"]["signup_source_present"] == "yes"
    assert mine[PREFIX + "adminmade"]["signup_source_present"] is None
    assert mine[PREFIX + "adminmade"]["signup_at"] is None
    db.execute("UPDATE user_account SET signup_utm_source = NULL WHERE id = ?", (tagged,))
    assert _mine(admin_funnel.rows())[PREFIX + "signedup"]["signup_source_present"] == "no"
    headers = [h for h, _k in admin_funnel.csv_columns("2026-09", "2026-10")]
    assert headers.index("signup_source_present") < headers.index("signed_up")
