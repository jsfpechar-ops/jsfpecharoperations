"""0102 round: wizard saves must not wipe fields owned by other steps."""
from __future__ import annotations

import secrets

import pytest

from app import auth, config, db, demo, feed_url, icalsync, property_setup
from app.main import app
from app.routes import admin as admin_routes
from tests.conftest import login_as

ADDRESS = {
    "addr_okres": "Brno-město",
    "addr_obec": "Brno",
    "addr_obec_cast": "Černá Pole",
    "addr_street": "Synthetic",
    "addr_house_no": "12",
    "addr_orient_no": "3",
    "addr_zip": "602 00",
}
POLICE = {
    "uby_idub": "123456789012",
    "uby_ws_user": "UBY-WSsynth",
    "uby_ws_password": "synthetic-secret",
    "uby_mark": "SYNTH",
    "uby_name": "Synthetic Garden",
    "uby_contact": "wizard@example.test",
}

GUARDED_COLUMNS = (
    "uby_idub",
    "uby_ws_user",
    "uby_name",
    "uby_mark",
    "uby_contact",
    "guest_message",
    "notes",
    "passport_photo_policy",
    "permalink_window_days",
    "permalink_reachback_days",
    "automation_mode",
    "submit_after_hours",
    "default_purpose",
    "stay_fee_rate_czk",
    "lock_provider",
    "lock_id",
    "checkin_hour",
    "checkout_hour",
    *ADDRESS.keys(),
)

STEP_OWNERS = {
    "property": (
        "internal_name",
        "city_en",
        "legal_entity_id",
        "data_controller_entity_id",
        "default_purpose",
        *ADDRESS.keys(),
    ),
    "police": ("uby_idub", "uby_mark", "uby_name", "uby_contact", "uby_ws_user"),
    "stay_fee": (
        "stay_fee_rate_czk",
        "stay_fee_cadence",
        "stay_fee_vs",
        "stay_fee_authority_name",
        "stay_fee_authority_address",
        "stay_fee_authority_contact",
        "stay_fee_payee",
        "stay_fee_instruction",
        "stay_fee_council_account",
    ),
    "door_lock": ("lock_provider", "lock_id", "checkin_hour", "checkout_hour"),
    "automation": ("automation_mode", "submit_after_hours"),
    "calendar": (),
    "guest_link": (),
    "try_it": (),
}


@pytest.fixture
def host(monkeypatch):
    db.init_db()
    monkeypatch.setattr(config, "DOOR_CODES_ENABLED", True)
    monkeypatch.setattr(config, "TTLOCK_CLIENT_ID", "cid")
    monkeypatch.setattr(config, "TTLOCK_CLIENT_SECRET", "csecret")
    monkeypatch.setattr(feed_url, "validate_calendar_url", lambda url: url)
    monkeypatch.setattr(
        icalsync,
        "sync_all",
        lambda apartment_id=None, owner_user_id=None: {
            "feeds": 1,
            "created": 0,
            "updated": 0,
            "cancelled": 0,
            "errors": 0,
            "not_modified": 0,
            "unchanged": 0,
            "changed": 0,
        },
    )
    username = f"survival-{secrets.token_hex(4)}"
    owner = auth.create_account(f"{username}@example.test", "Wizard Host", role="host", username=username)
    entity = db.insert(
        "legal_entity",
        {
            "name": "Synthetic Operator s.r.o.",
            "seat": "Brno",
            "ico": "12345678",
            "contact_email": "wizard@example.test",
            "owner_user_id": owner,
            "created_at": db.utcnow(),
        },
    )
    from fastapi.testclient import TestClient

    client = TestClient(app)
    assert login_as(client, username, url="/login?lang=en", follow_redirects=False).status_code == 303
    yield {"client": client, "owner": owner, "entity": entity}
    for row in db.query("SELECT id FROM apartment WHERE owner_user_id = ?", (owner,)):
        db.execute("DELETE FROM settings WHERE key = ?", (f"property_setup:{row['id']}",))
    db.execute(
        "DELETE FROM ical_feed WHERE apartment_id IN (SELECT id FROM apartment WHERE owner_user_id = ?)",
        (owner,),
    )


def _report_complete(apartment_id: int) -> bool:
    apartment = db.query_one("SELECT * FROM apartment WHERE id = ?", (apartment_id,))
    feeds = db.query("SELECT id FROM ical_feed WHERE apartment_id = ?", (apartment_id,))
    issues = admin_routes._apartment_issues(apartment)
    return all(
        item["done"]
        for item in admin_routes._readiness(apartment, [], issues, bool(feeds), invite=False)["report"]
    )


