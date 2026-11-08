# 1031 Stay fee: same-town rule for every Czech town, minors, and a Check box that is never stale

Status: todo. Executor: Haiku 5.5. Read AGENTS.md, docs/context/executor.md, this brief. Open only files named here.
Report: `docs/tasks/1031-report.md` (600 tokens max). Set `Status: review` or `blocked`. **Do not open a PR** (the orchestrator does). Never push to main.
Branch: `claude/obec-prague-districts` in worktree `/home/user/ubyhost-obec` (already exists, part 1 committed as `6875e53b`). Work only there.

Money. Correct beats fast. A step that does not go as written: stop and report (section 8); never guess.

## 1. Objective

A guest who owes nothing must never see an amount on "Check before you send", and the pay step, the charge and the council register must show the same number as that box. Specifically:
- a Czech resident of the property's town (any Czech town, any common spelling) pays 0 (zákon 565/1990 Sb. §3a);
- a guest under 18 pays 0;
- an adult from another town pays nights × rate (the rate comes from `stay_fee_rate.rate_on`, never a constant);
- after "Change" on the Check step (birth date or address edited, then back), the box shows the result for the new values, every time.

## 2. Context

### What the owner saw (reproduce this in step 1)

Prague property, rate 50 CZK, 3 nights. Guest form, nationality Czechia, home "<street>, Prague, Czechia":
1. born 2001 (adult): Check box "Local stay fee for you 150 CZK, 3 nights × 50 CZK". Expected: hidden (same town).
2. clicked Change, set the birth date to 2010 (minor), back to Check: still 150 CZK. Expected: hidden (minor).

### How the box works (why the steps look like this)
- `GET /l/{token}/{reservation_id}/new` renders the form; `_fee_box` draws the box at page load, before anything is typed, so it starts at the adult-from-elsewhere amount (150). Only `syncFeeBox` in `App/app/static/signature.js` (run by `build()` on `guest-wizard:shown`) hides or changes it, using `data-fee-live` and `data-obec-rule`.
- Check is on the signature step; "Change" buttons are `.g-review-change`. The pay step and the charge come from the saved guest row (`charge_for_reservation`), never from the browser.

