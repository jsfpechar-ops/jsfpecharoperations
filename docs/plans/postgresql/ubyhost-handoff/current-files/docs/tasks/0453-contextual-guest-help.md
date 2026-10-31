# 0453: Contextual guest-field help

Status: review
Base: `8b5317d0a49b840136fbfbcad7fb06af100f3575` | Branch: `codex/ubyhost-corrections-20261030`
Dependency: 0451 guest progression and visible acknowledgement. 0451 owns save-action labels, `person_saved`, `saved_body`, and legal acknowledgement behavior. 0453 owns only the contextual-purpose keys and the shared email-purpose partial; dictionaries and `form.html` are shared files, so apply as a dependent delta after 0451.

## 1. Objective

Explain why the guest supplies the main data groups, email, guest count, and conditional passport image. Use orchestrator-reviewed, source-backed short statements. Keep explanations in collapsed native `<details>` disclosures beside their fields, with keyboard, touch, and no-JavaScript operation. Preserve legal-notice wording, required fields, formatting hints, errors, nationality conditions, and upload conditions.

## 2. Context

The purpose statements summarize existing approved copy; they add no retention period, obligation, or other legal claim. Email copy remains byte-for-byte existing text: `tw_email_short`, `claim_email_help`, `claim_cookie_help`, and the existing privacy link. Summary labels contain no literal question mark; existing `.g-why-summary::after` supplies one visible `?`.

| Group | English body | Existing source basis |
|---|---|---|
| Identity details | Your host uses these details for the house book and, for foreign guests, police reporting. | `legal_notice_duty_body`, `legal_notice_reporting_body` |
| Address and stay purpose | Your address and purpose of stay are part of the registration details kept by your host. | `privacy_data_body`, `legal_notice_reporting_body` |
| Signature | Your signature is kept with your registration details. | `legal_notice_retention_body` |
| Guest count | The number of guests tells us when all expected registration forms are complete. | Registration completion context from the declared-count explanation in `privacy_data_body` |
| Passport image | Your host uses the image to check your registration details. It is not sent to the police. | `legal_notice_passport_body` |

### Translation values

Add these body values and concise purpose labels to the five dictionaries in `App/app/i18n.py` and the Ukrainian dictionary in `App/app/guest_uk_i18n.py`.

| Key | English | Czech | German | Spanish | French | Ukrainian |
|---|---|---|---|---|---|---|
| `email_help_label` | Why we need your email | Proč potřebujeme váš e-mail | Warum wir Ihre E-Mail-Adresse benötigen | Por qué necesitamos su correo electrónico | Pourquoi nous avons besoin de votre adresse e-mail | Навіщо нам потрібна ваша електронна адреса |
| `identity_purpose_help` | Your host uses these details for the house book and, for foreign guests, police reporting. | Hostitel používá tyto údaje pro domovní knihu a u zahraničních hostů pro hlášení cizinecké policii. | Ihr Gastgeber verwendet diese Angaben für das Hausbuch und meldet ausländische Gäste damit der Polizei. | Su anfitrión usa estos datos para el libro de registro y, en el caso de huéspedes extranjeros, para informar a la policía. | Votre hôte utilise ces informations pour le registre d’hébergement et, pour les voyageurs étrangers, pour les déclarer à la police. | Господар використовує ці дані для книги обліку гостей і, щодо іноземних гостей, для повідомлення поліції. |
| `address_purpose_help` | Your address and purpose of stay are part of the registration details kept by your host. | Vaše adresa a účel pobytu jsou součástí registračních údajů, které uchovává hostitel. | Ihre Adresse und der Aufenthaltszweck gehören zu den Registrierungsdaten, die Ihr Gastgeber aufbewahrt. | Su dirección y el motivo de la estancia forman parte de los datos de registro que conserva su anfitrión. | Votre adresse et le motif du séjour font partie des informations d’enregistrement conservées par votre hôte. | Ваша адреса та мета перебування є частиною реєстраційних даних, які зберігає господар. |
| `signature_purpose_help` | Your signature is kept with your registration details. | Váš podpis se uchovává spolu s registračními údaji. | Ihre Unterschrift wird zusammen mit Ihren Registrierungsdaten aufbewahrt. | Su firma se conserva junto con sus datos de registro. | Votre signature est conservée avec vos informations d’enregistrement. | Ваш підпис зберігається разом із реєстраційними даними. |
| `guest_count_purpose_help` | The number of guests tells us when all expected registration forms are complete. | Počet hostů nám ukáže, kdy jsou vyplněny všechny očekávané registrační formuláře. | Die Zahl der Gäste zeigt uns, wann alle erwarteten Registrierungsformulare vollständig sind. | El número de huéspedes nos indica cuándo están completos todos los formularios de registro esperados. | Le nombre de voyageurs nous indique quand tous les formulaires d’enregistrement attendus sont complets. | Кількість гостей показує, коли всі очікувані реєстраційні форми заповнено. |
| `passport_photo_purpose_help` | Your host uses the image to check your registration details. It is not sent to the police. | Hostitel obrázek používá ke kontrole vašich registračních údajů. Policii jej neposílá. | Ihr Gastgeber verwendet das Bild, um Ihre Registrierungsdaten zu prüfen. Es wird nicht an die Polizei gesendet. | Su anfitrión usa la imagen para comprobar sus datos de registro. No se envía a la policía. | Votre hôte utilise l’image pour vérifier vos informations d’enregistrement. Elle n’est pas transmise à la police. | Господар використовує зображення, щоб перевірити ваші реєстраційні дані. Його не надсилають поліції. |
| `identity_purpose_help_label` | Why we ask for these details | Proč tyto údaje požadujeme | Warum wir diese Angaben erfragen | Por qué pedimos estos datos | Pourquoi nous demandons ces informations | Навіщо ми просимо ці дані |
| `address_purpose_help_label` | Why we ask for your address and stay purpose | Proč se ptáme na adresu a účel pobytu | Warum wir nach Adresse und Aufenthaltszweck fragen | Por qué preguntamos la dirección y el motivo de la estancia | Pourquoi nous demandons l’adresse et le motif du séjour | Навіщо ми запитуємо адресу та мету перебування |
| `signature_purpose_help_label` | Why we ask for your signature | Proč požadujeme váš podpis | Warum wir um Ihre Unterschrift bitten | Por qué pedimos su firma | Pourquoi nous demandons votre signature | Навіщо ми просимо ваш підпис |
| `guest_count_purpose_help_label` | Why we ask for the guest count | Proč se ptáme na počet hostů | Warum wir nach der Gästezahl fragen | Por qué preguntamos el número de huéspedes | Pourquoi nous demandons le nombre de voyageurs | Навіщо ми запитуємо кількість гостей |
| `passport_photo_purpose_help_label` | Why we ask for this image | Proč žádáme tento obrázek | Warum wir um dieses Bild bitten | Por qué pedimos esta imagen | Pourquoi nous demandons cette image | Навіщо ми просимо це зображення |


