# 0947 report (Haiku executor)

Status: review

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
- Browser and geometry (run with `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium-1243/chrome-linux64/chrome`): `tests/test_layout_lint_browser.py`, `test_host_geometry.py`, `test_design_guardrails_browser.py`, `test_0786_settings_geometry_browser.py`: `29 passed in 343.69s`, 0 skipped.
- `python3 scripts/context_lint.py`: `context lint: OK` (warnings only).

## Screenshots (docs/tasks/screenshots-0947/, full page, lang=en, logged in as a test host)
- settings-security-390.png: "Signed-in devices" row sits first in the card, "Log out of all devices" button on the right, "?" under the title on its own line. Passkeys and 2FA rows look the same, so this is the existing help-tip layout. Button fits on one line. Nothing overflows; no horizontal scroll visible.
- settings-security-768.png: same row, button on the right, wider card. Clean, no wrapping of the button.
- settings-security-1280.png: desktop with sidebar. Card sits left at about 720 px, the button is on the right of the row, and the "?" again sits on its own line under the title. Nothing overlaps.
- Finding (not fixed, existing pattern): the "?" help tip drops under the label at all widths, same as Passkeys. Not a regression from this change.

## Deviations
- Done: steps 1, 2 (route, button, strings), 3 (all four routes), 4 (docs, retention line, decision), tests in section 7 (except the admin export, which has no test).
- Left: nothing for 0947. Browser tests and screenshots done in the second pass. No PR opened (brief says none).
- decisions.md was already 6 tokens over the cap on main. Nothing is 90 days old, so nothing moved to the archive. I shortened one long 2026-10-31 line (same rules, fewer words) to pass the lint.
- Bank route: treated as POST /entities/{entity_id}/invoice (admin.py, entity_invoice_details). Test passes with a stale login. Please confirm.
- Brief Status is review: browser tests 0 skipped and screenshots taken after the Playwright install.
- Trailer: Haiku 5.5 used, as the system reminder says (the brief says Sonnet 5.5).

## Questions
- None open. Playwright was installed locally in App/.venv by the coordinator (not a repo dependency).

## Owner steps left
- Merge the PR when opened by the orchestrator (no PR from the executor). Production deploy is manual.