### Hypotheses (step 1 tells which holds locally; answer in the report)
- H1 Stale box (lead): the script did not re-count, so the box kept 150. In code: (a) no `data-fee-live` when the stay crosses a rate change (#817), so `syncFeeBox` returns at once; (b) no re-count on input/change or `pageshow`. Outside code: production without 0898/1025 (`9af79325`, `02929cad`) or an old cached `signature.js`.
- H2 Town not matched: property town in a form `_obec_key` does not fold, or empty; the JS copy folds differently.
- H3 A birth format parses to None (counts as adult).

### Decided rules (owner, binding; do not ask about them)

Both sides (guest city, property town), Python and JS identical:
1. Diacritics, case, extra spaces, and spaces around "-" never matter: "Plzen" = "Plzeň", "BRNO" = "brno", "Frýdek - Místek" = "Frýdek-Místek".
2. Statutory cities (zákon 128/2000 Sb. §4) plus Praha fold their city-part forms to the city: a number, roman numeral or word after a space ("Praha 3", "Děčín IV", "Ostrava Poruba"), or a "-", "," or "(" after the name ("Brno-Líšeň", "Praha, Staré Město", "Praha 5 (Smíchov)", "Praha 1 - Staré Město"). The 26 cities plus Praha: `STATUTORY_DISTRICT_BASES` in step 2.
3. Not a city part: a word after the name that is a preposition (NAD, POD, U, NA, PRI): "Teplice nad Metují" stays Teplice nad Metují.
4. "Hlavní město Praha", "Hl. m. Praha" and "Statutární město Brno" are the official names of that same city: the prefix is dropped only when a statutory city follows it.
5. Exact match for everything else: "Město Albrechtice", "Obec Lhota", "Šlapanice u Brna", "Kolín" are their own towns. Never strip "Město " or "Obec ".
6. Okres (district) names are not the city: Praha-východ, Praha-západ, Brno-venkov, Plzeň-jih, Plzeň-sever.
7. Exonyms map to the Czech name (table in step 2): Prague, Pilsen, Budweis, Karlsbad, Marienbad and more.
8. Property side: `addr_obec`; if empty, the host's town field `city_en`; if both are empty the town is unknown: the box shows the amount plus one honest sentence (step 5). Never guess the town from `addr_okres`, `addr_obec_cast` or `addr_zip`.
9. "Praha 5 Brno" (two towns typed) folds to the first: PRAHA. `tests/test_stay_fee_obec_0898.py` is updated for this one case (step 2).
10. A host decision (`fee_host_decision`) still wins over every rule. A stay over 60 nights stays not subject.

## 3. Files

Code: `App/app/stay_fee.py`, `App/app/routes/guest.py`, `App/app/static/signature.js`, `App/app/templates/guest/_fee_estimate.html`, `App/app/templates/guest/base.html`, `App/app/templates/_signature_script.html`, `App/app/i18n.py`, `App/app/guest_uk_i18n.py`, `App/tests/static_versions.json` (regenerated).
Tests: `App/tests/test_stay_fee_obec_forms_1031.py` (rewrite), `App/tests/test_stay_fee_sametown_1031.py` (new), `App/tests/test_guest_browser_e2e.py` (append at the end), one-line updates in `App/tests/test_stay_fee_obec_0898.py` and `App/tests/test_stay_fee_rate_dates_1028.py`.
May open (ranges only): `App/tests/test_guest_browser_e2e.py` lines 286-470 (helper `Guest`, `fill_form`), 615-653 (`_fee_seed`), 1209-1238 (`_b07_open_review`), 1405-1437 (Change flow); `App/tests/test_stay_fee_audit_1025.py` lines 77-140.

## 4. Steps (each step = one commit `1031 step k`)

Shell variables used below (set them in each command, the shell does not keep them):
`W=/home/user/ubyhost-obec` and `PY=/home/user/jsfpecharoperations/App/.venv/bin/python` (the worktree has no venv of its own; this one imports the worktree's `app`, checked). Tests run from `$W/App`. Node is `/opt/node22/bin/node`.

### Step 0. Preflight (2 calls)
```
cd /home/user/ubyhost-obec && git branch --show-current && git status --short | head && git log --oneline -3
```
Done when: branch is `claude/obec-prague-districts`, status is empty, `6875e53b 1031 step 1` is in the log.
- Status not empty (another agent still writing `stay_fee.py`): STOP, report `blocked: obec branch busy`.
- Branch or commit missing: STOP and report; do not recreate it.
Then copy this brief into the branch and commit:
`cp /home/user/jsfpecharoperations/docs/tasks/1031-stay-fee-same-town-and-end-to-end.md docs/tasks/ && git add docs/tasks/1031-stay-fee-same-town-and-end-to-end.md && git commit -qm "1031 step 0: brief" && git log --oneline -1`

### Step 1. Reproduce in a real browser, before any fix
Append to the END of `App/tests/test_guest_browser_e2e.py` exactly this (it reuses `_fee_seed`, `Guest`, `live_server`, `browser`, `mail`, `db`, `i18n` already in that file). Test data is synthetic on purpose: the repo is public, never put a real name, birth date or street in it.

```python
# --- 1031: the Check box follows every edit (minor, same town, other town) -----------------

SHOTS_1031 = Path("/mnt/project-files/ux-shots/stayfee-sametown")
_ADULT_1031, _MINOR_1031 = "15062001", "15062010"


def _open_1031(live_server, browser, monkeypatch, token, addr_obec, city, city_en=None):
    """A Czech guest on the Check step (signature step, signed), property in ``addr_obec``."""
    from app import config

    monkeypatch.setattr(config, "STAY_FEE_GUEST_PAY", True)
    monkeypatch.setattr(config, "GUEST_PIN_REQUIRED", False)
    monkeypatch.setattr(mail, "mail_enabled", lambda: False)
    stay = _fee_seed(token, signed=False)
    row = db.query_one("SELECT apartment_id FROM reservation WHERE id = ?", (stay,))
    db.update("apartment", row["apartment_id"], {"addr_obec": addr_obec, "city_en": city_en})
    page = browser.new_page(viewport={"width": 390, "height": 812})
    guest = Guest(page, 390, "en")
    page.goto(f"{live_server}/l/{token}/{stay}/new?lang=en")
    page.fill("#first_name", "Test")
    page.fill("#surname", "Sametown")
    page.click("#birth_date")
    page.keyboard.type(_ADULT_1031)
    guest.pick_country("nationality", "CZE")
    page.fill("#doc_number", "123456789")
    guest.next()
    page.fill("#res_street", "Testovaci 1")
    page.fill("#res_city", city)
    if page.input_value("#res_country") != "CZE":
        guest.pick_country("res_country", "CZE")
    guest.next()
    assert guest.step() == i18n.translator("en")("signature")
    guest.sign()
    return page, guest, stay


def _box_1031(page):
    """[hidden, amount text, data-fee-live, data-obec-rule] of the Check box."""
    page.wait_for_timeout(300)
    return page.evaluate("""() => {
        const b = document.getElementById('fee-estimate');
        if (!b) return [true, '', null, null];
        return [b.hidden, b.querySelector('.g-fee-amt').textContent.trim(),
                b.getAttribute('data-fee-live'), b.getAttribute('data-obec-rule')];
    }""")


def _change_1031(page, guest, row, field, value):
    """Change on Check row ``row`` (1 = birth date, 4 = home address), type, go back to Check."""
    sign = i18n.translator("en")("signature")
    page.locator(".g-review-change").nth(row).scroll_into_view_if_needed()
    page.locator(".g-review-change").nth(row).click()
    page.wait_for_timeout(900)
    page.fill(field, "")
    if field == "#birth_date":
        page.click(field)
        page.keyboard.type(value)
    else:
        page.fill(field, value)
    while guest.step() != sign:
        guest.next()


def test_1031_check_box_follows_every_change(live_server, browser, monkeypatch):
    """Owner's case: Prague flat, 3 nights x 50. Same town -> hidden; other town -> 150;
    minor -> hidden; every Change re-counts. Saved charge = last box."""
    from app import stay_fee

    token = f"browser-1031-{secrets.token_hex(4)}"
    page, guest, stay = _open_1031(live_server, browser, monkeypatch, token, "Praha", "Prague")
    try:
        steps = [
            (None, None, None, True),                      # adult, Prague: same town
            (4, "#res_city", "Brno", False),               # adult, other town: 150
            (1, "#birth_date", _MINOR_1031, True),         # minor, Brno
            (1, "#birth_date", _ADULT_1031, False),        # adult again, Brno: 150
            (4, "#res_city", "Praha 3 - Žižkov", True),    # district form of the same town
            (4, "#res_city", "Brno", False),
            (4, "#res_city", "Prague", True),              # back to the owner's case
        ]
        for row, field, value, want_hidden in steps:
            if row is not None:
                _change_1031(page, guest, row, field, value)
            hidden, amount, live, rule = _box_1031(page)
            seen = (row, value, hidden, amount, live, rule)
            assert hidden == want_hidden, seen
            if not want_hidden:
                assert amount == "150 CZK", seen
            if value == "Brno" and row == 4:
                SHOTS_1031.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(SHOTS_1031 / "check-othertown-390.png"), full_page=True)
        SHOTS_1031.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SHOTS_1031 / "check-sametown-390.png"), full_page=True)
    finally:
        page.close()
    row = db.query_one("SELECT * FROM reservation WHERE id = ?", (stay,))
    apartment = db.query_one("SELECT * FROM apartment WHERE id = ?", (row["apartment_id"],))
    assert stay_fee.same_obec_resident({"res_country": "CZE", "res_city": "Prague"}, apartment)
```

Run (expect red now; that is the reproduction):
```
cd /home/user/ubyhost-obec/App && PY=/home/user/jsfpecharoperations/App/.venv/bin/python && $PY -m pytest tests/test_guest_browser_e2e.py -k 1031 -rs -q --tb=short -x 2>&1 | tail -30
```
Done when: it ran (pass or fail), 0 skipped. Copy the failing `seen` tuple (hidden, amount, `data-fee-live`, `data-obec-rule`) into the report under "Reproduction". A local pass means the owner's 150 is H1 outside the code; still do every step.
- If the wizard does not advance (a Czech guest may get a different field), read `fill_form` (lines 369-470) once, fix the helper once, rerun. Fails again: STOP.
- If a `.g-review-change` index lands on the wrong step, read lines 1405-1437 once and fix the index once. Fails again: STOP.
Commit `1031 step 1: browser reproduction (red)` even if red.

The submit part (save, then charge = 0) is added in step 7, after the fix.

### Step 2. One `_obec_key` for every Czech town (Python)
In `App/app/stay_fee.py` replace everything from the line `STATUTORY_DISTRICT_BASES = (` down to and including the whole function `same_obec_resident` (it ends with `return bool(obec) and _obec_key(guest["res_city"]) == obec`), keeping `fold_text` exactly as it is, with:

```python
# Statutory cities (zákon 128/2000 Sb. §4) plus Praha, folded. Only these fold their
# city-part forms ("Praha 3", "Brno-Líšeň", "Ostrava Poruba"); every other town is exact (1031).
STATUTORY_DISTRICT_BASES = (
    "PRAHA", "BRNO", "CESKE BUDEJOVICE", "DECIN", "FRYDEK-MISTEK", "HAVIROV",
    "HRADEC KRALOVE", "CHOMUTOV", "JABLONEC NAD NISOU", "JIHLAVA", "KARLOVY VARY",
    "KARVINA", "KLADNO", "LIBEREC", "MLADA BOLESLAV", "MOST", "OLOMOUC", "OPAVA",
    "OSTRAVA", "PARDUBICE", "PLZEN", "PROSTEJOV", "PREROV", "TEPLICE", "TRINEC",
    "USTI NAD LABEM", "ZLIN",
)
# Names guests type for Czech towns -> the Czech name, folded (1031, owner list).
OBEC_ALIASES = {
    "PRAGUE": "PRAHA", "PRAG": "PRAHA", "PRAGA": "PRAHA",
    "BRUNN": "BRNO", "PILSEN": "PLZEN", "BUDWEIS": "CESKE BUDEJOVICE",
    "OSTRAU": "OSTRAVA", "MAHRISCH OSTRAU": "OSTRAVA", "MAHRISCH-OSTRAU": "OSTRAVA",
    "MORAVIAN OSTRAVA": "OSTRAVA", "MORAVSKA OSTRAVA": "OSTRAVA",
    "KARLSBAD": "KARLOVY VARY", "CARLSBAD": "KARLOVY VARY",
    "MARIENBAD": "MARIANSKE LAZNE", "FRANZENSBAD": "FRANTISKOVY LAZNE",
    "OLMUTZ": "OLOMOUC", "REICHENBERG": "LIBEREC", "AUSSIG": "USTI NAD LABEM",
    "KONIGGRATZ": "HRADEC KRALOVE", "PARDUBITZ": "PARDUBICE", "IGLAU": "JIHLAVA",
    "TROPPAU": "OPAVA", "TEPLITZ": "TEPLICE", "KOMOTAU": "CHOMUTOV", "TETSCHEN": "DECIN",
    "JUNGBUNZLAU": "MLADA BOLESLAV", "GABLONZ": "JABLONEC NAD NISOU",
    "PROSSNITZ": "PROSTEJOV", "PRERAU": "PREROV", "BRUX": "MOST",
    "KRUMAU": "CESKY KRUMLOV", "KUTTENBERG": "KUTNA HORA", "ZNAIM": "ZNOJMO",
}
# The official long name of a statutory city; dropped only when such a city follows.
# Never "MESTO " or "OBEC " alone: "Město Albrechtice" is its own town.
OFFICIAL_PREFIXES = ("HLAVNI MESTO ", "HL. M. ", "HL.M. ", "HL M ", "STATUTARNI MESTO ")
# Okres (district) names that start with a city name but are not that city.
OKRES_NOT_OBEC = ("PRAHA-VYCHOD", "PRAHA-ZAPAD", "BRNO-VENKOV", "PLZEN-JIH", "PLZEN-SEVER")
# What may follow a city name in a city-part form. signature.js uses this same text.
OBEC_AFTER_BASE = r"$|\s*\d|-|\s*,|\s*\(| (?!(?:NAD|POD|U|NA|PRI)(?: |$))[A-Z]"
_AFTER_BASE = re.compile("(?:" + OBEC_AFTER_BASE + ")")
OBEC_SUFFIX_BASES = tuple(sorted(
    set(STATUTORY_DISTRICT_BASES)
    | {name for name, target in OBEC_ALIASES.items() if target in STATUTORY_DISTRICT_BASES},
    key=lambda name: (-len(name), name),
))
_OKRES_NEXT_LETTER = re.compile(r"[A-Z]")
```
(keep `fold_text` here, unchanged), then:
```python
def _suffix_base(text: str) -> Optional[str]:
    for base in OBEC_SUFFIX_BASES:
        if text.startswith(base) and _AFTER_BASE.match(text, len(base)):
            return base
    return None


def _obec_key(value) -> str:
    """The town a typed name means, folded (1031 rules; signature.js key() mirrors this)."""
    text = re.sub(r"\s*-\s*", "-", fold_text(value))
    for prefix in OFFICIAL_PREFIXES:
        rest = text[len(prefix):].strip()
        if text.startswith(prefix) and _suffix_base(rest):
            text = rest
            break
    for name in OKRES_NOT_OBEC:
        if text.startswith(name) and not _OKRES_NEXT_LETTER.match(text[len(name):]):
            return text
    base = _suffix_base(text)
    if base:
        text = base
    return OBEC_ALIASES.get(text, text)


def property_obec(apartment) -> str:
    """The property's town: addr_obec, else the town the host typed in city_en (1031)."""
    for key in ("addr_obec", "city_en"):
        try:
            value = apartment[key]
        except (KeyError, IndexError):
            value = None
        if value and str(value).strip():
            return str(value)
    return ""


def same_obec_resident(guest, apartment) -> bool:
    """True only for a CZ resident whose city is the property's town (1031 folding rules)."""
    if guest["res_country"] != validation.CZECH_CODE:
        return False
    obec = _obec_key(property_obec(apartment))
    return bool(obec) and _obec_key(guest["res_city"]) == obec
```
Check `Optional` is already imported at the top of `stay_fee.py` (`grep -n "^from typing" App/app/stay_fee.py`); it is used elsewhere in the file.

Then replace the whole file `App/tests/test_stay_fee_obec_forms_1031.py` with:

```python
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
    ("Prag", "PRAHA"), ("Praga", "PRAHA"), ("Prague 3", "PRAHA"), ("Praha 5", "PRAHA"),
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
```
In `App/tests/test_stay_fee_obec_0898.py`, in the line `refusals = ["Brno", "Prha", "Olomuc", "", "Kladno", "Praha 5 Brno"]` change `"Praha 5 Brno"` to `"Brno 5 Praha"` (rule 9; nothing else in that file).

Run (the JS parity test is expected to fail until step 3; everything else must pass):
```
cd /home/user/ubyhost-obec/App && PY=/home/user/jsfpecharoperations/App/.venv/bin/python && $PY -m pytest tests/test_stay_fee_obec_forms_1031.py tests/test_stay_fee_obec_0898.py tests/test_stay_fee_estimate_0910.py -q --tb=short --deselect tests/test_stay_fee_obec_forms_1031.py::test_form_script_key_is_the_python_key 2>&1 | tail -30
```
Done when: all pass. A FOLDS/EXACT/OKRES case fails: fix the code only if the code differs from the block above (a typo); if the block itself gives another answer, STOP and report the case (do not change the expected value). Commit.

### Step 3. Same rule in the browser (rule JSON + JS key)
a) `App/app/routes/guest.py`, function `_fee_obec_rule`: replace its body after the imports with:
```python
    obec = stay_fee._obec_key(stay_fee.property_obec(apartment))
    if not obec:
        return ""
    return json.dumps({"obec": obec, "country": validation.CZECH_CODE,
                       "bases": list(stay_fee.OBEC_SUFFIX_BASES),
                       "aliases": stay_fee.OBEC_ALIASES,
                       "prefixes": list(stay_fee.OFFICIAL_PREFIXES),
                       "okres": list(stay_fee.OKRES_NOT_OBEC),
                       "after": stay_fee.OBEC_AFTER_BASE})
```
b) `App/app/static/signature.js`, inside `feeObecResident`: replace the whole `function key(text) { ... }` (5 lines, anchor `var m = /^(.+?)(?:\s+\d+|-.+)$/.exec(t);`) with:
```js
      function key(text) {
        // 1031: same steps as stay_fee._obec_key; the tables and the pattern come from the server.
        var t = fold(text).replace(/\s*-\s*/g, "-");
        var after = new RegExp("^(?:" + rule.after + ")");
        function base(s) {
          for (var i = 0; i < rule.bases.length; i++) {
            var b = rule.bases[i];
            if (s.indexOf(b) === 0 && after.test(s.slice(b.length))) return b;
          }
          return null;
        }
        for (var p = 0; p < rule.prefixes.length; p++) {
          var rest = t.slice(rule.prefixes[p].length).trim();
          if (t.indexOf(rule.prefixes[p]) === 0 && base(rest)) { t = rest; break; }
        }
        for (var k = 0; k < rule.okres.length; k++) {
          var n = rule.okres[k];
          if (t.indexOf(n) === 0 && !/[A-Z]/.test(t.charAt(n.length))) return t;
        }
        var found = base(t);
        if (found) t = found;
        return Object.prototype.hasOwnProperty.call(rule.aliases, t) ? rule.aliases[t] : t;
      }
```
Leave `fold` and the `var country = document.getElementById("res_country")` line exactly as they are (tests slice the file between them).
Run:
```
cd /home/user/ubyhost-obec/App && PY=/home/user/jsfpecharoperations/App/.venv/bin/python && $PY -m pytest tests/test_stay_fee_obec_forms_1031.py tests/test_stay_fee_estimate_0910.py tests/test_stay_fee_audit_1025.py -q --tb=short 2>&1 | tail -30
```
Done when: all pass, including `test_form_script_key_is_the_python_key` and the old `test_form_script_folds_like_the_backend`. Commit.

