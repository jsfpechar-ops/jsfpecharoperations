# WP17: Copy cleanup on guest and host pages

## Summary

Applies review 3.E: 17 guest items and 16 host items, in EN and CS. Strings are cut, shortened or merged so each explanation appears once, and no line repeats a button label. Everything on the Keep list is unchanged: PIN recovery line, party-size help, document, child and visa help, guest signature line, review lock line, cookie notice, the full legal notice retention, refusal, accuracy and passport sections, the acknowledgement checkbox, and the GDPR Art. 13 privacy page. The two copy rules are now in `AGENTS.md`. Branch `wp17`, one commit on top of `wpbase`, not stacked on any other WP.

What changes on screen:

- Guest `pick.html`: the welcome line and the "choose your dates" line are gone. The "why" fold now has a one-line legal intro, the accuracy point, the statute line and the privacy link. The six other bullets are gone.
- Guest footer, host contact card, PIN screen, claim card, photo step, residence step and "forgot someone" line are all shorter.
- Guest confirm screen: just the title and the "Yes, this is my stay" button.
- Guest assigned screen: two help lines (body plus "We send your private link here. No marketing."). The full e-mail and cookie text sits in the same "What we use your e-mail for" fold the claim page uses.
- Guest done screen: the "Keep this page" line is gone, because "You can close this page" is shown just above it.
- Guest legal notice: intro line cut. The duty and reporting sections are shorter. By owner (legal) decision the reporting section still says, in one sentence, that the host reports foreign guests to the Foreign Police within three working days of arrival, straight away or a little later. Retention, refusal, accuracy, passport and the acknowledgement are untouched.
- Host house book: the first-visit modal that repeated the legal block, and its localStorage script, are removed. The collapsible legal panel stays, and its paper and footnote lines are shorter.
- Host property form: the UbyPort "Where each field comes from" table is gone. Each field keeps one hint, and the mark and contact hints now include the facts the table added. The guest-link section uses the single `guest_links.lede` line. The message lede now shows only on the Guest links page. The page lede for new properties is cut, and the calendars lede is shorter.
- Host page ledes cut on Properties, Stays and Automation.
- Onboarding: welcome lede and the "Nothing goes live by accident" box removed. The finish lede is shorter.
- Milestone celebration: the open `<dialog>` is replaced by a sticky toast in the existing toast stack. It has the same dismiss form, `/celebrations/dismiss`.
- The retention-purge sentence now appears only on the Archive page. It is removed from the Settings archive panel and the audit help.
- Signature hint: the statute numbers are dropped.

## Files changed

- `AGENTS.md`: new "Writing UI copy" section with the two rules.
- `App/app/i18n.py`: 27 guest keys changed or deleted per language.
- `App/app/host_i18n.py`: 40 host keys changed or deleted per language.
- `App/app/host_design_i18n.py`: deleted the `apartments.lede` override.
- `App/app/static/app.css`: removed the celebration dialog, onboarding safety box and house-book dialog rules.
- `App/app/templates/base.html`, `auth_base.html`, `public_legal_base.html`: celebration toast, and the `app.css?v=` cache key bumped to 20261003a.
- `App/app/templates/_components.html`: onboarding lede, safety box and finish lede.
- `App/app/templates/apartment_form.html`: UbyPort map table removed, single guest-link line, message lede removed, new-property lede removed.
- `App/app/templates/apartments.html`, `reservations.html`, `automation.html`: page ledes removed.
- `App/app/templates/housebook.html`: duplicate legal dialog and its script removed.
- `App/app/templates/guest/pick.html`, `_why.html`, `confirm.html`, `assigned.html`, `stay.html`, `_legal_notice.html`: cut lines.
- `App/tests/test_copy_cleanup.py`: new.
- `docs/TECHNICAL_COMPLIANCE_AUDIT.md`: four rows no longer cite deleted `why_point_*` keys; they cite `legal_notice_duty_body`, `legal_notice_reporting_body`, `signature_help` and `passport_photo_help`, which now carry those statements.
- Existing tests updated to the new text: `test_claim_copy.py`, `test_claim_mail.py`, `test_guest_assigned_actions.py`, `test_guest_confirm_screen.py`, `test_guest_host_noun.py`, `test_guest_language.py`, `test_guest_navigation.py`, `test_guest_residence_prefill.py`, `test_guest_why_passport.py`, `test_host_i18n.py`, `test_onboarding.py`, `test_overhaul.py`, `test_ticket_wallet_v2.py`, `test_ubyport_sample_pdf.py`.

## Tests added

`tests/test_copy_cleanup.py` (9 tests):

- Every deleted key is gone from both languages, and no template still calls it.
- The legal Keep list is present in EN and CS, and the legal notice still renders retention, refusal and the acknowledgement.
- The house-book legal block renders once, and the first-visit dialog is gone.
- The calendars lede, guest-link line and message lede each render once.
- Only `archive.retention_note` still carries the "permanently delete" sentence.
- The signature hint has no statute numbers in EN or CS.
- The reporting section still states the three-working-day deadline and the "straight away or a little later" timing in EN and CS, and the notice template renders it.
- The milestone renders as a toast, not a dialog. This is a real dashboard render with 10 sent guests: the text is right and the dismiss form posts to `/celebrations/dismiss`.

