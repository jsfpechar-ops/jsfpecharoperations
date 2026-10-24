# 0316: Guide: "Finding your way" and "Words we use" (en, cs)

Status: todo
Depends on: 0315 | Base commit: 92646d3 (check `git rev-parse --short origin/main` first; if it differs, write the current one here) | Branch: task/0316-guide-finding
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Add a first guide section, "Finding your way", that tells a beginner where the menu is on a phone and on a computer, what the tabs are and where search and "How does this work?" live, plus a short glossary ("Words we use"). Havel (AI) answers only from the guide, so a question like "Where is the settings button?" (plan test case 46) needs this text; a person reading `/guide` gets the same help.

## 2. Context

Plan: `docs/plans/havel-support-assistant.md` sections 16a.1, 16a.2 (four parts: what it is, when you need it, how to do it, if something goes wrong), 16a.5. Coverage table: `docs/plans/guide-coverage.md` (0315). Rules: AGENTS.md 7 (template change: browser test, 390 px screenshot, 0 skipped), 9 (copy keys only); the header of `App/app/guide_i18n.py` says "Every sentence describes behaviour in the code". No em dashes or en dashes in copy (`test_no_em_dashes.py`).

The copy below was written from these templates (read 2026-10-24), so do not reword it:
- `App/app/templates/_shell_tabbar.html`: the phone bar has `nav.overview` (Dashboard / Přehled), `nav.stays`, `nav.properties`, `nav.cleaning`, `nav.more` (More / Další); the More sheet lists `host.search`, `nav.stay_fees`, `nav.settings`, `nav.guide` (Help / Nápověda), `settings.nav.archive`, `nav.privacy_requests` (Data requests / Žádosti o údaje), the language buttons EN, CS, VI, `nav.logout` and a `common.close` button.
- `App/app/templates/_shell_sidebar.html`: the computer menu has the search row, Dashboard, Stays, Properties, Stay fees, Cleaning, Settings; `nav.guide` at the bottom; the account menu (`nav.account`) has Settings, `nav.support` (Help & support / Nápověda a podpora, with the support e-mail), Archive, Data requests, the language buttons, `shortcuts.open`, Log out; the `sidebar-collapse` button sits next to the brand.
- `App/app/templating.py` `_template_section_tabs`: Stays tabs `nav.stays`, `tabs.stays.reports`, `tabs.stays.register` (cs "Domovní kniha"); Invoices tabs `nav.invoices`, `nav.stay_fees`, `host.invoice_settings`, also shown on `/stay-fees`; Properties tabs add `host.business` once a business exists; Settings tabs `nav.settings`, `settings.nav.archive`, `nav.privacy_requests`.
- `App/app/templates/apartment_form.html`: a property's tabs `property_nav.overview`, `property_nav.bookings` (Bookings & calendars), `property_nav.settings`; `_property_editor.html` groups `property_nav.group.property|guests|reporting|lock|automation`.
- `App/app/templates/host_page.html`: the `how.toggle` panel ("How does this work?") with three steps and `how.more`.
- The sidebar is hidden below 1024 px and the phone bar and top bar show instead (the comments at the top of `_shell_sidebar.html` and `_shell_tabbar.html`).

Anchors, verified with `grep -nF` on 2026-10-24:
- `App/app/guide_i18n.py` line 170 (end of `"en"`): `        "guide.demo.body": "Press Explore with demo data to try every screen with sample properties and stays. Demo records are never sent to the police. Use Clear demo data on the Dashboard when you are done.",`
- `App/app/guide_i18n.py` line 334 (end of `"cs"`): `        "guide.demo.body": "Tlačítkem Prohlédnout s ukázkovými daty vyzkoušíte všechny obrazovky s ukázkovými ubytováními a pobyty. Ukázkové záznamy se policii nikdy neposílají. Až skončíte, použijte na Přehledu Smazat ukázková data.",`
- `App/app/templates/guide.html` line 9: `{% set sections = ['overview', 'statuses', 'setup', 'stays', 'guests', 'reporting', 'filters', 'housebook', 'stay_fee', 'invoices', 'settings', 'door-codes', 'faster', 'faq', 'legal'] + (['demo'] if demo_available else []) %}`; line 16: `    <section class="guide-section ui-section ui-section-plain" id="overview">`; line 184: `    <section class="guide-section ui-section ui-section-plain guide-legal" id="legal">`.
- `App/tests/test_guide.py` lines 10 and 12: `        for section in ("overview", "statuses", "setup", "stays", "guests", "reporting",` and `                        "door-codes", "faster", "faq", "legal"):`.
- `App/tests/test_design_guardrails_browser.py` line 44: `    "settings-account": "/settings",`.