### Step 4. The box re-counts on every entry and every edit, also across a rate change
a) `App/app/routes/guest.py`, `_fee_estimate`: replace these 2 lines
```python
    if typed["fee_host_decision"] not in stay_fee.DECISIONS and uniform:
        live = {"from": stay_from, "to": stay_to, "rate": rate}
```
with
```python
    if typed["fee_host_decision"] not in stay_fee.DECISIONS:
        live = {"from": stay_from, "to": stay_to, "rate": rate}
        if not uniform:
            # 1031: across a rate change send each counted night's rate, so the script can
            # still drop a child's or a resident's nights instead of freezing the box.
            live["nights"] = {
                (first_night + _timedelta(days=k)).isoformat():
                    stay_fee_rate.rate_on(schedule, first_night + _timedelta(days=k))
                for k in range(1, (last_night - first_night).days + 1)
            }
```
Also update the comment just above (`# signature.js multiplies by one rate: ...`) to: `# One rate: signature.js multiplies; across a rate change it adds the per-night rates (1031).`
b) `App/tests/test_stay_fee_rate_dates_1028.py`: replace `    assert estimate["live"] is None` with
`    assert sum(estimate["live"]["nights"].values()) == 140 and len(estimate["live"]["nights"]) == 4`
(decided behaviour change, say so in the report).
c) `App/app/static/signature.js`: directly after the end of `function feeLiableDays(live, birth) { ... }` add:
```js
    function feeLiableAmount(live, birth) {
      // 1031: the amount for the liable nights; per-night rates when the stay crosses a rate change.
      var start = feeIso(live.from), end = feeIso(live.to), day = 86400000, amount = 0;
      if (start === null || end === null) return -1;
      for (var t = start + day; t <= end; t += day) {
        var when = new Date(t);
        var y = when.getUTCFullYear(), mo = when.getUTCMonth() + 1, d = when.getUTCDate();
        var age = birth ? y - birth.y - ((mo < birth.m || (mo === birth.m && d < birth.d)) ? 1 : 0) : 99;
        if (age < 18) continue;
        var iso = when.toISOString().slice(0, 10);
        amount += (live.nights && live.nights[iso] !== undefined) ? live.nights[iso] : live.rate;
      }
      return amount;
    }
```
d) In `function syncFeeBox()` replace its first four lines
```js
      var box = document.getElementById("fee-estimate");
      var raw = box && box.getAttribute("data-fee-live");
      if (!raw) return;
```
with
```js
      var box = document.getElementById("fee-estimate");
      if (!box) return;
      // 1031: the same-town rule first; it needs no stay window.
      if (feeObecResident(box)) { box.hidden = true; return; }
      var raw = box.getAttribute("data-fee-live");
      if (!raw) { box.hidden = false; return; }
```
and in the same function replace `String(days * live.rate)` with `String(feeLiableAmount(live, feeBirth(input ? input.value : "")))`. Remove the now duplicate `if (feeObecResident(box)) ...` effect: change `var days = feeObecResident(box) ? 0 : feeLiableDays(` to `var days = feeLiableDays(`.
e) In the same closure, directly after `form.addEventListener("guest-wizard:shown", build);` add:
```js
    // 1031: re-count on every edit and when the browser restores the page from its cache.
    ["birth_date", "res_city", "res_country"].forEach(function (id) {
      var field = document.getElementById(id);
      if (!field) return;
      field.addEventListener("input", syncFeeBox);
      field.addEventListener("change", syncFeeBox);
    });
    window.addEventListener("pageshow", build);
```
f) Cache keys (signature.js is served immutable for a year, `tests/test_static_versions.py`): in `App/app/templates/guest/base.html` change `signature.js?v=20261108-1025` to `signature.js?v=20261108-1031`; in `App/app/templates/_signature_script.html` change `signature.js?v=20261106-0977` to `signature.js?v=20261108-1031`. Then `grep -rn "20261108-1025\|20261106-0977" tests/ | head` and change any pinned old signature.js key in a test to the new one (a key pin, not a behaviour). Then:
```
cd /home/user/ubyhost-obec/App && PY=/home/user/jsfpecharoperations/App/.venv/bin/python && $PY tests/test_static_versions.py --write 2>&1 | tail -5 && $PY -m pytest tests/test_static_versions.py tests/test_stay_fee_rate_dates_1028.py tests/test_stay_fee_audit_1025.py tests/test_stay_fee_obec_forms_1031.py tests/test_form_chrome.py -q --tb=short 2>&1 | tail -30
```
Done when: all pass. Commit `1031 step 4`.

