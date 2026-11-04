# 0947: log out of all devices, fresh login for exports and bank details

Status: review
Depends on: 0911 (merged) | Base commit: current main | Branch: claude/project-thread-4ocgy1
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens
Length: about 50 lines.

## 1. Objective

Owner (Josef 2026-11-04) wants all three follow-ups to 0911 done. Sessions now last 30 days, so: (a) separate "log out this device" from "log out of all devices"; (b) require a recent login for data exports and for changing bank details; (c) record the `ubyhost_device` cookie in the retention docs.

## 2. Context

- `POST /logout` in `App/app/routes/admin_accounts.py` currently calls `auth.end_all_sessions(account["id"])` (bumps `session_version`, which also invalidates the `ubyhost_device` cookie). So today logging out on one phone logs out every device.
- `auth.session_is_fresh(request)` (10 min since login) exists; users failing it get `_back("/settings/security#settings-security", err=_flash(request, "auth.error.recent_login"))`. The message already says to log out and in again, so no new copy.
- Exports: `POST /settings/workspace-export` and `GET /guests/{guest_id}/export.json` (routes/exports.py), plus the admin user export in routes/admin_customers.py (grep `export`).

## 3. Files

App/app/routes/admin_accounts.py, routes/exports.py, routes/admin_customers.py, the route that saves the host's bank account (grep `bank_account\|iban` in routes/*.py), the security settings template (grep `settings/security` in templates), host_i18n.py plus host_vi_i18n.py for new labels, App/app/retention.py, docs/privacy/RETENTION.md, docs/SECURITY.md, docs/context/decisions.md (one short line).

## 4. Steps

1. `/logout` clears only this browser's session cookie (`auth.clear_session`), keeps the `ubyhost_device` cookie, audits `logout`. Do NOT bump `session_version`.
2. New `POST /account/logout-all` (login required, CSRF as other POSTs): `auth.end_all_sessions`, audit `logout_all`, clear cookie, redirect `/login?notice=logged_out`. Add a button "Log out of all devices" on the security settings page (`/settings/security`) with one short line of help under a "?" per the no-fine-print rule. Add en, cs, vi strings. Light mode, no new JS.
3. Add the `session_is_fresh` guard (same redirect and message) to: workspace export, guest export.json, admin user export, and the route that changes bank account/IBAN. Do not touch other routes. For GET export.json, redirect to the security page the same way.
4. `retention.py`: add the personal-data line for `ubyhost_device` (account id + random id, lifetime 30 days, cookie only, nothing stored server-side). Mirror it in RETENTION.md. SECURITY.md: two sentences on logout vs logout-all and which actions need a fresh login.

## 5. Do not touch

Login, Turnstile, session lifetimes, payments consent/requests, guest pages.

## 6. Commands

From App/: `.venv/bin/python -m pytest <test-map rows: login/auth/security, exports, retention/privacy> -q --tb=short -x 2>&1 | tail -30`. If .venv is missing: `python3 -m venv .venv && .venv/bin/pip install -q -r requirements-dev.txt`.
Template change: also run the browser and geometry tests for the security settings page (0 skipped) and `test_layout_lint_browser.py`, and save 390/768/1280 screenshots of /settings/security in docs/tasks/screenshots-0947/.
From repo root: `python3 scripts/context_lint.py | tail -30` (decisions.md cap 2200 tokens: compact if needed).

## 7. Acceptance

New tests in App/tests/test_logout_devices.py: logout keeps another device's session valid; logout-all invalidates both sessions and the device cookie; exports and bank-detail change redirect with the recent-login error when the session is older than 10 min and succeed when fresh; unauthenticated logout-all redirects to login.

## 8. Stop and ask

If the bank-account route is unclear, or a test needs a template beyond the security page.

## 9. Report

docs/tasks/0947-report.md, short: routes guarded, tests, screenshots seen per width. Commit with trailers "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>" and "Claude-Session: https://claude.ai/code/session_01Cjmb7PxcYfFQVaBLXznbes"; push to claude/project-thread-4ocgy1; do not open a PR.
