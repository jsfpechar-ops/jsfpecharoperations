"""0397: door codes switched on without check-in/out times: never a 500."""
from __future__ import annotations

import re

from app import db
from tests.test_door_code_one_lock_one_property import (  # noqa: F401  (fixture)
    LOCK,
    _apartment,
    _client,
    two_properties,
)


def _post(client, apartment_id, entity, section, *, hours=True):
    data = {
        "internal_name": _apartment(apartment_id)["internal_name"],
        "legal_entity_id": str(entity),
        "return_to": f"/apartments/{apartment_id}?view=settings&section={section}",
        "door_code_section": "1",
        "door_codes_fields": "1",
        "door_codes": "1",
        "lock_id": LOCK["lock_id"],
    }
    if hours:
        data.update({"checkin_hour": "", "checkout_hour": ""})
    return client.post(
        f"/apartments/{apartment_id}", data=data, follow_redirects=False,
        headers={"accept": "text/html"},
    )


def test_lock_tab_save_without_times_stays_on_the_lock_tab(two_properties):
    _, entity, (a, _) = two_properties
    response = _post(_client(), a, entity, "lock")
    assert response.status_code == 400
    page = response.text
    assert 'id="door-code-times-error" role="alert"' in page
    assert "Set them first." in page
    assert re.search(r'data-settings-group="lock" id="settings-lock"', page)
    assert re.search(r'class="property-settings-group is-active" data-settings-group="lock"', page)
    switch = re.search(r'<input type="checkbox" role="switch" id="door_codes"[^>]*>', page).group(0)
    assert "checked" in switch
    option = re.search(r'<option value="%s"[^>]*>' % LOCK["lock_id"], page).group(0)
    assert "selected" in option
    assert "Not saved yet" in page or "is-unsaved" in page
    assert _apartment(a)["lock_provider"] is None


def test_lock_tab_save_without_posted_hours_does_not_crash(two_properties):
    _, entity, (a, _) = two_properties
    response = _post(_client(), a, entity, "lock", hours=False)
    assert response.status_code == 400
    assert 'id="door-code-times-error"' in response.text
    assert _apartment(a)["lock_provider"] is None


def test_property_tab_save_with_blank_times_shows_the_time_error(two_properties):
    _, entity, (a, _) = two_properties
    response = _post(_client(), a, entity, "property")
    assert response.status_code == 400
    assert "Choose the check-in and check-out hour." in response.text
    assert 'id="door-code-times-error"' not in response.text
    assert _apartment(a)["lock_provider"] is None


def test_times_set_then_codes_turn_on(two_properties):
    _, entity, (a, _) = two_properties
    db.update("apartment", a, {"checkin_hour": 15, "checkout_hour": 10})
    client = _client()
    data = {
        "internal_name": "Flat A", "legal_entity_id": str(entity),
        "return_to": f"/apartments/{a}?view=settings&section=lock",
        "door_code_section": "1", "door_codes_fields": "1", "door_codes": "1",
        "lock_id": LOCK["lock_id"], "checkin_hour": "15", "checkout_hour": "10",
    }
    assert client.post(f"/apartments/{a}", data=data, follow_redirects=False).status_code == 303
    assert _apartment(a)["lock_provider"] == "ttlock"