**Checkpoint.** If you are at 22 tool calls or more now, write the report with `Status: blocked`, Deviations `Done: steps 0 to 4. Left: steps 5 to 9.`, commit, stop. A fresh session continues from step 5.

### Step 5. Unknown property town: say it honestly
a) `App/app/routes/guest.py`, in the form context next to `"fee_obec_rule": _fee_obec_rule(apartment),` add the line
`            "fee_obec_unknown": not _fee_obec_rule(apartment),`
b) `App/app/templates/guest/_fee_estimate.html`: directly after the line `<p class="g-fee-calc">{{ t('fee_calc_you', days=fee_estimate.days, rate=fee_estimate.rate) }}</p>` add
`  {% if fee_obec_unknown %}<p id="fee-obec-unknown">{{ t('fee_obec_unknown') }}</p>{% endif %}`
c) New key `fee_obec_unknown`, one line directly after each `"fee_calc_you": ...` line (same indentation as that line):
- `App/app/i18n.py` en: `"fee_obec_unknown": "If your permanent address is in the same town as this place, you pay nothing. Your host will check.",`
- cs: `"fee_obec_unknown": "Máte-li trvalý pobyt ve stejné obci, kde je ubytování, poplatek neplatíte. Ubytovatel to ověří.",`
- de: `"fee_obec_unknown": "Wenn Ihr ständiger Wohnsitz in derselben Gemeinde wie die Unterkunft liegt, zahlen Sie nichts. Ihr Gastgeber prüft das.",`
- es: `"fee_obec_unknown": "Si su residencia permanente está en el mismo municipio que el alojamiento, no paga nada. Su anfitrión lo comprobará.",`
- fr: `"fee_obec_unknown": "Si votre résidence permanente est dans la même commune que le logement, vous ne payez rien. Votre hôte le vérifiera.",`
- `App/app/guest_uk_i18n.py`: `"fee_obec_unknown": "Якщо ваше постійне місце проживання в тому ж місті, що й житло, ви нічого не платите. Ваш господар це перевірить.",`
The five i18n.py lines are in the order en, cs, de, es, fr of `grep -n '"fee_calc_you"' App/app/i18n.py`.
Run:
```
cd /home/user/ubyhost-obec/App && PY=/home/user/jsfpecharoperations/App/.venv/bin/python && $PY -m pytest tests/test_guest_languages.py tests/test_stay_fee_audit_1025.py tests/test_stay_fee_estimate_0910.py -q --tb=short 2>&1 | tail -30
```
Done when: all pass. Commit.

