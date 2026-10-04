"""WP07: long-lived caching for versioned static files, per-job heartbeats,
and signature.js only where it is used."""
from __future__ import annotations

import re
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import claim, config, db, icalsync, mail, scheduler
from app.main import app
from tests.conftest import complete_guest_claim

TEMPLATES = Path(__file__).resolve().parent.parent / "app" / "templates"
IMMUTABLE = "public, max-age=31536000, immutable"


# --- static caching ----------------------------------------------------------


def test_a_versioned_static_file_is_cached_for_a_year():
    response = TestClient(app).get("/static/app.css?v=20261002a")
    assert response.status_code == 200
    assert response.headers["cache-control"] == IMMUTABLE


def test_an_unversioned_static_file_is_cached_for_a_day_only():
    response = TestClient(app).get("/static/favicon.png")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "public, max-age=86400"
    assert "immutable" not in response.headers["cache-control"]


def test_a_missing_static_file_is_not_cached():
    response = TestClient(app).get("/static/does-not-exist.css?v=1")
    assert response.status_code == 404
    assert "immutable" not in response.headers.get("cache-control", "")


def test_html_pages_keep_no_store():
    db.init_db()
    response = TestClient(app).get("/login")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store, private"
    assert "immutable" not in response.headers["cache-control"]


def test_every_static_url_in_the_templates_carries_a_version():
    """An unversioned URL would stay in browsers for a year after a change.

    Absolute URLs built from ``public_base_url`` (og:image, JSON-LD) are for
    crawlers and are exempt; they get the one-day header. The archived
    Ticket Wallet templates are reference copies that no route renders.
    """
    missing = []
    for path in TEMPLATES.rglob("*.html"):
        if "archive" in path.relative_to(TEMPLATES).parts:
            continue
        text = path.read_text(encoding="utf-8")
        for match in re.finditer(r'(?:src|href)="(/static/[^"]+)"', text):
            if "?v=" not in match.group(1):
                missing.append(f"{path.relative_to(TEMPLATES)}: {match.group(1)}")
    assert not missing, missing


# --- heartbeats ----------------------------------------------------------------


@pytest.fixture
def pings(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "heartbeat.sqlite3")
    db.init_db()
    calls = []
    monkeypatch.setattr(
        scheduler.requests, "get", lambda url, **kwargs: calls.append((url, kwargs))
    )
    return calls


def test_a_successful_calendar_sync_pings_its_heartbeat(monkeypatch, pings):
    monkeypatch.setattr(config, "HEARTBEAT_ICAL_URL", "https://heartbeat.example/ical")
    monkeypatch.setattr(icalsync, "sync_all", lambda: {"feeds": 0})
    scheduler._job_sync_calendars()
    assert pings == [("https://heartbeat.example/ical", {"timeout": 5})]


def test_a_failed_calendar_sync_does_not_ping(monkeypatch, pings):
    monkeypatch.setattr(config, "HEARTBEAT_ICAL_URL", "https://heartbeat.example/ical")

    def boom():
        raise RuntimeError("sync blew up")

    monkeypatch.setattr(icalsync, "sync_all", boom)
    scheduler._job_sync_calendars()
    assert pings == []


def _quiet_mail_steps(monkeypatch):
    monkeypatch.setattr(claim, "expire_holds", lambda: 0)
    monkeypatch.setattr(mail, "drain", lambda: 0)
    monkeypatch.setattr(claim, "sweep_reminders", lambda: 0)
    monkeypatch.setattr(mail, "purge_old", lambda: 0)


def test_a_successful_mail_run_pings_its_heartbeat(monkeypatch, pings):
    monkeypatch.setattr(config, "HEARTBEAT_MAIL_URL", "https://heartbeat.example/mail")
    _quiet_mail_steps(monkeypatch)
    scheduler._job_mail()
    assert pings == [("https://heartbeat.example/mail", {"timeout": 5})]


def test_a_mail_run_with_a_failed_step_does_not_ping(monkeypatch, pings):
    monkeypatch.setattr(config, "HEARTBEAT_MAIL_URL", "https://heartbeat.example/mail")
    _quiet_mail_steps(monkeypatch)

    def boom():
        raise RuntimeError("drain blew up")

    monkeypatch.setattr(mail, "drain", boom)
    scheduler._job_mail()
    assert pings == []