def _full_apartment(host) -> dict:
    apt_id = db.insert(
        "apartment",
        {
            "internal_name": "Guarded Flat",
            "owner_user_id": host["owner"],
            "legal_entity_id": host["entity"],
            "city_en": "Brno",
            "permalink_token": auth.new_permalink_token(),
            "permalink_pin": auth.new_permalink_pin(),
            "active": 1,
            "created_at": db.utcnow(),
            "guest_message": "Welcome guarded guests",
            "notes": "Operator notes kept",
            "passport_photo_policy": "required_foreign",
            "permalink_window_days": 5,
            "permalink_reachback_days": 30,
            "automation_mode": "scheduled",
            "submit_after_hours": 6,
            "default_purpose": "10",
            "stay_fee_rate_czk": 50,
            "stay_fee_cadence": "monthly",
            **ADDRESS,
            **{k: v for k, v in POLICE.items() if k != "uby_ws_password"},
            "uby_ws_password_enc": db.encrypt_secret(POLICE["uby_ws_password"]),
        },
    )
    property_setup.start(apt_id)
    return db.query_one("SELECT * FROM apartment WHERE id = ?", (apt_id,))


def _snapshot(row) -> dict:
    return {key: row[key] for key in GUARDED_COLUMNS}


def _assert_unchanged(before: dict, after: dict, step: str):
    owned = set(STEP_OWNERS[step])
    for key, value in before.items():
        if key in owned:
            continue
        assert after[key] == value, f"{step} overwrote {key}: {after[key]!r} != {value!r}"


def test_cross_step_guarded_fields_survive_each_wizard_post(host):
    """0A: every wizard post leaves other columns untouched; police stays complete."""
    flat = _full_apartment(host)
    apt_id = flat["id"]
    client = host["client"]
    base = f"/apartments/{apt_id}/setup"
    assert _report_complete(apt_id)

    identity = {
        "internal_name": flat["internal_name"],
        "legal_entity_id": str(host["entity"]),
        "city_en": flat["city_en"],
        "default_purpose": flat["default_purpose"],
    }

    steps = [
        (
            "property",
            lambda: client.post(
                f"/apartments/{apt_id}",
                data={
                    **identity,
                    **ADDRESS,
                    "setup_step": "property",
                    "return_to": f"{base}/calendar",
                },
                follow_redirects=False,
            ),
        ),
        (
            "calendar",
            lambda: client.post(
                base,
                data={"step": "calendar", "action": "skip"},
                follow_redirects=False,
            ),
        ),
        (
            "guest_link",
            lambda: client.post(
                base,
                data={"step": "guest_link", "action": "done"},
                follow_redirects=False,
            ),
        ),
        (
            "try_it",
            lambda: client.post(
                base,
                data={"step": "try_it", "action": "skip"},
                follow_redirects=False,
            ),
        ),
        (
            "police",
            lambda: client.post(
                f"/apartments/{apt_id}",
                data={
                    **identity,
                    "setup_step": "police",
                    "return_to": f"{base}/stay_fee",
                    **{k: v for k, v in POLICE.items() if k != "uby_ws_password"},
                },
                follow_redirects=False,
            ),
        ),
        (
            "stay_fee",
            lambda: client.post(
                f"/apartments/{apt_id}",
                data={
                    **identity,
                    "setup_step": "stay_fee",
                    "return_to": f"{base}/door_lock",
                    "stay_fee_rate_czk": "50",
                    "stay_fee_cadence": "monthly",
                },
                follow_redirects=False,
            ),
        ),
        (
            "door_lock",
            lambda: client.post(
                f"/apartments/{apt_id}",
                data={
                    **identity,
                    "setup_step": "door_lock",
                    "return_to": f"{base}/automation",
                    "door_code_section": "1",
                    "door_codes_fields": "1",
                },
                follow_redirects=False,
            ),
        ),
        (
            "automation",
            lambda: client.post(
                f"/apartments/{apt_id}/automation-timing",
                data={
                    "automation_mode": "scheduled",
                    "submit_after_hours": "6",
                    "setup_step": "automation",
                    "return_to": f"{base}/done",
                },
                follow_redirects=False,
            ),
        ),
    ]

    for step, action in steps:
        before = _snapshot(db.query_one("SELECT * FROM apartment WHERE id = ?", (apt_id,)))
        response = action()
        assert response.status_code in (200, 303, 400), (step, response.status_code)
        after = _snapshot(db.query_one("SELECT * FROM apartment WHERE id = ?", (apt_id,)))
        _assert_unchanged(before, after, step)
        if step in ("stay_fee", "door_lock", "automation"):
            assert _report_complete(apt_id), step


