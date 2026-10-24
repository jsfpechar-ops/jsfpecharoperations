# 0317: Guide: Cleaning, Guest links and PIN, Stays and calendars (en, cs)

Status: todo
Depends on: 0316 | Base commit: 92646d3 (check `git rev-parse --short origin/main` first; if it differs, write the current one here) | Branch: task/0317-guide-cleaning-links-stays
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Give the three areas hosts ask Havel (AI) about most a beginner's explanation in four parts (what it is, when you need it, how to do it, if something goes wrong): a new Cleaning section, a new Guest links and PIN section, and steps for connecting a calendar and adding a stay by hand in Stays & calendars. The guide is all Havel knows, so without these Havel must say "I don't know" to the most common questions.

## 2. Context

Plan: `docs/plans/havel-support-assistant.md` sections 16a.2 and 16a.3; coverage `docs/plans/guide-coverage.md` rows cleaning, guest-links, stays, stay-detail. Rules: AGENTS.md 7 (screenshot at 390, browser tests 0 skipped), 9; the header of `App/app/guide_i18n.py` ("Every sentence describes behaviour in the code"); no em or en dashes (`test_no_em_dashes.py`). Step wording: the step that opens a page names the place on a phone and on a computer; every other step says "Tap or click", so Havel can use either word.

