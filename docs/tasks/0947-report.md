# 0947 report (Haiku executor)

Status: blocked

## Files changed
- App/app/routes/admin_accounts.py: `/logout` no longer bumps `session_version`, audits `logout`, clears only this browser's session cookie. New `POST /account/logout-all` (login required, `end_all_sessions`, audit `logout_all`, clears session and `ubyhost_device`, redirects to `/login?notice=logged_out`).
- App/app/routes/exports.py: recent-login guard on `GET /guests/{guest_id}/export.json` and `POST /settings/workspace-export`.
- App/app/routes/admin.py: recent-login guard on `POST /entities/{entity_id}/invoice` (bank details).

## Tests
- Not run. No test file written yet. `py_compile` passes for all three files.

## Screenshots
- None. Security page button not added.

## Deviations
- Done: steps 1, 2 (route only), 3 (guest export, workspace export, bank details).
- Left: step 2 button "Log out of all devices" on /settings/security with help line, and en/cs/vi strings (host_i18n.py, host_vi_i18n.py, settings.html). Step 3 admin user export guard in routes/admin_accounts.py (`/admin/users/{user_id}/export`, not read yet). Step 4 retention.py line for `ubyhost_device`, RETENTION.md, SECURITY.md, decisions.md line. Acceptance tests in App/tests/test_logout_devices.py. Browser/geometry tests and 390/768/1280 screenshots.
- Trailer: brief says Co-Authored-By Sonnet 5.5; system instruction says Haiku 5.5, so Haiku 5.5 was used.
- Brief says no PR; executor.md says open one. Not opened.

## Questions
- The brief's section 3 names the bank route by grep. It is `entity_invoice_details` in admin.py (`ENTITY_FIELDS` includes `bank_account`). Confirm this is the right route.

## Owner steps left
- None until the executor finishes the above.