### Step 6. Server tests: the real form route, every birth format, one number everywhere
Create `App/tests/test_stay_fee_sametown_1031.py`:

```python
"""1031: the form route carries the same-town rule; minors and residents owe nothing in every
birth format; the Check box, pay panel, charge and council register give one number."""
from __future__ import annotations

import json
from datetime import date, timedelta
from html import unescape

import pytest
from fastapi.testclient import TestClient

from app import auth, claim, config, db, stay_fee
from app.main import app
from app.routes import guest as guest_routes
from tests.conftest import complete_guest_claim
from tests.test_stay_fee_audit_1025 import _apt, _register_total, _stay, flat  # noqa: F401

USER = "sametown-1031"


def _cleanup():
    for row in db.query("SELECT id FROM user_account WHERE username = ?", (USER,)):
        uid = row["id"]
        db.execute("DELETE FROM guest WHERE reservation_id IN (SELECT r.id FROM reservation r "
                   "JOIN apartment a ON a.id = r.apartment_id WHERE a.owner_user_id = ?)", (uid,))
        db.execute("DELETE FROM reservation WHERE apartment_id IN "
                   "(SELECT id FROM apartment WHERE owner_user_id = ?)", (uid,))
        db.execute("DELETE FROM alert WHERE owner_user_id = ?", (uid,))
        db.execute("DELETE FROM audit WHERE owner_user_id = ?", (uid,))
        db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (uid,))
        db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (uid,))
        db.execute("DELETE FROM user_account WHERE id = ?", (uid,))


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setattr(config, "STAY_FEE_GUEST_PAY", True)
    db.init_db()
    _cleanup()
    yield
    _cleanup()


def _seed(token, addr_obec, city_en=None):
    now = db.utcnow()
    today = claim.prague_today()
    host = auth.create_account(f"{token}@example.test", "Same town", username=USER)
    entity = db.insert("legal_entity", {
        "name": "Same town entity", "seat": "Praha 1", "ico": "12345678",
        "contact_email": "pm@example.test", "iban": "CZ6508000000192000145399",
        "owner_user_id": host, "created_at": now})
    apartment = db.insert("apartment", {
        "legal_entity_id": entity, "owner_user_id": host, "internal_name": "Same town flat",
        "uby_name": "Same town", "permalink_token": token, "permalink_window_days": 14,
        "default_purpose": "10", "passport_photo_policy": "off", "automation_mode": "manual",
        "active": 1, "created_at": now, "addr_obec": addr_obec, "city_en": city_en,
        "stay_fee_collect": 1, "stay_fee_rate_czk": 50, "stay_fee_vs": "1234567890",
        "stay_fee_cadence": "monthly", "stay_fee_guest_rails": "iban"})
    reservation = db.insert("reservation", {
        "apartment_id": apartment, "source": "airbnb", "uid": f"{token}-stay",
        "date_from": today.isoformat(), "date_to": (today + timedelta(days=3)).isoformat(),
        "declared_guests": 1, "status": "active", "created_at": now, "updated_at": now})
    return apartment, reservation


def _form_html(token, reservation):
    client = TestClient(app)
    complete_guest_claim(client, token, reservation, party_size=1, lang="en")
    page = client.get(f"/l/{token}/{reservation}/new?lang=en")
    assert page.status_code == 200, page.text[:300]
    return page.text


def _rule(html):
    if 'data-obec-rule="' not in html:
        return None
    return json.loads(unescape(html.split('data-obec-rule="')[1].split('"')[0]))


@pytest.mark.parametrize("addr_obec, city_en", [
    ("Praha", None), ("Praha 1 - Staré Město", None), ("Hlavní město Praha", None),
    ("Hl. m. Praha", None), ("Praha, Staré Město", None), ("", "Prague"), (None, "Prague"),
])
def test_form_route_carries_the_prague_rule(addr_obec, city_en):
    _apartment, reservation = _seed("sametown1031a", addr_obec, city_en)
    html = _form_html("sametown1031a", reservation)
    assert 'id="fee-estimate"' in html and "data-fee-live" in html
    rule = _rule(html)
    assert rule is not None and rule["obec"] == "PRAHA" and rule["country"] == "CZE"
    assert 'id="fee-obec-unknown"' not in html


def test_form_route_without_a_property_town_says_so():
    _apartment, reservation = _seed("sametown1031b", "", None)
    html = _form_html("sametown1031b", reservation)
    assert 'id="fee-estimate"' in html and _rule(html) is None
    assert 'id="fee-obec-unknown"' in html


APT = {"stay_fee_collect": 1, "stay_fee_rate_czk": 50, "addr_obec": "Praha", "legal_entity_id": None}
RES = {"id": 7, "date_from": "2026-07-01", "date_to": "2026-07-04"}


@pytest.mark.parametrize("birth", ["15.06.2010", "15062010", "15/06/2010", "15-06-2010"])
@pytest.mark.parametrize("city", ["Prague", "Brno"])
def test_minor_owes_nothing_in_every_birth_format(birth, city):
    typed = {"birth_date": birth, "res_country": "CZE", "res_city": city}
    assert guest_routes._fee_estimate(APT, RES, typed) is None


@pytest.mark.parametrize("city", ["Prague", "Praha", "Praha 3 - Žižkov", "Hlavní město Praha", "prague"])
def test_adult_from_the_same_town_owes_nothing(city):
    typed = {"birth_date": "15.06.2001", "res_country": "CZE", "res_city": city}
    assert guest_routes._fee_estimate(APT, RES, typed) is None


def test_adult_from_another_town_owes_nights_times_the_rate():
    typed = {"birth_date": "15.06.2001", "res_country": "CZE", "res_city": "Brno"}
    other = guest_routes._fee_estimate(APT, RES, typed)
    assert (other["amount"], other["days"], other["rate"]) == (150, 3, 50)


@pytest.mark.parametrize("obec", ["Praha", "Hlavní město Praha", "Praha 1 - Staré Město"])
def test_preview_pay_panel_charge_and_register_agree(flat, obec):  # noqa: F811
    db.update("apartment", flat, {"addr_obec": obec})
    cz = {"nationality": "CZE", "res_country": "CZE"}
    res = _stay(flat, "2026-07-01", "2026-07-04", [
        dict(cz, birth_date="15062010", res_city="Prague"),   # minor: 0
        dict(cz, birth_date="15062001", res_city="Prague"),   # same town: 0
        dict(cz, birth_date="15062001", res_city="Brno"),     # other town: 3 nights
    ])
    apartment = _apt(flat)
    rate = int(apartment["stay_fee_rate_czk"])
    charge = stay_fee.charge_for_reservation(apartment, res)
    assert (charge["total_czk"], charge["liable_nights"]) == (3 * rate, 3)
    panel = guest_routes._fee_pay_panel(apartment, res, lambda key, **kw: key)
    assert panel["total"] == 3 * rate
    assert _register_total(apartment, date(2026, 7, 1), 1) == (3 * rate, 3)
    previews = [guest_routes._fee_estimate(apartment, res, {"birth_date": b, "res_country": "CZE", "res_city": c})
                for b, c in (("15.06.2010", "Prague"), ("15.06.2001", "Prague"), ("15.06.2001", "Brno"))]
    assert sum(p["amount"] for p in previews if p) == charge["total_czk"]
```
Also run this check (expect no output: the save route must not read any fee number from the browser):
`grep -n 'form.get("fee\|fee_amount\|fee_total\|"amount"' /home/user/ubyhost-obec/App/app/routes/guest.py | head`
If it prints a line inside the save handler (`@router.post("/l/{token}/{reservation_id}/save")` and below), STOP and report the line.
Run:
```
cd /home/user/ubyhost-obec/App && PY=/home/user/jsfpecharoperations/App/.venv/bin/python && $PY -m pytest tests/test_stay_fee_sametown_1031.py -q --tb=short 2>&1 | tail -30
```
Done when: all pass. If a birth format fails, that is a found cause (H3): STOP and report the format and the value `stay_fee.conservative_birth(<format>)` returns; do not change parsing yourself. If `complete_guest_claim` or the seed fails, read `App/tests/test_controller_gate.py` lines 44-112 once and fix the seed once; fails again: STOP. Commit.

