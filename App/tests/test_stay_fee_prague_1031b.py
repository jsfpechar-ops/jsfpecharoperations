"""1031b: every way a Prague resident writes Prague is exempt for a Prague flat (owner, 2026-11-09).

A bare district name ("Řepy") stays liable: owner decision, the guest must write the town.
"""
import json
import pathlib
import shutil
import subprocess

import pytest

from app import stay_fee
from app.routes import guest as guest_routes

PRAGUE_TYPED = (
    ["Praha", "Prague", "praha", "PRAHA", "prague", "PRAGUE", "Prag", "  Praha  "]
    + [f"Praha {n}" for n in range(1, 23)]
    + [f"praha {n}" for n in range(1, 23)]
    + ["Praha 17 - Řepy", "Praha 17 - Repy", "praha 17 - repy", "PRAHA 17 - ŘEPY", "Praha 17-Řepy",
       "Praha-Řepy", "praha-repy", "Praha - Řepy", "Praha Řepy", "Praha, Řepy", "Praha 17 (Řepy)",
       "praha 6 – Dejvice", "Praha – Řepy", "Praha–Řepy", "Praha—Řepy", "Praha 17 – Řepy",
       "Hlavní město Praha", "hlavni mesto praha", "HLAVNÍ MĚSTO PRAHA", "Hlavní město Praha 17",
       "Hl. m. Praha", "hl. m. praha", "Hl.m. Praha", "Prague 17", "Prague 6 - Dejvice"]
)
APARTMENT_TOWNS = ["Praha", "Prague", "Hlavní město Praha", "praha"]
NOT_PRAGUE = ["Řepy", "repy", "REPY", "Dejvice", "Brno", "Praha-východ", "Praha-západ",
              "Kladno", "Pražmo", ""]


@pytest.mark.parametrize("typed", PRAGUE_TYPED)
def test_prague_forms_fold_to_praha(typed):
    assert stay_fee._obec_key(typed) == "PRAHA"


@pytest.mark.parametrize("town", APARTMENT_TOWNS)
@pytest.mark.parametrize("typed", PRAGUE_TYPED)
def test_prague_resident_is_exempt_for_a_prague_flat(town, typed):
    guest = {"res_country": "CZE", "res_city": typed}
    assert stay_fee.same_obec_resident(guest, {"addr_obec": town, "city_en": None})


@pytest.mark.parametrize("town", APARTMENT_TOWNS)
@pytest.mark.parametrize("typed", NOT_PRAGUE)
def test_bare_district_and_other_towns_stay_liable(town, typed):
    guest = {"res_country": "CZE", "res_city": typed}
    assert not stay_fee.same_obec_resident(guest, {"addr_obec": town, "city_en": None})


def test_prague_flat_from_city_en_when_addr_obec_is_empty():
    guest = {"res_country": "CZE", "res_city": "Praha 17 - Řepy"}
    assert stay_fee.same_obec_resident(guest, {"addr_obec": "", "city_en": "Prague"})


def test_prague_forms_not_exempt_without_czech_residence():
    guest = {"res_country": "SVK", "res_city": "Praha 17 - Řepy"}
    assert not stay_fee.same_obec_resident(guest, {"addr_obec": "Praha", "city_en": None})


def test_form_script_folds_prague_like_python():
    """signature.js key() gives the Python answer for every Prague case (browser recount)."""
    node = shutil.which("node") or "/opt/node22/bin/node"
    src = (pathlib.Path(guest_routes.__file__).resolve().parents[1] / "static" / "signature.js").read_text()
    start = src.index("function fold(text)")
    end = src.index('var country = document.getElementById("res_country")')
    rule = json.loads(guest_routes._fee_obec_rule({"addr_obec": "Praha"}))
    typed = PRAGUE_TYPED + NOT_PRAGUE
    js = ("var rule=%s;%s;console.log(JSON.stringify(%s.map(key)));"
          % (json.dumps(rule), src[start:end], json.dumps(typed)))
    out = subprocess.run([node, "-e", js], capture_output=True, text=True, check=True).stdout
    assert json.loads(out) == [stay_fee._obec_key(t) for t in typed]
