"""Task 1031: the same-town (same obec) rule for every Czech town. Rules: brief 1031, Decided rules."""
import json
import pathlib
import shutil
import subprocess

import pytest

from app import stay_fee, validation
from app.routes import guest as guest_routes

CZ = validation.CZECH_CODE

FOLDS = [
    ("Praha", "PRAHA"), ("praha", "PRAHA"), ("  PRAHA  ", "PRAHA"), ("Prague", "PRAHA"),
    ("Prag", "PRAHA"), ("Prague 3", "PRAHA"), ("Praha 5", "PRAHA"),
    ("Praha 1 - Staré Město", "PRAHA"), ("Praha 3 - Žižkov", "PRAHA"),
    ("Praha, Staré Město", "PRAHA"), ("Praha 5 (Smíchov)", "PRAHA"), ("Praha-Smíchov", "PRAHA"),
    ("Praha - Vinohrady", "PRAHA"), ("Praha Vinohrady", "PRAHA"), ("Praha 5 Brno", "PRAHA"),
    ("Hlavní město Praha", "PRAHA"), ("Hl. m. Praha", "PRAHA"), ("Hl.m. Praha", "PRAHA"),
    ("Hlavní město Praha 1", "PRAHA"),
    ("Brno", "BRNO"), ("BRNO", "BRNO"), ("Brno-střed", "BRNO"), ("Brno-Líšeň", "BRNO"),
    ("Brno - Líšeň", "BRNO"), ("Statutární město Brno", "BRNO"), ("Brünn", "BRNO"),
    ("Ostrava-Poruba", "OSTRAVA"), ("ostrava poruba", "OSTRAVA"), ("Ostrava-Jih", "OSTRAVA"),
    ("Moravian Ostrava", "OSTRAVA"), ("Moravská Ostrava", "OSTRAVA"),
    ("Plzeň", "PLZEN"), ("Plzen", "PLZEN"), ("Plzeň 3", "PLZEN"), ("Pilsen", "PLZEN"),
    ("Pilsen-Doubravka", "PLZEN"),
    ("České Budějovice", "CESKE BUDEJOVICE"), ("Ceske Budejovice 2", "CESKE BUDEJOVICE"),
    ("Budweis", "CESKE BUDEJOVICE"),
    ("Karlovy Vary", "KARLOVY VARY"), ("Karlsbad", "KARLOVY VARY"), ("Carlsbad", "KARLOVY VARY"),
    ("Marienbad", "MARIANSKE LAZNE"), ("Mariánské Lázně", "MARIANSKE LAZNE"),
    ("Frýdek-Místek", "FRYDEK-MISTEK"), ("Frýdek - Místek", "FRYDEK-MISTEK"),
    ("Ústí nad Labem-Střekov", "USTI NAD LABEM"), ("Hradec Králové", "HRADEC KRALOVE"),
    ("Liberec 2", "LIBEREC"), ("Olomouc-Nová Ulice", "OLOMOUC"), ("Pardubice V", "PARDUBICE"),
    ("Zlín-Malenovice", "ZLIN"), ("Havířov-Podlesí", "HAVIROV"), ("Kladno 2", "KLADNO"),
    ("Kladno-Kročehlavy", "KLADNO"), ("Most", "MOST"), ("Opava-Kateřinky", "OPAVA"),
    ("Karviná-Fryštát", "KARVINA"), ("Teplice-Trnovany", "TEPLICE"), ("Děčín IV", "DECIN"),
    ("Mladá Boleslav II", "MLADA BOLESLAV"), ("Přerov I-Město", "PREROV"),
    ("Třinec-Lyžbice", "TRINEC"), ("Jablonec nad Nisou-Mšeno", "JABLONEC NAD NISOU"),
    ("Prostějov", "PROSTEJOV"), ("Chomutov", "CHOMUTOV"), ("Jihlava", "JIHLAVA"),
]
EXACT = [
    ("Město Albrechtice", "MESTO ALBRECHTICE"), ("Obec Lhota", "OBEC LHOTA"),
    ("Šlapanice u Brna", "SLAPANICE U BRNA"), ("Teplice nad Metují", "TEPLICE NAD METUJI"),
    ("Ústí nad Orlicí", "USTI NAD ORLICI"), ("Jablonec nad Jizerou", "JABLONEC NAD JIZEROU"),
    ("Kolín", "KOLIN"), ("Pražské Předměstí", "PRAZSKE PREDMESTI"), ("Mostek", "MOSTEK"),
    ("Kutná Hora", "KUTNA HORA"), ("Prha", "PRHA"),
]
OKRES = [
    ("Praha-východ", "PRAHA-VYCHOD"), ("Praha - Východ", "PRAHA-VYCHOD"),
    ("Praha-západ", "PRAHA-ZAPAD"), ("Brno-venkov", "BRNO-VENKOV"),
    ("Plzeň-jih", "PLZEN-JIH"), ("Plzeň-sever", "PLZEN-SEVER"),
]


