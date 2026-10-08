# 0016: Door codes guide, terms, guest notice and subprocessor entry

Status: todo
Depends on: 0010 (run any time after it) | Base commit: after 0010 merges | Branch: task/0016-door-codes-guide-and-legal
Executor: Cursor local agent (composer, Kimi or GLM) | Fits one session

## 1. Objective

Hosts get one place that explains door codes step by step, plus the door-code terms they accept on Set up. Guests of a property with door codes see one extra paragraph in that property's privacy notice. The public subprocessor register and the ROPA list TTLock. The wording follows `docs/privacy/DOOR_CODES_LEGAL.md`.

## 2. Context

- Legal basis for every text here: `docs/privacy/DOOR_CODES_LEGAL.md`. Copy rules (`docs/context/rules.md` "Copy"): one explanation lives in one place (the steps live only in the Guide; pages link to it), EN and CS keys in parity, no em dashes.
- The Smart locks page (task 0010) links to `/guide#door-codes` and `/guide#door-codes-terms` and records `ttlock.DOOR_CODE_TERMS_VERSION = "2026-10-08"`.
- Guide: `App/app/templates/guide.html`, sections like `<section class="guide-section panel" id="setup"><h2>…</h2><ol class="guide-steps">{% for n in range(1, 6) %}<li><strong>{{ t('guide.setup.step' ~ n ~ '_title') }}:</strong> {{ t('guide.setup.step' ~ n) }}</li>{% endfor %}</ol></section>`. Strings in `App/app/guide_i18n.py` (`GUIDE_STRINGS["en"]`, `["cs"]`), nav keys like `guide.nav.settings`; if the guide has a section nav, add the new one.
- Guest privacy notice: route `privacy_notice` in `App/app/routes/guest.py` (near line 1020) passes `passport_photo_policy`; `App/app/templates/guest/privacy.html` shows `{% if passport_photo_policy == 'required_foreign' %}<h3>{{ t('privacy_passport_photo_title') }}</h3><p>{{ t('privacy_passport_photo_body') }}</p>{% endif %}`. Guest strings in `App/app/i18n.py` for `en`, `cs`, `de`, `es`, `fr`.
- Register: `SUBPROCESSOR_IDS` in `App/app/routes/legal.py` (line 21); rows from `subprocessors.<id>_provider/_purpose/_data/_location/_safeguard` in `App/app/subprocessors_i18n.py` (EN, CS). Tests: `tests/test_legal_contents.py`.
- ROPA: `docs/privacy/ROPA.md`, section A rows "Categories of personal data" and "Recipients", list "Open questions for counsel".

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/templates/guide.html` | edit | Step 1 |
| `App/app/guide_i18n.py` | edit | Step 2 |
| `App/app/routes/guest.py` | edit | Step 3, one context key |
| `App/app/templates/guest/privacy.html` | edit | Step 3 |
| `App/app/i18n.py` | edit | Step 3 |
| `App/app/routes/legal.py` | edit | Add `"ttlock"` to `SUBPROCESSOR_IDS`, last |
| `App/app/subprocessors_i18n.py` | edit | Step 4 |
| `docs/privacy/ROPA.md` | edit | Step 5 |
| `App/tests/test_door_codes_guide.py` | create | Step 6 |

No other file may change.

## 4. Steps

1. **Guide section** after the settings section:
   ```
   <section class="guide-section panel" id="door-codes">
     <h2>{{ t('guide.nav.door_codes') }}</h2>
     <p>{{ t('guide.door_codes.lede') }}</p>
     <h3>{{ t('guide.door_codes.need_title') }}</h3>
     <ul>{% for n in range(1, 4) %}<li>{{ t('guide.door_codes.need' ~ n) }}</li>{% endfor %}</ul>
     <h3>{{ t('guide.door_codes.steps_title') }}</h3>
     <ol class="guide-steps">{% for n in range(1, 7) %}<li><strong>{{ t('guide.door_codes.step' ~ n ~ '_title') }}:</strong> {{ t('guide.door_codes.step' ~ n) }}</li>{% endfor %}</ol>
     <h3>{{ t('guide.door_codes.how_title') }}</h3>
     <ul>{% for n in range(1, 6) %}<li>{{ t('guide.door_codes.how' ~ n) }}</li>{% endfor %}</ul>
     <h3 id="door-codes-terms">{{ t('guide.door_codes.terms_title') }}</h3>
     <p class="small muted">{{ t('guide.door_codes.terms_version', version='2026-10-08') }}</p>
     <ol>{% for n in range(1, 10) %}<li>{{ t('guide.door_codes.terms' ~ n) }}</li>{% endfor %}</ol>
   </section>
   ```
2. **Guide strings** (EN, CS):

   | Key | EN | CS |
   |---|---|---|
   | `guide.nav.door_codes` | Door codes with TTLock | Kódy ke dveřím s TTLock |
   | `guide.door_codes.lede` | Optional, per property. If a property has a TTLock lock with a keypad and a gateway, each guest gets a timed door code once everyone on the stay is registered. Properties you do not switch on are not affected. | Volitelné, pro každé ubytování zvlášť. Má-li ubytování zámek TTLock s klávesnicí a bránou, každý host dostane časově omezený kód ke dveřím, jakmile jsou zaregistrováni všichni hosté pobytu. Ubytování, u kterých funkci nezapnete, se nic nemění. |
   | `guide.door_codes.need_title` | What you need | Co potřebujete |
   | `guide.door_codes.need1` | A TTLock lock with a keypad, added in your TTLock app. | Zámek TTLock s klávesnicí, přidaný ve vaší aplikaci TTLock. |
   | `guide.door_codes.need2` | A TTLock gateway near the lock, or a Wi-Fi lock. | Bránu TTLock poblíž zámku, nebo zámek s Wi-Fi. |
   | `guide.door_codes.need3` | The lock's clock on Prague time: in the TTLock app open the lock, then Settings, Lock Time, and calibrate it. | Hodiny zámku na pražském čase: v aplikaci TTLock otevřete zámek, pak Nastavení, Čas zámku, a čas zkalibrujte. |
   | `guide.door_codes.steps_title` | Set it up | Nastavení |
   | `guide.door_codes.step1_title` | Set up | Nastavte |
   | `guide.door_codes.step1` | Open Properties, Property tools, Smart locks. Accept the terms below and tap Set up. UbyHost creates its own TTLock account for you and shows its name. | Otevřete Ubytování, Nástroje ubytování, Chytré zámky. Přijměte podmínky níže a klepněte na Nastavit. UbyHost pro vás vytvoří vlastní účet TTLock a zobrazí jeho název. |
   | `guide.door_codes.step2_title` | Share each lock | Sdílejte každý zámek |
   | `guide.door_codes.step2` | In the TTLock app open the lock, tap Send eKey and enter that account name. Turn on Authorized admin, turn off Remote unlock and leave the end date empty. UbyHost can then create codes but can never open the door remotely, and your TTLock password never reaches UbyHost. | V aplikaci TTLock otevřete zámek, klepněte na Odeslat eKey a zadejte název toho účtu. Zapněte Autorizovaný správce, vypněte Vzdálené odemykání a datum konce nechte prázdné. UbyHost pak může vytvářet kódy, ale nikdy neotevře dveře na dálku, a vaše heslo TTLock se k UbyHost nikdy nedostane. |
   | `guide.door_codes.step3_title` | Check for locks | Zkontrolujte zámky |
   | `guide.door_codes.step3` | Back in UbyHost, tap Check for locks. Your locks appear with their name, ID (the one the TTLock app shows under Basic information) and battery. | Zpět v UbyHost klepněte na Zkontrolovat zámky. Zobrazí se vaše zámky s názvem, ID (stejným, jaké ukazuje aplikace TTLock v Základních informacích) a stavem baterie. |
   | `guide.door_codes.step4_title` | Switch it on per property | Zapněte u ubytování |
   | `guide.door_codes.step4` | Open the property, section Door code. Tick Send guests a door code, pick the lock and set the check-in and check-out hour. | Otevřete ubytování, sekci Kód ke dveřím. Zaškrtněte Posílat hostům kód ke dveřím, vyberte zámek a nastavte hodinu příjezdu a odjezdu. |
   | `guide.door_codes.step5_title` | Test it | Vyzkoušejte |
   | `guide.door_codes.step5` | Add a stay by hand for tomorrow, open the guest link yourself and register. The code shows on the stay page and arrives by e-mail. Try it on the keypad from 1 hour before check-in. | Přidejte ručně pobyt na zítřek, sami otevřete odkaz pro hosty a zaregistrujte se. Kód se zobrazí na stránce pobytu a přijde e-mailem. Vyzkoušejte ho na klávesnici od 1 hodiny před příjezdem. |
   | `guide.door_codes.step6_title` | Switch it off | Vypnutí |
   | `guide.door_codes.step6` | Untick the property, or tap Remove on the Smart locks page. Remove also deletes the eKeys you shared with UbyHost. | Zrušte zaškrtnutí u ubytování, nebo na stránce Chytré zámky klepněte na Odebrat. Odebrání smaže i eKey, které jste s UbyHost sdíleli. |
   | `guide.door_codes.how_title` | How codes work | Jak kódy fungují |
   | `guide.door_codes.how1` | A code is created once every guest of the stay is registered. It works from 1 hour before check-in to 1 hour after check-out. | Kód vznikne, jakmile jsou zaregistrováni všichni hosté pobytu. Funguje od 1 hodiny před příjezdem do 1 hodiny po odjezdu. |
   | `guide.door_codes.how2` | The guest sees it on the stay page and gets it by e-mail. You get a copy. | Host ho uvidí na stránce pobytu a dostane ho e-mailem. Vy dostanete kopii. |
   | `guide.door_codes.how3` | The guest must type the code for the first time within 24 hours of its start, or TTLock invalidates it. For a late arrival, create a new code in the TTLock app. | Host musí kód poprvé zadat do 24 hodin od začátku jeho platnosti, jinak ho TTLock zneplatní. Při pozdním příjezdu vytvořte nový kód v aplikaci TTLock. |
   | `guide.door_codes.how4` | If the calendar moves the stay, the code moves with it and the guest gets a new e-mail. If the stay is cancelled, UbyHost deletes the code and tells you. A code nobody has typed yet may still work until its end, so check the lock in the TTLock app. | Když kalendář pobyt posune, kód se posune s ním a host dostane nový e-mail. Když se pobyt zruší, UbyHost kód smaže a dá vám vědět. Kód, který ještě nikdo nezadal, může fungovat až do konce platnosti, proto zámek zkontrolujte v aplikaci TTLock. |
   | `guide.door_codes.how5` | Codes are created in TTLock's cloud, so they work even while the gateway is offline. Changing or deleting a code needs the gateway online. | Kódy vznikají v cloudu TTLock, takže fungují i ve chvíli, kdy je brána offline. Ke změně nebo smazání kódu musí být brána online. |
   | `guide.door_codes.terms_title` | Door code terms | Podmínky pro kódy ke dveřím |
   | `guide.door_codes.terms_version` | Version %(version)s | Verze %(version)s |
   | `guide.door_codes.terms1` | Door codes are optional and run on your own TTLock locks. You stay responsible for access to your property and for keeping another way in, such as a key or your own code. | Kódy ke dveřím jsou volitelné a běží na vašich vlastních zámcích TTLock. Za přístup do ubytování odpovídáte vy, včetně náhradní možnosti vstupu, například klíče nebo vlastního kódu. |
   | `guide.door_codes.terms2` | A code is sent only after every guest of the stay has registered. Anyone who knows the property's guest link and PIN can register for an upcoming stay, so keep the PIN private and change it from time to time. | Kód se pošle až poté, co se zaregistrují všichni hosté pobytu. Kdokoli, kdo zná odkaz pro hosty a PIN ubytování, se může zaregistrovat k nadcházejícímu pobytu, proto PIN nikomu nesdělujte a čas od času ho změňte. |
   | `guide.door_codes.terms3` | The service depends on TTLock's cloud, your gateway and Wi-Fi, the lock's battery and clock, and e-mail delivery. UbyHost cannot guarantee that a code is created, delivered or accepted by the lock in time. Liability follows section 17 of the Terms. | Služba závisí na cloudu TTLock, vaší bráně a Wi-Fi, baterii a hodinách zámku a na doručení e-mailu. UbyHost nemůže zaručit, že kód vznikne, bude doručen nebo že ho zámek včas přijme. Odpovědnost se řídí článkem 17 obchodních podmínek. |
   | `guide.door_codes.terms4` | TTLock is a service of Hangzhou Sciener Intelligent Control Technology Co., Ltd. (China). By setting up smart locks you authorise UbyHost to use it as a subprocessor for door codes (DPA, section 11). UbyHost sends it the lock ID, the code's validity times and a reference number, never guest names or contact details, and uses the EU Standard Contractual Clauses for any transfer outside the EEA. | TTLock je služba společnosti Hangzhou Sciener Intelligent Control Technology Co., Ltd. (Čína). Nastavením chytrých zámků UbyHost pověřujete, aby ji pro kódy ke dveřím využíval jako dalšího zpracovatele (smlouva o zpracování, článek 11). UbyHost jí posílá ID zámku, dobu platnosti kódu a referenční číslo, nikdy jména ani kontakty hostů, a pro předání mimo EHP používá standardní smluvní doložky EU. |
   | `guide.door_codes.terms5` | UbyHost uses its own TTLock account for you and never sees your TTLock password. It keeps that account's access encrypted and uses it only to create, change and delete codes and to read your shared locks and their clocks. It never opens a door remotely. | UbyHost pro vás používá vlastní účet TTLock a vaše heslo TTLock nikdy nevidí. Přístup k tomuto účtu uchovává šifrovaně a používá ho jen k vytváření, změně a mazání kódů a ke čtení sdílených zámků a jejich hodin. Nikdy neotevírá dveře na dálku. |
   | `guide.door_codes.terms6` | Door codes are stored encrypted and deleted one day after they expire. | Kódy ke dveřím se ukládají šifrovaně a mažou se den po skončení platnosti. |
   | `guide.door_codes.terms7` | Guests of every property that uses door codes see a paragraph about them in the property's privacy notice. | Hosté každého ubytování, které kódy ke dveřím používá, uvidí o nich odstavec v informacích o ochraně osobních údajů daného ubytování. |
   | `guide.door_codes.terms8` | Door codes may pause when TTLock's monthly call limit is nearly reached. | Kódy ke dveřím se mohou pozastavit, když se blíží měsíční limit volání TTLock. |
   | `guide.door_codes.terms9` | You can switch door codes off at any time, per property or by removing the connection, which also deletes the shared eKeys. | Kódy ke dveřím můžete kdykoli vypnout, u jednotlivého ubytování nebo odebráním připojení, které smaže i sdílené eKey. |

   For `terms3` CS, use the app's existing Czech name for the Terms if it differs (grep `terms.page_title` or the Terms heading in `App/app/terms_i18n.py`).
3. **Guest privacy notice.**
   - In `privacy_notice`, add `"door_codes": apartment["lock_provider"] == "ttlock"` to `context.update({...})`.
   - In `guest/privacy.html`, right after the passport-photo block: `{% if door_codes %}<h3>{{ t('privacy_door_code_title') }}</h3><p>{{ t('privacy_door_code_body') }}</p>{% endif %}`.
   - Strings, all five languages:

   | lang | `privacy_door_code_title` | `privacy_door_code_body` |
   |---|---|---|
   | en | Door code | This property gives you a door code once every guest is registered, so you can enter during your stay. The code is created through TTLock, a service of Hangzhou Sciener Intelligent Control Technology Co., Ltd. (China), which receives the lock, the code, its validity times and a reference number, but not your name or contact details. The code is shown on your stay page and sent to the e-mail address you registered with, with a copy to the host. It is stored encrypted and deleted one day after it expires. The legal basis is your accommodation contract (Art. 6(1)(b) GDPR). The lock records when the code is used, and the host sees that in their TTLock app. |
   | cs | Kód ke dveřím | Toto ubytování vám po registraci všech hostů pošle kód ke dveřím, abyste mohli během pobytu vstoupit. Kód vzniká přes TTLock, službu společnosti Hangzhou Sciener Intelligent Control Technology Co., Ltd. (Čína), která dostane zámek, kód, dobu jeho platnosti a referenční číslo, nikoli vaše jméno ani kontakty. Kód se zobrazí na stránce pobytu a pošle se na e-mail, kterým jste se registrovali, s kopií hostiteli. Ukládá se šifrovaně a maže se den po skončení platnosti. Právním základem je vaše smlouva o ubytování (čl. 6 odst. 1 písm. b) GDPR). Zámek zaznamenává použití kódu a hostitel to vidí ve své aplikaci TTLock. |
   | de | Türcode | Diese Unterkunft gibt Ihnen einen Türcode, sobald alle Gäste registriert sind, damit Sie während Ihres Aufenthalts eintreten können. Der Code wird über TTLock erstellt, einen Dienst der Hangzhou Sciener Intelligent Control Technology Co., Ltd. (China), die das Schloss, den Code, seine Gültigkeitszeiten und eine Referenznummer erhält, aber nicht Ihren Namen oder Ihre Kontaktdaten. Der Code wird auf Ihrer Aufenthaltsseite angezeigt und an die E-Mail-Adresse gesendet, mit der Sie sich registriert haben, mit einer Kopie an den Gastgeber. Er wird verschlüsselt gespeichert und einen Tag nach Ablauf gelöscht. Rechtsgrundlage ist Ihr Beherbergungsvertrag (Art. 6 Abs. 1 lit. b DSGVO). Das Schloss zeichnet auf, wann der Code verwendet wird, und der Gastgeber sieht das in seiner TTLock-App. |
   | es | Código de la puerta | Este alojamiento le da un código de la puerta cuando todos los huéspedes se han registrado, para que pueda entrar durante su estancia. El código se crea a través de TTLock, un servicio de Hangzhou Sciener Intelligent Control Technology Co., Ltd. (China), que recibe la cerradura, el código, sus horas de validez y un número de referencia, pero no su nombre ni sus datos de contacto. El código se muestra en la página de su estancia y se envía a la dirección de correo con la que se registró, con copia al anfitrión. Se guarda cifrado y se elimina un día después de que caduque. La base jurídica es su contrato de alojamiento (art. 6, apdo. 1, letra b, del RGPD). La cerradura registra cuándo se usa el código y el anfitrión lo ve en su aplicación TTLock. |
   | fr | Code de porte | Cet hébergement vous donne un code de porte dès que tous les voyageurs sont enregistrés, pour que vous puissiez entrer pendant votre séjour. Le code est créé via TTLock, un service de Hangzhou Sciener Intelligent Control Technology Co., Ltd. (Chine), qui reçoit la serrure, le code, ses horaires de validité et un numéro de référence, mais ni votre nom ni vos coordonnées. Le code s'affiche sur la page de votre séjour et est envoyé à l'adresse e-mail utilisée pour l'enregistrement, avec une copie à l'hôte. Il est conservé chiffré et supprimé un jour après son expiration. La base légale est votre contrat d'hébergement (art. 6, paragraphe 1, point b, du RGPD). La serrure enregistre l'utilisation du code et l'hôte le voit dans son application TTLock. |
4. **Subprocessor row** `ttlock` (EN, CS):

   | Key | EN | CS |
   |---|---|---|
   | `subprocessors.ttlock_provider` | Hangzhou Sciener Intelligent Control Technology Co., Ltd. (TTLock) | Hangzhou Sciener Intelligent Control Technology Co., Ltd. (TTLock) |
   | `subprocessors.ttlock_purpose` | Only if used: door codes. Creating, changing and deleting timed passcodes on the host's TTLock locks, for properties where the host switched door codes on. | Jen při použití: kódy ke dveřím. Vytváření, změna a mazání časově omezených kódů na zámcích TTLock hostitele, u ubytování, kde hostitel kódy zapnul. |
   | `subprocessors.ttlock_data` | Lock ID, the code, its validity times and a reference number. No guest names or contact details. | ID zámku, kód, doba jeho platnosti a referenční číslo. Žádná jména ani kontakty hostů. |
   | `subprocessors.ttlock_location` | EU API endpoint (euapi.ttlock.com); company based in China. | Rozhraní API v EU (euapi.ttlock.com); společnost se sídlem v Číně. |
   | `subprocessors.ttlock_safeguard` | EU Standard Contractual Clauses (2021/914, processor to processor), being concluded with TTLock; until signed, door codes run only on the operator's own properties. Data limited as stated. | Standardní smluvní doložky EU (2021/914, zpracovatel zpracovateli), uzavírají se s TTLock; do podpisu běží kódy ke dveřím jen na vlastních ubytováních provozovatele. Rozsah údajů omezen, jak je uvedeno. |
5. **ROPA** (`docs/privacy/ROPA.md`, section A):
   - "Categories of personal data": append `; when the host uses door codes, the door code and its validity times (encrypted, deleted a day after expiry)`.
   - "Recipients": append `; TTLock (Hangzhou Sciener Intelligent Control Technology Co., Ltd.), only for properties with door codes on: lock ID, code, validity times, reference number ([DOOR_CODES_LEGAL](DOOR_CODES_LEGAL.md))`.
   - "Open questions for counsel": add `Door codes: confirm the TTLock SCCs, the transfer impact assessment and the door-code terms ([DOOR_CODES_LEGAL](DOOR_CODES_LEGAL.md) section 9).`
6. **Tests** (`App/tests/test_door_codes_guide.py`):
   - `test_guide_has_the_door_code_section_and_terms_anchor` (EN and CS: `id="door-codes"`, `id="door-codes-terms"`, terms item 1 present).
   - `test_terms_version_matches_the_client` (the version on the page equals `ttlock.DOOR_CODE_TERMS_VERSION`).
   - `test_guest_privacy_notice_mentions_door_codes_only_when_on` (parametrized over the five languages: present with `lock_provider='ttlock'`, absent with NULL).
   - `test_register_lists_ttlock` (`/subprocessors?lang=en` and `cs`).

## 5. Do not touch

Everything outside §3. The Terms of Service, the DPA and the host privacy policy texts (versioned documents with 30 days' notice; TTLock joins DPA §11 at the next revision, see `docs/privacy/DOOR_CODES_LEGAL.md` section 3).

## 6. Commands

From `App/`: `.venv/bin/python -m pytest tests -q` (all pass, including `tests/test_legal_contents.py`, `tests/test_no_em_dashes.py`, `tests/test_host_i18n.py`), then `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_guest_browser_e2e.py tests/test_wp28_geometry.py -q -rs` (0 skipped; the guest privacy page changed). From the repo root: `python3 scripts/context_lint.py` (last line `context lint: OK`).

## 7. Acceptance

- [ ] The tests in step 6 pass; the full suite passes; browser and geometry: 0 skipped.
- [ ] Screenshots of the guide section (390, 1280 px) and of a guest privacy notice with the door-code paragraph (360, 390 px) in `docs/tasks/0016-shots/`.
- [ ] `git diff --stat` shows only the files in §3 plus the screenshots.

## 8. Stop and ask

Stop, and write the report, if:

- a test requires a legal document version bump for the register change (the owner decides; see `DOOR_CODES_LEGAL.md` section 3);
- a name or excerpt in §2 is not found;
- a test fails twice;
- a file outside §3 needs a change;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/0016-report.md` (1,500 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

- `App/app/guide_i18n.py` (terms, both languages)
- `App/app/i18n.py` (guest notice, five languages)
- `App/app/subprocessors_i18n.py`

## Owner steps

1. Before this PR is deployed: write to TTLock developer support and TTLock Europe asking for their data processing agreement with the EU Standard Contractual Clauses (2021/914, Module 3) and where `euapi.ttlock.com` is hosted. When they are signed, the orchestrator writes a one-line brief to change the register row to "EU Standard Contractual Clauses (2021/914, processor to processor)". Until then no other host may use door codes (`DOOR_CODES_LEGAL.md` section 9).
2. Forward their answer to the orchestrator for the one-page transfer impact assessment.
