# WP26: Guest pages in German, Spanish and French

Commit `6976059` on branch `wp26`, based on `golive` (ae9a430). It is one commit and does not depend on any other round-3 WP. Patch: `round3/WP26-guest-languages.patch`.

## Summary
- Guest pages now come in five languages: en, cs, de, es, fr. The host app stays EN/CS (`host_i18n.LANGUAGES` is unchanged).
- The guest's language is picked in this order:
  1. What the guest chose: `?lang=` or the existing `ubyhost_guest_lang` cookie.
  2. The best match in the browser's `Accept-Language` header. Q-values count, and `q=0` is skipped. `de-AT` gives de, `es-MX` gives es, `fr-CA` gives fr, and `cs` or `sk` gives cs.
  3. English.
- Only the header is read. There is no IP lookup, no outside service, no new cookie and no new stored field.
- Guest e-mails (claim, claim_resend, reminder_guest, completion) use the language of the request that triggers the claim. That language is saved in the column that already existed, `reservation_claim.lang`. The reminder and the receipt already read it from there.
- These were also translated: country names (bundled table), purposes of stay, the guest validation sentences, passport-upload errors, the cookie table on the guest privacy page, ticket dates (months and weekdays), the date-of-birth placeholders, and the 404 and 500 pages under `/l/`.

## Files changed
- `App/app/i18n.py`: five-language catalog (de/es/fr have all 325 keys). New `supported_language`, `normalise_language`, `accept_language_match` and `ENDONYMS`. New keys `server_error_title` and `server_error_help` in all five languages.
- `App/app/routes/guest.py`: language order as above. `_mail_language` now equals the page language. `PASSPORT_UPLOAD_MESSAGES` per language. `_GUEST_ISSUE_MESSAGES` per language. New `error_page()`.
- `App/app/main.py`: a 404/405 or 500 under `/l/` now shows the guest page in the guest's language.
- `App/app/validation_i18n.py`: `GUEST_MESSAGES` for de/es/fr (guest sentences only).
- `App/app/validation.py`: `PURPOSE_LABELS` for de/es/fr. `country_name` and `purpose_label` read them.
- `App/app/codelists.py`: country and purpose options for de/es/fr. The police code list is used only when it is cached, with the name taken from the bundled table by country code.
- `App/app/data/countries.json`: de/es/fr names for all 254 codes. They come from CLDR through `babel`, which was used once offline and is not a runtime dependency. The XX* police codes were translated by hand.
- `App/app/cookie_inventory.py`: de/es/fr purpose and lifetime for every row.
- `App/app/templating.py`: ticket month and weekday names for de/es/fr. New global `guest_endonyms`.
- `App/app/templates/guest/base.html`: the switcher is now a no-JS `<details>` menu (see Deviations). Cache keys bumped.
- `App/app/templates/guest/form.html`: the date-of-birth boxes get their placeholders from `date_placeholder`.
- `App/app/templates/_cookie_table.html`: falls back to `en` if a language is missing.
- `App/app/templates/guest_form_admin.html`: signature.js cache key bumped.
- `App/app/static/guest-ticket.css`: language menu styles. The app-bar band is now painted by a pseudo-element. Step strip is slightly tighter at 340px and below.
- `App/app/static/guest.css`: card layout for the cookie table on the guest privacy page.
- `App/app/static/signature.js`: the date read-back uses the de/es/fr locales.
- `App/app/static/ticket.js`: the date-of-birth box placeholders come from `data-tw-format`.
- `App/tests/test_guest_languages.py`: new test file.
- `App/tests/test_guest_language.py`, `test_host_i18n.py`: updated for the new order.
- `App/tests/test_ticket_wallet_v3.py`: updated for the new cache keys.
- `App/tests/test_guest_browser_e2e.py`: now also runs de/es/fr at 320/360/390 and checks the privacy page.
- `AGENTS.md`, `docs/DESIGN.md`: the e2e description now lists the new languages and widths.

## Tests added
`tests/test_guest_languages.py` has 42 tests:
- Key parity: same keys, non-empty, same placeholders in all five languages.
- Every key used in a guest template exists.
- Legal-notice, why and privacy keys are non-empty in all five.
- Legal facts survive translation in de/es/fr: 326/1999, §101, DSGVO/RGPD, six years.
- 17 Accept-Language cases: q-values, `q=0`, a garbled q, `*`, empty, no match.
- Order: explicit choice > header > English. A link beats the cookie. An unsupported choice counts as no choice.
- The switcher lists all five languages, reuses the guest cookie and adds no new cookie.
- Pick and privacy pages render in de/es/fr.
- The guest 404 and 500 pages render in the guest's language.
- The claim POST with `Accept-Language: de-AT` gives a German subject, `reservation_claim.lang = de` and payload `lang = de`.
- The reminder and receipt are built in the stored language.
- Country names, the full country list, purposes, validation sentences, passport-upload errors and the child note in de/es/fr.
- The cookie table and ticket dates cover all five languages.
- Host pages stay EN/CS, even with `?lang=de` and a German header.

