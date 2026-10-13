"""The setup banner and its readiness steps (0101: the /setup wizard URLs are gone)."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app import auth, db, host_i18n, onboarding
from app.main import app


def setup_module():
    db.init_db()


def _session_client(username: str) -> TestClient:
    owner_id = auth.create_account(f"{username}@example.test", "", role="host", username=username)
    account = db.query_one("SELECT * FROM user_account WHERE id = ?", (owner_id,))
    client = TestClient(app)
    client.cookies.set(auth.SESSION_COOKIE, auth.issue_session(owner_id, account["session_version"]))
    client.owner_id = owner_id
    return client


def _apartment(owner_id: int, token: str) -> int:
    return db.insert(
        "apartment",
        {
            "owner_user_id": owner_id,
            "internal_name": "Banner flat",
            "permalink_token": token,
            "permalink_pin": "123456",
            "automation_mode": "manual",
            "submit_after_hours": 24,
            "active": 1,
            "created_at": db.utcnow(),
        },
    )


def test_the_old_setup_urls_are_gone():
    client = _session_client("setup-gone")
    for path in ("/setup", "/setup/welcome", "/setup/name", "/setup/address", "/setup/bookings"):
        assert client.get(path, follow_redirects=False).status_code == 404, path
        assert client.post(path, data={}, follow_redirects=False).status_code in (404, 405), path


def test_onboarding_no_longer_counts_wizard_steps():
    owner_id = auth.create_account("wizard-banner@example.test", "", role="host", username="wizard-banner")
    progress = onboarding.progress(owner_id)
    assert progress["wizard_complete"] is False
    assert progress["setup_url"] == "/apartments/new"
    property_step = next(step for step in progress["steps"] if step["id"] == "property")
    assert property_step["url"] in ("/apartments/new", "/entities")
    apartment_id = _apartment(owner_id, "tokbanner01")
    progress = onboarding.progress(owner_id)
    # wizard_step stays a readiness indicator; the banner names no step count.
    assert progress["wizard_step"] == "address"
    assert progress["wizard_total_steps"] == len(onboarding.WIZARD_STEPS)
    assert progress["setup_url"] == f"/apartments/{apartment_id}?view=settings&section=property#address"
    for lang in ("en", "cs"):
        line = host_i18n.translate(lang, "setup.banner.line", step=1, total=5)
        assert "5" not in line and "1" not in line


def test_wizard_step_progress_and_banner_target():
    owner_id = auth.create_account("wizard-step@example.test", "", role="host", username="wizard-step")
    assert onboarding.wizard_step(owner_id) == "name"
    apartment_id = _apartment(owner_id, "tok1234567")
    assert onboarding.wizard_step(owner_id) == "address"
    db.execute(
        "UPDATE apartment SET addr_street = 'S', addr_house_no = '1', addr_zip = '11000', addr_obec = 'Praha' "
        "WHERE id = ?",
        (apartment_id,),
    )
    assert onboarding.wizard_step(owner_id) == "bookings"
    assert onboarding.progress(owner_id)["setup_url"] == f"/apartments/{apartment_id}?view=bookings#calendars"


def test_banner_links_the_canonical_step_page():
    client = _session_client("setup-banner-link")
    apartment_id = _apartment(client.owner_id, "tokbanner02")
    page = client.get("/").text
    assert 'href="/setup"' not in page
    if "onboarding-banner-setup-link" in page:
        assert f'href="/apartments/{apartment_id}?view=settings&amp;section=property#address"' in page
