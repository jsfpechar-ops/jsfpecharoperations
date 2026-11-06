# 0961 report
Status: review
Files: App/app/routes/onboarding_wizard.py, App/app/routes/stay_fees.py, App/tests/test_stay_fee_guest_pay_browser.py, App/tests/test_stay_fee_guest_pay_0897.py, App/tests/test_db_postgres.py, App/tests/test_migrations.py, docs/tasks/0961-fix-ruff-and-wizard-nameerror.md
Ruff (E9,F63,F7,F82,F401,F841): All checks passed. Pytest 0897: 46 passed. test_migrations.py: 14 passed.
Scope addition (coordinator): schema version 36 -> 37 in test_db_postgres.py and test_migrations.py; unsupported-source test now drops MAX(version) row. Postgres tests NOT run locally (no Postgres here).
Deviations: no PR opened (user instruction). Commit attribution uses Haiku 5.5 per system reminder, not Sonnet 5.5 as the brief says.
Follow-up: test_db_postgres.py:290 history range(1, 37) -> range(1, 38) (versions 1..37); no other same-history lists found (test_connection_reuse.py:276 range(1, 33) left alone). Postgres tests still not run locally.
Copy follow-up: cs fee_intro 'ubytovatel' -> 'hostitel' (only non-legal cs key with the word); uk all_done_body_fee added; all six language key sets now match. Guest tests 99 passed; ruff clean; context lint OK.
Wizard 500 follow-up: onboarding_wizard.py:150 apartment.get -> apartment["legal_entity_id"] (sqlite3.Row); line 92 and the draft path at ~242 left as-is (old code from 8891d9c). New test test_the_setup_wizard_stay_fee_post_with_flag_on_does_not_500 fails without the fix, passes with it. 0897 tests: 47 passed; ruff clean; context lint OK. Browser tests not run locally (no chromium; test_property_navigation_browser.py fails at launch).
