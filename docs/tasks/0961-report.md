# 0961 report
Status: review
Files: App/app/routes/onboarding_wizard.py, App/app/routes/stay_fees.py, App/tests/test_stay_fee_guest_pay_browser.py, App/tests/test_stay_fee_guest_pay_0897.py, App/tests/test_db_postgres.py, App/tests/test_migrations.py, docs/tasks/0961-fix-ruff-and-wizard-nameerror.md
Ruff (E9,F63,F7,F82,F401,F841): All checks passed. Pytest 0897: 46 passed. test_migrations.py: 14 passed.
Scope addition (coordinator): schema version 36 -> 37 in test_db_postgres.py and test_migrations.py; unsupported-source test now drops MAX(version) row. Postgres tests NOT run locally (no Postgres here).
Deviations: no PR opened (user instruction). Commit attribution uses Haiku 5.5 per system reminder, not Sonnet 5.5 as the brief says.