@pytest.mark.parametrize("typed, key", FOLDS + EXACT + OKRES)
def test_obec_key(typed, key):
    assert stay_fee._obec_key(typed) == key


SAME = [
    ("Prague", "Praha"), ("Praha", "Hlavní město Praha"), ("Praha 3 - Žižkov", "Praha 1 - Staré Město"),
    ("Prague", "Praha, Staré Město"), ("Prague", "Praha 5 (Smíchov)"), ("Prague", "Hl. m. Praha"),
    ("Brno-Líšeň", "Statutární město Brno"), ("brno", "Brno-střed"), ("ostrava poruba", "Ostrava"),
    ("Pilsen", "Plzeň 3"), ("Plzen", "Plzeň"), ("Budweis", "České Budějovice"),
    ("Karlsbad", "Karlovy Vary"), ("Marienbad", "Mariánské Lázně"), ("Kolín", "Kolin"),
    ("Frýdek - Místek", "Frýdek-Místek"), ("Kladno-Kročehlavy", "Kladno"),
]
DIFFERENT = [
    ("Praha", "Praha-východ"), ("Praha", "Praha-západ"), ("Brno", "Brno-venkov"),
    ("Plzeň", "Plzeň-jih"), ("Albrechtice", "Město Albrechtice"), ("Brno", "Šlapanice u Brna"),
    ("Teplice", "Teplice nad Metují"), ("Lhota", "Obec Lhota"), ("Prha", "Praha"),
    ("Brno", "Praha"), ("Kladno", "Praha"), ("Brno 5 Praha", "Praha"),
]


@pytest.mark.parametrize("a, b", SAME)
def test_same_town_both_directions(a, b):
    assert stay_fee.same_obec_resident({"res_country": CZ, "res_city": a}, {"addr_obec": b})
    assert stay_fee.same_obec_resident({"res_country": CZ, "res_city": b}, {"addr_obec": a})


@pytest.mark.parametrize("a, b", DIFFERENT)
def test_different_town_both_directions(a, b):
    assert not stay_fee.same_obec_resident({"res_country": CZ, "res_city": a}, {"addr_obec": b})
    assert not stay_fee.same_obec_resident({"res_country": CZ, "res_city": b}, {"addr_obec": a})


def test_only_a_czech_residence_counts():
    assert not stay_fee.same_obec_resident({"res_country": "DEU", "res_city": "Prague"}, {"addr_obec": "Praha"})


def test_property_town_falls_back_to_city_en_only_when_addr_obec_is_empty():
    guest = {"res_country": CZ, "res_city": "Prague"}
    assert stay_fee.same_obec_resident(guest, {"addr_obec": "", "city_en": "Prague"})
    assert stay_fee.same_obec_resident(guest, {"addr_obec": None, "city_en": "Praha"})
    assert not stay_fee.same_obec_resident(guest, {"addr_obec": "Brno", "city_en": "Prague"})
    assert not stay_fee.same_obec_resident(guest, {"addr_obec": "", "city_en": ""})
    assert not stay_fee.same_obec_resident(guest, {"addr_obec": None})


def test_form_script_key_is_the_python_key():
    """signature.js key() must give the same answer as stay_fee._obec_key for every case."""
    node = shutil.which("node") or "/opt/node22/bin/node"
    src = (pathlib.Path(guest_routes.__file__).resolve().parents[1] / "static" / "signature.js").read_text()
    start = src.index("function fold(text)")
    end = src.index('var country = document.getElementById("res_country")')
    rule = json.loads(guest_routes._fee_obec_rule({"addr_obec": "Praha"}))
    typed = [t for t, _ in FOLDS + EXACT + OKRES]
    js = ("var rule=%s;%s;console.log(JSON.stringify(%s.map(key)));"
          % (json.dumps(rule), src[start:end], json.dumps(typed)))
    out = subprocess.run([node, "-e", js], capture_output=True, text=True, check=True).stdout
    assert json.loads(out) == [stay_fee._obec_key(t) for t in typed]
