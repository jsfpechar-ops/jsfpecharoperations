# 0347 report

Status: review

## Files changed (git diff --stat plus new files)
- Modified: App/app/config.py, App/app/host_i18n.py, App/app/retention.py, App/app/routes/guest_guide.py, App/app/scheduler.py, App/app/templates/guest_guide.html, docs/ENVIRONMENT.md, docs/privacy/RETENTION.md
- New: App/app/guest_guide_import.py, App/app/migrations/0016_guide_import.sql, App/tests/test_guest_guide_import.py
- Report: docs/tasks/0297-report.md

## Commands (from App/ unless noted)
- test_guest_guide_import.py + test_guest_guide_pages.py: 50 passed (brief says 51)
- test_migrations.py: 13 passed
- test_db_*.py: 5 passed
- test_retention*, test_privacy_*, test_no_tracking, test_cookie_inventory, test_pii_encryption, test_dsr_audit, test_data_keys: 120 passed
- test_*_i18n.py, test_no_em_dashes, test_copy_cleanup, test_flash_literals: 3 failed (test_host_i18n.py, known, predate 0347), rest passed
- test_scheduler, test_push, test_admin_operations: 57 passed
- test_retention, test_retention_alignment, test_retention_job: 41 passed
- test_host_*.py + test_host_geometry + test_design_guardrails_browser: 209 passed, 1 skipped (test_host_copy_corrections.py, needs UBYHOST_REQUIRE_BROWSER=1); rerun with that set: 9 passed, 0 skipped
- Repo root: design_lint OK; context_lint OK

## Section 7
Ticked except the screenshot (skipped per owner note; orchestrator takes it).

## Deviations
- Migration: 0016_guide_import.sql (0015 reserved for brief 0310). context_lint now prints migration 0017 as next free.
- test count 50 passed, not 51 as the brief expects.
- test_host_i18n.py: 3 known failures (predate this work), ignored.
- No 390 px screenshot taken (orchestrator takes it).
- Single commit at the end, not one per step (per orchestrator instruction).
- Acceptance check `grep APIFY_TOKEN` shows two hits in guest_guide_import.py (enabled() and the Bearer header), as the brief describes.
- Route-path check command in step 4 errors (`_IncludedRouter` has no `.path`); not a functional problem, the POST route is covered by the tests.

## Questions
None.

## Owner steps left
Apify account and token steps from the brief's Owner steps section; deploy with UBYHOST_APIFY_TOKEN set.