def test_property_step_shows_stored_values_and_refused_save(host):
    """0B: GET shows stored name/address; refused save keeps typed values."""
    apt_id = db.insert(
        "apartment",
        {
            "internal_name": "Named but no ZIP",
            "owner_user_id": host["owner"],
            "legal_entity_id": host["entity"],
            "city_en": "Brno",
            "addr_obec": "Brno",
            "addr_house_no": "9",
            "addr_street": "Masarykova",
            "permalink_token": auth.new_permalink_token(),
            "permalink_pin": auth.new_permalink_pin(),
            "active": 1,
            "created_at": db.utcnow(),
        },
    )
    property_setup.start(apt_id)
    client = host["client"]
    page = client.get(f"/apartments/{apt_id}/setup/property?lang=en")
    assert page.status_code == 200
    assert 'value="Named but no ZIP"' in page.text
    assert 'value="Masarykova"' in page.text
    assert 'value="Brno"' in page.text
    refused = client.post(
        f"/apartments/{apt_id}",
        data={
            "internal_name": "Typed name",
            "legal_entity_id": str(host["entity"]),
            "city_en": "Typed city",
            "addr_obec": "Typed obec",
            "addr_house_no": "1",
            "setup_step": "property",
            "return_to": f"/apartments/{apt_id}/setup/calendar",
        },
        follow_redirects=False,
    )
    assert refused.status_code == 400
    assert 'value="Typed name"' in refused.text
    assert 'value="Typed obec"' in refused.text


