# 0016: Door codes guide, terms and subprocessor entry

Status: todo
Depends on: 0010 (run any time after it) | Base commit: after 0010 merges | Branch: task/0016-door-codes-guide-and-legal
Executor: Cursor local agent (composer, Kimi or GLM) | Fits one session

## 1. Objective

Hosts get one place that explains how to set up door codes with TTLock, step by step, plus the door-code terms they accept when connecting. The public subprocessor register and the ROPA list TTLock. All copy here is marked for lawyer review before door codes go live.

## 2. Context

- Plan: `docs/plans/ttlock-door-codes.md` §8 and §12. Copy rules (`docs/context/rules.md` "Copy"): one explanation lives in one place, EN and CS keys in parity, no em dashes.
- The Smart locks card (task 0010) links to `/guide#door-codes` and `/guide#door-codes-terms`, and records acceptance of `ttlock.DOOR_CODE_TERMS_VERSION = "2026-10-08"`.
- Guide: `App/app/templates/guide.html`, sections like
  ```
  <section class="guide-section panel" id="setup">
    <h2>{{ t('guide.nav.setup') }}</h2>
    <ol class="guide-steps">
      {% for n in range(1, 6) %}
      <li><strong>{{ t('guide.setup.step' ~ n ~ '_title') }}:</strong> {{ t('guide.setup.step' ~ n) }}</li>
      {% endfor %}
    </ol>
  </section>
  ```
  Strings in `App/app/guide_i18n.py`, `GUIDE_STRINGS["en"]` and `["cs"]`, with nav keys like `guide.nav.settings`. If the guide has a nav list of sections, add the new one there.