### Step 7. Duplicate arithmetic: list only
Run `grep -n "liable \* rate\|nights \* rate\|\* rate" App/app/stay_fee.py App/app/stay_fee_remittance_pdf.py App/app/routes/stay_fees.py | head` (from `/home/user/ubyhost-obec`). For each hit read ±8 lines and write one report line: number taken from `guest_period` output / `rate_on`, or computed alone? Change nothing (the step 6 agreement test is the guard). The JS `feeLiableDays`/`feeLiableAmount` copy is by design, guarded by node tests.

### Step 8. Browser: green, the submit, screenshots
a) In `test_1031_check_box_follows_every_change` (added in step 1), replace the `finally:` block's surroundings so that before `page.close()` the guest saves. Insert directly before `    finally:` of that test:
```python
        # Save with the last values (adult, Prague) and check the stored charge equals the box: 0.
        page.check("#legal_ack")
        page.locator("form[action*='/save'] button[type=submit]").last.click()
        page.wait_for_load_state("networkidle")
        res = db.query_one("SELECT * FROM reservation WHERE id = ?", (stay,))
        apt = db.query_one("SELECT * FROM apartment WHERE id = ?", (res["apartment_id"],))
        assert db.query_one("SELECT COUNT(*) AS n FROM guest WHERE reservation_id = ?", (stay,))["n"] == 1
        assert stay_fee.charge_for_reservation(apt, res)["total_czk"] == 0
```
If `#legal_ack` or the submit selector does not exist, read `fill_form` lines 420-470 once and use the selectors it uses. Fails again: STOP.
b) Append two more tests after it:
```python
def test_1031_official_name_and_district_form_hide_the_box(live_server, browser, monkeypatch):
    token = f"browser-1031b-{secrets.token_hex(4)}"
    page, _guest, _stay = _open_1031(live_server, browser, monkeypatch, token,
                                     "Hlavní město Praha", "Praha 1 - Staré Město")
    try:
        assert _box_1031(page)[0] is True, _box_1031(page)
    finally:
        page.close()


def test_1031_unknown_property_town_shows_the_amount_and_says_why(live_server, browser, monkeypatch):
    token = f"browser-1031c-{secrets.token_hex(4)}"
    page, _guest, _stay = _open_1031(live_server, browser, monkeypatch, token, "", "Prague", city_en=None)
    try:
        hidden, amount, _live, rule = _box_1031(page)
        assert (hidden, amount, rule) == (False, "150 CZK", None)
        assert page.locator("#fee-obec-unknown").count() == 1
        page.locator("#fee-estimate").scroll_into_view_if_needed()
        SHOTS_1031.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SHOTS_1031 / "check-unknown-town-390.png"), full_page=True)
    finally:
        page.close()
```
Run:
```
cd /home/user/ubyhost-obec/App && PY=/home/user/jsfpecharoperations/App/.venv/bin/python && $PY -m pytest tests/test_guest_browser_e2e.py -k 1031 -rs -q --tb=short 2>&1 | tail -30
```
Done when: 3 passed, 0 skipped, and `ls /mnt/project-files/ux-shots/stayfee-sametown/` lists `check-sametown-390.png`, `check-othertown-390.png`, `check-unknown-town-390.png`. Open each PNG once and write one sentence per page in the report (box hidden or shown, amount, nothing overlapping). Commit.