Updated tests now pin the new exact strings in both languages, or assert that cut lines are absent. The existing promise checks were kept as strict as before. `test_claim_copy` still requires every DESIGN.md e-mail disclosure point. It now counts the four lines actually rendered, and its word budget is tighter: 55/50, down from 65/55.

## Test commands and results (exact counts)

Run from `/tmp/wp/wp17/App` with `/tmp/pr230/App/.venv/bin/python -m pytest -q -p no:warnings`:

- `tests/test_[a-c]*.py`: 292 passed, 2 skipped
- `tests/test_[d-g]*.py`: 615 passed, 4 skipped. The 4 skips are `test_guest_browser_e2e.py`: Chromium cannot start in this sandbox (exit 127).
- `tests/test_[h-l]*.py`: 268 passed, 1 skipped, 1 failed. The failure is `test_host_geometry.py::test_the_month_filter_shares_its_page_edges`, a Playwright browser crash. It fails the same way on `wpbase`.
- `tests/test_[m-p]*.py`: 428 passed, 1 failed. The failure is `test_mail_failed_alert.py::test_the_send_loop_stores_the_code_and_renders_a_name`, with "no such table: email_outbox". It is order-dependent and fails the same way on `wpbase`.
- `tests/test_[q-s]*.py`: 415 passed, 1 failed. The failure is `test_stale_submission.py::test_a_running_batch_without_a_live_claim_becomes_outcome_unknown`. It fails the same way in this chunk on `wpbase` and passes alone (1 passed).
- `tests/test_[t-z]*.py`: 153 passed
- `tests/test_copy_cleanup.py`: 9 passed
- After the owner amendment (deadline sentence, audit doc): every test file that mentions `i18n` or `legal_notice` (97 files) run together: 1273 passed. Focused rerun of `test_copy_cleanup`, `test_guest_navigation`, `test_guest_why_passport`, `test_guest_language`, `test_host_i18n`: 64 passed. The chunk counts above are from before the amendment.
- Lint: `ruff check app tests tools --select E9,F63,F7,F82,F401,F841`: all checks passed.

## Deviations from the spec and why

- **Guest item 9 (`claim_email_help`, "Cut"):** shortened instead of cut. `docs/DESIGN.md` line 326 requires that, at collection, the guest is told about the single reminder, the receipt with host copy, and masking. Only the repeated parts were removed: the private link and "no marketing", which `tw_email_short` already says one line above. The line stays inside the closed "What we use your e-mail for" fold.
- **Guest item 11 (assigned, "four lines to two"):** `assigned_private_link` and `assigned_resend_help` were deleted, and the resend instruction was merged into `assigned_body`. The e-mail and cookie hints were kept but moved into the same fold the claim page uses, so the cookie notice (Keep list) still shows. The visible help is now the body plus `tw_email_short`.
- **Guest item 4 (`_why`):** the accuracy point is kept unchanged. The passport bullet's facts (only the host sees it, deleted after the check) still appear in the legal notice passport section on the form, which shows only when the property requires a photo. `test_guest_why_passport.py` now checks it there.
- **Guest item 7 vs the Keep list ("PIN help"):** item 7 shortens `pin_help`. I read "Keep: the PIN help" as `pin_recovery` ("Can't find the PIN? ..."), which is unchanged.
- **Host item 4:** the spec says the calendars lede is rendered twice. In the code, the second mention (`apartment_form.html:28`) is an unused hint value in a loop tuple and was never printed. I removed it from the tuple and shortened the one real render.
- **Host item 3:** "one line, only once" is done by deleting `apartment.form.guest_link.lede`. The property form now reuses the one-line `guest_links.lede`, so the same short line is used on both pages.
- **Host item 1:** the duplicate kept is the collapsible panel. The auto-opening first-visit modal and its localStorage key were removed. The keys `housebook.legal_intro_title`, `_ack` and `_skip` are deleted.
- **Host item 6:** `dashboard.minutes_saved` was used only by two generic i18n tests. Those tests now use `archive.chip.all_count`. `celebrations.minutes_saved()` and the `minutes_saved` template context are still there, because `test_celebrations.py` covers them. They are dead in templates and can go later.
- **Host item 11:** the toast message drops the separate title (`celebration.title` deleted). The dismiss label "Thanks!" / "Díky!" is unchanged.
- **Host item 16:** `host.verify_in_person` had no statute numbers in either language, so it is unchanged. Only `host.signature_help` changed. It now opens with "Required by law." / "Vyžaduje to zákon."
- **Host item 9:** the note kept is the one on the Archive page (`archive.retention_note`). The other two strings were trimmed, not deleted.
- **Host item 7:** 9 keys deleted (the map table and its labels). Only `mark_hint` and `contact_hint` were rewritten. The other field hints already covered what the table said.
- **Host item 10:** `onboarding.welcome_lede`, `safe_title` and `safe_body` are deleted. `finish_lede` is shortened and no longer takes `%(property)s`, which avoids Czech gender agreement problems with property names.
- `.tw-keep` in `guest-ticket.css` is now an unused selector. I left it so the guest CSS cache key, which `test_ticket_wallet_v3.py` pins, did not have to change.