Vietnamese falls back to English for the new keys until brief 0326. Havel's page map gets the new anchors in brief 0327 (not here), so this brief needs no Havel code.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/guide_i18n.py | edit | new keys, en and cs |
| App/app/templates/guide.html | edit | sections list, two new sections |
| App/tests/test_guide.py | edit | section list |
| App/tests/test_guide_browser.py | new | 390 and 1280, screenshots |
| App/tests/test_design_guardrails_browser.py | edit | `ROUTES["guide"]` |
| docs/tasks/screenshots-guide/*.png | new | |
| docs/tasks/0316-report.md | new | report |

No other file may change.

## 4. Steps

Commit after each step: `0316 step k`.

1. **Branch.** `git fetch origin && git checkout -b task/0316-guide-finding origin/main`. Command: `grep -c "guide.nav.finding" App/app/guide_i18n.py`. Expected: `0`.

2. **English copy.** In `App/app/guide_i18n.py`, directly after the English `guide.demo.body` line quoted in section 2, insert:

```python
        # 0316: Finding your way and Words we use (plan 16a.1, 16a.5). Written from
        # _shell_tabbar.html, _shell_sidebar.html, templating._template_section_tabs.
        "guide.how_title": "How to do it",
        "guide.wrong_title": "If something goes wrong",
        "guide.nav.finding": "Finding your way",
        "guide.finding.what": "UbyHost has the same pages on a phone and on a computer. Only the menu is in a different place.",
        "guide.finding.when": "Read this first when you are new, or whenever you cannot find a page.",
        "guide.finding.phone_title": "On a phone",
        "guide.finding.phone1": "The bar at the bottom of the screen has Dashboard, Stays, Properties, Cleaning and More.",
        "guide.finding.phone2": "Tap More to open a list with Search, Stay fees, Settings, Help, Archive and Data requests. The language buttons (EN, CS, VI) and Log out are in the same list. Tap Close to go back.",
        "guide.finding.phone3": "The magnifying glass at the top of the screen opens search.",
        "guide.finding.computer_title": "On a computer",
        "guide.finding.computer1": "The menu on the left has Search, Dashboard, Stays, Properties, Stay fees, Cleaning and Settings. Help is at the bottom of the menu.",
        "guide.finding.computer2": "Click your name at the bottom of the menu to open the account menu. It has Settings, Help & support (the e-mail address of UbyHost support), Archive, Data requests, the language buttons, Keyboard shortcuts and Log out.",
        "guide.finding.computer3": "The button next to the UbyHost name at the top of the menu hides the menu. Click it again to show the menu.",
        "guide.finding.pages_title": "Tabs and help on the pages",
        "guide.finding.tabs": "Some pages have tabs under the page title. Stays has Stays, Police reports and Guest register. Stay fees has Invoices, Stay fees and Invoice settings, so you reach Invoices from there. Properties has Properties and, once you have added a business, Business & legal details. Settings has Settings, Archive and Data requests.",
        "guide.finding.property": "Open a property from Properties and it has three tabs: Overview, Bookings & calendars and Settings. Settings is split into parts, such as Property information, Guest experience, Reporting & fees and Automation.",
        "guide.finding.how": "Many pages have How does this work? under the title. Tap or click it to see three short steps and a link to this guide.",
        "guide.finding.search": "Search finds pages, properties, stays and reports. Type a few letters, then tap or click a result.",
        "guide.finding.wrong1": "You cannot see the menu on the left: the window may be narrow, so UbyHost shows the phone layout with the bar at the bottom. Make the window wider, or use the bar.",
        "guide.finding.wrong2": "A page is not in the menu: look under More on a phone, or in the account menu under your name on a computer.",
        "guide.nav.glossary": "Words we use",
        "guide.glossary.lede": "Short meanings of the words you meet in UbyHost.",
        "guide.glossary.stay_term": "Stay",
        "guide.glossary.stay": "One booking at one property: the dates and the guests who come. Stays come from your calendars, or you add them by hand.",
        "guide.glossary.guest_link_term": "Guest link",
        "guide.glossary.guest_link": "One permanent web link per property. You send it to your guests, and they fill in their own check-in form on their phone.",
        "guide.glossary.pin_term": "PIN",
        "guide.glossary.pin": "Six digits that guests enter before the check-in form opens. Each property has its own PIN, under Guest links.",
        "guide.glossary.ical_term": "iCal",
        "guide.glossary.ical": "A calendar link from Airbnb, Booking.com or another portal. UbyHost reads your bookings from it. It gives dates only, no guest names and no guest count.",
        "guide.glossary.ubyport_term": "UbyPort",
        "guide.glossary.ubyport": "The Czech foreign police system for reporting foreign guests. UbyHost sends your reports to UbyPort for you.",
        "guide.glossary.idub_term": "IDUB",
        "guide.glossary.idub": "The number of your accommodation in UbyPort. It is in the letter from the foreign police. You enter it in the property's Settings, under Reporting & fees.",
        "guide.glossary.stay_fee_term": "Stay fee",
        "guide.glossary.stay_fee": "The local fee (poplatek z pobytu) that a municipality charges per night. You collect it and pay it to the council. UbyHost counts the nights and prepares the report and a QR code for the payment.",
        "guide.glossary.housebook_term": "Guest register",
        "guide.glossary.housebook": "The list of every guest who stayed with you, Czech and foreign (in Czech: domovní kniha). The law asks you to keep it. UbyHost fills it from the guests' forms.",
```

   Command: `cd App && .venv/bin/python -c "from app.guide_i18n import GUIDE_STRINGS as g; print(len([k for k in g['en'] if k.startswith('guide.finding.') or k.startswith('guide.glossary.')]))"`. Expected: `34`.

3. **Czech copy.** Directly after the Czech `guide.demo.body` line quoted in section 2, insert:

```python
        # 0316: Jak se tu vyznat a Slovníček (plan 16a.1, 16a.5).
        "guide.how_title": "Jak na to",
        "guide.wrong_title": "Když něco nejde",
        "guide.nav.finding": "Jak se tu vyznat",
        "guide.finding.what": "UbyHost má na telefonu i na počítači stejné stránky. Jinde je jen menu.",
        "guide.finding.when": "Přečtěte si to jako první, když začínáte, nebo kdykoli nemůžete najít stránku.",
        "guide.finding.phone_title": "Na telefonu",
        "guide.finding.phone1": "Lišta dole na obrazovce má Přehled, Pobyty, Ubytování, Úklid a Další.",
        "guide.finding.phone2": "Klepnutím na Další otevřete seznam s položkami Hledat, Poplatky z pobytu, Nastavení, Nápověda, Archiv a Žádosti o údaje. Ve stejném seznamu jsou tlačítka jazyka (EN, CS, VI) a Odhlásit se. Klepnutím na Zavřít se vrátíte zpět.",
        "guide.finding.phone3": "Lupa nahoře na obrazovce otevře hledání.",
        "guide.finding.computer_title": "Na počítači",
        "guide.finding.computer1": "Menu vlevo má Hledat, Přehled, Pobyty, Ubytování, Poplatky z pobytu, Úklid a Nastavení. Nápověda je dole v menu.",
        "guide.finding.computer2": "Kliknutím na své jméno dole v menu otevřete nabídku účtu. Najdete v ní Nastavení, Nápověda a podpora (e-mailová adresa podpory UbyHostu), Archiv, Žádosti o údaje, tlačítka jazyka, Klávesové zkratky a Odhlásit se.",
        "guide.finding.computer3": "Tlačítko vedle názvu UbyHost nahoře v menu menu skryje. Dalším kliknutím ho zase zobrazíte.",
        "guide.finding.pages_title": "Záložky a nápověda na stránkách",
        "guide.finding.tabs": "Některé stránky mají pod nadpisem záložky. Pobyty mají Pobyty, Hlášení policii a Domovní kniha. Poplatky z pobytu mají Faktury, Poplatky z pobytu a Nastavení faktur, takže Faktury najdete tam. Ubytování má Ubytování, a jakmile přidáte firmu, také Firma a právní údaje. Nastavení má Nastavení, Archiv a Žádosti o údaje.",
        "guide.finding.property": "Když v Ubytování otevřete ubytování, má tři záložky: Přehled, Rezervace a kalendáře a Nastavení. Nastavení je rozdělené na části, například Údaje o ubytování, Pro hosty, Hlášení a poplatky a Automatizace.",
        "guide.finding.how": "Mnoho stránek má pod nadpisem Jak to funguje? Klepnutím nebo kliknutím zobrazíte tři krátké kroky a odkaz do tohoto návodu.",
        "guide.finding.search": "Hledání najde stránky, ubytování, pobyty a hlášení. Napište pár písmen a pak klepněte nebo klikněte na výsledek.",
        "guide.finding.wrong1": "Nevidíte menu vlevo: okno je možná úzké, a tak UbyHost ukazuje rozložení pro telefon s lištou dole. Okno rozšiřte, nebo použijte lištu.",
        "guide.finding.wrong2": "Stránka v menu není: na telefonu se podívejte pod Další, na počítači do nabídky účtu pod svým jménem.",
        "guide.nav.glossary": "Slovníček",
        "guide.glossary.lede": "Krátké vysvětlení slov, se kterými se v UbyHostu setkáte.",
        "guide.glossary.stay_term": "Pobyt",
        "guide.glossary.stay": "Jedna rezervace v jednom ubytování: termín a hosté, kteří přijedou. Pobyty přicházejí z vašich kalendářů, nebo je přidáte ručně.",
        "guide.glossary.guest_link_term": "Odkaz pro hosty",
        "guide.glossary.guest_link": "Jeden trvalý webový odkaz pro každé ubytování. Pošlete ho hostům a ti si na svém telefonu sami vyplní registrační formulář.",
        "guide.glossary.pin_term": "PIN",
        "guide.glossary.pin": "Šest číslic, které host zadá, než se formulář otevře. Každé ubytování má vlastní PIN v části Odkazy pro hosty.",
        "guide.glossary.ical_term": "iCal",
        "guide.glossary.ical": "Odkaz na kalendář z Airbnb, Booking.com nebo jiného portálu. UbyHost z něj čte vaše rezervace. Obsahuje jen termíny, žádná jména ani počet hostů.",
        "guide.glossary.ubyport_term": "UbyPort",
        "guide.glossary.ubyport": "Systém cizinecké policie pro hlášení cizinců. UbyHost do něj vaše hlášení odesílá za vás.",
        "guide.glossary.idub_term": "IDUB",
        "guide.glossary.idub": "Číslo vašeho ubytovacího zařízení v UbyPortu. Je v dopise od cizinecké policie. Zadáte ho v Nastavení ubytování v části Hlášení a poplatky.",
        "guide.glossary.stay_fee_term": "Poplatek z pobytu",
        "guide.glossary.stay_fee": "Místní poplatek, který obec vybírá za každou noc. Vy ho od hostů vyberete a zaplatíte obci. UbyHost spočítá noci a připraví hlášení a QR kód k platbě.",
        "guide.glossary.housebook_term": "Kniha hostů",
        "guide.glossary.housebook": "Seznam všech hostů, kteří u vás bydleli, českých i cizích (domovní kniha). Zákon vám ukládá ji vést. UbyHost ji plní z formulářů hostů.",
```

   Command: `cd App && .venv/bin/python -m pytest tests/test_guide.py -q -k same_keys 2>&1 | tail -3`. Expected: `1 passed`.

4. **Sections list.** In `App/app/templates/guide.html`, replace the line 9 quoted in section 2 with:

```jinja
{% set sections = ['finding', 'overview', 'statuses', 'setup', 'stays', 'guests', 'reporting', 'filters', 'housebook', 'stay_fee', 'invoices', 'settings', 'door-codes', 'faster', 'faq', 'glossary', 'legal'] + (['demo'] if demo_available else []) %}
```

   Command: `grep -c "\['finding', 'overview'" App/app/templates/guide.html`. Expected: `1`.

5. **"Finding your way" section.** In `App/app/templates/guide.html`, directly before the line `    <section class="guide-section ui-section ui-section-plain" id="overview">`, insert:

```jinja
    <section class="guide-section ui-section ui-section-plain" id="finding">
      <h2>{{ t('guide.nav.finding') }}</h2>
      <p>{{ t('guide.finding.what') }}</p>
      <p class="ui-sub">{{ t('guide.finding.when') }}</p>
      {% for part in ['phone', 'computer'] %}
      <h3>{{ t('guide.finding.' ~ part ~ '_title') }}</h3>
      <ul class="guide-steps">{% for n in range(1, 4) %}<li>{{ t('guide.finding.' ~ part ~ n) }}</li>{% endfor %}</ul>
      {% endfor %}
      <h3>{{ t('guide.finding.pages_title') }}</h3>
      {% for item in ['tabs', 'property', 'how', 'search'] %}<p>{{ t('guide.finding.' ~ item) }}</p>{% endfor %}
      <h3>{{ t('guide.wrong_title') }}</h3>
      <ul>{% for n in range(1, 3) %}<li>{{ t('guide.finding.wrong' ~ n) }}</li>{% endfor %}</ul>
    </section>

```

   Command: `grep -c 'id="finding"' App/app/templates/guide.html`. Expected: `1`.

6. **Glossary section.** In `App/app/templates/guide.html`, directly before the line `    <section class="guide-section ui-section ui-section-plain guide-legal" id="legal">`, insert:

```jinja
    <section class="guide-section ui-section ui-section-plain" id="glossary">
      <h2>{{ t('guide.nav.glossary') }}</h2>
      <p>{{ t('guide.glossary.lede') }}</p>
      <dl class="kv">
        {% for term in ['stay', 'guest_link', 'pin', 'ical', 'ubyport', 'idub', 'stay_fee', 'housebook'] %}
        <dt>{{ t('guide.glossary.' ~ term ~ '_term') }}</dt>
        <dd>{{ t('guide.glossary.' ~ term) }}</dd>
        {% endfor %}
      </dl>
    </section>

```

   Command: `grep -c 'id="glossary"' App/app/templates/guide.html`. Expected: `1`.

7. **Guide test.** In `App/tests/test_guide.py`, replace `        for section in ("overview", "statuses", "setup", "stays", "guests", "reporting",` with `        for section in ("finding", "overview", "statuses", "setup", "stays", "guests", "reporting",`, and `                        "door-codes", "faster", "faq", "legal"):` with `                        "door-codes", "faster", "faq", "glossary", "legal"):`.

   Command: `cd App && .venv/bin/python -m pytest tests/test_guide.py -q --tb=short -x 2>&1 | tail -5`. Expected: `3 passed`.

8. **Layout guard route.** In `App/tests/test_design_guardrails_browser.py`, directly after the line `    "settings-account": "/settings",`, insert `    "guide": "/guide",`. Command: `grep -c '"guide": "/guide"' App/tests/test_design_guardrails_browser.py`. Expected: `1`.

9. **Browser test.** Create `App/tests/test_guide_browser.py`:

```python
"""0316: the Help & guide at phone and computer width (rule 7): no sideways scroll,
and a 390 px screenshot of each beginner section that exists. Briefs 0317, 0318
and 0328 rerun it for their own sections."""
from __future__ import annotations

import os
import socket
import threading
import time
from pathlib import Path

import pytest
import uvicorn

REQUIRE_BROWSER = os.environ.get("UBYHOST_REQUIRE_BROWSER") == "1"
if REQUIRE_BROWSER:
    import playwright.sync_api as sync_api
else:
    sync_api = pytest.importorskip("playwright.sync_api")

from app import auth, db
from app.main import app
from tests.browser_support import chromium_launch_kwargs
from tests.test_submission_retry_cap import host as host  # noqa: F401

SHOTS = Path(__file__).resolve().parents[2] / "docs" / "tasks" / "screenshots-guide"
SECTIONS = ("finding", "glossary", "cleaning", "stays", "setup", "stay_fee", "invoices", "overview", "settings")


@pytest.fixture
def origin(host):
    db.init_db()
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 15
    while not server.started and time.time() < deadline:
        time.sleep(.05)
    assert server.started
    yield f"http://127.0.0.1:{port}", host.cookies.get(auth.SESSION_COOKIE)
    server.should_exit = True
    thread.join(timeout=5)


@pytest.mark.parametrize("lang", ["en", "cs"])
def test_the_guide_fits_a_phone_and_a_computer(origin, lang):
    SHOTS.mkdir(parents=True, exist_ok=True)
    with sync_api.sync_playwright() as pw:
        try:
            browser = pw.chromium.launch(**chromium_launch_kwargs())
        except Exception:
            if REQUIRE_BROWSER:
                raise
            pytest.skip("Chromium is required for the guide browser test")
        for width in (390, 1280):
            context = browser.new_context(viewport={"width": width, "height": 900})
            context.add_cookies([{"name": auth.SESSION_COOKIE, "value": origin[1], "url": origin[0] + "/"}])
            page = context.new_page()
            page.goto(f"{origin[0]}/guide?lang={lang}")
            page.locator("#finding").wait_for()
            assert page.evaluate("document.documentElement.scrollWidth") <= width, (lang, width)
            if width == 390 and lang == "en":
                for section in SECTIONS:
                    if page.locator(f"#{section}").count():
                        page.locator(f"#{section}").screenshot(path=str(SHOTS / f"guide-{section}-390.png"))
            context.close()
        browser.close()
```

   Command (from `App/`, `export UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium-1194/chrome-linux/chrome UBYHOST_REQUIRE_BROWSER=1`): `.venv/bin/python -m pytest tests/test_guide_browser.py -q -rs 2>&1 | tail -5`. Expected: `2 passed`, nothing skipped. Look once at `docs/tasks/screenshots-guide/guide-finding-390.png` and `guide-glossary-390.png`: headings, short lines, no text cut off. Commit the screenshots.

10. **Guards.** Run section 6 commands 3 and 4. If the layout guard reports a finding on `/guide` outside `#finding` and `#glossary` (an old problem, not yours), remove the line you added in step 8, rerun, and write the finding under Questions in the report.

## 5. Do not touch

`App/app/havel*.py`, `App/app/host_i18n.py`, `App/app/host_vi_i18n.py`, every other template, CSS (the new sections reuse `guide-section`, `guide-steps`, `kv`, `ui-sub`; no new class), every existing guide key (Havel's quick-help topics cite them by name). Hard rules: AGENTS.md 7, 8, 9.

## 6. Commands (from `App/`, `export UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium-1194/chrome-linux/chrome UBYHOST_REQUIRE_BROWSER=1`)

1. `.venv/bin/python -m pytest tests/test_guide.py tests/test_host_i18n.py tests/test_no_em_dashes.py tests/test_copy_cleanup.py -q --tb=short -x 2>&1 | tail -30` → all passed.
2. `.venv/bin/python -m pytest tests/test_guide_browser.py -q -rs 2>&1 | tail -30` → 2 passed, 0 skipped.
3. `.venv/bin/python -m pytest tests/test_design_guardrails_browser.py tests/test_a11y_guard_browser.py -q -rs 2>&1 | tail -30` → passed, 0 skipped.
4. `.venv/bin/python -m pytest tests/test_host_geometry.py -q -rs 2>&1 | tail -30` → passed, 0 skipped.
5. From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -3` → OK.

## 7. Acceptance

- [ ] `/guide` starts with "Finding your way" (Czech "Jak se tu vyznat"), with the phone list, the computer list, the tabs paragraphs and the trouble list; "Words we use" (Czech "Slovníček") sits before "Your legal duties" with eight terms.
- [ ] Both are in the guide's side navigation; `test_guide.py` lists both anchors.
- [ ] `GUIDE_STRINGS["en"]` and `["cs"]` have the same keys (test passes).
- [ ] Screenshots `guide-finding-390.png` and `guide-glossary-390.png` saved and looked at; browser tests 0 skipped.

## 8. Stop and ask

As in docs/tasks/TEMPLATE.md section 8, plus: an anchor in section 2 is not found (another guide brief ran first), or a guide key you add already exists.

## 9. Report

Write `docs/tasks/0316-report.md` (600 tokens at most) and set `Status: review`: files changed, each command with its last 5 lines, section 7 ticked, deviations, questions, owner steps left, one sentence per screenshot.

## Risk list (for the reviewer)

`App/app/guide_i18n.py` (the new copy matches the templates named in section 2; nothing claims a place the screen does not have), `App/app/templates/guide.html` (no existing section changed).

## Owner steps

1. Open `/guide` on your phone and on your computer. Read "Finding your way" and check each place it names is where it says.
2. Read "Words we use". Say if a word is missing.
