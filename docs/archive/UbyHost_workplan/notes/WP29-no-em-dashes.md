# WP29: No em dashes in user-visible copy

Last commit of the series (`0032-WP29-...patch`), on top of WP21, on `final` (origin/main 709076a plus 0001 to 0031).

## Summary
- Every em dash (U+2014) used as punctuation in a user-visible string is gone. 230 catalogue strings were changed: 157 in `host_i18n.py`, 54 in `i18n.py` (en, cs, de, es, fr), 7 in `privacy_policy_i18n.py`, 5 in `validation_i18n.py`, 4 in `landing_i18n.py`, 2 in `dpa_i18n.py`, 1 in `terms_i18n.py`. `guide_i18n.py` had none left after WP03, WP23 and WP24.
- Rules used, with the meaning kept exact:
  - two clauses: a full stop, the next word capitalised ("Saved. Not shown again.");
  - a label and its explanation: a colon ("Active: sync calendars and report guests ...", "Article 6(1)(c) GDPR: compliance with ...");
  - a short qualifier: parentheses ("Exempt (under 18)", "Ready (you send)", "Připraveno k hlášení (hostů: 2).");
  - a list continuation: a comma ("Connect Airbnb or Booking.com, or add a direct booking by hand.", "Saved, thank you");
  - a few sentences were rewritten so the joint reads naturally ("Czech nationals stay in the house book only and are not reported ...", "Archived and hidden from your daily work.").
- Select placeholders `— none —` / `— select —` became `(none)` / `(select)` (`(žádná)` / `(vyberte)`).
- Text glued to a link or a list in a template:
  - `settings.privacy.no_entity_suffix` is now "(guests cannot be told who controls their data).";
  - the missing-contact note reads "No contact e-mail on: A, B. Add one so guests can exercise their rights." (`settings.privacy.add_contact` is capitalised);
  - `apartment.form.ubyport.sample_help` is a sentence of its own after the sample button (and the Czech "se vodoznaky" typo is fixed to "s vodoznaky").
- Templates (host, user visible):
  - `guide.html`: the setup step title ends with a colon;
  - `settings.html`: the retention and backup lines use a comma;
  - `stay_fee_detail.html`: the period and the adjustment reason are in parentheses.
- Legal templates and mail templates had em dashes only in Jinja comments, which are not rendered. Mail text is built in `mail_notify.py` from the catalogues, which had none of its own.
- A lone `—` as an empty-cell placeholder in templates stays (house book, entities, reports, stay page, select option in the guest form).

## Files changed
- `App/app/i18n.py`, `host_i18n.py`, `terms_i18n.py`, `privacy_policy_i18n.py`, `dpa_i18n.py`, `landing_i18n.py`, `validation_i18n.py`: the strings above. A changed value is written as one string literal, so some long legal strings that were split over several lines are now on one line.
- `App/app/templates/guide.html`, `settings.html`, `stay_fee_detail.html`: as above.
- `App/tests/test_no_em_dashes.py`: new.
- Tests that pinned the old wording: `test_claim_mail`, `test_claim_resend_complete`, `test_dashboard_order`, `test_dashboard_queue_copy`, `test_flash_next_step`, `test_guest_error_summary`, `test_guest_mail`, `test_guest_residence_prefill`, `test_onboarding`, `test_operator_naming`, `test_overhaul`, `test_plural_helper`, `test_stay_fee_detail`, `test_stay_missing_guest_rows`, `test_two_factor_lockout`, `test_two_factor_setup_page`, `test_users_disable_confirm`.

## Tests added
`tests/test_no_em_dashes.py` (4 tests):
- every string in every `app/*_i18n.py` catalogue and in `app/i18n.py` (walked recursively through all module-level dicts, lists and tuples) is free of " — " and "— ";
- every guest language is checked by name (en, cs, de, es, fr);
- the check itself catches an em dash and lets a lone placeholder dash through;
- the visible text of the legal and mail templates (`terms`, `privacy`, `dpa`, `legal`, `subprocessors`, `public_legal_base`, `_legal_toc`, `_cookie_table`, `mail_unsubscribe`, with Jinja comments removed) has none.

## Test commands and results
From `/tmp/wp/final/App` with `LD_LIBRARY_PATH=/tmp/libs/root/usr/lib/aarch64-linux-gnu /tmp/pr230/App/.venv/bin/python -m pytest -q -p no:cacheprovider`:
- `tests/test_no_em_dashes.py`: 4 passed.
- Copy, legal and guest tests (`test_no_em_dashes`, `test_*copy*`, `test_legal_*`, `test_public_legal*`, `test_terms_copy`, `test_wp24_terms_dpa`, `test_privacy_*`, every `test_guest_*` except the browser e2e): 503 passed.
- Full suite on the final tree, in four chunks: 2724 passed, 2 skipped. Guest browser e2e with `UBYHOST_REQUIRE_BROWSER=1`: 16 passed. `test_host_geometry` and `test_wp28_geometry`: 9 passed.
- Ruff (`app tests tools scripts mock_ubyport`, E9,F63,F7,F82,F401,F841): all checks passed.

## Deviations from the spec and why
- The test covers every `*_i18n.py` catalogue, not only the three named, so the public pages (`landing_i18n.py`), the legal catalogues and the validation messages were cleaned too.
- `common.none` / `common.select` were placeholders built from dashes. They are now in parentheses, which the spec lists, rather than a bare dash.
- Legal texts change punctuation only. No legal version (Terms, Privacy, DPA 1.6) was bumped, because the meaning is the same.

## What Cursor must verify or adapt when applying on the real main
- Any string added on main after this series needs the same rule, or `test_no_em_dashes.py` fails, as intended.
- Python modules outside the catalogues still contain em dashes, mostly in comments, plus some English code-side text: demo data (`demo.py`), the PDF builders (`invoice_pdf.py`, `ubyport_sample_pdf.py`), alert and log text written in English in code (for example `icalsync.py`, `auth.py`, `rate_limit.py`). These are not in the catalogues and were out of scope. If the owner wants those too, a follow-up can extend the test to PDF text.
- The en dash (–) in ranges such as "12–14 digits" and "§§ 101–103" is a range sign, not punctuation, and stays.

## Manual steps for the owner
- Skim the Czech host strings that moved to parentheses or colons (status pills, stay-fee status, guest placeholders) in the app once.
- Have the native-speaker review for de/es/fr (see WP26 notes) cover the changed guest strings too.