## What Cursor must verify or adapt when applying on the real main

- Find the keys by name, not by line number. The patch rewrites some multi-line string values as single-line literals. If main has edited any of these keys since PR 230, re-apply the new text by hand.
- Run `pytest tests/test_guest_browser_e2e.py -q -rs` where Chromium works. It must report 0 skipped. Guest pages lost lines in pick, claim, assigned, confirm and stay. Also check the done screen and the arrival hero, which now has only a heading and an optional city.
- Check that the dashboard milestone toast looks right next to other toasts (`.toast-undo` button styling), and that dismissing it posts and does not show again.
- If main has new tests that assert any deleted or changed string, update them to the table below.
- `docs/TECHNICAL_COMPLIANCE_AUDIT.md` is updated to the keys that now carry the deleted `why_point_*` statements. If main has edited those rows, re-point them by hand. `docs/plans/UX_AUDIT.md` and `PLAN_TICKET_WALLET_V2.md` still name deleted keys; they are historical records and were not edited.

## Manual steps for the owner

- Review the Czech text in the table below, mainly the guest legal notice lines (`legal_notice_duty_body`, `legal_notice_reporting_body`), `legal_intro`, the footer `privacy` line and `housebook.legal_footnote`.
- Have the lawyer re-read the shortened guest legal notice. The duty section no longer states the deadline; the reporting section now carries it in one sentence ("within three working days of arrival, straight away or a little later" / "do tří pracovních dnů od příjezdu, hned, nebo o něco později"). The "why" fold no longer lists Czech-citizen handling, signing by under-15s or "not used for marketing". "No marketing" still appears on the claim screen.

## Before/after table of every changed string

`(deleted)` means the key was removed. These are the effective strings after all catalogue merges.

### Guest strings (`i18n.py`), 27 keys