The browser e2e now has 13 runs: en at 320/375/1280, de/es/fr at 320/360/390, and Czech. Each run also checks the guest privacy page.

## Test commands and results
All commands were run from `App/` with `LD_LIBRARY_PATH=/tmp/libs/root/usr/lib/aarch64-linux-gnu`.
- `pytest tests/test_guest_languages.py`: 42 passed.
- `pytest tests/test_[a-f]*.py`: 676 passed, 2 skipped.
- `pytest tests/test_[g-l]*.py` (without browser_e2e): 618 passed.
- `pytest tests/test_[m-r]*.py`: 540 passed, 1 failed. The failure is `test_mail_failed_alert.py::test_the_send_loop_stores_the_code_and_renders_a_name` ("no such table: email_outbox"). It fails the same way on unchanged `golive`, because it depends on test order.
- `pytest tests/test_[s-z]*.py`: 581 passed.
- `UBYHOST_REQUIRE_BROWSER=1 pytest tests/test_guest_browser_e2e.py -rs`: 14 passed, 0 skipped, in three chunks of 6, 4 and 3+1.
- `UBYHOST_REQUIRE_BROWSER=1 pytest tests/test_host_geometry.py`: 2 passed.
- `ruff check app tests tools --select E9,F63,F7,F82,F401,F841`: all checks passed.
- Screenshots are in `round3/shots/wp26-*.png`: menu, pick, form, privacy cookies.

## Deviations from the spec and why
- **No header at all, or `*`, now gives English. It used to give Czech.** This follows the owner's order (… > English). An unsupported `?lang=xx` or cookie now falls through to the header; before, it fell back to Czech. The old tests that pinned Czech were updated.
- **The switcher is now a `<details>` menu.** Five 44px pills left about 60px for the property name on a 320px phone; it showed as "B.". The bar now shows the current code ("DE ▾") and the menu lists the language names. The links, `?lang=` and the cookie work exactly as before, and no JS was added. To let the menu hang below the sticky bar, the band's shadow and clip-path moved to `.g-head::before`.
- **Two step-strip labels were shortened** so they fit at 320px: de "Signatur" (was "Unterschrift") and fr "Contrôle". At 340px and below the strip also uses 10.5px text with tighter spacing.
- **The cookie table on the guest privacy page made a 320px page scroll sideways in every language, English included.** This bug was already there; adding the privacy page to the e2e exposed it. Fixed in guest.css.
- **Translations were produced with a model,** not by a professional translator. See the review list below.
- **Guest invoice mail is unchanged.** It keeps the invoice's own language, because `invoice.lang` has a CHECK constraint limiting it to cs/en. The host `error.html` stays EN/CS for non-guest paths.

## What Cursor must verify or adapt when applying on the real main
- Re-run the key-parity test after rebasing. Any guest key added on main since `golive` needs de/es/fr text, or the parity test fails.
- If main changed `guest/base.html` or the `.tw .g-head` CSS, merge carefully. The band now lives on `::before`.
- Cache keys: guest.css, guest-ticket.css, ticket.js and signature.js now use `?v=20261004b`. Bump them again if main has newer keys.
- If main added more `lang == "cs"` branches on guest paths, route them through the per-language tables.
- `countries.json` was regenerated with the same layout (one key per line). If main edited it, regenerate de/es/fr instead of merging line by line.
- Not covered by the e2e: the form with the passport-photo step, which has six strip segments. Labels like "Documento" or "Bydliště" may end in an ellipsis there, in Czech as well.

## Manual steps for the owner
Have a native speaker review these strings, in this order:
1. **Legal notice:** `legal_notice_*`, `why_*`, `legal_ack_label`, `notice_version`.
2. **Guest privacy notice:** `privacy_*`, especially controller/processor, legal basis, recipients, retention and rights. Terms used: de "Verantwortlicher"/"Auftragsverarbeiter", es "responsable/encargado del tratamiento", fr "responsable du traitement"/"sous-traitant".
3. **The "house book" term:** de "Hausbuch (domovní kniha)" (not an established German legal term), es "libro de registro", fr "registre d'hébergement".
4. **The word for "claim" a reservation by e-mail:** de "beanspruchen/Zuordnung", es "reclamar", fr "revendiquer". The es and fr words read stiffly; "vincular"/"rattacher" may be better.
5. **E-mail subjects and bodies:** `mail_*`. In French, "à votre hébergement" reads oddly when the property-name fallback is used.
6. **Gendered forms:** es "Bienvenido/a", fr masculine default ("enregistré").
7. **Purpose labels and Cloudflare cookie descriptions.**
8. **Some CLDR country names are long or formal,** for example "Sonderverwaltungsregion Hongkong".

Also decide whether a guest with no Accept-Language header should get English (as built now) or Czech.
