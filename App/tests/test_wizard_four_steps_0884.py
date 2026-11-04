"""0884: four required wizard steps; the rest are Do next cards on the done page."""
from __future__ import annotations

import json
from urllib.parse import urlparse

from app import auth, db, property_setup
from app.routes import invoices as invoice_routes
from tests.test_onboarding_wizard_survival import POLICE, _full_apartment, host  # noqa: F401
from tests.wizard_walk import walk_to

RETIRED = ("automation", "stay_fee", "door_lock", "try_it")


def _path(response) -> str:
    return urlparse(response.headers.get("location", "")).path


def _police_form(flat, host, **extra):
    data = {**POLICE, "setup_step": "police", "internal_name": flat["internal_name"],
            "legal_entity_id": str(host["entity"]), "default_purpose": "10",
            "return_to": f"/apartments/{flat['id']}/setup/guest_link"}
    data.update(extra)
    return data


def test_four_required_steps():
    assert property_setup.STEPS == ("property", "calendar", "police", "guest_link")
    assert property_setup.TOTAL_STEPS == 4
    assert set(property_setup.RETIRED_STEPS) == set(RETIRED)


def test_retired_step_urls_go_to_done(host):  # noqa: F811
    flat = _full_apartment(host)
    for step in [s for s in RETIRED if s != "try_it"]:  # try_it is an optional page again
        response = host["client"].get(f"/apartments/{flat['id']}/setup/{step}", follow_redirects=False)
        assert response.status_code == 303, step
        assert _path(response) == f"/apartments/{flat['id']}/setup/done", step


def test_saved_marks_of_retired_steps_stay_valid(host):  # noqa: F811
    flat = _full_apartment(host)
    old = {"stay_fee": "skipped", "door_lock": "not_needed", "try_it": "done", "automation": "done", "police": "waiting"}
    db.set_setting(f"property_setup:{flat['id']}", json.dumps(
        {"steps": old, "finished": False, "hidden": False, "legacy": False}))
    property_setup.mark(flat["id"], "calendar", "skipped")
    assert property_setup.load(flat["id"])["steps"] == {**old, "calendar": "skipped"}
    assert host["client"].get(f"/apartments/{flat['id']}/setup/done?lang=en").status_code == 200


def test_done_page_shows_four_rows_and_do_next_cards(host):  # noqa: F811
    flat = _full_apartment(host)
    page = host["client"].get(f"/apartments/{flat['id']}/setup/done?lang=en").text
    assert page.count('data-setup-summary-step="') == 4
    assert 'data-setup-next-step="stay_fee"' in page
    assert 'data-setup-next-step="try_it"' in page


def test_police_save_stores_the_automation_choice(host):  # noqa: F811
    flat = _full_apartment(host)
    data = _police_form(flat, host, automation_mode="immediate", submit_after_hours="6")
    response = host["client"].post(f"/apartments/{flat['id']}", data=data, follow_redirects=False)
    assert response.status_code == 303, response.text[:300]
    row = db.query_one("SELECT automation_mode FROM apartment WHERE id = ?", (flat["id"],))
    assert row["automation_mode"] == "immediate"
    assert property_setup.load(flat["id"])["steps"].get("automation") == "done"


def test_police_save_with_bad_hours_saves_nothing(host):  # noqa: F811
    flat = _full_apartment(host)
    data = _police_form(flat, host, automation_mode="scheduled", submit_after_hours="0", uby_name="Changed name")
    response = host["client"].post(f"/apartments/{flat['id']}", data=data, follow_redirects=False)
    assert response.status_code == 400
    row = db.query_one("SELECT automation_mode, submit_after_hours, uby_name FROM apartment WHERE id = ?", (flat["id"],))
    assert (row["automation_mode"], row["submit_after_hours"], row["uby_name"]) == ("scheduled", 6, POLICE["uby_name"])


def test_police_wait_keeps_the_automation_choice(host):  # noqa: F811
    flat = _full_apartment(host)
    db.update("apartment", flat["id"], {"uby_idub": ""})
    client = host["client"]
    assert walk_to(client, flat["id"], "police") == "police"
    response = client.post(f"/apartments/{flat['id']}/setup", data={
        "step": "police", "action": "wait", "setup_step": "police",
        "automation_mode": "manual", "submit_after_hours": "24"}, follow_redirects=False)
    assert response.status_code == 303
    assert db.query_one("SELECT automation_mode FROM apartment WHERE id = ?", (flat["id"],))["automation_mode"] == "manual"
    steps = property_setup.load(flat["id"])["steps"]
    assert steps["police"] == "waiting" and steps["automation"] == "done"


def test_stale_post_from_a_retired_step_saves_nothing(host):  # noqa: F811
    flat = _full_apartment(host)
    response = host["client"].post(f"/apartments/{flat['id']}", data={
        "setup_step": "stay_fee", "stay_fee_rate_czk": "99", "uby_idub": "",
        "return_to": f"/apartments/{flat['id']}/setup/door_lock"}, follow_redirects=False)
    assert response.status_code == 303
    assert _path(response) == f"/apartments/{flat['id']}/setup/done"
    row = db.query_one("SELECT stay_fee_rate_czk, uby_idub FROM apartment WHERE id = ?", (flat["id"],))
    assert row["stay_fee_rate_czk"] == 50 and row["uby_idub"] == POLICE["uby_idub"]


def test_try_it_card_starts_the_demo_after_setup_is_finished(host):  # noqa: F811
    flat = _full_apartment(host)
    property_setup.finish(flat["id"])
    response = host["client"].post(f"/apartments/{flat['id']}/setup",
                                   data={"step": "try_it", "action": "demo"}, follow_redirects=False)
    assert response.status_code == 303
    assert _path(response).startswith("/l/") and "/demo/" in _path(response)


def test_register_fill_from_the_property_step(host, monkeypatch):  # noqa: F811
    db.update("legal_entity", host["entity"], {"archived_at": db.utcnow()})
    apt = db.insert("apartment", {"internal_name": "No business yet", "owner_user_id": host["owner"],
                                  "permalink_token": auth.new_permalink_token(), "active": 1, "created_at": db.utcnow()})
    client = host["client"]
    page = client.get(f"/apartments/{apt}/setup/property?lang=en").text
    assert 'id="wizard-ares-form"' in page and 'name="fill_from_register"' in page
    assert 'data-ruian-suggest' in page and "ruian_suggest.js" in page
    monkeypatch.setattr(invoice_routes, "register_lookup",
                        lambda owner, lang, ico: ({"name": "Register s.r.o.", "seat": "Brno", "dic": "CZ12345678"}, None))
    back = f"/apartments/{apt}/setup/property"
    filled = client.post("/entities", data={"fill_from_register": "1", "ico": "12345679", "next": back})
    assert filled.status_code == 200
    assert "Register s.r.o." in filled.text and f'name="next" value="{back}"' in filled.text
    saved = client.post("/entities", data={"name": "Register s.r.o.", "seat": "Brno", "ico": "12345679",
                                           "contact_email": "wizard@example.test", "next": back},
                        follow_redirects=False)
    assert saved.status_code == 303 and _path(saved) == back