| Key | Lang | Before | After |
|---|---|---|---|
| `arrival_help` | EN | Choose your arrival and departure dates to continue. | (deleted) |
| `arrival_help` | CS | Vyberte termín příjezdu a odjezdu a pokračujte. | (deleted) |
| `arrival_welcome` | EN | Welcome — guest registration for %(facility)s. | (deleted) |
| `arrival_welcome` | CS | Vítejte — registrace ubytovaného pro %(facility)s. | (deleted) |
| `assigned_body` | EN | This stay is already linked to the e-mail below. If that's you, we can send the private link again. | This stay is already linked to the e-mail below. If that's you, enter it and we'll send the private link again. |
| `assigned_body` | CS | Tento pobyt je už propojený s e-mailem níže. Pokud jste to vy, pošleme vám soukromý odkaz znovu. | Tento pobyt je už propojený s e-mailem níže. Pokud jste to vy, zadejte ho a soukromý odkaz pošleme znovu. |
| `assigned_private_link` | EN | For your privacy, registration continues through the secure link sent to this address. | (deleted) |
| `assigned_private_link` | CS | Kvůli ochraně soukromí pokračuje registrace přes zabezpečený odkaz zaslaný na tuto adresu. | (deleted) |
| `assigned_resend_help` | EN | Enter the same e-mail to receive the link again. | (deleted) |
| `assigned_resend_help` | CS | Zadejte stejný e-mail a odkaz pošleme znovu. | (deleted) |
| `claim_confirm_help` | EN | One tap to confirm it’s really you. | (deleted) |
| `claim_confirm_help` | CS | Jedním klepnutím potvrďte, že jste to opravdu vy. | (deleted) |
| `claim_email_help` | EN | We send the link here, one reminder the day before arrival if forms are missing, and a receipt (your host gets a copy). Elsewhere it is shown masked. No marketing. | Also one reminder the day before arrival if forms are missing, and a receipt (your host gets a copy). Shown masked elsewhere. |
| `claim_email_help` | CS | Pošleme sem odkaz, jedno připomenutí den před příjezdem, pokud formuláře chybí, a potvrzení (kopii dostane i hostitel). Jinde se adresa zobrazuje zakrytě. Žádný marketing. | Dále jedno připomenutí den před příjezdem, pokud formuláře chybí, a potvrzení (kopii dostane i hostitel). Jinde se adresa zobrazuje zakrytě. |
| `claim_help` | EN | We'll e-mail you a private link so only your group can open the forms. | Only your group can open the forms. |
| `claim_help` | CS | Pošleme vám soukromý odkaz, aby formuláře otevřela jen vaše skupina. | Formuláře otevře jen vaše skupina. |
| `host_details_help` | EN | If there is any problem, feel free to contact your host. UbyHost does not run the property and cannot change your booking. | Questions? Contact your host. |
| `host_details_help` | CS | Pokud máte jakýkoli problém, neváhejte kontaktovat svého hostitele. UbyHost objekt neprovozuje a rezervaci nemůže měnit. | Máte dotaz? Kontaktujte hostitele. |
| `legal_intro` | EN | Czech law treats every rented apartment as an accommodation facility. Your host must write each guest into a house book and report every foreign guest to the Foreign Police within three working days of arrival. This form is how that is done — one form per person, including children. | Czech law requires your host to register every guest, including children, and report foreign guests to the police. |
| `legal_intro` | CS | Podle českého práva je pronajímaný apartmán ubytovacím zařízením. Ubytovatel musí každého hosta zapsat do domovní knihy a každého ubytovaného cizince oznámit cizinecké policii do 3 pracovních dnů od ubytování. K tomu slouží tento formulář — jeden za každou osobu včetně dětí. | Podle zákona musí ubytovatel zaregistrovat každého hosta včetně dětí a cizince ohlásit policii. |
| `legal_notice_disclaimer` | EN | UbyHost is a software tool and this information does not replace legal advice. | (deleted) |
| `legal_notice_disclaimer` | CS | UbyHost je softwarový nástroj a tyto informace nenahrazují právní poradenství. | (deleted) |
| `legal_notice_duty_body` | EN | Everyone staying must be registered. Foreign guests are reported to the Foreign Police within three working days; Czech citizens only go into the house book. This is required by law. | Everyone staying must be registered. Foreign guests are reported to the Foreign Police; Czech citizens only go into the house book. |
| `legal_notice_duty_body` | CS | Registrovat se musí každý ubytovaný. Cizince ubytovatel do tří pracovních dnů ohlásí cizinecké policii, občany ČR jen zapíše do domovní knihy. Vyžaduje to zákon. | Registrovat se musí každý ubytovaný. Cizince ubytovatel ohlásí cizinecké policii, občany ČR jen zapíše do domovní knihy. |
| `legal_notice_intro` | EN | Please read this before you send. | (deleted) |
| `legal_notice_intro` | CS | Před odesláním si to prosím přečtěte. | (deleted) |
| `legal_notice_reporting_body` | EN | Complete records of foreign guests may be sent to the Czech Police automatically — straight away or after a delay your host chooses. The same details stay in the house book for six years. | Your host reports the details of foreign guests to the Foreign Police within three working days of arrival, straight away or a little later. Complete records may be sent automatically. The same details stay in the house book for six years. |
| `legal_notice_reporting_body` | CS | Kompletní záznamy cizinců se mohou Policii ČR odeslat automaticky — hned, nebo s odkladem, který nastaví ubytovatel. Stejné údaje zůstávají šest let v domovní knize. | Ubytovatel údaje cizinců ohlásí cizinecké policii do tří pracovních dnů od příjezdu, hned, nebo o něco později. Kompletní záznamy se mohou odeslat automaticky. Stejné údaje zůstávají šest let v domovní knize. |
| `passport_photo_help` | EN | Your host must check your details against your document. Take a photo of the page with your photo, or upload a PDF. Only your host can see it, and it is deleted after they check it. | Take a photo of the page with your photo, or upload a PDF. Only your host can see it, and it is deleted after they check it. |
| `passport_photo_help` | CS | Hostitel musí vaše údaje porovnat s dokladem. Vyfoťte stránku s fotografií, nebo nahrajte PDF. Uvidí ji jen hostitel a po kontrole se smaže. | Vyfoťte stránku s fotografií, nebo nahrajte PDF. Uvidí ji jen hostitel a po kontrole se smaže. |
| `pin_help` | EN | Your host sent a PIN together with the registration link. Enter it to open the form. | The PIN is in your host's message. |
| `pin_help` | CS | Hostitel vám spolu s odkazem poslal PIN. Zadejte ho pro otevření formuláře. | PIN najdete ve zprávě od hostitele. |
| `privacy` | EN | Your details are used only to meet the host's legal reporting duty towards the Police of the Czech Republic and are kept for the statutory six years. | Used only for your host's legal reporting to the Czech Police, and kept for six years. |
| `privacy` | CS | Údaje slouží výhradně ke splnění zákonné oznamovací povinnosti ubytovatele vůči Policii České republiky a uchovávají se zákonných 6 let. | Údaje slouží jen k zákonnému hlášení ubytovatele Policii ČR a uchovávají se 6 let. |
| `residence_help` | EN | Your permanent home address, as in your passport or ID card. Required by law. | Your permanent home address, as in your passport or ID card. |
| `residence_help` | CS | Adresa trvalého bydliště podle pasu nebo občanského průkazu. Vyžaduje ji zákon. | Adresa trvalého bydliště podle pasu nebo občanského průkazu. |
| `someone_missing` | EN | Forgot someone? Everyone staying must be registered, including children. | Forgot someone? Children must be registered too. |
| `someone_missing` | CS | Zapomněli jste na někoho? Registrovat se musí každý ubytovaný, včetně dětí. | Zapomněli jste na někoho? Registrují se i děti. |
| `tw_done_keep` | EN | Keep this page — it is your confirmation. | (deleted) |
| `tw_done_keep` | CS | Tuto stránku si nechte — je to vaše potvrzení. | (deleted) |
| `why_more` | EN | What happens with what you enter | (deleted) |
| `why_more` | CS | Co se s údaji stane | (deleted) |
| `why_point_book` | EN | The same details go into the house book (domovní kniha), which the host must keep for six years and produce at a police inspection. | (deleted) |
| `why_point_book` | CS | Stejné údaje se zapisují do domovní knihy, kterou hostitel uchovává 6 let a předkládá při kontrole policie. | (deleted) |
| `why_point_czech` | EN | Czech citizens are not reported to the police — only the house-book entry is made. | (deleted) |
| `why_point_czech` | CS | Občané ČR se policii neoznamují — provede se pouze zápis do domovní knihy. | (deleted) |
| `why_point_nothing_else` | EN | Nothing here is used for marketing, and none of it goes back to the booking site you booked through. | (deleted) |
| `why_point_nothing_else` | CS | Údaje se nepoužívají k marketingu a nevracejí se rezervačnímu portálu, přes který jste rezervovali. | (deleted) |
| `why_point_passport` | EN | If your host requires it, foreign guests upload a photo of their passport or ID page so the host can check the details. Only your host sees it, and it is deleted after the check. | (deleted) |
| `why_point_passport` | CS | Pokud to hostitel vyžaduje, cizinci nahrají fotku stránky pasu nebo průkazu, aby mohl údaje zkontrolovat. Vidí ji jen hostitel a po kontrole se smaže. | (deleted) |
| `why_point_report` | EN | Foreign nationals are reported electronically to the Police of the Czech Republic, Directorate of the Alien Police Service. | (deleted) |
| `why_point_report` | CS | Cizinci se elektronicky oznamují Policii České republiky, Ředitelství služby cizinecké policie. | (deleted) |
| `why_point_sign` | EN | Completing and signing the form is required for adult foreign guests. Children under 15 do not have to fill and sign personally — a parent or guardian completes the record. | (deleted) |
| `why_point_sign` | CS | Vyplnit a podepsat formulář musí dospělý cizinec. Děti mladší 15 let formulář osobně vyplňovat a podepisovat nemusí — záznam doplní rodič nebo opatrovník. | (deleted) |