The copy was written from (read 2026-10-24; do not reword it): `App/app/templates/cleaning.html`, `_cleaning_list.html`, `cleaning_edit.html`, `cleaning_settings.html`, `cleaning_shares.html` with `App/app/cleaning_i18n.py` labels (Add cleaning, Property instructions & codes, Share schedule, After checkout, Extra cleaning, Edit cleaning, Remove cleaning, Cleaning dates, Saved manual code, Create permanent TTLock code, Create sharing link, Revoke link); `App/app/cleaning.py` `reconcile()` (a cleaning per active stay on its `date_to`, moved with it unless `overridden`, `source_cancelled` when the stay goes) and `new_share()` (30-day expiry); `_property_calendars.html` (Bookings & calendars, Add calendar, Platform, iCal export URL, Update calendars, Last sync with OK, Incomplete, Error, Never); `App/app/icalsync.py` around line 875 (Incomplete: the feed returned far fewer stored stays, so no cancellation sweep); `routes/admin.py` `add_feed` (reads the calendar at once, flash "Calendar added. %(count)s stays imported."); `_property_editor.html` lines 142 to 205 (Guest links: copy button, Preview as a guest, Access PIN, Generate a new PIN, Generate a new link with "The current link and PIN stop working", Show stays starting within (days), Keep past stay links open for (days), Save changes); `reservations.html` lines 11 and 33 to 75 (Add stay; Property, Arrival, Departure required; Number of guests, Label, Guest e-mail optional; Create stay); `reservation_detail.html` line 170 (Release assignment in the stay's menu).

Anchors, verified with `grep -nF` on 2026-10-24 (`App/app/templates/guide.html`): line 54 `      <p>{{ t('guide.stays.body') }}</p>`; line 57 `      <p class="ui-sub">{{ t('guide.stays.cancelled') }}</p>`; line 60 `    <section class="guide-section ui-section ui-section-plain" id="guests">`; line 72 `    <section class="guide-section ui-section ui-section-plain" id="reporting">`. `App/app/guide_i18n.py` lines 170 and 334: the English and Czech `guide.demo.body` lines (quoted in brief 0316 section 2; they start `        "guide.demo.body": "Press Explore` and `        "guide.demo.body": "Tlačítkem Prohlédnout`).

From brief 0316 (grep before editing): `guide.html` line 9 is

```jinja
{% set sections = ['finding', 'overview', 'statuses', 'setup', 'stays', 'guests', 'reporting', 'filters', 'housebook', 'stay_fee', 'invoices', 'settings', 'door-codes', 'faster', 'faq', 'glossary', 'legal'] + (['demo'] if demo_available else []) %}
```

`App/tests/test_guide.py` line 10 is `        for section in ("finding", "overview", "statuses", "setup", "stays", "guests", "reporting",`. Keys `guide.how_title` and `guide.wrong_title` exist. `App/tests/test_guide_browser.py` screenshots `cleaning` and `stays` when they exist.

Existing keys stay unchanged: Havel's quick-help topics (brief 0313) cite `guide.stays.body`, `guide.stays.detail`, `guide.stays.cancelled`, `guide.stays.dates_changed` by name.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/guide_i18n.py | edit | new keys, en and cs |
| App/app/templates/guide.html | edit | sections list, stays additions, two new sections |
| App/tests/test_guide.py | edit | section list |
| docs/tasks/screenshots-guide/*.png | new or updated | |
| docs/tasks/0317-report.md | new | report |

No other file may change.

## 4. Steps

Commit after each step: `0317 step k`.

1. **Branch.** `git fetch origin && git checkout -b task/0317-guide-cleaning-links-stays origin/main`. Command: `grep -c "guide.nav.finding" App/app/guide_i18n.py && grep -c "guide.nav.cleaning" App/app/guide_i18n.py`. Expected: `2` then `0` (else STOP: 0316 is not merged, or this brief already ran).

2. **English copy.** In `App/app/guide_i18n.py`, directly after the English `guide.demo.body` line, insert:

```python
        # 0317: Cleaning, Guest links and PIN, Stays and calendars (plan 16a.2). Written from
        # cleaning*.html, cleaning.py, _property_calendars.html, _property_editor.html, reservations.html.
        "guide.nav.cleaning": "Cleaning",
        "guide.cleaning.what": "Cleaning shows when each property needs cleaning, on a calendar and as a list, with the door code and your instructions for the cleaner.",
        "guide.cleaning.when": "Use it to plan the cleaning between guests, to add an extra cleaning, and to give your cleaning team a read-only link.",
        "guide.cleaning.auto": "Every active stay gets a cleaning on its check-out day, marked After checkout. If the check-out date changes, the cleaning moves with it, unless you changed the cleaning's date yourself. If the stay is cancelled, its cleaning goes away. A cleaning you add yourself is marked Extra cleaning.",
        "guide.cleaning.add_title": "Add or change a cleaning",
        "guide.cleaning.add1": "Open Cleaning: on a phone, tap Cleaning in the bar at the bottom; on a computer, click Cleaning in the menu on the left.",
        "guide.cleaning.add2": "Tap or click Add cleaning at the top of the page.",
        "guide.cleaning.add3": "Choose the property and the cleaning date.",
        "guide.cleaning.add4": "Write notes for the cleaner if you want to, then tap or click Save. Everyone with your shared link can read these notes.",
        "guide.cleaning.add5": "To change or remove a cleaning, find it under Cleaning dates and tap or click Edit cleaning. Remove cleaning is at the bottom of that page; the stay itself does not change.",
        "guide.cleaning.codes_title": "Instructions and door code for a property",
        "guide.cleaning.codes1": "Tap or click Property instructions & codes at the top of the Cleaning page, then the property.",
        "guide.cleaning.codes2": "Write what the cleaner should do in Property instructions and tap or click Save. Every cleaning of this property shows it.",
        "guide.cleaning.codes3": "Under Door access code, type a code that already works on your door in Saved manual code and tap or click Save. If the property's TTLock lock is connected to UbyHost, you can tap or click Create permanent TTLock code instead.",
        "guide.cleaning.share_title": "Share the schedule with your cleaning team",
        "guide.cleaning.share1": "Tap or click Share schedule at the top of the Cleaning page.",
        "guide.cleaning.share2": "Tick the properties, then tap or click Create sharing link.",
        "guide.cleaning.share3": "Copy the link straight away and send it to your team: it is shown only once. The team sees the next 30 days, door codes included, and the link expires after 30 days.",
        "guide.cleaning.share4": "To stop a link early, tap or click Revoke link next to it on the same page.",
        "guide.cleaning.wrong1": "A cleaning asks you to set valid checkout and check-in times: open the property's Settings, Property information, and set the arrival and departure times. The link Edit timing in Properties on the cleaning's page takes you there.",
        "guide.cleaning.wrong2": "A cleaning conflicts with the booking window: compare its date with the stay's dates and change it with Edit cleaning.",
        "guide.cleaning.wrong3": "A stay has no cleaning: cleanings are made only for active stays at properties that are switched on. Check the stay on Stays.",
        "guide.cleaning.wrong4": "TTLock could not confirm the code: try again, or save a manual code instead.",
        "guide.cleaning.wrong5": "The shared link reached the wrong person: revoke it. Revoking does not change a code they already saw, so change that code on your lock too.",
        "guide.nav.guest_links": "Guest links and PIN",
        "guide.guest_links.what": "Each property has one permanent guest link and a six-digit PIN. Guests open the link on their phone, enter the PIN, pick their stay and fill in their forms.",
        "guide.guest_links.when": "You need them for every booking: put the link and the PIN in your check-in message on Airbnb, Booking.com and in your own e-mails. The same text works on every portal.",
        "guide.guest_links.find1": "Open Properties: on a phone, tap Properties in the bar at the bottom; on a computer, click Properties in the menu on the left.",
        "guide.guest_links.find2": "Tap or click the property.",
        "guide.guest_links.find3": "Tap or click the Settings tab, then Guest experience.",
        "guide.guest_links.find4": "Under Guest links, tap or click the copy button next to Guest link.",
        "guide.guest_links.find5": "Paste the link into your check-in message. Copy the Access PIN the same way and paste it too.",
        "guide.guest_links.find6": "To see what guests see, tap or click Preview as a guest.",
        "guide.guest_links.pin_title": "Change the PIN or the link",
        "guide.guest_links.pin1": "To choose your own PIN, type six digits in Access PIN and tap or click Save changes.",
        "guide.guest_links.pin2": "For a random PIN, tap or click Generate a new PIN and confirm. Then send the new PIN to guests who have not registered yet.",
        "guide.guest_links.pin3": "Only if the link itself has leaked, tap or click Generate a new link and confirm. You get a new link and a new PIN, and the old ones stop working. Update your message on every portal.",
        "guide.guest_links.windows": "Show stays starting within (days) sets how many days ahead a stay is offered on the link. Keep past stay links open for (days) sets how long a guest who forgot the form can still finish it through the stay's own link.",
        "guide.guest_links.wrong1": "A guest cannot find their stay: a stay is offered only when its arrival date falls within Show stays starting within (days). Check the dates on Stays, or raise the number.",
        "guide.guest_links.wrong2": "A guest's PIN is refused: they may have an old one. Send them the PIN shown in Access PIN.",
        "guide.guest_links.wrong3": "A guest says someone else already took the stay: open the stay, open its menu and choose Release assignment.",
        "guide.stays.when": "Use Stays to see every booking, to add one that is not on a calendar, and to check that guests have registered.",
        "guide.stays.calendar_title": "Connect a calendar (Airbnb, Booking.com)",
        "guide.stays.calendar1": "On Airbnb, Booking.com or your other portal, copy the calendar's iCal export link. Airbnb: Calendar, Availability, Connect calendars. Booking.com: Rates & Availability, Sync calendars.",
        "guide.stays.calendar2": "In UbyHost, open Properties and tap or click the property.",
        "guide.stays.calendar3": "Tap or click the Bookings & calendars tab.",
        "guide.stays.calendar4": "If a calendar is already connected, tap or click Add calendar first.",
        "guide.stays.calendar5": "Under Connect a calendar, choose the Platform and paste the whole link into iCal export URL.",
        "guide.stays.calendar6": "Tap or click Add calendar. UbyHost reads the calendar at once and tells you how many stays it imported.",
        "guide.stays.calendar7": "After that UbyHost checks your calendars on its own. To fetch new bookings now, tap or click Update calendars on the same tab.",
        "guide.stays.add_title": "Add a stay by hand",
        "guide.stays.add1": "Open Stays: on a phone, tap Stays in the bar at the bottom; on a computer, click Stays in the menu on the left.",
        "guide.stays.add2": "Tap or click Add stay at the top of the page.",
        "guide.stays.add3": "Choose the Property, then the Arrival and Departure dates.",
        "guide.stays.add4": "If you know them, fill in the Number of guests, a Label for yourself and the Guest e-mail. All three are optional.",
        "guide.stays.add5": "Tap or click Create stay. The stay opens, and you can copy the guest link or add the guests yourself.",
        "guide.stays.wrong1": "A booking is missing: open the property's Bookings & calendars tab and look at Last sync. Error means UbyHost could not read the link. Check that it is the whole iCal export link from the portal.",
        "guide.stays.wrong2": "Last sync says Incomplete: the calendar suddenly sent far fewer future bookings than UbyHost has. UbyHost then cancels no stays until the calendar looks complete again.",
        "guide.stays.wrong3": "UbyHost says the calendar link is already added to another property: one booking calendar belongs to one property, otherwise every booking would be reported twice. Remove it from the other property first.",
```

   Command: `cd App && .venv/bin/python -c "from app.guide_i18n import GUIDE_STRINGS as g; print(sum(1 for k in g['en'] if k.split('.')[1] in ('cleaning', 'guest_links') or k.startswith(('guide.stays.when', 'guide.stays.calendar', 'guide.stays.add', 'guide.stays.wrong'))))"`. Expected: `57`.

3. **Czech copy.** Directly after the Czech `guide.demo.body` line, insert:

```python
        # 0317: Úklid, Odkaz pro hosty a PIN, Pobyty a kalendáře (plan 16a.2).
        "guide.nav.cleaning": "Úklid",
        "guide.cleaning.what": "Úklid ukazuje, kdy které ubytování potřebuje uklidit, v kalendáři i jako seznam, spolu s kódem ke dveřím a vašimi pokyny pro uklízeče.",
        "guide.cleaning.when": "Použijte ho k plánování úklidu mezi hosty, k přidání mimořádného úklidu a k odkazu pouze ke čtení pro váš úklidový tým.",
        "guide.cleaning.auto": "Každý aktivní pobyt dostane úklid v den odjezdu s označením Po odjezdu. Když se datum odjezdu změní, úklid se posune s ním, pokud jste jeho datum nezměnili sami. Když se pobyt zruší, jeho úklid zmizí. Úklid, který přidáte sami, má označení Mimořádný úklid.",
        "guide.cleaning.add_title": "Přidat nebo změnit úklid",
        "guide.cleaning.add1": "Otevřete Úklid: na telefonu klepněte na Úklid v liště dole, na počítači klikněte na Úklid v menu vlevo.",
        "guide.cleaning.add2": "Klepněte nebo klikněte na Přidat úklid nahoře na stránce.",
        "guide.cleaning.add3": "Vyberte ubytování a datum úklidu.",
        "guide.cleaning.add4": "Pokud chcete, napište poznámky pro uklízeče, a pak klepněte nebo klikněte na Uložit. Poznámky si přečte každý, kdo má váš sdílený odkaz.",
        "guide.cleaning.add5": "Chcete-li úklid změnit nebo odstranit, najděte ho v části Termíny úklidů a klepněte nebo klikněte na Upravit úklid. Odstranit úklid je dole na té stránce; samotný pobyt se nezmění.",
        "guide.cleaning.codes_title": "Pokyny a kód ke dveřím pro ubytování",
        "guide.cleaning.codes1": "Klepněte nebo klikněte na Pokyny a kódy ubytování nahoře na stránce Úklid a pak na ubytování.",
        "guide.cleaning.codes2": "Do pole Pokyny pro ubytování napište, co má uklízeč udělat, a klepněte nebo klikněte na Uložit. Zobrazí se u každého úklidu tohoto ubytování.",
        "guide.cleaning.codes3": "V části Kód ke dveřím napište do pole Ručně uložený kód kód, který už na vašich dveřích funguje, a klepněte nebo klikněte na Uložit. Pokud je zámek TTLock tohoto ubytování připojený k UbyHostu, můžete místo toho klepnout nebo kliknout na Vytvořit trvalý kód TTLock.",
        "guide.cleaning.share_title": "Sdílet rozpis s úklidovým týmem",
        "guide.cleaning.share1": "Klepněte nebo klikněte na Sdílet rozpis nahoře na stránce Úklid.",
        "guide.cleaning.share2": "Zaškrtněte ubytování a klepněte nebo klikněte na Vytvořit odkaz.",
        "guide.cleaning.share3": "Odkaz si hned zkopírujte a pošlete týmu: zobrazí se jen jednou. Tým uvidí příštích 30 dní včetně kódů ke dveřím a odkaz vyprší za 30 dní.",
        "guide.cleaning.share4": "Chcete-li odkaz zrušit dřív, klepněte nebo klikněte na téže stránce vedle něj na Zrušit odkaz.",
        "guide.cleaning.wrong1": "Úklid chce, abyste nastavili platný čas odjezdu a příjezdu: otevřete Nastavení ubytování, Údaje o ubytování, a nastavte časy příjezdu a odjezdu. Dostanete se tam odkazem Upravit časy v Ubytování na stránce úklidu.",
        "guide.cleaning.wrong2": "Úklid koliduje s termínem pobytu: porovnejte jeho datum s termínem pobytu a změňte ho přes Upravit úklid.",
        "guide.cleaning.wrong3": "Pobyt nemá úklid: úklidy vznikají jen pro aktivní pobyty v zapnutých ubytováních. Zkontrolujte pobyt v Pobytech.",
        "guide.cleaning.wrong4": "TTLock vytvoření kódu nepotvrdil: zkuste to znovu, nebo místo toho uložte ruční kód.",
        "guide.cleaning.wrong5": "Sdílený odkaz se dostal k nesprávné osobě: zrušte ho. Zrušení nezmění kód, který už viděla, proto ten kód změňte i v zámku.",
        "guide.nav.guest_links": "Odkaz pro hosty a PIN",
        "guide.guest_links.what": "Každé ubytování má jeden trvalý odkaz pro hosty a šestimístný PIN. Hosté odkaz otevřou na telefonu, zadají PIN, vyberou svůj pobyt a vyplní formuláře.",
        "guide.guest_links.when": "Potřebujete je u každé rezervace: odkaz i PIN vložte do zprávy k příjezdu na Airbnb, Booking.com i do vlastních e-mailů. Stejný text funguje na všech portálech.",
        "guide.guest_links.find1": "Otevřete Ubytování: na telefonu klepněte na Ubytování v liště dole, na počítači klikněte na Ubytování v menu vlevo.",
        "guide.guest_links.find2": "Klepněte nebo klikněte na ubytování.",
        "guide.guest_links.find3": "Klepněte nebo klikněte na záložku Nastavení a pak na Pro hosty.",
        "guide.guest_links.find4": "V části Odkazy pro hosty klepněte nebo klikněte na tlačítko kopírování vedle Odkaz pro hosty.",
        "guide.guest_links.find5": "Odkaz vložte do zprávy k příjezdu. Stejně zkopírujte Přístupový PIN a vložte ho také.",
        "guide.guest_links.find6": "Chcete-li vidět, co vidí hosté, klepněte nebo klikněte na Zobrazit jako host.",
        "guide.guest_links.pin_title": "Změnit PIN nebo odkaz",
        "guide.guest_links.pin1": "Vlastní PIN nastavíte tak, že do pole Přístupový PIN napíšete šest číslic a klepnete nebo kliknete na Uložit změny.",
        "guide.guest_links.pin2": "Náhodný PIN vytvoříte klepnutím nebo kliknutím na Vygenerovat nový PIN a potvrzením. Nový PIN pak pošlete hostům, kteří se ještě neregistrovali.",
        "guide.guest_links.pin3": "Jen pokud unikl samotný odkaz, klepněte nebo klikněte na Vygenerovat nový odkaz a potvrďte. Dostanete nový odkaz i nový PIN a staré přestanou fungovat. Zprávu aktualizujte na všech portálech.",
        "guide.guest_links.windows": "Zobrazit pobyty začínající do (dní) určuje, kolik dní dopředu se pobyt na odkazu nabízí. Ponechat odkazy minulých pobytů otevřené (dní) určuje, jak dlouho může host, který formulář zapomněl, vše dokončit přes odkaz svého pobytu.",
        "guide.guest_links.wrong1": "Host nemůže najít svůj pobyt: pobyt se nabízí, jen když jeho datum příjezdu spadá do Zobrazit pobyty začínající do (dní). Zkontrolujte termín v Pobytech, nebo číslo zvyšte.",
        "guide.guest_links.wrong2": "Hostovi nejde PIN: možná má starý. Pošlete mu PIN, který vidíte v poli Přístupový PIN.",
        "guide.guest_links.wrong3": "Host říká, že pobyt už zabral někdo jiný: otevřete pobyt, otevřete jeho nabídku a zvolte Uvolnit přiřazení.",
        "guide.stays.when": "Pobyty použijte, když chcete vidět všechny rezervace, přidat rezervaci, která v kalendáři není, a zkontrolovat, že se hosté zaregistrovali.",
        "guide.stays.calendar_title": "Připojit kalendář (Airbnb, Booking.com)",
        "guide.stays.calendar1": "Na Airbnb, Booking.com nebo jiném portálu zkopírujte odkaz pro export kalendáře iCal. Airbnb: Kalendář, Dostupnost, Propojit kalendáře. Booking.com: Ceny a dostupnost, Synchronizace.",
        "guide.stays.calendar2": "V UbyHostu otevřete Ubytování a klepněte nebo klikněte na ubytování.",
        "guide.stays.calendar3": "Klepněte nebo klikněte na záložku Rezervace a kalendáře.",
        "guide.stays.calendar4": "Pokud už je nějaký kalendář připojený, klepněte nebo klikněte nejdřív na Přidat kalendář.",
        "guide.stays.calendar5": "V části Připojit kalendář vyberte Platforma a do pole URL exportu iCal vložte celý odkaz.",
        "guide.stays.calendar6": "Klepněte nebo klikněte na Přidat kalendář. UbyHost kalendář hned načte a napíše, kolik pobytů importoval.",
        "guide.stays.calendar7": "Potom UbyHost kontroluje kalendáře sám. Nové rezervace načtete hned klepnutím nebo kliknutím na Aktualizovat kalendáře na stejné záložce.",
        "guide.stays.add_title": "Přidat pobyt ručně",
        "guide.stays.add1": "Otevřete Pobyty: na telefonu klepněte na Pobyty v liště dole, na počítači klikněte na Pobyty v menu vlevo.",
        "guide.stays.add2": "Klepněte nebo klikněte na Přidat pobyt nahoře na stránce.",
        "guide.stays.add3": "Vyberte Ubytování a pak data Příjezd a Odjezd.",
        "guide.stays.add4": "Pokud je znáte, vyplňte Počet hostů, Popisek pro sebe a E-mail hosta. Všechna tři pole jsou volitelná.",
        "guide.stays.add5": "Klepněte nebo klikněte na Vytvořit pobyt. Pobyt se otevře a můžete zkopírovat odkaz pro hosty, nebo hosty zadat sami.",
        "guide.stays.wrong1": "Rezervace chybí: otevřete u ubytování záložku Rezervace a kalendáře a podívejte se na Poslední sync. Chyba znamená, že UbyHost odkaz nepřečetl. Zkontrolujte, že je to celý odkaz pro export iCal z portálu.",
        "guide.stays.wrong2": "U Poslední sync stojí Neúplný: kalendář náhle poslal mnohem méně budoucích rezervací, než má UbyHost. UbyHost pak nezruší žádný pobyt, dokud kalendář nebude zase vypadat úplně.",
        "guide.stays.wrong3": "UbyHost píše, že odkaz na kalendář už je přidaný u jiného ubytování: jeden kalendář rezervací patří k jednomu ubytování, jinak by se každá rezervace hlásila dvakrát. Nejdřív ho u druhého ubytování odeberte.",
```

   Command: `cd App && .venv/bin/python -m pytest tests/test_guide.py -q -k same_keys 2>&1 | tail -3`. Expected: `1 passed`.

4. **Sections list.** In `App/app/templates/guide.html`, replace the 0316 line 9 quoted in section 2 with:

```jinja
{% set sections = ['finding', 'overview', 'statuses', 'setup', 'stays', 'cleaning', 'guests', 'guest_links', 'reporting', 'filters', 'housebook', 'stay_fee', 'invoices', 'settings', 'door-codes', 'faster', 'faq', 'glossary', 'legal'] + (['demo'] if demo_available else []) %}
```

   Command: `grep -c "'stays', 'cleaning', 'guests', 'guest_links'" App/app/templates/guide.html`. Expected: `1`.

5. **Stays: when.** Directly after `      <p>{{ t('guide.stays.body') }}</p>` insert `      <p>{{ t('guide.stays.when') }}</p>`. Command: `grep -c "guide.stays.when" App/app/templates/guide.html`. Expected: `1`.

6. **Stays: steps and trouble.** Directly after `      <p class="ui-sub">{{ t('guide.stays.cancelled') }}</p>` insert:

```jinja
      <h3 id="connect-calendar">{{ t('guide.stays.calendar_title') }}</h3>
      <ol class="guide-steps">{% for n in range(1, 8) %}<li>{{ t('guide.stays.calendar' ~ n) }}</li>{% endfor %}</ol>
      <h3 id="add-stay">{{ t('guide.stays.add_title') }}</h3>
      <ol class="guide-steps">{% for n in range(1, 6) %}<li>{{ t('guide.stays.add' ~ n) }}</li>{% endfor %}</ol>
      <h3>{{ t('guide.wrong_title') }}</h3>
      <ul>{% for n in range(1, 4) %}<li>{{ t('guide.stays.wrong' ~ n) }}</li>{% endfor %}</ul>
```

   Command: `grep -c 'id="connect-calendar"\|id="add-stay"' App/app/templates/guide.html`. Expected: `2`.

7. **Cleaning section.** Directly before `    <section class="guide-section ui-section ui-section-plain" id="guests">` insert:

```jinja
    <section class="guide-section ui-section ui-section-plain" id="cleaning">
      <h2>{{ t('guide.nav.cleaning') }}</h2>
      <p>{{ t('guide.cleaning.what') }}</p>
      <p>{{ t('guide.cleaning.when') }}</p>
      <p>{{ t('guide.cleaning.auto') }}</p>
      {% for part, count in [('add', 5), ('codes', 3), ('share', 4)] %}
      <h3>{{ t('guide.cleaning.' ~ part ~ '_title') }}</h3>
      <ol class="guide-steps">{% for n in range(1, count + 1) %}<li>{{ t('guide.cleaning.' ~ part ~ n) }}</li>{% endfor %}</ol>
      {% endfor %}
      <h3>{{ t('guide.wrong_title') }}</h3>
      <ul>{% for n in range(1, 6) %}<li>{{ t('guide.cleaning.wrong' ~ n) }}</li>{% endfor %}</ul>
    </section>

```

   Command: `grep -c 'id="cleaning"' App/app/templates/guide.html`. Expected: `1`.

8. **Guest links section.** Directly before `    <section class="guide-section ui-section ui-section-plain" id="reporting">` insert:

```jinja
    <section class="guide-section ui-section ui-section-plain" id="guest_links">
      <h2>{{ t('guide.nav.guest_links') }}</h2>
      <p>{{ t('guide.guest_links.what') }}</p>
      <p>{{ t('guide.guest_links.when') }}</p>
      <h3>{{ t('guide.how_title') }}</h3>
      <ol class="guide-steps">{% for n in range(1, 7) %}<li>{{ t('guide.guest_links.find' ~ n) }}</li>{% endfor %}</ol>
      <h3>{{ t('guide.guest_links.pin_title') }}</h3>
      <ol class="guide-steps">{% for n in range(1, 4) %}<li>{{ t('guide.guest_links.pin' ~ n) }}</li>{% endfor %}</ol>
      <p class="ui-sub">{{ t('guide.guest_links.windows') }}</p>
      <h3>{{ t('guide.wrong_title') }}</h3>
      <ul>{% for n in range(1, 4) %}<li>{{ t('guide.guest_links.wrong' ~ n) }}</li>{% endfor %}</ul>
    </section>

```

   Command: `grep -c 'id="guest_links"' App/app/templates/guide.html`. Expected: `1`.

9. **Guide test.** In `App/tests/test_guide.py`, replace `        for section in ("finding", "overview", "statuses", "setup", "stays", "guests", "reporting",` with `        for section in ("finding", "overview", "statuses", "setup", "stays", "cleaning", "guests", "guest_links", "reporting",`. Command: `cd App && .venv/bin/python -m pytest tests/test_guide.py -q --tb=short -x 2>&1 | tail -5`. Expected: `3 passed`.

10. **Browser test and screenshots.** In `App/tests/test_guide_browser.py`, change `SECTIONS = ("finding", "glossary", "cleaning", "stays",` to `SECTIONS = ("finding", "glossary", "cleaning", "guest_links", "stays",`. Then run section 6 command 2. Look once at `guide-cleaning-390.png`, `guide-guest_links-390.png` and `guide-stays-390.png`: numbered steps, headings, nothing cut off. Commit them.

## 5. Do not touch

`App/app/havel*.py`, `App/app/host_i18n.py`, `App/app/host_vi_i18n.py`, `App/app/cleaning_i18n.py`, every other template, CSS (no new class), every existing guide key. Hard rules: AGENTS.md 7, 8, 9.

## 6. Commands (from `App/`, `export UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium-1194/chrome-linux/chrome UBYHOST_REQUIRE_BROWSER=1`)

1. `.venv/bin/python -m pytest tests/test_guide.py tests/test_host_i18n.py tests/test_no_em_dashes.py tests/test_copy_cleanup.py -q --tb=short -x 2>&1 | tail -30` → all passed.
2. `.venv/bin/python -m pytest tests/test_guide_browser.py -q -rs 2>&1 | tail -30` → 2 passed, 0 skipped.
3. `.venv/bin/python -m pytest tests/test_design_guardrails_browser.py tests/test_a11y_guard_browser.py -q -rs 2>&1 | tail -30` → passed, 0 skipped.
4. From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -3` → OK.

## 7. Acceptance

- [ ] `/guide` has Cleaning (after Stays & calendars) and Guest links and PIN (after Guest check-in), both in the side navigation, each with what, when, numbered steps and an "If something goes wrong" list.
- [ ] Stays & calendars has "Connect a calendar" (`#connect-calendar`) and "Add a stay by hand" (`#add-stay`) with steps, and a trouble list; its four old paragraphs are unchanged.
- [ ] en and cs have the same keys; no dashes; three screenshots looked at; browser tests 0 skipped.

## 8. Stop and ask

As in docs/tasks/TEMPLATE.md section 8, plus: step 1 does not print `2` and `0`; an anchor is missing.

## 9. Report

Write `docs/tasks/0317-report.md` (600 tokens at most) and set `Status: review`: files changed, each command with its last 5 lines, section 7 ticked, deviations, questions, owner steps left, one sentence per screenshot.

## Risk list (for the reviewer)

`App/app/guide_i18n.py`: each sentence against the template or code named in section 2 (labels, what moves and when, the 30 days, Incomplete).

## Owner steps

1. On your phone, follow "Add a stay by hand" and "Guest links and PIN" step by step on staging. Say where a step does not match the screen.
2. Read the Cleaning section. If your cleaner uses the shared link, check that "shown only once" matches what you saw.
