"""0414: the Door lock tab has its own check-in/out pickers."""
from __future__ import annotations

import re

from app import db
from tests.test_door_code_one_lock_one_property import (  # noqa: F401  (fixture)
    LOCK,
    _apartment,
    _client,
    two_properties,
)


def _base(apartment_id, entity):
    return {
        "internal_name": _apartment(apartment_id)["internal_name"],
        "legal_entity_id": str(entity),
        "return_to": f"/apartments/{apartment_id}?view=settings&section=lock",
        "door_code_section": "1",
        "door_codes_fields": "1",
        "lock_id": LOCK["lock_id"],
        "checkin_hour": "",
        "checkout_hour": "",
    }


def test_lock_tab_shows_the_time_pickers(two_properties):
    _, _, (a, _) = two_properties
    page = _client().get(f"/apartments/{a}?view=settings&section=lock").text
    for name in ("lock_checkin_hour", "lock_checkout_hour"):
        assert re.search(rf'<select id="{name}" name="{name}"', page)
    assert "Edit in Properties" not in page


def test_times_picked_on_the_lock_tab_turn_codes_on_in_one_save(two_properties):
    _, entity, (a, _) = two_properties
    data = _base(a, entity)
    data.update({"door_codes": "1", "lock_checkin_hour": "15", "lock_checkout_hour": "10"})
    response = _client().post(f"/apartments/{a}", data=data, follow_redirects=False)
    assert response.status_code == 303
    row = _apartment(a)
    assert (row["checkin_hour"], row["checkout_hour"], row["lock_provider"]) == (15, 10, "ttlock")


def test_pickers_are_required_while_codes_are_on(two_properties):
    _, entity, (a, _) = two_properties
    db.update("apartment", a, {"checkin_hour": 15, "checkout_hour": 10, "lock_provider": "ttlock", "lock_id": LOCK["lock_id"]})
    page = _client().get(f"/apartments/{a}?view=settings&section=lock").text
    select = re.search(r'<select id="lock_checkin_hour"[^>]*>', page).group(0)
    assert "required" in select
    assert re.search(r'<select id="lock_checkin_hour".*?<option value="15" selected', page, re.S)


def test_missing_times_on_the_lock_tab_are_refused_inline(two_properties):
    _, entity, (a, _) = two_properties
    data = _base(a, entity)
    data.update({"door_codes": "1", "lock_checkin_hour": "", "lock_checkout_hour": ""})
    response = _client().post(
        f"/apartments/{a}", data=data, follow_redirects=False, headers={"accept": "text/html"}
    )
    assert response.status_code == 400
    assert 'id="door-code-times-error" role="alert"' in response.text
    assert _apartment(a)["lock_provider"] is None


def test_property_tab_change_still_wins_when_lock_tab_is_untouched(two_properties):
    _, entity, (a, _) = two_properties
    db.update("apartment", a, {"checkin_hour": 14, "checkout_hour": 10})
    data = _base(a, entity)
    data.update({"checkin_hour": "16", "checkout_hour": "10", "lock_checkin_hour": "14", "lock_checkout_hour": "10"})
    data["return_to"] = f"/apartments/{a}?view=settings&section=property"
    assert _client().post(f"/apartments/{a}", data=data, follow_redirects=False).status_code == 303
    assert _apartment(a)["checkin_hour"] == 16