### Step 9. Test-map rows, report
Run, one at a time (rule 7 and test-map rows "Invoices, stay fee" and "Guest pages"):
```
cd /home/user/ubyhost-obec/App && PY=/home/user/jsfpecharoperations/App/.venv/bin/python && $PY -m pytest tests/test_stay_fee*.py tests/test_invoice_*.py tests/test_static_versions.py -q --tb=short -x 2>&1 | tail -30
cd /home/user/ubyhost-obec/App && PY=/home/user/jsfpecharoperations/App/.venv/bin/python && $PY -m pytest tests/test_guest_*.py -rs -q --tb=short -x 2>&1 | tail -30
```
(includes the browser file; Bash timeout 600000; 0 skipped.) Then from the repo root `cd /home/user/ubyhost-obec && python3 scripts/context_lint.py 2>&1 | tail -10`.
Write the report (section 9), commit `1031 step 9: report`. Do not push.

## 5. Do not touch (never do)
- Never skip, xfail, delete or loosen a test; never add `pytest.skip` (the node test uses `/opt/node22/bin/node`).
- No schema change, no migration, no new dependency, no new outbound request.
- No UX change beyond the fix: no new CSS, no layout, no copy other than `fee_obec_unknown`.
- No real personal data in tests or the report (public repo): no real names, birth dates, streets.
- No push, no PR, no merge, no `main`. Do not touch `App/app/property_setup.py`, the host pages, or the pay panel code.
- Do not change how the server charges (`guest_period`, `charge_for_reservation`, `property_period`) beyond step 2.

