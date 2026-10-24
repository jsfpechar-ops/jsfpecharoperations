# 0318: Guide: Properties and setup, Business details, Stay fees, Invoices (en, cs)

Status: todo
Depends on: 0317 | Base commit: 92646d3 (check `git rev-parse --short origin/main` first; if it differs, write the current one here) | Branch: task/0318-guide-setup-fees-invoices
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Add the beginner parts (what it is, when you need it, numbered steps, if something goes wrong) to four more guide areas: adding a property and the guided setup, a new Business details section, Stay fees and Invoices. Havel (AI) answers only from the guide, so "How do I add a property?" (plan test cases 43 and 44) needs these steps. The plan's original 0318 (also Vietnamese, the coverage test and the PR template line) did not fit one session: Vietnamese is brief 0326, the test and the PR line are 0327, and Dashboard, Settings, Archive and Data requests are 0328.

## 2. Context

Plan: `docs/plans/havel-support-assistant.md` sections 16a.2, 16a.3; coverage `docs/plans/guide-coverage.md`. Rules: AGENTS.md 7, 9; the `guide_i18n.py` header ("Every sentence describes behaviour in the code"); no em or en dashes. The step that opens a page names the place on a phone and on a computer; other steps say "Tap or click".

Copy written from (read 2026-10-24; do not reword it): `App/app/templates/apartments.html` (Add a property; empty state Add operator, Add your first property); `_property_create.html`, `_property_identity_fields.html`, `_property_operator.html` (Name of the apartment, Address with "Municipality, house number and postcode are needed", Managed by, Add an operator to continue, Add business details, Check again, Create property); `routes/admin.py` line 1581 (a new property starts its guided setup); `App/app/property_setup.py` `STEPS` and `SKIPPABLE` (calendar, try_it, stay_fee, door_lock) with labels `wizard.step.*`, Save and continue, Skip this step, Exit setup, Setup summary; `_property_overview.html` line 15 (Continue on the Overview tab); `entities.html`, `_entity_business_fields.html` (Add operator, Company ID (IČO), Fill from register, ARES, Name, Registered seat, Tax ID (DIČ), Contact email for data requests "Shown to guests as your contact", Save changes); `_entity_invoice_fields.html` (Bank account for guest payments, VAT status, Invoice number prefix, Default payment term); `_stay_fee_fields.html` and `_property_editor.html` line 294 (Stay fee (poplatek z pobytu), Rate per person per night (Kč), Reporting period, Council account, Variable symbol (from the council)); `stay_fees.html` (three steps: Confirm figures, Download PDF, the QR code; Open report; Set up stay fee) with `stay_fees.pay.*`; `invoices.html`, `invoice_stay_picker.html`, `invoice_form.html`, `invoice_detail.html` (Generate invoice, Stay, Continue, Customer, Items, Preview, Issue invoice, Download PDF, Send to the customer's e-mail, Record payment, Cancel / correct).

Anchors in `App/app/templates/guide.html`, verified with `grep -nF` on 2026-10-24: line 44 `      <h2>{{ t('guide.nav.setup') }}</h2>`; line 52 `    <section class="guide-section ui-section ui-section-plain" id="stays">`; line 126 `      <p>{{ t('guide.stay_fee.body') }}</p>`; line 128 `      <p>{{ t('guide.stay_fee.save') }}</p>`; line 133 `      <p>{{ t('guide.invoices.body') }}</p>`; line 134 `      <p>{{ t('guide.invoices.flow') }}</p>` (line numbers move after 0316 and 0317; the text does not). `App/app/guide_i18n.py`: the English and Czech `guide.demo.body` lines (they start `        "guide.demo.body": "Press Explore` and `        "guide.demo.body": "Tlačítkem Prohlédnout`).

From brief 0317 (grep before editing): `guide.html` line 9 is

```jinja
{% set sections = ['finding', 'overview', 'statuses', 'setup', 'stays', 'cleaning', 'guests', 'guest_links', 'reporting', 'filters', 'housebook', 'stay_fee', 'invoices', 'settings', 'door-codes', 'faster', 'faq', 'glossary', 'legal'] + (['demo'] if demo_available else []) %}
```

and `App/tests/test_guide.py` line 10 is `        for section in ("finding", "overview", "statuses", "setup", "stays", "cleaning", "guests", "guest_links", "reporting",`. `App/tests/test_guide_browser.py` has `SECTIONS = ("finding", "glossary", "cleaning", "guest_links", "stays",`. Keys `guide.how_title`, `guide.wrong_title` exist (0316).

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/guide_i18n.py | edit | new keys, en and cs |
| App/app/templates/guide.html | edit | sections list, setup, new business section, stay fee, invoices |
| App/tests/test_guide.py | edit | section list |
| App/tests/test_guide_browser.py | edit | `SECTIONS` |
| docs/tasks/screenshots-guide/*.png | new or updated | |
| docs/tasks/0318-report.md | new | report |

No other file may change.

## 4. Steps

Commit after each step: `0318 step k`.

1. **Branch.** `git fetch origin && git checkout -b task/0318-guide-setup-fees-invoices origin/main`. Command: `grep -c "guide.nav.guest_links" App/app/guide_i18n.py && grep -c "guide.nav.business" App/app/guide_i18n.py`. Expected: `2` then `0` (else STOP).

2. **English copy.** In `App/app/guide_i18n.py`, directly after the English `guide.demo.body` line, insert:

```python
        # 0318: Properties and setup, Business details, Stay fees, Invoices (plan 16a.2).
        "guide.setup.what": "A property is one flat or house you let. UbyHost needs its name, its address and who runs it. A guided setup then takes you through the rest.",
        "guide.setup.when": "Do it once for each property, before your first guests arrive.",
        "guide.setup.add_title": "Add a property",
        "guide.setup.add1": "Open Properties: on a phone, tap Properties in the bar at the bottom; on a computer, click Properties in the menu on the left.",
        "guide.setup.add2": "The first time, the page asks who runs the accommodation: tap or click Add operator and fill it in (see Business details below).",
        "guide.setup.add3": "Tap or click Add your first property. Later the button at the top of the page is called Add a property.",
        "guide.setup.add4": "Type the Name of the apartment: the name guests know from Airbnb, Booking.com or wherever they booked.",
        "guide.setup.add5": "Fill in the Address. Police reporting needs the municipality, the house number and the postcode.",
        "guide.setup.add6": "Under Managed by, choose the operator, then tap or click Create property. The guided setup starts.",
        "guide.setup.wizard_title": "The guided setup",
        "guide.setup.wizard1": "The setup has eight steps: Property details, Connect your calendar, Police reporting, Automation, Stay fee, Door lock, Guest link and PIN, and Test run. The top of the page shows which step you are on.",
        "guide.setup.wizard2": "Fill in a step and tap or click Save and continue.",
        "guide.setup.wizard3": "Connect your calendar, Stay fee, Door lock and Test run can wait: tap or click Skip this step.",
        "guide.setup.wizard4": "To stop for now, tap or click Exit setup. Later, open the property: its Overview tab has a Continue button.",
        "guide.setup.wizard5": "At the end, the Setup summary shows what is done and what is left.",
        "guide.setup.fields_title": "What each part needs",
        "guide.setup.wrong1": "The form says Add an operator to continue: tap or click Add business details, save the business, come back and tap or click Check again.",
        "guide.setup.wrong2": "Police reporting asks for details you do not have at hand: they are in the letter from the foreign police. Tap or click Exit setup and continue when you have the letter.",
        "guide.setup.wrong3": "The address or the UbyPort details do not match the police letter: correct them in the property's Settings, under Property information and Reporting & fees. They must match exactly.",
        "guide.nav.business": "Business details",
        "guide.business.what": "The operator is the person or company that runs the accommodation. UbyHost uses its details for police reporting and on invoices, and shows its contact e-mail to guests.",
        "guide.business.when": "Add it before your first property, and change it when your company, address or contact changes.",
        "guide.business.how1": "Open Properties: on a phone, tap Properties in the bar at the bottom; on a computer, click Properties in the menu on the left.",
        "guide.business.how2": "Tap or click the Business & legal details tab. Before your first property, tap or click Add operator on the Properties page instead.",
        "guide.business.how3": "Type the Company ID (IČO) and tap or click Fill from register. UbyHost copies the details from the public business register (ARES).",
        "guide.business.how4": "Check the Name, the Registered seat and the Tax ID (DIČ). Add the Contact email for data requests: guests see it as your contact.",
        "guide.business.how5": "Tap or click Add operator, or Save changes when you edit an existing one.",
        "guide.business.wrong1": "Fill from register finds nothing: check the IČO, or fill in the fields yourself.",
        "guide.business.wrong2": "A property shows the wrong operator: open the property's Settings, Property information, and choose the right one under Property manager / operator.",
        "guide.stay_fee.when": "You need it if your municipality charges a stay fee. Every month or quarter you send the council a report and pay the fee.",
        "guide.stay_fee.setup_title": "Set it up for a property",
        "guide.stay_fee.setup1": "Open Properties, tap or click the property, then the Settings tab and Reporting & fees.",
        "guide.stay_fee.setup2": "Under Stay fee (poplatek z pobytu), fill in the Rate per person per night (Kč), the Reporting period and the council's details, such as the Council account and the Variable symbol.",
        "guide.stay_fee.setup3": "Tap or click Save changes.",
        "guide.stay_fee.pay_title": "Report and pay a period",
        "guide.stay_fee.pay1": "Open Stay fees: on a phone, tap More, then Stay fees; on a computer, click Stay fees in the menu on the left.",
        "guide.stay_fee.pay2": "Pick the period with the month arrows in the filter. You start on the last finished month.",
        "guide.stay_fee.pay3": "Step 1 for each property: check the figures and tap or click Confirm figures. This freezes the numbers, so the PDF and the payment match what the council sees.",
        "guide.stay_fee.pay4": "Step 2: tap or click Download PDF and send it to the council, for example from your data box.",
        "guide.stay_fee.pay5": "Step 3: scan the QR code with your banking app and pay.",
        "guide.stay_fee.pay6": "To see the guests and nights behind the figures, tap or click Open report.",
        "guide.stay_fee.wrong1": "A property shows Set up stay fee: it has no rate yet. Tap or click Set up stay fee and fill it in.",
        "guide.stay_fee.wrong2": "There is no QR code: add the council's bank account in the stay fee settings and the QR code appears.",
        "guide.stay_fee.wrong3": "The figures were confirmed but are wrong: open the report and correct it there. Start correction creates a new version.",
        "guide.stay_fee.wrong4": "The account number is refused: check it against the town's website, or paste the IBAN.",
        "guide.invoices.when": "Use it when a guest or a company asks for an invoice for their stay.",
        "guide.invoices.settings": "Before your first invoice, open the Invoice settings tab and fill in the Bank account for guest payments and the VAT status. The invoice number prefix and the default payment term are up to you. Then tap or click Save.",
        "guide.invoices.how1": "Open Invoices: on a phone, tap More, then Stay fees, then the Invoices tab; on a computer, click Stay fees in the menu on the left, then the Invoices tab.",
        "guide.invoices.how2": "Tap or click Generate invoice.",
        "guide.invoices.how3": "Choose the Stay and tap or click Continue.",
        "guide.invoices.how4": "Fill in the Customer and the Items, then tap or click Preview.",
        "guide.invoices.how5": "If everything is right, tap or click Issue invoice. After that the invoice cannot be changed.",
        "guide.invoices.how6": "On the invoice you can Download PDF, Send to the customer's e-mail, and Record payment when the money arrives.",
        "guide.invoices.wrong1": "The stay is not in the list: add it under Stays first. The list holds stays from the last 400 days and the next year.",
        "guide.invoices.wrong2": "An issued invoice has a mistake: open it and tap or click Cancel / correct. UbyHost issues a new document that reverses it, and the original stays on file. This cannot be undone.",
        "guide.invoices.wrong3": "There are no VAT rates: they appear only when the operator is a VAT payer. Check the VAT status in Invoice settings.",
```

   Command: `cd App && .venv/bin/python -c "from app.guide_i18n import GUIDE_STRINGS as g; print(sum(1 for k in g['en'] if k.startswith(('guide.setup.what', 'guide.setup.when', 'guide.setup.add', 'guide.setup.wizard', 'guide.setup.fields', 'guide.setup.wrong', 'guide.business.', 'guide.nav.business', 'guide.stay_fee.when', 'guide.stay_fee.setup', 'guide.stay_fee.pay', 'guide.stay_fee.wrong', 'guide.invoices.when', 'guide.invoices.settings', 'guide.invoices.how', 'guide.invoices.wrong'))))"`. Expected: `56`.

3. **Czech copy.** Directly after the Czech `guide.demo.body` line, insert:

```python
        # 0318: Ubytování a nastavení, Firemní údaje, Poplatky z pobytu, Faktury (plan 16a.2).
        "guide.setup.what": "Ubytování je jeden byt nebo dům, který pronajímáte. UbyHost potřebuje jeho název, adresu a údaje o tom, kdo ho provozuje. Zbytek s vámi projde průvodce nastavením.",
        "guide.setup.when": "Udělejte to jednou pro každé ubytování, ještě před příjezdem prvních hostů.",
        "guide.setup.add_title": "Přidat ubytování",
        "guide.setup.add1": "Otevřete Ubytování: na telefonu klepněte na Ubytování v liště dole, na počítači klikněte na Ubytování v menu vlevo.",
        "guide.setup.add2": "Poprvé se stránka zeptá, kdo ubytování provozuje: klepněte nebo klikněte na Přidat provozovatele a vyplňte ho (viz Firemní údaje níže).",
        "guide.setup.add3": "Klepněte nebo klikněte na Přidat první ubytování. Později se tlačítko nahoře na stránce jmenuje Přidat ubytování.",
        "guide.setup.add4": "Napište Název ubytování: název, který hosté znají z Airbnb, Booking.com nebo odjinud, kde rezervovali.",
        "guide.setup.add5": "Vyplňte Adresu. Hlášení policii potřebuje obec, číslo popisné a PSČ.",
        "guide.setup.add6": "V části Provozovatel vyberte provozovatele a klepněte nebo klikněte na Vytvořit ubytování. Spustí se průvodce nastavením.",
        "guide.setup.wizard_title": "Průvodce nastavením",
        "guide.setup.wizard1": "Průvodce má osm kroků: Údaje o ubytování, Připojte kalendář, Hlášení policii, Automatizace, Poplatek z pobytu, Zámek dveří, Odkaz a PIN pro hosty a Zkušební běh. Nahoře na stránce vidíte, ve kterém kroku jste.",
        "guide.setup.wizard2": "Vyplňte krok a klepněte nebo klikněte na Uložit a pokračovat.",
        "guide.setup.wizard3": "Připojte kalendář, Poplatek z pobytu, Zámek dveří a Zkušební běh můžou počkat: klepněte nebo klikněte na Přeskočit tento krok.",
        "guide.setup.wizard4": "Chcete-li zatím skončit, klepněte nebo klikněte na Ukončit nastavení. Později otevřete ubytování: na záložce Přehled je tlačítko Pokračovat.",
        "guide.setup.wizard5": "Na konci ukáže Shrnutí nastavení, co je hotové a co zbývá.",
        "guide.setup.fields_title": "Co která část potřebuje",
        "guide.setup.wrong1": "Formulář píše Nejprve přidejte provozovatele: klepněte nebo klikněte na Přidat firemní údaje, firmu uložte, vraťte se a klepněte nebo klikněte na Zkontrolovat znovu.",
        "guide.setup.wrong2": "Hlášení policii chce údaje, které nemáte po ruce: jsou v dopise od cizinecké policie. Klepněte nebo klikněte na Ukončit nastavení a pokračujte, až dopis budete mít.",
        "guide.setup.wrong3": "Adresa nebo údaje pro UbyPort nesouhlasí s dopisem od policie: opravte je v Nastavení ubytování v částech Údaje o ubytování a Hlášení a poplatky. Musí souhlasit přesně.",
        "guide.nav.business": "Firemní údaje",
        "guide.business.what": "Provozovatel je osoba nebo firma, která ubytování provozuje. UbyHost jeho údaje používá pro hlášení policii a na fakturách a hostům ukazuje jeho kontaktní e-mail.",
        "guide.business.when": "Přidejte ho před prvním ubytováním a změňte, když se změní firma, adresa nebo kontakt.",
        "guide.business.how1": "Otevřete Ubytování: na telefonu klepněte na Ubytování v liště dole, na počítači klikněte na Ubytování v menu vlevo.",
        "guide.business.how2": "Klepněte nebo klikněte na záložku Firma a právní údaje. Před prvním ubytováním místo toho klepněte nebo klikněte na stránce Ubytování na Přidat provozovatele.",
        "guide.business.how3": "Napište IČO a klepněte nebo klikněte na Vyplnit z registru. UbyHost zkopíruje údaje z veřejného obchodního rejstříku (ARES).",
        "guide.business.how4": "Zkontrolujte Název, Sídlo a DIČ. Doplňte Kontaktní e-mail pro žádosti o údaje: hosté ho uvidí jako váš kontakt.",
        "guide.business.how5": "Klepněte nebo klikněte na Přidat provozovatele, nebo na Uložit změny, když upravujete existujícího.",
        "guide.business.wrong1": "Vyplnit z registru nic nenajde: zkontrolujte IČO, nebo pole vyplňte sami.",
        "guide.business.wrong2": "U ubytování je špatný provozovatel: otevřete Nastavení ubytování, Údaje o ubytování, a v poli Správce objektu / provozovatel vyberte správného.",
        "guide.stay_fee.when": "Potřebujete ho, pokud vaše obec vybírá poplatek z pobytu. Každý měsíc nebo čtvrtletí pošlete obci hlášení a poplatek zaplatíte.",
        "guide.stay_fee.setup_title": "Nastavit ho pro ubytování",
        "guide.stay_fee.setup1": "Otevřete Ubytování, klepněte nebo klikněte na ubytování a pak na záložku Nastavení a na Hlášení a poplatky.",
        "guide.stay_fee.setup2": "V části Poplatek z pobytu vyplňte Sazba za osobu a noc (Kč), Období hlášení a údaje obce, například Účet obce a Variabilní symbol (od obce).",
        "guide.stay_fee.setup3": "Klepněte nebo klikněte na Uložit změny.",
        "guide.stay_fee.pay_title": "Nahlásit a zaplatit období",
        "guide.stay_fee.pay1": "Otevřete Poplatky z pobytu: na telefonu klepněte na Další a pak na Poplatky z pobytu, na počítači klikněte na Poplatky z pobytu v menu vlevo.",
        "guide.stay_fee.pay2": "Období vyberte šipkami měsíce ve filtru. Začínáte na posledním ukončeném měsíci.",
        "guide.stay_fee.pay3": "Krok 1 u každého ubytování: zkontrolujte čísla a klepněte nebo klikněte na Potvrdit čísla. Čísla se tím uzamknou, takže PDF i platba odpovídají tomu, co uvidí úřad.",
        "guide.stay_fee.pay4": "Krok 2: klepněte nebo klikněte na Stáhnout PDF a pošlete ho úřadu, například ze své datové schránky.",
        "guide.stay_fee.pay5": "Krok 3: načtěte QR kód v bankovní aplikaci a zaplaťte.",
        "guide.stay_fee.pay6": "Hosty a noci, ze kterých čísla vycházejí, uvidíte po klepnutí nebo kliknutí na Otevřít hlášení.",
        "guide.stay_fee.wrong1": "U ubytování stojí Nastavit poplatek: zatím nemá sazbu. Klepněte nebo klikněte na Nastavit poplatek a vyplňte ji.",
        "guide.stay_fee.wrong2": "Chybí QR kód: doplňte v nastavení poplatku bankovní účet obce a QR kód se objeví.",
        "guide.stay_fee.wrong3": "Čísla jsou potvrzená, ale špatně: otevřete hlášení a opravte je tam. Opravit vytvoří novou verzi.",
        "guide.stay_fee.wrong4": "Číslo účtu se nepřijme: zkontrolujte ho podle webu obce, nebo vložte IBAN.",
        "guide.invoices.when": "Použijte je, když host nebo firma chce za pobyt fakturu.",
        "guide.invoices.settings": "Před první fakturou otevřete záložku Nastavení faktur a vyplňte Bankovní účet pro platby hostů a Postavení k DPH. Předponu čísla faktury a výchozí splatnost nastavte podle sebe. Pak klepněte nebo klikněte na Uložit.",
        "guide.invoices.how1": "Otevřete Faktury: na telefonu klepněte na Další, pak na Poplatky z pobytu a na záložku Faktury; na počítači klikněte na Poplatky z pobytu v menu vlevo a pak na záložku Faktury.",
        "guide.invoices.how2": "Klepněte nebo klikněte na Vystavit fakturu.",
        "guide.invoices.how3": "Vyberte Pobyt a klepněte nebo klikněte na Pokračovat.",
        "guide.invoices.how4": "Vyplňte Odběratele a Položky a klepněte nebo klikněte na Náhled.",
        "guide.invoices.how5": "Pokud je vše v pořádku, klepněte nebo klikněte na Vystavit fakturu. Potom už fakturu nelze měnit.",
        "guide.invoices.how6": "U faktury můžete Stáhnout PDF, Poslat na e-mail odběratele a Zaznamenat platbu, když peníze dorazí.",
        "guide.invoices.wrong1": "Pobyt v seznamu chybí: nejdřív ho přidejte v Pobytech. Seznam obsahuje pobyty za posledních 400 dní a na příští rok.",
        "guide.invoices.wrong2": "Vystavená faktura má chybu: otevřete ji a klepněte nebo klikněte na Stornovat / opravit. UbyHost vystaví nový doklad, který ji obrací, a původní faktura zůstane uložená. Nelze to vrátit.",
        "guide.invoices.wrong3": "Nevidíte sazby DPH: zobrazí se jen u provozovatele, který je plátcem DPH. Zkontrolujte Postavení k DPH v Nastavení faktur.",
```

   Command: `cd App && .venv/bin/python -m pytest tests/test_guide.py -q -k same_keys 2>&1 | tail -3`. Expected: `1 passed`.

4. **Sections list.** In `App/app/templates/guide.html`, in the 0317 line 9 quoted in section 2, replace `'setup', 'stays', 'cleaning'` with `'setup', 'business', 'stays', 'cleaning'`. Command: `grep -c "'setup', 'business', 'stays'" App/app/templates/guide.html`. Expected: `1`.

5. **Setup section.** Directly after `      <h2>{{ t('guide.nav.setup') }}</h2>` insert:

```jinja
      <p>{{ t('guide.setup.what') }}</p>
      <p class="ui-sub">{{ t('guide.setup.when') }}</p>
      <h3 id="add-property">{{ t('guide.setup.add_title') }}</h3>
      <ol class="guide-steps">{% for n in range(1, 7) %}<li>{{ t('guide.setup.add' ~ n) }}</li>{% endfor %}</ol>
      <h3 id="setup-guide">{{ t('guide.setup.wizard_title') }}</h3>
      <ol class="guide-steps">{% for n in range(1, 6) %}<li>{{ t('guide.setup.wizard' ~ n) }}</li>{% endfor %}</ol>
      <h3>{{ t('guide.wrong_title') }}</h3>
      <ul>{% for n in range(1, 4) %}<li>{{ t('guide.setup.wrong' ~ n) }}</li>{% endfor %}</ul>
      <h3>{{ t('guide.setup.fields_title') }}</h3>
```

   (The five old numbered parts follow under "What each part needs".) Command: `grep -c 'id="add-property"\|id="setup-guide"' App/app/templates/guide.html`. Expected: `2`.

6. **Business section.** Directly before `    <section class="guide-section ui-section ui-section-plain" id="stays">` insert:

```jinja
    <section class="guide-section ui-section ui-section-plain" id="business">
      <h2>{{ t('guide.nav.business') }}</h2>
      <p>{{ t('guide.business.what') }}</p>
      <p class="ui-sub">{{ t('guide.business.when') }}</p>
      <h3>{{ t('guide.how_title') }}</h3>
      <ol class="guide-steps">{% for n in range(1, 6) %}<li>{{ t('guide.business.how' ~ n) }}</li>{% endfor %}</ol>
      <h3>{{ t('guide.wrong_title') }}</h3>
      <ul>{% for n in range(1, 3) %}<li>{{ t('guide.business.wrong' ~ n) }}</li>{% endfor %}</ul>
    </section>

```

   Command: `grep -c 'id="business"' App/app/templates/guide.html`. Expected: `1`.

7. **Stay fee: when.** Directly after `      <p>{{ t('guide.stay_fee.body') }}</p>` insert `      <p>{{ t('guide.stay_fee.when') }}</p>`. Command: `grep -c "guide.stay_fee.when" App/app/templates/guide.html`. Expected: `1`.

8. **Stay fee: steps.** Directly after `      <p>{{ t('guide.stay_fee.save') }}</p>` insert:

```jinja
      <h3 id="stay-fee-setup">{{ t('guide.stay_fee.setup_title') }}</h3>
      <ol class="guide-steps">{% for n in range(1, 4) %}<li>{{ t('guide.stay_fee.setup' ~ n) }}</li>{% endfor %}</ol>
      <h3 id="stay-fee-pay">{{ t('guide.stay_fee.pay_title') }}</h3>
      <ol class="guide-steps">{% for n in range(1, 7) %}<li>{{ t('guide.stay_fee.pay' ~ n) }}</li>{% endfor %}</ol>
      <h3>{{ t('guide.wrong_title') }}</h3>
      <ul>{% for n in range(1, 5) %}<li>{{ t('guide.stay_fee.wrong' ~ n) }}</li>{% endfor %}</ul>
```

   Command: `grep -c 'id="stay-fee-pay"' App/app/templates/guide.html`. Expected: `1`.

9. **Invoices: when.** Directly after `      <p>{{ t('guide.invoices.body') }}</p>` insert `      <p>{{ t('guide.invoices.when') }}</p>`. Command: `grep -c "guide.invoices.when" App/app/templates/guide.html`. Expected: `1`.

10. **Invoices: steps.** Directly after `      <p>{{ t('guide.invoices.flow') }}</p>` insert:

```jinja
      <p class="ui-sub">{{ t('guide.invoices.settings') }}</p>
      <h3>{{ t('guide.how_title') }}</h3>
      <ol class="guide-steps">{% for n in range(1, 7) %}<li>{{ t('guide.invoices.how' ~ n) }}</li>{% endfor %}</ol>
      <h3>{{ t('guide.wrong_title') }}</h3>
      <ul>{% for n in range(1, 4) %}<li>{{ t('guide.invoices.wrong' ~ n) }}</li>{% endfor %}</ul>
```

   Command: `grep -c "guide.invoices.how" App/app/templates/guide.html`. Expected: `1`.

11. **Tests.** In `App/tests/test_guide.py` line 10 replace `"setup", "stays",` with `"setup", "business", "stays",`. In `App/tests/test_guide_browser.py` replace `SECTIONS = ("finding", "glossary", "cleaning", "guest_links", "stays",` with `SECTIONS = ("finding", "glossary", "cleaning", "guest_links", "business", "stays",`. Command: `cd App && .venv/bin/python -m pytest tests/test_guide.py -q --tb=short -x 2>&1 | tail -5`. Expected: `3 passed`.

12. **Browser and screenshots.** Run section 6 command 2. Look once at `guide-setup-390.png`, `guide-business-390.png`, `guide-stay_fee-390.png`, `guide-invoices-390.png`. Commit them. Then section 6 command 3.

## 5. Do not touch

`App/app/havel*.py`, `App/app/host_i18n.py`, `App/app/host_vi_i18n.py`, every other template, CSS, every existing guide key (the five `guide.setup.step*` parts stay as they are). Hard rules: AGENTS.md 7, 8, 9.

## 6. Commands (from `App/`, `export UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium-1194/chrome-linux/chrome UBYHOST_REQUIRE_BROWSER=1`)

1. `.venv/bin/python -m pytest tests/test_guide.py tests/test_host_i18n.py tests/test_no_em_dashes.py tests/test_copy_cleanup.py -q --tb=short -x 2>&1 | tail -30` → all passed.
2. `.venv/bin/python -m pytest tests/test_guide_browser.py -q -rs 2>&1 | tail -30` → 2 passed, 0 skipped.
3. `.venv/bin/python -m pytest tests/test_design_guardrails_browser.py tests/test_a11y_guard_browser.py -q -rs 2>&1 | tail -30` → passed, 0 skipped.
4. From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -3` → OK.

## 7. Acceptance

- [ ] First-time setup starts with what and when, "Add a property" (`#add-property`), "The guided setup" (`#setup-guide`), a trouble list, then the old five parts under "What each part needs".
- [ ] A new Business details section (`#business`) follows First-time setup and is in the side navigation.
- [ ] Stay fees has "Set it up for a property" (`#stay-fee-setup`), "Report and pay a period" (`#stay-fee-pay`) and a trouble list; Invoices has the settings note, steps and a trouble list.
- [ ] en and cs have the same keys; no dashes; four screenshots looked at; browser tests 0 skipped.

## 8. Stop and ask

As in docs/tasks/TEMPLATE.md section 8, plus: step 1 does not print `2` and `0`; an anchor is missing.

## 9. Report

Write `docs/tasks/0318-report.md` (600 tokens at most) and set `Status: review`: files changed, each command with its last 5 lines, section 7 ticked, deviations, questions, owner steps left, one sentence per screenshot.

## Risk list (for the reviewer)

`App/app/guide_i18n.py`: each sentence against the template named in section 2 (button labels, which setup steps can be skipped, the three stay-fee steps, "cannot be undone" on cancelling an invoice).

## Owner steps

1. On staging, add a test property by following "Add a property" on your phone, and say where a step does not match.
2. Read "Report and pay a period" against your last real stay-fee month.
3. The guide says an invoice is always for a stay (the picker's wording); the older sentence "for any stay or customer" in `guide.invoices.body` was left as it was. Say if invoices without a stay should be possible.
