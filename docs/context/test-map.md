# Test map

Run only the row for the area you changed, from `App/`, always ending `-q --tb=short -x 2>&1 | tail -30`. CI runs the full suite; the full suite locally only when the owner asks in the current chat. Globs are under `tests/`. Add the test file you wrote or changed.

| Changed | Run |
|---|---|
| Guest pages, guest templates | `test_guest_*.py` and `test_guest_browser_e2e.py` (0 skipped) |
| Host pages, host templates, host CSS | `test_host_*.py` and `test_host_geometry.py` (0 skipped) |
| Login, 2FA, passkeys, sessions | `test_login_*.py test_auth_*.py test_two_factor_*.py test_passkeys.py test_remember_me_reissue.py test_security*.py` |
| Filing, UbyPort, worker, claim | `test_ubyport_*.py test_soap.py test_worker.py test_submission_*.py test_stale_submission.py test_filed_by_hand.py test_filing_watchdog.py test_police_*.py test_deadline*.py test_claim_*.py test_endtoend.py` |
| Invoices, stay fee | `test_invoice_*.py test_stay_fee*.py` |
| Door-code access disclosure | `test_door_code_window.py test_door_code_window_browser.py`; CI `door-code-access-review` requires Chromium/WebKit, zero skips, 390 px screenshots |
| Door codes, TTLock | `test_door_code*.py test_ttlock*.py test_smart_locks_page.py` |
| Cleaning | `test_cleaning*.py` |
| Calendar, iCal feeds | `test_icalsync.py test_ical_skip_unchanged.py test_feed_*.py test_dashboard_calendar*.py test_calendar_*.py test_sample_calendar.py` |
| Mail, SES | `test_ses_mail.py test_mail_*.py test_*_mail.py test_lifecycle_mail.py test_notification_copy.py` |
| Retention, privacy, personal data | `test_retention*.py test_privacy_*.py test_no_tracking.py test_cookie_inventory.py test_pii_encryption.py test_dsr_audit.py test_data_keys.py` |
| Database, migrations | `test_migrations.py test_db_*.py` |
| Public pages, legal, landing | `test_public_*.py test_legal_*.py test_landing_*.py test_terms_copy.py test_wp24_terms_dpa.py` |
| Copy, translations | `test_*_i18n.py test_no_em_dashes.py test_copy_cleanup.py test_flash_literals.py` |
| Onboarding, properties | `test_onboarding*.py test_property_*.py test_first_*.py` |
| Analytics | `test_posthog_*.py test_umami_guard.py test_meta_capi.py` |
| Design system, catalog page, design lint | `test_design_*.py test_dev_ui*.py` |
| Static files under App/app/static (any), cache keys | `test_static_versions.py test_wp07_cache_heartbeats.py` plus the row of the page the file styles |
| Any host template, host CSS or host JS | test_design_guardrails_browser.py (0 skipped; the rules are in MASTER 11.0) |
| Public/app domain configuration | `test_app_domain.py test_env_guard.py test_passkeys.py test_pwa.py`, login/auth/security row, relevant mail tests; Caddy validation in both TLS modes |
| A module with no row | `tests/test_<module name>*.py`; none exists: `-k <module name>` |

A row missing or wrong: the orchestrator fixes this table in the same brief.