## 6. Commands
Only those in steps 0 to 9. Never the full suite.

## 7. Acceptance
- [ ] Browser: owner's case and every Change in `test_1031_check_box_follows_every_change` give the right box; saved charge 0; 0 skipped.
- [ ] Same town for every spelling in Decided rules, both directions; okres names, "Město X", "Obec X", "X u Brna" stay different.
- [ ] Python `_obec_key` and signature.js `key()` agree on every case (node test).
- [ ] Minor owes 0 in every birth format; adult from another town owes 3 × 50.
- [ ] Box, pay panel, `charge_for_reservation` and register agree (step 6).
- [ ] Across a rate change the box still re-counts (`live.nights`).
- [ ] Empty property town: amount plus the one honest sentence, in six languages.
- [ ] signature.js cache keys bumped, `static_versions.json` regenerated.
- [ ] Three 390 px screenshots in `/mnt/project-files/ux-shots/stayfee-sametown/`, described in the report.

## 8. Stop and ask (how to decide when stuck)
- The brief's code gives a different answer than its own test: STOP, report the case. Never edit an expected value to make a test pass (the only expected-value edits allowed are the ones named: 0898 `"Praha 5 Brno"`, 1028 `live is None`, pinned old cache keys).
- An anchor (`grep -nF`) is not found: STOP, report the anchor.
- A test outside this brief fails: run it alone once; still failing and it touches stay fee, guest form or signature.js: STOP and report; otherwise note it under Deviations and go on.
- Two ways to read a step: take neither, STOP and ask.
- Over 25 tool calls: finish the step you are in, commit, write the report `Status: blocked` with `Done: steps 0 to k. Left: steps k+1 to 9.`

## 9. Report

`docs/tasks/1031-report.md`, 600 tokens max; replace the part-1 text, keep one line `Part 1 (district forms): 6875e53b.` Sections: Status, Reproduction (step 1 `seen`, which hypothesis), Cause in plain words (local pass: "code path right locally; the owner's 150 is H1 outside the code"), Files, Commands (last 5 lines), Duplicate arithmetic, Screenshots, Deviations, Questions, Owner steps. Owner steps, as written:
1. On the server, check the deployed commit includes this branch (and 0898 `9af79325`, 1025 `02929cad`).
2. In the production database run `SELECT id, internal_name, addr_obec, city_en, stay_fee_rate_czk, stay_fee_collect FROM apartment;` and `SELECT apartment_id, effective_from, rate_czk FROM stay_fee_rate ORDER BY apartment_id, effective_from;` and send the orchestrator the row of the Prague flat (no guest data).
3. On the phone, open the guest link once after the deploy (the new `?v=20261108-1031` key forces the new script).