### Host strings (`host_i18n.py`), 40 keys

| Key | Lang | Before | After |
|---|---|---|---|
| `apartment.form.calendars.lede` | EN | Airbnb and Booking.com iCal feeds give dates only — no name, no e-mail, no headcount. That is enough to know somebody is arriving, which is all the app needs to start chasing the data. | iCal feeds give dates only, which is enough to start collecting guest details. |
| `apartment.form.calendars.lede` | CS | iCal z Airbnb a Booking.com dává jen termíny — bez jména, e-mailu a počtu osob. To stačí vědět, že někdo přijede, a aplikace může začít shánět údaje. | iCal dává jen termíny, a to stačí k zahájení sběru údajů hostů. |
| `apartment.form.guest_link.lede` | EN | There is exactly one link per apartment. The same string goes into every automated arrival message — Airbnb, Booking.com, direct bookings — because the guest picks their own dates when they open it. It never changes, so you set it up once and never touch it again. | (deleted) |
| `apartment.form.guest_link.lede` | CS | Na ubytování je právě jeden odkaz. Stejný text vložíte do každé automatické zprávy o příjezdu — Airbnb, Booking.com, přímé rezervace — host si po otevření zvolí vlastní termín. Nikdy se nemění, nastavíte jednou. | (deleted) |
| `apartment.form.guest_message.hint` | EN | Shown on this property’s guest registration form. Use it for a welcome note or important property-specific guidance; do not include access codes or other secrets. | Shown on the guest form. Do not include access codes or other secrets. |
| `apartment.form.guest_message.hint` | CS | Zobrazí se v registračním formuláři hostů pro toto ubytování. Použijte ji jako uvítání nebo důležitou informaci k objektu; nevkládejte přístupové kódy ani jiná tajná data. | Zobrazí se ve formuláři hostů. Nevkládejte přístupové kódy ani jiná tajná data. |
| `apartment.form.internal_name.hint` | EN | Shown to guests at the top of the registration form. Use the name you list this property under on Airbnb, Booking.com or wherever guests book — it is usually the name a guest recognises. | Shown to guests. Use the name they know from Airbnb, Booking.com or wherever they booked. |
| `apartment.form.internal_name.hint` | CS | Zobrazí se hostům v záhlaví registračního formuláře. Použijte název, pod kterým ubytování inzerujete na Airbnb, Booking.com nebo jinde — hosté ho podle něj poznají. | Vidí ho hosté. Použijte název, který znají z Airbnb, Booking.com nebo odjinud, kde rezervovali. |
| `apartment.form.lede` | EN | Complete the sections below so guest registration and UbyPort reporting work reliably. | (deleted) |
| `apartment.form.lede` | CS | Vyplňte sekce níže, aby registrace hostů a hlášení do UbyPortu fungovaly spolehlivě. | (deleted) |
| `apartment.form.passport_policy.hint` | EN | Off means the guest form does not request a document image. Required asks foreign guests for a temporary upload for your optional review; it is never sent to Police. | Required asks foreign guests to upload a document photo for your review. It is never sent to the police. |
| `apartment.form.passport_policy.hint` | CS | Vypnuto znamená, že formulář obrázek dokladu nevyžaduje. Povinné požádá cizince o dočasné nahrání k vaší volitelné kontrole; policii se neposílá. | Povinné: cizinci nahrají fotku dokladu k vaší kontrole. Policii se nikdy neposílá. |
| `apartment.form.ubyport.contact_hint` | EN | E-mail/phone from original registration or UbyPort portal — not on the WS password letter. | E-mail or phone from your original UbyPort registration; often not on the web-service PDF. A wrong value can get reports rejected. |
| `apartment.form.ubyport.contact_hint` | CS | E-mail/telefon z registrace nebo portálu UbyPort — není na dopise s heslem WS. | E-mail nebo telefon z původní registrace v UbyPortu; na PDF webové služby často chybí. Špatná hodnota může vést k odmítnutí hlášení. |
| `apartment.form.ubyport.map.contact` | EN | E-mail or phone you gave on the original UbyPort accommodation registration — often not printed on the web-service PDF. Same value as in the UbyPort portal profile for this facility. UbyPort may reject reports if this is wrong; leave blank only if you never registered one. | (deleted) |
| `apartment.form.ubyport.map.contact` | CS | E-mail nebo telefon z původní registrace ubytování — často není na PDF webové služby. Stejná hodnota jako v profilu zařízení v UbyPortu. Špatný kontakt může vést k odmítnutí; prázdné jen pokud jste ho nikdy neuváděli. | (deleted) |
| `apartment.form.ubyport.map.contact_label` | EN | Contact (optional here) | (deleted) |
| `apartment.form.ubyport.map.contact_label` | CS | Kontakt (volitelné zde) | (deleted) |
| `apartment.form.ubyport.map.idub` | EN | Line IDUB: on the web-service PDF. | (deleted) |
| `apartment.form.ubyport.map.idub` | CS | Řádek IDUB: na PDF webové služby. | (deleted) |
| `apartment.form.ubyport.map.login` | EN | Line Přihlašovací jméno: (e.g. UBY-WS_DEMO1). | (deleted) |
| `apartment.form.ubyport.map.login` | CS | Řádek Přihlašovací jméno: (např. UBY-WS_DEMO1). | (deleted) |
| `apartment.form.ubyport.map.mark` | EN | Five letters assigned when the facility was registered — not on the cover e-mail. Often the same five letters after UBY-WS_ in the web-service login (e.g. login UBY-WS_DEMO1 → zkratka DEMO1). Confirm in the UbyPort portal under facility details or your original registration decision if unsure. | (deleted) |
| `apartment.form.ubyport.map.mark` | CS | Pět písmen přidělených při registraci — ne v úvodním e-mailu. Často stejných pět písmen za UBY-WS_ v přihlášení (např. UBY-WS_DEMO1 → zkratka DEMO1). Ověřte v portálu UbyPort nebo v rozhodnutí o registraci. | (deleted) |
| `apartment.form.ubyport.map.mark_label` | EN | Facility abbreviation (zkratka) | (deleted) |
| `apartment.form.ubyport.map.mark_label` | CS | Zkratka ubytovacího zařízení | (deleted) |
| `apartment.form.ubyport.map.name` | EN | Line Ubytovací zařízení: on the web-service PDF — copy the first line only (before any bracket with Praha/address). Not your Airbnb title. Max 35 characters; the police register uses the short legal name. | (deleted) |
| `apartment.form.ubyport.map.name` | CS | Řádek Ubytovací zařízení: na PDF — kopírujte jen první řádek (před závorkou s Prahou/adresou). Ne název na Airbnb. Max. 35 znaků; v registru je krátký právní název. | (deleted) |
| `apartment.form.ubyport.map.password` | EN | Line Přístupové heslo: on the same PDF — enter once, then leave blank on later saves. | (deleted) |
| `apartment.form.ubyport.map.password` | CS | Řádek Přístupové heslo: na stejném PDF — zadejte jednou, při dalších uloženích nechte prázdné. | (deleted) |
| `apartment.form.ubyport.map_summary` | EN | Where each UbyHost field comes from (read this once) | (deleted) |
| `apartment.form.ubyport.map_summary` | CS | Odkud se bere každé pole v UbyHostu (přečtěte jednou) | (deleted) |
| `apartment.form.ubyport.mark_hint` | EN | Five letters on file with the police (often = letters after UBY-WS_ in your login). | Five letters on file with the police, often the letters after UBY-WS_ in your login (UBY-WS_DEMO1 → DEMO1). Check the UbyPort portal if unsure. |
| `apartment.form.ubyport.mark_hint` | CS | Pět písmen v evidenci policie (často = písmena za UBY-WS_ v přihlášení). | Pět písmen v evidenci policie, často písmena za UBY-WS_ v přihlášení (UBY-WS_DEMO1 → DEMO1). Při nejistotě ověřte v portálu UbyPort. |
| `apartments.lede` | EN | Bookings, guest links and reporting, in one place. | (deleted) |
| `apartments.lede` | CS | Rezervace, odkazy pro hosty a hlášení na jednom místě. | (deleted) |
| `automation.lede` | EN | Choose when completed guest registrations are sent and manage each property's police web-service credentials. | (deleted) |
| `automation.lede` | CS | Nastavte odesílání dokončených registrací hostů a přístupové údaje policejní webové služby pro každé ubytování. | (deleted) |
| `automation.timing_help` | EN | Immediate sends when all declared forms are complete. Delayed sends after the chosen number of hours from completion, giving you time to review. Both are automatic and do not wait for verification. A rejected record is retried automatically at most three times, and again after you correct it; you get an alert either way. | Automatic modes do not wait for ID verification. A rejected record is retried up to three times, and again after you fix it; you get an alert either way. |
| `automation.timing_help` | CS | Okamžitý režim odešle po dokončení všech nahlášených formulářů. Odložený odešle po zvoleném počtu hodin od dokončení a dává vám čas na kontrolu. Oba jsou automatické a nečekají na ověření. Odmítnutý záznam se automaticky zkusí nejvýše třikrát a znovu po opravě; upozornění dostanete vždy. | Automatické režimy nečekají na ověření dokladu. Odmítnutý záznam se zkusí nejvýše třikrát a znovu po opravě; upozornění dostanete vždy. |
| `celebration.body` | EN | You have reported %(count)s guests through UbyHost — a %(milestone)s-guest milestone. Thank you for keeping everything in order. | Milestone: %(count)s guests reported through UbyHost. |
| `celebration.body` | CS | Přes UbyHost jste nahlásili %(count)s hostů — milník %(milestone)s hostů. Díky, že máte vše v pořádku. | Milník: přes UbyHost jste nahlásili %(count)s hostů. |
| `celebration.title` | EN | Well done! | (deleted) |
| `celebration.title` | CS | Výborně! | (deleted) |
| `dashboard.minutes_saved` | EN | ~%(minutes)s min saved vs manual UbyPort entry | (deleted) |
| `dashboard.minutes_saved` | CS | ~%(minutes)s min ušetřeno oproti ručnímu UbyPortu | (deleted) |
| `dashboard.reporting_modes_body` | EN | Manual waits for your Send click. Delayed automation sends after the chosen number of hours from completion. Immediate automation sends as soon as all declared forms are complete. Automatic modes do not wait for passport verification. | (deleted) |
| `dashboard.reporting_modes_body` | CS | Ruční režim čeká na Odeslat. Odložená automatizace odešle po zvoleném počtu hodin od dokončení. Okamžitá automatizace odešle, jakmile jsou hotové všechny nahlášené formuláře. Automatické režimy nečekají na ověření pasu. | (deleted) |
| `demo.load_detail` | EN | Two sample properties covering the stay picker, claims, passport toggle, controller split, reporting, and house book. Nothing is sent to the real police. | Two sample properties. Nothing is sent to the police. |
| `demo.load_detail` | CS | Dvě ukázková ubytování: výběr pobytu, převzetí e-mailem, pas, oddělený správce, hlášení a domovní kniha. Na skutečnou policii se nic neodešle. | Dvě ukázková ubytování. Na policii se nic neodešle. |
| `guest.admin.resend.help` | EN | UbyPort files duplicates under errors that cannot be corrected, and repeatedly sending them without reason can cost you web-service access. Only do this if you have a genuine reason — for example the connection dropped mid-transfer and you are not sure the data arrived. | Resending creates a duplicate that UbyPort cannot correct, and repeated resends can cost you web-service access. Use it only if you are not sure the first send arrived. |
| `guest.admin.resend.help` | CS | UbyPort duplicity eviduje jako neopravitelné chyby a opakované odesílání bez důvodu může vést ke ztrátě přístupu k webové službě. Použijte jen s oprávněným důvodem — např. spojení spadlo a nejste si jisti doručením. | Opětovné odeslání vytvoří v UbyPortu neopravitelnou duplicitu a opakované odesílání může vést ke ztrátě přístupu k webové službě. Použijte ho jen, když si nejste jisti, že první odeslání dorazilo. |
| `guest_links.lede` | EN | One permanent property link for portal messages. Guests choose their stay dates after opening it. | One permanent link per property for portal messages; guests pick their own dates. |
| `guest_links.lede` | CS | Jeden trvalý odkaz pro každé ubytování do zpráv portálu. Host si po otevření vybere termín. | Jeden trvalý odkaz na ubytování do zpráv portálu; host si termín vybere sám. |
| `host.signature_help` | EN | Required by Czech law (§ 101–103, Act 326/1999 Coll.). The guest must sign, or you must keep a matching paper form on file. Unsigned records cannot be reported to UbyPort. | Required by law. The guest must sign, or you must keep a matching paper form. Unsigned records cannot be sent to UbyPort. |
| `host.signature_help` | CS | Vyžaduje zákon (§ 101–103, zákon č. 326/1999 Sb.). Host se musí podepsat, nebo musíte mít shodný papírový formulář. Nepodepsané záznamy nelze odeslat do UbyPortu. | Vyžaduje to zákon. Host se musí podepsat, nebo musíte mít shodný papírový formulář. Nepodepsané záznamy nelze odeslat do UbyPortu. |
| `housebook.legal_footnote` | EN | You remain the data controller for guest data. The software operator identified in the Legal notice is the technology provider only — not your accommodation business, not legal advice, and not liable for incorrect data you or guests enter or for how you use the software. Keep signed paper you already hold; a screen alone may not satisfy an inspection. | You are the data controller for guest data. UbyHost only provides the software: it is not legal advice and is not liable for data you or guests enter, or for how you use it. |
| `housebook.legal_footnote` | CS | Zůstáváte správcem údajů hostů. Provozovatel software uvedený v Právních informacích je pouze poskytovatel technologie — ne váš ubytovací podnik, ne právní poradenství a neodpovídá za chybné údaje, které zadáte vy nebo hosté, ani za způsob použití software. Uchovejte podepsané papíry; obrazovka sama o sobě nemusí při kontrole stačit. | Správcem údajů hostů jste vy. UbyHost poskytuje jen software: nejde o právní poradenství a neodpovídá za údaje zadané vámi nebo hosty ani za způsob jeho použití. |
| `housebook.legal_intro_ack` | EN | Got it — hide this next time | (deleted) |
| `housebook.legal_intro_ack` | CS | Rozumím — příště skrýt | (deleted) |
| `housebook.legal_intro_skip` | EN | Skip for now | (deleted) |
| `housebook.legal_intro_skip` | CS | Teď přeskočit | (deleted) |
| `housebook.legal_intro_title` | EN | House book — your legal duty | (deleted) |
| `housebook.legal_intro_title` | CS | Domovní kniha — vaše zákonná povinnost | (deleted) |
| `housebook.legal_paper` | EN | UbyHost helps you maintain the register digitally. It does not replace paper you already have: keep any original signed forms, ledgers, or binders you used before this app in a safe place for the full retention period. | Keep any signed paper forms or books you used before UbyHost for the full retention period. |
| `housebook.legal_paper` | CS | UbyHost vám pomáhá vést evidenci digitálně. Nenahrazuje papír, který už máte: uschovejte původní podepsané formuláře, knihy nebo pořadače z doby před aplikací po celou zákonnou dobu. | Podepsané papírové formuláře a knihy z doby před UbyHostem uschovejte po celou zákonnou dobu. |
| `onboarding.finish_lede` | EN | %(property)s can welcome guests now. Copy the permanent link and PIN into every portal's pre-arrival message. | Paste the link and PIN into each portal's pre-arrival message. |
| `onboarding.finish_lede` | CS | %(property)s už může vítat hosty. Trvalý odkaz a PIN vložte do zprávy před příjezdem na každém portálu. | Odkaz a PIN vložte do zprávy před příjezdem na každém portálu. |
| `onboarding.safe_body` | EN | New reporting starts in the mode you choose. Demo data never reaches the real police, and guest e-mail stays off until delivery is configured. | (deleted) |
| `onboarding.safe_body` | CS | Hlášení začne v režimu, který zvolíte. Ukázková data se skutečné policii nikdy neodešlou a e-maily hostům zůstanou vypnuté, dokud není připraveno doručení. | (deleted) |
| `onboarding.safe_title` | EN | Nothing goes live by accident | (deleted) |
| `onboarding.safe_title` | CS | Nic se nespustí omylem | (deleted) |
| `onboarding.welcome_lede` | EN | We will take you from legal details to a guest-ready link. One clear task at a time; UbyHost remembers where you stopped. | (deleted) |
| `onboarding.welcome_lede` | CS | Provedeme vás od právních údajů až k odkazu připravenému pro hosty. Vždy jeden jasný úkol; UbyHost si pamatuje, kde jste skončili. | (deleted) |
| `settings.archive_hint_extended` | EN | Stays, properties, house-book entries, and operators you archived are collected in one place. Restore anything you hid by mistake. The retention purge below is the only way guest records are permanently deleted. | Archived stays, properties, house-book entries and operators. Restore anything you hid by mistake. |
| `settings.archive_hint_extended` | CS | Archivované pobyty, ubytování, záznamy knihy a provozovatelé jsou na jednom místě. Obnovte, co jste skryli omylem. Trvalé smazání hostů provede pouze retence níže. | Archivované pobyty, ubytování, záznamy knihy a provozovatelé. Obnovte, co jste skryli omylem. |
| `settings.audit.help` | EN | Important changes, archives, PIN rotations, and police submissions are recorded here. Only the retention purge permanently deletes guest records. | Important changes, archives, PIN rotations and police submissions are recorded here. |
| `settings.audit.help` | CS | Důležité změny, archivace, změny PIN a policejní hlášení se zapisují zde. Trvale maže pouze retence. | Důležité změny, archivace, změny PIN a policejní hlášení se zapisují zde. |
| `stays.lede` | EN | Calendar stays and manual bookings, earliest arrival first. | (deleted) |
| `stays.lede` | CS | Pobyty z kalendářů a ruční rezervace, nejdříve nejbližší příjezd. | (deleted) |
