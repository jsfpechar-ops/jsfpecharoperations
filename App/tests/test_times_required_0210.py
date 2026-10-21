from __future__ import annotations

from app import db
from tests.test_onboarding_wizard_survival import ADDRESS, _full_apartment, host  # noqa: F401


def _property_post(host_data, apt_id, flat, checkin, checkout):
    return host_data["client"].post(
        f"/apartments/{apt_id}",
        data={
            "internal_name": flat["internal_name"],
            "legal_entity_id": str(host_data["entity"]),
            "city_en": flat["city_en"],
            "default_purpose": flat["default_purpose"],
            **ADDRESS,
            "checkin_hour": checkin,
            "checkout_hour": checkout,
            "setup_step": "property",
            "return_to": f"/apartments/{apt_id}/setup/calendar",
        },
        follow_redirects=False,
    )


def _stored_hours(apt_id):
    row = db.query_one("SELECT checkin_hour, checkout_hour FROM apartment WHERE id = ?", (apt_id,))
    return (row["checkin_hour"], row["checkout_hour"])


def test_blank_check_in_time_is_refused_on_property_step(host):
    flat = _full_apartment(host)
    apt_id = flat["id"]
    before = _stored_hours(apt_id)
    response = _property_post(host, apt_id, flat, "", "10")
    assert response.status_code == 400
    assert "Choose the check-in and check-out time" in response.text
    assert 'id="checkin_hour" name="checkin_hour" required' in response.text
    assert 'id="checkout_hour" name="checkout_hour" required' in response.text
    assert _stored_hours(apt_id) == before


def test_both_times_on_property_step_are_saved(host):
    flat = _full_apartment(host)
    apt_id = flat["id"]
    response = _property_post(host, apt_id, flat, "16", "10")
    assert response.status_code == 303
    assert _stored_hours(apt_id) == (16, 10)

