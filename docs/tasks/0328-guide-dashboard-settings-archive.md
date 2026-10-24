# 0328: Guide: Dashboard, Settings and security, Archive, Data requests (en, cs)

Status: todo
Depends on: 0318 | Base commit: 92646d3 (check `git rev-parse --short origin/main` first; if it differs, write the current one here) | Branch: task/0328-guide-dashboard-settings
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Finish the guide's beginner parts for the last host areas: steps and trouble lists for the Dashboard and Settings and security, and two new sections, Archive and Data requests. It also corrects the Settings sentence that still mentions a password: UbyHost logs in with an e-mail link, passkeys and an optional authenticator app (the Vietnamese text already says so). Split from the plan's 0318 for the one-session limit.

## 2. Context

Plan: `docs/plans/havel-support-assistant.md` sections 16a.2, 16a.3; coverage `docs/plans/guide-coverage.md` rows dashboard, settings, archive and the `/privacy-requests` line. Rules: AGENTS.md 7, 9; `guide_i18n.py` header ("Every sentence describes behaviour in the code"); no em or en dashes. The step that opens a page names the place on a phone and on a computer; other steps say "Tap or click".

Copy written from (read 2026-10-24; do not reword it): `dashboard.html` (What needs you, each line's action button, "Nothing needs you today.", stay rows that open the stay, View all stays, Add stay and Add cleaning at the top, "Last updated", the empty text "No stays yet. Connect a booking calendar..."); `_shell_topbar.html` and `_shell_sidebar.html` (the UbyHost logo links to `/`); `settings.html` lines 13 to 160 (groups Account, Security, Phone app, Data & archive, Privacy, Technical, Help; Login e-mail, New login e-mail, Send confirmation link with "Nothing changes until you open it"; Passkeys, Add a passkey, Remove; Two-factor authentication, Set up, Move to a new phone with "You need a current code", recovery codes); `two_factor_setup.html` (authenticator apps named, Add to authenticator app on this phone, Six-digit code, Enable two-factor authentication); `passkeys.help`, `passkeys.unsupported`, `passkeys.remove_confirm`; `settings_archived.html` (Archived stays, properties, house-book entries, operators; Restore, in the row's menu except for house-book entries; `archive.retention_note`); `privacy_requests.html` (Record a request with Received, Channel, Request, Subject, Guest id, Record request; per request Status, Outcome note, Identity checked, Save; the one-month deadline).

Anchors, verified with `grep -nF` on 2026-10-24: `App/app/templates/guide.html` line 22 `      <p>{{ t('guide.overview.deadline') }}</p>`, line 139 `      <p>{{ t('guide.settings.body') }}</p>`, line 145 `    <section class="guide-section ui-section ui-section-plain" id="door-codes">` (line numbers move after 0316 to 0318; the text does not). `App/app/guide_i18n.py` line 150:

```python
        "guide.settings.body": "Settings hold your password and two-factor sign-in, the guest PIN setting, archived records, data protection (retention and deleting expired records), the activity log and technical details.",
```

and line 314:

```python
        "guide.settings.body": "Nastavení obsahuje heslo a dvoufázové přihlášení, nastavení PINu pro hosty, archiv, ochranu dat (doba uchování a mazání prošlých záznamů), protokol aktivit a technické údaje.",
```

plus the English and Czech `guide.demo.body` lines (they start `        "guide.demo.body": "Press Explore` and `        "guide.demo.body": "Tlačítkem Prohlédnout`). `App/tests/test_guide.py` line 11: `                        "filters", "housebook", "stay_fee", "invoices", "settings",`.

