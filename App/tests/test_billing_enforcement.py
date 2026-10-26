"""Brief 0415: the plan sets the limits. AI, TTLock, calendars, read-only; reporting never stops."""
from __future__ import annotations

import pathlib
import secrets

import pytest
from fastapi.testclient import TestClient

from app import auth, billing, config, db, havel, icalsync, leon, ttlock
from app.main import app
from tests.conftest import login_as


@pytest.fixture
def host():
    db.init_db()
    username = f"enf{secrets.token_hex(4)}"
    owner_id = auth.create_account(f"{username}@example.test", "Enforcement host", username=username)
    apartment_id = db.insert("apartment", {"internal_name": "Enforcement flat", "owner_user_id": owner_id, "created_at": db.utcnow()})
    yield {"owner": owner_id, "username": username, "apartment": apartment_id}
    db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (owner_id,))
    db.execute("DELETE FROM billing_account WHERE owner_user_id = ?", (owner_id,))


@pytest.fixture
def billing_on(monkeypatch):
    monkeypatch.setattr(config, "BILLING_ENABLED", True)


def _status(owner: int, status: str, plan=None, ttlock_addon=0) -> None:
    billing.ensure_account(owner)
    db.execute(
        "UPDATE billing_account SET status = ?, plan = ?, addon_ttlock = ? WHERE owner_user_id = ?",
        (status, plan, ttlock_addon, owner),
    )


def test_billing_off_changes_nothing(host, monkeypatch):
    monkeypatch.setattr(ttlock, "enabled", lambda: True)
    _status(host["owner"], "paused")
    assert ttlock.allowed_for(host["owner"]) is True
    assert havel.plan_multiplier(host["owner"]) == 1
    assert leon.plan_multiplier(host["apartment"]) == 1
    assert icalsync.import_paused(host["apartment"], {}) is False


def test_og_hosts_keep_everything(host, billing_on, monkeypatch):
    monkeypatch.setattr(ttlock, "enabled", lambda: True)
    assert ttlock.allowed_for(host["owner"]) is True
    assert havel.plan_multiplier(host["owner"]) == 1


@pytest.mark.parametrize("status, plan, addon, allowed, multiplier", [
    ("trialing", None, 0, True, 1),
    ("active", "standard", 0, False, 1),
    ("active", "standard", 1, True, 1),
    ("active", "max", 0, True, 3),
    ("overdue", "max", 0, True, 3),
    ("paused", "max", 0, False, 0),
])
def test_the_plan_sets_ttlock_and_ai(host, billing_on, monkeypatch, status, plan, addon, allowed, multiplier):
    monkeypatch.setattr(ttlock, "enabled", lambda: True)
    _status(host["owner"], status, plan, addon)
    assert ttlock.allowed_for(host["owner"]) is allowed
    assert havel.plan_multiplier(host["owner"]) == multiplier
    assert leon.plan_multiplier(host["apartment"]) == multiplier


def test_havel_limits_scale_with_the_plan(host, billing_on):
    _status(host["owner"], "active", "max")
    left, _period = havel.remaining(host["owner"])
    assert left == 3 * min(config.HAVEL_WEEKLY_MESSAGES, config.HAVEL_MONTHLY_MESSAGES)
    _status(host["owner"], "paused", "max")
    assert havel.remaining(host["owner"])[0] == 0
    assert havel.limit_state(host["owner"]) is not None


def test_a_paused_plan_stops_calendar_import_only(host, billing_on):
    _status(host["owner"], "paused", "standard")
    assert icalsync.import_paused(host["apartment"], {}) is True
    _status(host["owner"], "active", "standard")
    assert icalsync.import_paused(host["apartment"], {}) is False


def test_a_paused_plan_is_read_only_but_filing_and_the_way_out_stay_open(host, billing_on):
    client = TestClient(app)
    login_as(client, host["username"], url="/login?lang=cs")
    _status(host["owner"], "paused", "standard")
    blocked = client.post("/apartments/999999/archive", follow_redirects=False)
    assert blocked.status_code == 303
    assert blocked.headers["location"] == "/predplatne?paused=1"
    for path in ("/reservations/999999/submit", "/guests/999999/resend", "/reservations/submit-ready"):
        response = client.post(path, follow_redirects=False)
        assert response.headers.get("location") != "/predplatne?paused=1", path
    assert client.get("/apartments").status_code == 200
    _status(host["owner"], "active", "standard")
    allowed = client.post("/apartments/999999/archive", follow_redirects=False)
    assert allowed.headers.get("location") != "/predplatne?paused=1"


def test_the_filing_code_never_asks_about_billing():
    """UbyPort reporting goes on whatever the plan: the filing path must not read billing."""
    app_dir = pathlib.Path(__file__).resolve().parents[1] / "app"
    for name in ("reporting.py", "submit_state.py"):
        path = app_dir / name
        if path.exists():
            assert "billing" not in path.read_text(encoding="utf-8"), name
    for path in (app_dir / "ubyport").rglob("*.py"):
        assert "billing" not in path.read_text(encoding="utf-8"), path.name
