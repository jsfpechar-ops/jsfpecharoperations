"""Task 1031: a Prague district form of the property obec is the same town as Praha.

Pure function tests for stay_fee._obec_key and one check through same_obec_resident.
Praha-vychod / Praha-zapad are separate districts (okres), never the city.
"""
import pytest

from app import stay_fee, validation


@pytest.mark.parametrize("form", [
    "Praha 1 - Staré Město",
    "Praha 3 - Žižkov",
    "Hlavní město Praha",
    "Hl. m. Praha",
    "Hl.m. Praha",
    "Praha, Staré Město",
    "Praha 5 (Smíchov)",
    "Praha-Smichov",
    "Praha 5",
    "Prague",
    "Praha",
    "praha",
    "  PRAHA  ",
])
def test_prague_forms_fold_to_praha(form):
    assert stay_fee._obec_key(form) == "PRAHA"


@pytest.mark.parametrize("form, expected", [
    ("Statutární město Brno", "BRNO"),
    ("Brno", "BRNO"),
    ("Brno-venkov", "BRNO"),
    ("Brno 2", "BRNO"),
    ("Hlavní město Praha 1", "PRAHA"),
])
def test_other_statutory_cities_fold_to_their_base(form, expected):
    assert stay_fee._obec_key(form) == expected


@pytest.mark.parametrize("form, expected", [
    ("Praha-východ", "PRAHA-VYCHOD"),
    ("Praha - Východ", "PRAHA - VYCHOD"),
    ("Praha-západ", "PRAHA-ZAPAD"),
    ("Praha - Západ", "PRAHA - ZAPAD"),
])
def test_praha_okres_suffixes_do_not_fold_to_praha(form, expected):
    assert stay_fee._obec_key(form) == expected


@pytest.mark.parametrize("form, expected", [
    ("Kladno", "KLADNO"),
    ("Kladno 2", "KLADNO 2"),
    ("Kolín", "KOLIN"),
    ("Pražské Předměstí", "PRAZSKE PREDMESTI"),
])
def test_non_statutory_towns_stay_exact(form, expected):
    assert stay_fee._obec_key(form) == expected


@pytest.mark.parametrize("form", [
    "Praha 1 - Staré Město",
    "Praha 3 - Žižkov",
    "Hlavní město Praha",
    "Hl. m. Praha",
    "Praha, Staré Město",
    "Praha 5 (Smíchov)",
])
def test_same_obec_resident_prague_district_forms(form):
    guest = {"res_country": validation.CZECH_CODE, "res_city": "Prague"}
    apartment = {"addr_obec": form}
    assert stay_fee.same_obec_resident(guest, apartment) is True


def test_same_obec_resident_praha_okres_is_not_same_town():
    guest = {"res_country": validation.CZECH_CODE, "res_city": "Praha"}
    apartment = {"addr_obec": "Praha-východ"}
    assert stay_fee.same_obec_resident(guest, apartment) is False