- Subprocessor register: ids in `SUBPROCESSOR_IDS` (`App/app/routes/legal.py`, line 21), rows from strings `subprocessors.<id>_provider`, `_purpose`, `_data`, `_location`, `_safeguard` in `App/app/subprocessors_i18n.py` (EN and CS). Tests: `tests/test_legal_contents.py`.
- ROPA: `docs/privacy/ROPA.md`, section "A. Processor record — guest data", rows "Categories of personal data" and "Recipients", and the list "Open questions for counsel".

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/templates/guide.html` | edit | Step 1 |
| `App/app/guide_i18n.py` | edit | Step 2 |
| `App/app/routes/legal.py` | edit | Add `"ttlock"` to `SUBPROCESSOR_IDS`, last |
| `App/app/subprocessors_i18n.py` | edit | Step 3 |
| `docs/privacy/ROPA.md` | edit | Step 4 |
| `App/tests/test_door_codes_guide.py` | create | Step 5 |

No other file may change.

## 4. Steps

1. **Guide section**, after the settings section, `id="door-codes"`:
   ```
   <section class="guide-section panel" id="door-codes">
     <h2>{{ t('guide.nav.door_codes') }}</h2>
     <p>{{ t('guide.door_codes.lede') }}</p>
     <h3>{{ t('guide.door_codes.need_title') }}</h3>
     <ul>{% for n in range(1, 4) %}<li>{{ t('guide.door_codes.need' ~ n) }}</li>{% endfor %}</ul>
     <h3>{{ t('guide.door_codes.steps_title') }}</h3>
     <ol class="guide-steps">{% for n in range(1, 6) %}<li><strong>{{ t('guide.door_codes.step' ~ n ~ '_title') }}:</strong> {{ t('guide.door_codes.step' ~ n) }}</li>{% endfor %}</ol>
     <h3>{{ t('guide.door_codes.how_title') }}</h3>
     <ul>{% for n in range(1, 6) %}<li>{{ t('guide.door_codes.how' ~ n) }}</li>{% endfor %}</ul>
     <h3 id="door-codes-terms">{{ t('guide.door_codes.terms_title') }}</h3>
     <p class="small muted">{{ t('guide.door_codes.terms_version', version='2026-10-08') }}</p>
     <ol>{% for n in range(1, 9) %}<li>{{ t('guide.door_codes.terms' ~ n) }}</li>{% endfor %}</ol>
   </section>
   ```
2. **Guide strings** (EN, CS). Add `guide.nav.door_codes` and every key below.

   | Key | EN | CS |
   |---|---|---|
   | `guide.nav.door_codes` | Door codes with TTLock | Kódy ke dveřím s TTLock |
   | `guide.door_codes.lede` | Optional. If a property has a TTLock lock with a keypad and a gateway, UbyHost sends each guest a timed door code once everyone on the stay is registered. Properties you do not switch on are not affected. | Volitelné. Pokud má ubytování zámek TTLock s klávesnicí a bránou, UbyHost pošle každému hostovi časově omezený kód ke dveřím, jakmile jsou zaregistrováni všichni hosté pobytu. Ubytování, u kterých funkci nezapnete, se nic nemění. |
   | `guide.door_codes.need_title` | What you need | Co potřebujete |
   | `guide.door_codes.need1` | A TTLock lock with a keypad, added in the TTLock app. | Zámek TTLock s klávesnicí, přidaný v aplikaci TTLock. |
   | `guide.door_codes.need2` | A TTLock gateway near the lock, or a Wi-Fi lock. UbyHost needs it to change or delete codes. | Bránu TTLock poblíž zámku, nebo zámek s Wi-Fi. UbyHost ji potřebuje ke změně a mazání kódů. |
   | `guide.door_codes.need3` | The lock's clock on Prague time: in the TTLock app open the lock, then Settings, Lock Time, and calibrate it. | Hodiny zámku na pražském čase: v aplikaci TTLock otevřete zámek, pak Nastavení, Čas zámku, a čas zkalibrujte. |
   | `guide.door_codes.steps_title` | Set it up | Nastavení |
   | `guide.door_codes.step1_title` | Choose the account | Vyberte účet |
   | `guide.door_codes.step1` | Recommended: create a second TTLock account with a spare e-mail. In your own account open the lock, tap Send eKey, enter the second account, turn on Authorized admin, turn off Remote unlock, and leave the end date empty. UbyHost can then create codes but never open the door remotely. You can also use your own TTLock account, which gives UbyHost every right on all your locks. | Doporučeno: založte druhý účet TTLock s náhradním e-mailem. Ve svém účtu otevřete zámek, klepněte na Odeslat eKey, zadejte druhý účet, zapněte Autorizovaný správce, vypněte Vzdálené odemykání a datum konce nechte prázdné. UbyHost pak může vytvářet kódy, ale nikdy neotevře dveře na dálku. Můžete použít i svůj vlastní účet TTLock, UbyHost tím ale dostane všechna práva ke všem vašim zámkům. |
   | `guide.door_codes.step2_title` | Connect | Připojte |
   | `guide.door_codes.step2` | In UbyHost open Settings, Smart locks. Enter the account's e-mail or phone and password, accept the terms below, and tap Connect. Your locks appear with their name, ID and battery. The password is used once and is not stored. | V UbyHost otevřete Nastavení, Chytré zámky. Zadejte e-mail nebo telefon a heslo účtu, přijměte podmínky níže a klepněte na Připojit. Zobrazí se vaše zámky s názvem, ID a stavem baterie. Heslo se použije jednou a neukládá se. |
   | `guide.door_codes.step3_title` | Switch it on per property | Zapněte u ubytování |
   | `guide.door_codes.step3` | Open the property, section Door code. Tick Send guests a door code, pick the lock (its ID matches TTLock app, lock, Basic information) and set the check-in and check-out hour. | Otevřete ubytování, sekci Kód ke dveřím. Zaškrtněte Posílat hostům kód ke dveřím, vyberte zámek (jeho ID odpovídá aplikaci TTLock, zámek, Základní informace) a nastavte hodinu příjezdu a odjezdu. |
   | `guide.door_codes.step4_title` | Test it | Vyzkoušejte |
   | `guide.door_codes.step4` | Add a stay by hand for tomorrow, open the guest link yourself and register. The code shows on the stay page and arrives by e-mail. Try it on the keypad from 1 hour before check-in. | Přidejte ručně pobyt na zítřek, sami otevřete odkaz pro hosty a zaregistrujte se. Kód se zobrazí na stránce pobytu a přijde e-mailem. Vyzkoušejte ho na klávesnici od 1 hodiny před příjezdem. |
   | `guide.door_codes.step5_title` | Switch it off | Vypnutí |
   | `guide.door_codes.step5` | Untick the property, or remove the connection in Settings, Smart locks. In the TTLock app you can also delete the second account's eKey. | Zrušte zaškrtnutí u ubytování, nebo odeberte připojení v Nastavení, Chytré zámky. V aplikaci TTLock můžete také smazat eKey druhého účtu. |
   | `guide.door_codes.how_title` | How codes work | Jak kódy fungují |
   | `guide.door_codes.how1` | A code is created once every guest of the stay is registered. It works from 1 hour before check-in to 1 hour after check-out. | Kód vznikne, jakmile jsou zaregistrováni všichni hosté pobytu. Funguje od 1 hodiny před příjezdem do 1 hodiny po odjezdu. |
   | `guide.door_codes.how2` | The guest sees it on the stay page and gets it by e-mail. You get a copy. | Host ho uvidí na stránce pobytu a dostane ho e-mailem. Vy dostanete kopii. |
   | `guide.door_codes.how3` | The guest must type the code for the first time within 24 hours of its start, or TTLock invalidates it. For a late arrival, create a new code in the TTLock app. | Host musí kód poprvé zadat do 24 hodin od začátku jeho platnosti, jinak ho TTLock zneplatní. Při pozdním příjezdu vytvořte nový kód v aplikaci TTLock. |
   | `guide.door_codes.how4` | If the calendar moves the stay, the code moves with it and the guest gets a new e-mail. If the stay is cancelled, UbyHost deletes the code and tells you. A code nobody has typed yet may still work until its end date, so check the lock in the TTLock app. | Když kalendář pobyt posune, kód se posune s ním a host dostane nový e-mail. Když se pobyt zruší, UbyHost kód smaže a dá vám vědět. Kód, který ještě nikdo nezadal, může fungovat až do konce platnosti, proto zámek zkontrolujte v aplikaci TTLock. |
   | `guide.door_codes.how5` | Codes are created in TTLock's cloud, so they work even while the gateway is offline. Changing or deleting a code needs the gateway online. | Kódy vznikají v cloudu TTLock, takže fungují i ve chvíli, kdy je brána offline. Ke změně nebo smazání kódu musí být brána online. |
   | `guide.door_codes.terms_title` | Door code terms | Podmínky pro kódy ke dveřím |
   | `guide.door_codes.terms_version` | Version %(version)s | Verze %(version)s |
   | `guide.door_codes.terms1` | Door codes are optional and run on your own TTLock locks and account. You stay responsible for access to your property and for keeping another way in, such as a key or your own code. | Kódy ke dveřím jsou volitelné a běží na vašich vlastních zámcích a účtu TTLock. Za přístup do ubytování odpovídáte vy, včetně náhradní možnosti vstupu, například klíče nebo vlastního kódu. |
   | `guide.door_codes.terms2` | UbyHost sends a code only after every guest of the stay has registered. Anyone who knows the property's guest link and PIN can register for an upcoming stay, so keep the PIN private and change it from time to time. | UbyHost pošle kód až poté, co se zaregistrují všichni hosté pobytu. Kdokoli, kdo zná odkaz pro hosty a PIN ubytování, se může zaregistrovat k nadcházejícímu pobytu, proto PIN nikomu nesdělujte a čas od času ho změňte. |
   | `guide.door_codes.terms3` | The service depends on TTLock's cloud, your gateway and Wi-Fi, the lock's battery and clock, and e-mail delivery. UbyHost cannot guarantee that a code is created, delivered or accepted by the lock in time, and is not liable for lockouts, delays or entry by people who obtained a code, except where the law does not allow this limit. | Služba závisí na cloudu TTLock, vaší bráně a Wi-Fi, baterii a hodinách zámku a na doručení e-mailu. UbyHost nemůže zaručit, že kód vznikne, bude doručen nebo že ho zámek včas přijme, a neodpovídá za nemožnost vstupu, zpoždění ani za vstup osob, které kód získaly, s výjimkou případů, kdy zákon takové omezení nepřipouští. |
   | `guide.door_codes.terms4` | TTLock is a third-party service of Hangzhou Sciener Intelligent Control Technology Co., Ltd. (China) with its own terms and privacy policy. UbyHost sends TTLock the lock ID, the code's validity times and a code name. It sends no guest names or contact details. | TTLock je služba třetí strany společnosti Hangzhou Sciener Intelligent Control Technology Co., Ltd. (Čína) s vlastními podmínkami a zásadami ochrany soukromí. UbyHost posílá TTLock ID zámku, dobu platnosti kódu a název kódu. Neposílá jména ani kontakty hostů. |
   | `guide.door_codes.terms5` | UbyHost never stores your TTLock password. It keeps TTLock's access token encrypted and uses it only to create, change and delete codes and to read your lock list and lock clock. It never opens a door remotely. | UbyHost nikdy neukládá vaše heslo TTLock. Přístupový token TTLock uchovává šifrovaně a používá ho jen k vytváření, změně a mazání kódů a ke čtení seznamu zámků a jejich hodin. Nikdy neotevírá dveře na dálku. |
   | `guide.door_codes.terms6` | Door codes are stored encrypted and deleted one day after they expire. | Kódy ke dveřím se ukládají šifrovaně a mažou se den po skončení platnosti. |
   | `guide.door_codes.terms7` | UbyHost may pause door codes when TTLock's monthly call limit is nearly reached. | UbyHost může kódy ke dveřím pozastavit, když se blíží měsíční limit volání TTLock. |
   | `guide.door_codes.terms8` | You can switch door codes off at any time, per property or for your whole account. | Kódy ke dveřím můžete kdykoli vypnout, u jednotlivého ubytování nebo pro celý účet. |
3. **Subprocessor row** `ttlock` (EN, CS):

   | Key | EN | CS |
   |---|---|---|
   | `subprocessors.ttlock_provider` | Hangzhou Sciener Intelligent Control Technology Co., Ltd. (TTLock) | Hangzhou Sciener Intelligent Control Technology Co., Ltd. (TTLock) |
   | `subprocessors.ttlock_purpose` | Optional door codes: creating, changing and deleting timed passcodes on the host's TTLock locks. Only for properties where the host switched door codes on. | Volitelné kódy ke dveřím: vytváření, změna a mazání časově omezených kódů na zámcích TTLock hostitele. Jen u ubytování, kde hostitel kódy zapnul. |
   | `subprocessors.ttlock_data` | Lock ID, the code's validity times, the code and a code name. No guest names or contact details. | ID zámku, doba platnosti kódu, kód a název kódu. Žádná jména ani kontakty hostů. |
   | `subprocessors.ttlock_location` | EU API endpoint (euapi.ttlock.com); company based in China. | Rozhraní API v EU (euapi.ttlock.com); společnost se sídlem v Číně. |
   | `subprocessors.ttlock_safeguard` | TTLock privacy policy and developer terms. Transfer safeguard under review by counsel. | Zásady ochrany soukromí a vývojářské podmínky TTLock. Záruky pro předání posuzuje právník. |
4. **ROPA** (`docs/privacy/ROPA.md`, section A):
   - "Categories of personal data": append `; when the host uses door codes, the door code and its validity times (encrypted, deleted a day after expiry)`.
   - "Recipients": append `; TTLock (Hangzhou Sciener Intelligent Control Technology Co., Ltd.) for properties with door codes on: lock ID, code validity times, code name`.
   - "Open questions for counsel": add one item: `TTLock (Sciener, China): is it UbyHost's subprocessor or the host's own service (the host holds the TTLock account)? Transfer basis for data sent to euapi.ttlock.com. Review of the door-code terms in the Guide (version 2026-10-08) and of the guest privacy notice wording for door codes.`
5. **Tests** (`App/tests/test_door_codes_guide.py`):
   - `test_guide_has_the_door_code_section_and_terms_anchor` (EN and CS: `id="door-codes"` and `id="door-codes-terms"` present, terms text 1 present).
   - `test_terms_version_matches_the_client` (the version shown on the page equals `ttlock.DOOR_CODE_TERMS_VERSION`).
   - `test_register_lists_ttlock` (`/subprocessors?lang=en` and `cs` contain the TTLock provider name).

## 5. Do not touch

Everything outside §3. The Terms of Service, DPA and privacy policy texts (versioned legal documents; changes go through the lawyer, see `docs/context/status.md`).

## 6. Commands

From `App/`: `.venv/bin/python -m pytest tests -q` (all pass, including `tests/test_legal_contents.py`, `tests/test_no_em_dashes.py`, `tests/test_host_i18n.py`). From the repo root: `python3 scripts/context_lint.py` (last line `context lint: OK`).

## 7. Acceptance

- [ ] The 3 tests in step 5 pass; the full suite passes.
- [ ] Screenshots of the guide section at 390 and 1280 px in `docs/tasks/0016-shots/`.
- [ ] `git diff --stat` shows only the files in §3 plus the screenshots.

## 8. Stop and ask

Stop, and write the report, if:

- a test requires a legal document version bump when the subprocessor register changes (the owner and the lawyer decide that);
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

- `App/app/guide_i18n.py` (terms wording, both languages)
- `App/app/subprocessors_i18n.py`

## Owner steps

1. Send the lawyer the door-code terms (Guide, "Door code terms"), the subprocessor row and the ROPA question. Ask for the transfer safeguard line and any wording change.
2. Do not set `UBYHOST_DOOR_CODES_LIVE=1` before the lawyer has answered.
