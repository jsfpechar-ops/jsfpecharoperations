# 0947 report (Haiku executor, second session)

Status: blocked

## Files changed
- App/app/templates/settings.html: "Signed-in devices" row with "Log out of all devices" button (POST /account/logout-all) and "?" help, inside #settings-security.
- App/app/host_i18n.py, App/app/host_vi_i18n.py: settings.security.devices, .logout_all, .logout_all_help (en, cs, vi).
- App/app/routes/admin_accounts.py: recent-login guard on POST /admin/users/{user_id}/export.
- App/app/retention.py: one comment line for ubyhost_device. docs/privacy/RETENTION.md: table row. docs/SECURITY.md: logout vs logout-all and fresh-login sentences. docs/context/decisions.md: one [auth] line; one long 2026-10-31 line compacted (see Deviations).
- App/tests/test_logout_devices.py: new, 6 tests (logout keeps other device; logout-all ends both sessions and clears ubyhost_device; logout-all without login redirects; workspace export, guest export.json and bank details redirect when stale; guest export passes the guard when fresh).
- App/tests/test_logout_everywhere.py: deleted (asserted the old behaviour that /logout ends all devices).
- docs/tasks/0947-logout-devices-fresh-exports.md: Status set to blocked.

## Tests
- `.venv/bin/python -m pytest tests/test_logout_devices.py <login/auth/security/passkey/2FA/privacy/retention/export files> -q --tb=short -x`: `251 passed in 34.99s`
- `.venv/bin/python -m pytest tests/test_0789_settings_subpages.py tests/test_design_settings.py tests/test_invoice_settings.py -q -rs --tb=short -x`: `24 passed in 3.84s`
- Browser and geometry: `tests/test_layout_lint_browser.py`, `test_host_geometry.py`, `test_design_guardrails_browser.py`, `test_0786_settings_geometry_browser.py`: `4 skipped ... could not import 'playwright.sync_api'`. NOT RUN, so 0 skipped is not met.
- `python3 scripts/context_lint.py`: `context lint: OK` (warnings only).

## Screenshots
- None. docs/tasks/screenshots-0947/ not created. Blocked by the missing browser library.

## Deviations
- Done: steps 1, 2 (route, button, strings), 3 (all four routes), 4 (docs, retention line, decision), tests in section 7 (except the admin export, which has no test).
- Left: browser/geometry tests and 390/768/1280 screenshots of /settings/security (UX gate, hard rule 10). No PR opened (brief says none).
- decisions.md was already 6 tokens over the cap on main. Nothing is 90 days old, so nothing moved to the archive. I shortened one long 2026-10-31 line (same rules, fewer words) to pass the lint.
- Bank route: treated as POST /entities/{entity_id}/invoice (admin.py, entity_invoice_details). Test passes with a stale login. Please confirm.
- Brief Status set to blocked, not review, because the UX gate is not met.
- Trailer: Haiku 5.5 used, as the system reminder says (the brief says Sonnet 5.5).

## Questions
- Playwright is not in requirements-dev.txt, and the venv does not have it. Chrome exists at /usr/bin/google-chrome. Adding the playwright package is a new dependency (hard rule 4), so it needs an owner decision line in docs/context/decisions.md first. Do you approve adding it (dev-only)?

## Owner steps left
1. Decide on the playwright dev dependency (question above), and add the decision line.
2. Then the executor reruns the four browser test files with `-rs` (0 skipped), takes the screenshots, and writes the per-width notes here.
