# 0240 report

Status: review

## Commits (branch claude/project-thread-kbrf7w, not pushed)

- 4bd0477 0240 step 1: legend shows "(optional)" with the scope text behind help_tip (`App/app/templates/_entity_business_fields.html`)
- 47a37da 0240 step 2: 9 values changed in `App/app/host_i18n.py` (EN and CS, later definitions) and `App/app/host_vi_i18n.py` (VI)

## Step 3 result (last lines, from App/)

Set run (test_host_i18n, test_no_em_dashes, test_stay_fee_signature, test_fee_setup_compatibility, test_onboarding_wizard_survival, test_entity_editor_fields, test_entity_editor_navigation):

    6 failed, 128 passed, 1 skipped

Failures, none asserts old wording:
- test_host_i18n: test_language_endpoint_sets_cookie_and_rejects_open_redirects, test_a_signed_in_dashboard_keeps_vietnamese, test_language_endpoint_accepts_vietnamese: `sqlite3.OperationalError: no such table: apartment` (test DB not migrated here; fails in isolation too)
- test_entity_editor_fields, test_entity_editor_navigation (2 tests): `Executable doesn't exist at /opt/pw-browsers/chromium_headless_shell-1243/...` (Chromium not installed)
- Skipped: test_fee_setup_compatibility.py:381, Chromium required

## Deviations

- Brief section 9 asks for "Status: review" and the report commit; I did not push and did not open a PR (owner said do not push).
- Steps 1 and 2 applied exactly; step 2 applied by line number with key checks, because the old-value anchors were not unique as text.
- The failures above are environment (no migrated DB, no Chromium). Not fixed. Owner or CI should rerun those.
- Only the report file is committed in the report commit; the brief file status line was not changed.

## Owner steps left

- Run the three i18n and two entity-editor tests in an environment with a migrated DB and Chromium.
- Orchestrator: 390 px screenshot of the stay-fee step.
