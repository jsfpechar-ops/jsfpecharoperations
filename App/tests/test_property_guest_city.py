"""0204: the guest-facing city is never typed; it follows the address town."""
from __future__ import annotations

from app import property_setup


def test_big_towns_get_their_english_name_and_the_rest_stay_as_typed():
    assert property_setup.guest_city("Praha") == "Prague"
    assert property_setup.guest_city("Praha 3") == "Prague"
    assert property_setup.guest_city(" Plzeň ") == "Pilsen"
    assert property_setup.guest_city("Český  Krumlov") == "Český Krumlov"
    assert property_setup.guest_city("") == ""