def test_calendar_sync_failure_stays_in_wizard(host, monkeypatch):
    """0C: a failed first sync returns to the wizard calendar step with the error."""
    flat = _full_apartment(host)
    apt_id = flat["id"]
    monkeypatch.setattr(
        icalsync,
        "sync_all",
        lambda apartment_id=None, owner_user_id=None: {
            "feeds": 1,
            "created": 0,
            "updated": 0,
            "cancelled": 0,
            "errors": 1,
            "not_modified": 0,
            "unchanged": 0,
            "changed": 0,
        },
    )
    response = host["client"].post(
        f"/apartments/{apt_id}/feeds",
        data={
            "label": "airbnb",
            "url": "https://example.test/calendar.ics",
            "return_to": f"/apartments/{apt_id}/setup/guest_link",
            "setup_step": "calendar",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert f"/apartments/{apt_id}/setup/" in response.headers["location"]
    assert "view=bookings" not in response.headers["location"]
    follow = host["client"].get(response.headers["location"], follow_redirects=False)
    assert follow.status_code == 200
    assert 'data-setup-step="calendar"' in follow.text
    assert 'data-toast-kind="error"' in follow.text
    assert "read" in follow.text.lower()


def test_stay_fee_save_skips_door_lock_when_unavailable(host, monkeypatch):
    """0D: stay_fee save lands on automation with one redirect when door lock does not apply."""
    monkeypatch.setattr(config, "DOOR_CODES_ENABLED", False)
    flat = _full_apartment(host)
    apt_id = flat["id"]
    client = host["client"]
    base = f"/apartments/{apt_id}/setup"
    for step, action in (
        ("calendar", "skip"),
        ("guest_link", "done"),
        ("try_it", "skip"),
    ):
        client.post(base, data={"step": step, "action": action}, follow_redirects=False)
    saved = client.post(
        f"/apartments/{apt_id}",
        data={
            "internal_name": flat["internal_name"],
            "legal_entity_id": str(host["entity"]),
            "city_en": flat["city_en"],
            "default_purpose": "10",
            "setup_step": "stay_fee",
            "return_to": property_setup.wizard_url(apt_id, "automation"),
            "stay_fee_rate_czk": "50",
            "stay_fee_cadence": "monthly",
        },
        follow_redirects=False,
    )
    assert saved.status_code == 303
    from urllib.parse import urlparse

    location = saved.headers["location"]
    assert urlparse(location).path.endswith("/setup/automation")
    assert "/setup/door_lock" not in location
    page = client.get(location, follow_redirects=False)
    assert page.status_code == 200
    assert 'data-setup-step="automation"' in page.text


def test_try_it_skip_deletes_demo_stay(host):
    """0E: Skip removes an open demo stay instead of leaving it behind."""
    flat = _full_apartment(host)
    apt_id = flat["id"]
    client = host["client"]
    base = f"/apartments/{apt_id}/setup"
    client.post(base, data={"step": "calendar", "action": "skip"}, follow_redirects=False)
    client.post(base, data={"step": "guest_link", "action": "done"}, follow_redirects=False)
    client.post(base, data={"step": "try_it", "action": "demo"}, follow_redirects=False)
    stay = demo.demo_stay_for(apt_id)
    assert stay is not None
    skipped = client.post(base, data={"step": "try_it", "action": "skip"}, follow_redirects=False)
    assert skipped.status_code == 303
    assert demo.demo_stay_for(apt_id) is None


def test_refuse_setup_save_ignores_posted_id(host):
    flat = _full_apartment(host)
    response = host["client"].post(
        f"/apartments/{flat['id']}",
        data={
            "id": "999",
            "internal_name": flat["internal_name"],
            "legal_entity_id": str(host["entity"]),
            "city_en": flat["city_en"],
            "setup_step": "police",
            "return_to": f"/apartments/{flat['id']}/setup/stay_fee",
            "uby_idub": "12",
            "uby_ws_user": "x",
            "uby_mark": "BAD",
            "uby_name": "Bad",
        },
        follow_redirects=False,
    )
    assert response.status_code == 400
    assert 'name="id"' not in response.text
    assert 'value="999"' not in response.text


def test_form_return_to_drops_fragment_by_default(host):
    flat = _full_apartment(host)
    response = host["client"].post(
        f"/apartments/{flat['id']}/archive",
        data={"return_to": "/smart-locks#smart-locks-how"},
        follow_redirects=False,
    )
    assert response.status_code in (303, 400, 404)
    if response.status_code == 303:
        from urllib.parse import urlparse

        assert urlparse(response.headers["location"]).path == "/smart-locks"
        assert "#" not in response.headers["location"]


@pytest.mark.parametrize("lock_available", [False, True])
@pytest.mark.parametrize("mode", ["manual", "scheduled"])
@pytest.mark.parametrize("defer_police", [False, True])
def test_finish_setup_with_police_credentials_deferred(host, monkeypatch, lock_available, mode, defer_police):
    """Waiting is an explicit answer, while unacknowledged missing credentials block."""
    from urllib.parse import urlparse

    monkeypatch.setattr(config, "DOOR_CODES_ENABLED", lock_available)
    flat = _full_apartment(host)
    apt_id = flat["id"]
    db.execute(
        "UPDATE apartment SET uby_idub = '', uby_ws_user = '', uby_mark = '', "
        "uby_name = '', uby_ws_password_enc = NULL WHERE id = ?",
        (apt_id,),
    )
    client = host["client"]
    base = f"/apartments/{apt_id}/setup"
    actions = [("calendar", "skip"), ("guest_link", "done"), ("try_it", "skip")]
    if defer_police:
        actions.extend([("police", "wait"), ("stay_fee", "skip")])
        if lock_available:
            actions.append(("door_lock", "skip"))
    for step, action in actions:
        response = client.post(base, data={"step": step, "action": action}, follow_redirects=False)
        assert response.status_code == 303
    saved = client.post(
        f"/apartments/{apt_id}/automation-timing",
        data={
            "automation_mode": mode,
            "submit_after_hours": "24",
            "setup_step": "automation",
            "return_to": f"{base}/done",
        },
        follow_redirects=False,
    )
    assert saved.status_code == 303
    target = urlparse(saved.headers["location"]).path
    assert target == f"{base}/{'done' if defer_police else 'police'}"
    assert property_setup.load(apt_id)["finished"] is defer_police
    assert not _report_complete(apt_id)
    if defer_police:
        page = client.get(f"{base}/done?lang=en")
        assert page.status_code == 200
        assert 'class="is-waiting"' in page.text
        assert f'href="{base}/police"' in page.text
        assert property_setup.load(apt_id)["steps"]["police"] == "waiting"
        entry = client.get(base, follow_redirects=False)
        assert urlparse(entry.headers["location"]).path == f"/apartments/{apt_id}"
        assert client.get(f"{base}/police").status_code == 200
        assert property_setup.load(apt_id)["finished"] is True


@pytest.mark.parametrize("missing_step", ["calendar", "guest_link", "try_it"])
def test_waiting_for_police_does_not_skip_other_required_steps(host, monkeypatch, missing_step):
    from urllib.parse import urlparse

    monkeypatch.setattr(config, "DOOR_CODES_ENABLED", False)
    flat = _full_apartment(host)
    apt_id = flat["id"]
    db.execute(
        "UPDATE apartment SET uby_idub = '', uby_ws_password_enc = NULL WHERE id = ?",
        (apt_id,),
    )
    for step, mark in (("calendar", "skipped"), ("guest_link", "done"),
                       ("try_it", "skipped"), ("police", "waiting")):
        if step != missing_step:
            property_setup.mark(apt_id, step, mark)
    base = f"/apartments/{apt_id}/setup"
    response = host["client"].post(
        f"/apartments/{apt_id}/automation-timing",
        data={
            "automation_mode": "manual",
            "submit_after_hours": "24",
            "setup_step": "automation",
            "return_to": f"{base}/done",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert urlparse(response.headers["location"]).path == f"{base}/{missing_step}"
    assert property_setup.load(apt_id)["finished"] is False