From brief 0318 (grep before editing): `guide.html` line 9 contains `'invoices', 'settings', 'door-codes'`; `App/tests/test_guide_browser.py` has `SECTIONS` ending `"stay_fee", "invoices", "overview", "settings")`.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/guide_i18n.py | edit | two corrected sentences, new keys en and cs |
| App/app/templates/guide.html | edit | sections list, overview and settings additions, two new sections |
| App/tests/test_guide.py | edit | section list |
| App/tests/test_guide_browser.py | edit | `SECTIONS` |
| docs/tasks/screenshots-guide/*.png | new or updated | |
| docs/tasks/0328-report.md | new | report |

No other file may change.

## 4. Steps

Commit after each step: `0328 step k`.

1. **Branch.** `git fetch origin && git checkout -b task/0328-guide-dashboard-settings origin/main`. Command: `grep -c "guide.nav.business" App/app/guide_i18n.py && grep -c "guide.nav.archive" App/app/guide_i18n.py`. Expected: `2` then `0` (else STOP).

2. **Correct the Settings sentence.** Replace the English line 150 quoted in section 2 with:

```python
        "guide.settings.body": "Settings hold how you log in (your login e-mail, passkeys and two-factor authentication), the guest PIN setting, archived records, data protection (retention and deleting expired records), the activity log and technical details.",
```

   and the Czech line 314 with:

```python
        "guide.settings.body": "Nastavení obsahuje způsob přihlášení (přihlašovací e-mail, přístupové klíče a dvoufázové ověření), nastavení PINu pro hosty, archiv, ochranu dat (doba uchování a mazání prošlých záznamů), protokol aktivit a technické údaje.",
```

   Command: `grep -c "password and two-factor\|heslo a dvoufázové" App/app/guide_i18n.py`. Expected: `0`.

3. **English copy.** Directly after the English `guide.demo.body` line, insert:

```python
        # 0328: Dashboard, Settings and security, Archive, Data requests (plan 16a.2).
        "guide.overview.when": "Open it first every time: it shows what needs you today, so you do not have to check every stay.",
        "guide.overview.how1": "Open Dashboard: on a phone, tap Dashboard in the bar at the bottom; on a computer, click Dashboard in the menu on the left. The UbyHost logo also takes you there.",
        "guide.overview.how2": "Start with What needs you. Each line says what is missing and has a button that takes you to the place to fix it.",
        "guide.overview.how3": "Below it, tap or click a stay to open it. View all stays opens the full list.",
        "guide.overview.how4": "Add stay and Add cleaning at the top of the page open the same forms as on Stays and Cleaning.",
        "guide.overview.wrong1": "No stays yet: connect a booking calendar so arrivals appear here on their own, or add a stay by hand (see Stays & calendars).",
        "guide.overview.wrong2": "A booking you expected is missing: Last updated shows when your calendars were last read. Check the calendar on the property's Bookings & calendars tab.",
        "guide.overview.wrong3": "A deadline is red: the stay must be reported in less than a day, or it is already late. Open the stay and check its colour (see What the colours mean).",
        "guide.settings.when": "You need it to change your login e-mail, to log in faster with a passkey, or to add a second step with an authenticator app.",
        "guide.settings.login": "You log in with a link that UbyHost sends to your login e-mail. That link always works, also when you add a passkey.",
        "guide.settings.passkey_title": "Log in with a passkey",
        "guide.settings.passkey1": "Open Settings: on a phone, tap More, then Settings; on a computer, click Settings in the menu on the left.",
        "guide.settings.passkey2": "Under Security, tap or click Add a passkey.",
        "guide.settings.passkey3": "Confirm with Face ID, a fingerprint or your device PIN. Next time this device logs in without opening your inbox.",
        "guide.settings.twofa_title": "Add two-factor authentication",
        "guide.settings.twofa1": "Under Security, next to Two-factor authentication, tap or click Set up.",
        "guide.settings.twofa2": "Open an authenticator app, for example Google Authenticator, Microsoft Authenticator or 1Password, and scan the QR code. On the phone itself, tap Add to authenticator app on this phone instead.",
        "guide.settings.twofa3": "Type the six-digit code from the app and tap or click Enable two-factor authentication.",
        "guide.settings.twofa4": "Keep the recovery codes somewhere safe. Each one works once.",
        "guide.settings.email_title": "Change your login e-mail",
        "guide.settings.email1": "Under Account, type the New login e-mail and tap or click Send confirmation link.",
        "guide.settings.email2": "Open the link in the e-mail that arrives at the new address. Nothing changes until you open it.",
        "guide.settings.wrong1": "You have a new phone for the authenticator app: use Move to a new phone under Security. You need a current code from the app or a recovery code.",
        "guide.settings.wrong2": "This browser cannot create passkeys: try your phone, or a current Safari, Chrome, Edge or Firefox. The e-mail link keeps working.",
        "guide.settings.wrong3": "You lost a device that has a passkey: tap or click Remove next to that passkey under Security. That device then has to log in with the e-mail link.",
        "guide.nav.archive": "Archive",
        "guide.archive.what": "Archive holds the stays, properties, guest register entries and operators you archived. Archiving hides them from your daily work but keeps their history.",
        "guide.archive.when": "Use it to bring back something you archived by mistake, or to look at old records.",
        "guide.archive.how1": "Open Archive: on a phone, tap More, then Archive; on a computer, click your name at the bottom of the menu, then Archive.",
        "guide.archive.how2": "Find the item under Archived stays, Archived properties, Archived house-book entries or Archived operators.",
        "guide.archive.how3": "Tap or click Restore. For stays, properties and operators, Restore is in the row's menu (the three dots).",
        "guide.archive.note": "Archiving never deletes guest records. Only the six-year retention purge in Settings deletes them for good.",
        "guide.archive.wrong1": "An archived property is missing from the Dashboard and its guest link does not offer stays: restore it to use it again.",
        "guide.nav.privacy_requests": "Data requests",
        "guide.privacy_requests.what": "Data requests is your record of requests from guests or hosts to see, correct or erase their personal data. The deadline is one month.",
        "guide.privacy_requests.when": "Use it whenever someone asks what data you hold about them, or asks you to correct or delete it.",
        "guide.privacy_requests.how1": "Open Data requests: on a phone, tap More, then Data requests; on a computer, click your name at the bottom of the menu, then Data requests.",
        "guide.privacy_requests.how2": "Under Record a request, fill in when it was Received, the Channel, the Request and the Subject, then tap or click Record request.",
        "guide.privacy_requests.how3": "The request appears in the list with its due date.",
        "guide.privacy_requests.how4": "When you have dealt with it, tick Identity checked if you checked who asked, write what you did in Outcome note, set the Status and tap or click Save.",
        "guide.privacy_requests.wrong1": "You do not know what the guest's data is: open the guest's stay, or the Guest register, to see what UbyHost holds.",
```

   Command: `cd App && .venv/bin/python -c "from app.guide_i18n import GUIDE_STRINGS as g; print(sum(1 for k in g['en'] if k.startswith(('guide.overview.when', 'guide.overview.how', 'guide.overview.wrong', 'guide.settings.when', 'guide.settings.login', 'guide.settings.passkey', 'guide.settings.twofa', 'guide.settings.email', 'guide.settings.wrong', 'guide.archive.', 'guide.nav.archive', 'guide.privacy_requests.', 'guide.nav.privacy_requests'))))"`. Expected: `40`.

4. **Czech copy.** Directly after the Czech `guide.demo.body` line, insert:

```python
        # 0328: Přehled, Nastavení a zabezpečení, Archiv, Žádosti o údaje (plan 16a.2).
        "guide.overview.when": "Otevřete ho pokaždé jako první: ukazuje, co na vás dnes čeká, takže nemusíte procházet každý pobyt.",
        "guide.overview.how1": "Otevřete Přehled: na telefonu klepněte na Přehled v liště dole, na počítači klikněte na Přehled v menu vlevo. Dostanete se tam i přes logo UbyHost.",
        "guide.overview.how2": "Začněte částí Co na vás čeká. Každý řádek říká, co chybí, a má tlačítko, které vás zavede tam, kde to opravíte.",
        "guide.overview.how3": "Pod ní klepněte nebo klikněte na pobyt a otevře se. Všechny pobyty otevře celý seznam.",
        "guide.overview.how4": "Přidat pobyt a Přidat úklid nahoře na stránce otevřou stejné formuláře jako v Pobytech a v Úklidu.",
        "guide.overview.wrong1": "Zatím žádné pobyty: připojte kalendář rezervací a příjezdy se tu objeví samy, nebo pobyt přidejte ručně (viz Pobyty a kalendáře).",
        "guide.overview.wrong2": "Chybí rezervace, kterou čekáte: Naposledy aktualizováno ukazuje, kdy se kalendáře naposledy načetly. Zkontrolujte kalendář na záložce Rezervace a kalendáře u ubytování.",
        "guide.overview.wrong3": "Termín je červený: pobyt se musí nahlásit za méně než den, nebo už je pozdě. Otevřete pobyt a podívejte se na jeho barvu (viz Co znamenají barvy).",
        "guide.settings.when": "Potřebujete ho, když chcete změnit přihlašovací e-mail, přihlašovat se rychleji přístupovým klíčem nebo přidat druhý krok s autentizační aplikací.",
        "guide.settings.login": "Přihlašujete se odkazem, který UbyHost pošle na váš přihlašovací e-mail. Ten odkaz funguje vždy, i když si přidáte přístupový klíč.",
        "guide.settings.passkey_title": "Přihlášení přístupovým klíčem",
        "guide.settings.passkey1": "Otevřete Nastavení: na telefonu klepněte na Další a pak na Nastavení, na počítači klikněte na Nastavení v menu vlevo.",
        "guide.settings.passkey2": "V části Zabezpečení klepněte nebo klikněte na Přidat klíč.",
        "guide.settings.passkey3": "Potvrďte pomocí Face ID, otisku prstu nebo PINu zařízení. Příště se toto zařízení přihlásí, aniž byste otevírali e-mail.",
        "guide.settings.twofa_title": "Zapnout dvoufázové ověření",
        "guide.settings.twofa1": "V části Zabezpečení klepněte nebo klikněte vedle Dvoufázové ověření na Nastavit.",
        "guide.settings.twofa2": "Otevřete autentizační aplikaci, třeba Google Authenticator, Microsoft Authenticator nebo 1Password, a naskenujte QR kód. Přímo v telefonu místo toho klepněte na Přidat do autentizační aplikace v tomto telefonu.",
        "guide.settings.twofa3": "Napište šestimístný kód z aplikace a klepněte nebo klikněte na Zapnout dvoufázové ověření.",
        "guide.settings.twofa4": "Záložní kódy si uložte na bezpečné místo. Každý funguje jen jednou.",
        "guide.settings.email_title": "Změnit přihlašovací e-mail",
        "guide.settings.email1": "V části Účet napište Nový přihlašovací e-mail a klepněte nebo klikněte na Poslat potvrzovací odkaz.",
        "guide.settings.email2": "Otevřete odkaz v e-mailu, který přijde na novou adresu. Dokud ho neotevřete, nic se nezmění.",
        "guide.settings.wrong1": "Máte nový telefon pro autentizační aplikaci: použijte Přechod na nový telefon v části Zabezpečení. Budete potřebovat platný kód z aplikace nebo záložní kód.",
        "guide.settings.wrong2": "Tento prohlížeč neumí vytvořit přístupový klíč: zkuste telefon nebo aktuální Safari, Chrome, Edge či Firefox. Odkaz z e-mailu funguje dál.",
        "guide.settings.wrong3": "Ztratili jste zařízení s přístupovým klíčem: v části Zabezpečení klepněte nebo klikněte u toho klíče na Odebrat. Zařízení se pak musí přihlásit odkazem z e-mailu.",
        "guide.nav.archive": "Archiv",
        "guide.archive.what": "Archiv obsahuje pobyty, ubytování, záznamy knihy hostů a provozovatele, které jste archivovali. Archivace je skryje z každodenní práce, ale jejich historie zůstává.",
        "guide.archive.when": "Použijte ho, když chcete vrátit něco, co jste archivovali omylem, nebo projít staré záznamy.",
        "guide.archive.how1": "Otevřete Archiv: na telefonu klepněte na Další a pak na Archiv, na počítači klikněte na své jméno dole v menu a pak na Archiv.",
        "guide.archive.how2": "Najděte položku v části Archivované pobyty, Archivovaná ubytování, Archivované záznamy knihy nebo Archivovaní provozovatelé.",
        "guide.archive.how3": "Klepněte nebo klikněte na Obnovit. U pobytů, ubytování a provozovatelů je Obnovit v nabídce řádku (tři tečky).",
        "guide.archive.note": "Archivace záznamy hostů nikdy nesmaže. Natrvalo je smaže jen šestileté mazání podle doby uchování v Nastavení.",
        "guide.archive.wrong1": "Archivované ubytování chybí na Přehledu a jeho odkaz pro hosty nenabízí pobyty: obnovte ho, chcete-li ho znovu používat.",
        "guide.nav.privacy_requests": "Žádosti o údaje",
        "guide.privacy_requests.what": "Žádosti o údaje jsou váš záznam žádostí hostů nebo ubytovatelů o přístup k jejich osobním údajům, jejich opravu nebo výmaz. Lhůta je jeden měsíc.",
        "guide.privacy_requests.when": "Použijte je vždy, když se vás někdo zeptá, jaké údaje o něm máte, nebo vás požádá o jejich opravu či smazání.",
        "guide.privacy_requests.how1": "Otevřete Žádosti o údaje: na telefonu klepněte na Další a pak na Žádosti o údaje, na počítači klikněte na své jméno dole v menu a pak na Žádosti o údaje.",
        "guide.privacy_requests.how2": "V části Zaznamenat žádost vyplňte, kdy byla Přijato, Kanál, Žádost a Subjekt, a klepněte nebo klikněte na Zaznamenat žádost.",
        "guide.privacy_requests.how3": "Žádost se objeví v seznamu se svým termínem.",
        "guide.privacy_requests.how4": "Až ji vyřídíte, zaškrtněte Totožnost ověřena, pokud jste ověřili, kdo žádá, do Poznámka k výsledku napište, co jste udělali, nastavte Stav a klepněte nebo klikněte na Uložit.",
        "guide.privacy_requests.wrong1": "Nevíte, jaké údaje o hostovi máte: otevřete jeho pobyt nebo Knihu hostů a uvidíte, co UbyHost uchovává.",
```

   Command: `cd App && .venv/bin/python -m pytest tests/test_guide.py -q -k same_keys 2>&1 | tail -3`. Expected: `1 passed`.

5. **Sections list.** In `App/app/templates/guide.html` line 9 replace `'invoices', 'settings', 'door-codes'` with `'invoices', 'settings', 'archive', 'privacy_requests', 'door-codes'`. Command: `grep -c "'settings', 'archive', 'privacy_requests'" App/app/templates/guide.html`. Expected: `1`.

6. **Dashboard.** Directly after `      <p>{{ t('guide.overview.deadline') }}</p>` insert:

```jinja
      <p>{{ t('guide.overview.when') }}</p>
      <h3>{{ t('guide.how_title') }}</h3>
      <ol class="guide-steps">{% for n in range(1, 5) %}<li>{{ t('guide.overview.how' ~ n) }}</li>{% endfor %}</ol>
      <h3>{{ t('guide.wrong_title') }}</h3>
      <ul>{% for n in range(1, 4) %}<li>{{ t('guide.overview.wrong' ~ n) }}</li>{% endfor %}</ul>
```

   Command: `grep -c "guide.overview.how" App/app/templates/guide.html`. Expected: `1`.

7. **Settings.** Directly after `      <p>{{ t('guide.settings.body') }}</p>` insert:

```jinja
      <p>{{ t('guide.settings.when') }}</p>
      <p>{{ t('guide.settings.login') }}</p>
      {% for part, count in [('passkey', 3), ('twofa', 4), ('email', 2)] %}
      <h3 id="settings-{{ part }}">{{ t('guide.settings.' ~ part ~ '_title') }}</h3>
      <ol class="guide-steps">{% for n in range(1, count + 1) %}<li>{{ t('guide.settings.' ~ part ~ n) }}</li>{% endfor %}</ol>
      {% endfor %}
      <h3>{{ t('guide.wrong_title') }}</h3>
      <ul>{% for n in range(1, 4) %}<li>{{ t('guide.settings.wrong' ~ n) }}</li>{% endfor %}</ul>
```

   Command: `grep -c "('passkey', 3)" App/app/templates/guide.html`. Expected: `1`.

8. **Archive and Data requests.** Directly before `    <section class="guide-section ui-section ui-section-plain" id="door-codes">` insert:

```jinja
    <section class="guide-section ui-section ui-section-plain" id="archive">
      <h2>{{ t('guide.nav.archive') }}</h2>
      <p>{{ t('guide.archive.what') }}</p>
      <p class="ui-sub">{{ t('guide.archive.when') }}</p>
      <h3>{{ t('guide.how_title') }}</h3>
      <ol class="guide-steps">{% for n in range(1, 4) %}<li>{{ t('guide.archive.how' ~ n) }}</li>{% endfor %}</ol>
      <p class="ui-sub">{{ t('guide.archive.note') }}</p>
      <h3>{{ t('guide.wrong_title') }}</h3>
      <ul><li>{{ t('guide.archive.wrong1') }}</li></ul>
    </section>

    <section class="guide-section ui-section ui-section-plain" id="privacy_requests">
      <h2>{{ t('guide.nav.privacy_requests') }}</h2>
      <p>{{ t('guide.privacy_requests.what') }}</p>
      <p class="ui-sub">{{ t('guide.privacy_requests.when') }}</p>
      <h3>{{ t('guide.how_title') }}</h3>
      <ol class="guide-steps">{% for n in range(1, 5) %}<li>{{ t('guide.privacy_requests.how' ~ n) }}</li>{% endfor %}</ol>
      <h3>{{ t('guide.wrong_title') }}</h3>
      <ul><li>{{ t('guide.privacy_requests.wrong1') }}</li></ul>
    </section>

```

   Command: `grep -c 'id="archive"\|id="privacy_requests"' App/app/templates/guide.html`. Expected: `2`.

9. **Tests.** In `App/tests/test_guide.py` replace `                        "filters", "housebook", "stay_fee", "invoices", "settings",` with `                        "filters", "housebook", "stay_fee", "invoices", "settings", "archive", "privacy_requests",`. In `App/tests/test_guide_browser.py` replace `"overview", "settings")` with `"overview", "settings", "archive", "privacy_requests")`. Command: `cd App && .venv/bin/python -m pytest tests/test_guide.py -q --tb=short -x 2>&1 | tail -5`. Expected: `3 passed`.

10. **Browser and screenshots.** Run section 6 command 2. Look once at `guide-overview-390.png`, `guide-settings-390.png`, `guide-archive-390.png`, `guide-privacy_requests-390.png`. Commit them. Then section 6 command 3.

## 5. Do not touch

`App/app/havel*.py`, `App/app/host_i18n.py`, `App/app/host_vi_i18n.py`, every other template, CSS, every other existing guide key. Hard rules: AGENTS.md 7, 8, 9.

## 6. Commands (from `App/`, `export UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium-1194/chrome-linux/chrome UBYHOST_REQUIRE_BROWSER=1`)

1. `.venv/bin/python -m pytest tests/test_guide.py tests/test_host_i18n.py tests/test_no_em_dashes.py tests/test_copy_cleanup.py -q --tb=short -x 2>&1 | tail -30` → all passed.
2. `.venv/bin/python -m pytest tests/test_guide_browser.py -q -rs 2>&1 | tail -30` → 2 passed, 0 skipped.
3. `.venv/bin/python -m pytest tests/test_design_guardrails_browser.py tests/test_a11y_guard_browser.py -q -rs 2>&1 | tail -30` → passed, 0 skipped.
4. From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -3` → OK.

## 7. Acceptance

- [ ] The Settings sentence no longer mentions a password, in en and cs.
- [ ] Dashboard and Settings & security have when, steps and a trouble list; Settings has `#settings-passkey`, `#settings-twofa`, `#settings-email`.
- [ ] New sections Archive (`#archive`) and Data requests (`#privacy_requests`) sit after Settings & security and are in the side navigation.
- [ ] en and cs have the same keys; no dashes; four screenshots looked at; browser tests 0 skipped.

## 8. Stop and ask

As in docs/tasks/TEMPLATE.md section 8, plus: step 1 does not print `2` and `0`; an anchor is missing.

## 9. Report

Write `docs/tasks/0328-report.md` (600 tokens at most) and set `Status: review`: files changed, each command with its last 5 lines, section 7 ticked, deviations, questions, owner steps left, one sentence per screenshot.

## Risk list (for the reviewer)

`App/app/guide_i18n.py`: the corrected `guide.settings.body` and each new sentence against the templates named in section 2.

## Owner steps

1. On your phone, follow "Log in with a passkey" on staging and say if a label differs.
2. Read "Data requests": it is the record you keep for GDPR requests. Say if you want more on how to answer one.