def test_unset_heartbeat_urls_send_nothing(monkeypatch, pings):
    monkeypatch.setattr(config, "HEARTBEAT_ICAL_URL", "")
    monkeypatch.setattr(config, "HEARTBEAT_MAIL_URL", "")
    monkeypatch.setattr(icalsync, "sync_all", lambda: {"feeds": 0})
    _quiet_mail_steps(monkeypatch)
    scheduler._job_sync_calendars()
    scheduler._job_mail()
    assert pings == []


def test_a_failing_ping_is_logged_not_raised(monkeypatch, pings, caplog):
    monkeypatch.setattr(config, "HEARTBEAT_MAIL_URL", "https://heartbeat.example/mail")
    _quiet_mail_steps(monkeypatch)

    def down(url, **kwargs):
        raise OSError("network down")

    monkeypatch.setattr(scheduler.requests, "get", down)
    scheduler._job_mail()
    assert "heartbeat ping for mail failed" in caplog.text


# --- signature.js only on the form and PIN pages ------------------------------

TOKEN = "wp07-sigjs-token"
SIGNATURE_JS = "/static/signature.js"


def _cleanup():
    apartment = db.query_one("SELECT * FROM apartment WHERE permalink_token = ?", (TOKEN,))
    if not apartment:
        return
    db.execute(
        "DELETE FROM reservation_claim WHERE reservation_id IN "
        "(SELECT id FROM reservation WHERE apartment_id = ?)",
        (apartment["id"],),
    )
    db.execute("DELETE FROM reservation WHERE apartment_id = ?", (apartment["id"],))
    db.execute("DELETE FROM apartment WHERE id = ?", (apartment["id"],))
    db.execute("DELETE FROM legal_entity WHERE id = ?", (apartment["legal_entity_id"],))


def _stay() -> int:
    db.init_db()
    _cleanup()
    now = db.utcnow()
    today = claim.prague_today()
    entity_id = db.insert("legal_entity", {"name": "WP07 test", "created_at": now})
    apartment_id = db.insert(
        "apartment",
        {
            "legal_entity_id": entity_id,
            "internal_name": "WP07 apartment",
            "permalink_token": TOKEN,
            "permalink_pin": "482915",
            "permalink_window_days": 14,
            "default_purpose": "10",
            "automation_mode": "manual",
            "active": 1,
            "created_at": now,
        },
    )
    return db.insert(
        "reservation",
        {
            "apartment_id": apartment_id,
            "source": "airbnb",
            "uid": "wp07-sigjs",
            "date_from": today.isoformat(),
            "date_to": (today + timedelta(days=3)).isoformat(),
            "status": "active",
            "created_at": now,
            "updated_at": now,
        },
    )


def test_signature_js_loads_on_the_form_but_not_on_the_stay_page():
    reservation_id = _stay()
    try:
        browser = TestClient(app)
        stay = browser.get(f"/l/{TOKEN}/{reservation_id}?lang=en")
        assert stay.status_code == 200
        assert "data-guest-wizard" not in stay.text
        assert SIGNATURE_JS not in stay.text
        assert "/static/guest-enhancements.js" in stay.text

        complete_guest_claim(browser, TOKEN, reservation_id)
        form = browser.get(f"/l/{TOKEN}/{reservation_id}?lang=en")
        assert form.status_code == 200
        assert "data-guest-wizard" in form.text
        assert SIGNATURE_JS in form.text
        assert form.text.index("/static/skeleton.js") < form.text.index(SIGNATURE_JS)
        assert form.text.index(SIGNATURE_JS) < form.text.index("/static/guest-enhancements.js")
    finally:
        _cleanup()


def test_signature_js_loads_on_the_pin_page(monkeypatch):
    """initPinReturn in signature.js carries the claim secret across the PIN gate."""
    monkeypatch.setattr(config, "GUEST_PIN_REQUIRED", True)
    _stay()
    try:
        page = TestClient(app).get(f"/l/{TOKEN}?lang=en")
        assert page.status_code == 200
        assert 'action="/l/' + TOKEN + '/pin' in page.text
        assert SIGNATURE_JS in page.text
    finally:
        _cleanup()