## 3. Files

| Path | Action |
|---|---|
| `App/app/templates/guest/claim.html` | Add one guest-count purpose disclosure by the party field and include the shared email disclosure. Keep all labels and privacy link. |
| `App/app/templates/guest/assigned.html` | Replace its resend-only email disclosure with the shared email purpose disclosure. |
| `App/app/templates/guest/_email_purpose_help.html` | Shared, collapsed email-purpose disclosure with the existing email/cookie copy and privacy link. |
| `App/app/templates/guest/form.html` | Add one identity-purpose disclosure in the details step, address/stay-purpose disclosure in the residence step, one guest-count disclosure only when `ask_party_size`, signature-purpose disclosure in signature step, and conditional passport-image help beside upload. Keep existing field hints and errors visible. |
| `App/app/i18n.py`, `App/app/guest_uk_i18n.py` | Add all body and summary labels in all six supported catalogs. |
| `App/tests/test_guest_browser_e2e.py` | Browser-check email label, one CSS `?`, open/closed behavior, contextual purpose at the matching step, no-JS native disclosure operation, and conditional photo help. |
| `docs/tasks/0453-contextual-guest-help.md` | This brief. |
| `docs/tasks/0453-report.md` | Actual checks and remaining evidence. |
| `docs/tasks/screenshots-0453/` | Synthetic 390 px claim-email and guest-form screenshots. |

Use existing `.g-why` styling; no CSS/JS change or cache-key bump is expected. Do not place errors, formatting hints, or required controls inside the new details elements.


## 4. Steps

1. After 0451, include one shared email-purpose disclosure on both the email-claim and assigned-link resend forms.
2. Add guest-count explanation beside each guest-count field.
3. Add identity, address/stay, signature, and conditional passport-image explanations beside their matching steps.
4. Add contextual translations and browser assertions. Capture synthetic 390 px screenshots for claim email, guest form, acknowledgement, next guest, and completion summary.
5. Run the test-map guest row and geometry check.

## 5. Do not touch

Do not change existing legal notice wording, requiredness, formatting hints, errors, nationality gates, upload conditions, persistence, routes, cookies, or dependencies. Keep 0451 save/action copy separate from contextual-help keys. No CSS, JavaScript, or static cache-key change is in scope.

## 6. Commands

From `App/`, run with `set -o pipefail`:

```bash
.venv/bin/python -m pytest tests/test_guest_*.py tests/test_host_geometry.py -q -rs --tb=short -x 2>&1 | tail -30
```

From repository root:

```bash
git diff --check 2>&1 | tail -30
```

## 7. Acceptance

- Email helper is collapsed, email-specific, uses existing privacy/cookie copy, has one generated question marker, and toggles with JavaScript disabled on claim and resend pages.
- Guest-count purpose appears on claim and only when a form asks for headcount.
- Each purpose explanation appears at the matching form step; passport help appears only with the conditional photo upload.
- All contextual keys are localized for `en`, `cs`, `de`, `es`, `fr`, and `uk`.
- Browser and geometry checks pass with zero skips; required 390 px screenshots are inspected and listed in the report.

## 8. Stop and ask

Stop if an approved source string is missing, a new legal claim would be required, existing conditions or requiredness would need to change, the layout overflows at 390 px, or browser/geometry failures persist after one focused correction. Preserve partial work and report exact evidence. Do not commit, push, merge, or deploy.

## 9. Report

Record exact commands, exit codes, pass/fail/skip counts, 390 px screenshot paths, legal-copy preservation, and remaining gaps. Set status to `review` only after acceptance is met; otherwise retain `in-progress` and report the failed evidence.
