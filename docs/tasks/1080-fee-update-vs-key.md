# 1080: fee update mail lost its variable-symbol line after #868 merged

Status: review

Tier: B | Branch: claude/1078-f3 (PR #869), no new PR | Executor: Opus 5.5 | Attempts: 3 at most
Report: docs/tasks/1080-report.md

## 1. Objective
Restore the variable-symbol line in the fee update mail (#869) after #868 removed the key it used.

## 2. Context
#868 (brief 1077, step 6) deleted the i18n key `mail_completion_fee_vs`, and
`App/tests/test_completion_fee_mail_1077.py::test_the_two_old_keys_are_gone` asserts it stays deleted.
#869 (brief 1078) still uses that key in `App/app/mail_notify.py` `build_fee_update` (around line 1863),
so after merging main `host_i18n.lookup` returns the raw key name and the "more" fee update mail shows the literal text `mail_completion_fee_vs` instead of the variable-symbol line. CI fails:
`tests/test_fee_update_1078.py::test_a_changed_total_mails_once_after_ten_quiet_minutes`
(`assert f"variable symbol {stay.id}." in text`).

## 3. Files
App/app/mail_notify.py, App/app/i18n.py, App/app/guest_uk_i18n.py, App/tests/test_fee_update_1078.py.

## 4. Steps
1. Add a new key `mail_fee_update_vs` in `App/app/i18n.py` (en, cs, de, es, fr) and `App/app/guest_uk_i18n.py` (uk),
   next to the other `mail_fee_update_*` keys, with exactly the old wording:
   - en: `Bank transfer: use variable symbol %(vs)s.`
   - cs: `Bankovní převod: použijte variabilní symbol %(vs)s.`
   - de: `Banküberweisung: Variablensymbol %(vs)s verwenden.`
   - es: `Transferencia bancaria: use el símbolo variable %(vs)s.`
   - fr: `Virement bancaire : utilisez le symbole variable %(vs)s.`
   - uk: `Банківський переказ: використовуйте змінний символ %(vs)s.`
2. In `build_fee_update`, use `mail_fee_update_vs` instead of `mail_completion_fee_vs`. No other logic change.
3. In `App/tests/test_fee_update_1078.py` (around line 522) replace `mail_completion_fee_vs` with `mail_fee_update_vs`.
4. Add `mail_fee_update_vs` to `NEW_KEYS` in `App/tests/test_fee_update_1078.py` (around line 27), and add `vs="V"` to the `values` dict near line 489. Without it the `"%(" not in` assert fails.
5. Do not touch `test_completion_fee_mail_1077.py`; the old key stays deleted.
6. Since #868, `stay_fee.guest_pay_ways` drops the bank way when the property's legal entity has no IBAN or valid bank account (intended behaviour, keep it). The `stay` fixture in `App/tests/test_fee_update_1078.py` (around line 81) seeds an entity without one, so rails come out `['cash']` and `vs` is never passed. In that fixture, give the apartment's legal entity an IBAN: look up `legal_entity_id` on the apartment row and `db.update("legal_entity", <id>, {"iban": "CZ6508000000192000145399"})` (match the IBAN format `test_completion_fee_mail_1077.py` uses for its `IBAN` constant). Restore the old value at teardown if the fixture has a teardown; otherwise the seed is per-test and needs none. Do not change app code for this.
7. Re-check `test_a_higher_total_without_the_iban_rail_has_no_variable_symbol` still passes (it turns the rail off itself).

## 5. Do not touch
App/tests/test_completion_fee_mail_1077.py; stay_fee.guest_pay_ways.

## 6. Commands (from App/)
`.venv/bin/python -m pytest tests/test_fee_update_1078.py tests/test_completion_fee_mail_1077.py tests/test_guest_languages.py tests/test_no_em_dashes.py -q --tb=short -x 2>&1 | tail -30`
(create `App/.venv` with the requirements file if missing). Then `python3 scripts/context_lint.py` from the repo root.

## 7. Acceptance
Tests above pass; one commit on `claude/1078-f3` pushed. Report the test tail, nothing else.

## 8. Stop and ask
If a test outside the named files fails, stop and report.

## 9. Report
docs/tasks/1080-report.md: test tail and lint result.
