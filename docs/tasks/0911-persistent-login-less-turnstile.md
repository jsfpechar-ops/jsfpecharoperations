# 0911: persistent login, Turnstile only on a new device

Executor: Haiku 5.5. Read AGENTS.md, docs/context/executor.md, this brief, and only the files named here.
Owner ask (Josef 2026-11-04): hosts jump between apps (phone) and get logged out and face Turnstile again. Make it smooth: no re-login or Turnstile for about a month.

## Findings (already checked, do not re-investigate)
- `App/app/auth.py`: login always sets `remember=True` (routes/admin_accounts.py `login_submit`), so the cookie lives 400 days (`SESSION_REMEMBER_MAX_AGE`). Not sliding. The cookie is `SameSite=strict` (`attach_session`, `clear_session`), so a link from another app (mail, push, Stripe return, in-app browser handoff) arrives without the cookie and the host sees the login page. That is the "logged out when switching apps" bug.
- `turnstile.verify(..., "host_login")` runs on every `POST /login` (routes/admin_accounts.py, also the staging password path).

## Do
1. Session cookie `SameSite=lax` (set and delete in `attach_session`, `clear_session`). Keep httponly, Secure, path. CSRF cookie in `security.py` stays strict unless a test shows lax is needed; POSTs are still CSRF-checked.
2. Lifetime: `SESSION_REMEMBER_MAX_AGE` = 30 days, sliding. In `current_user` flow (or the existing middleware that sees `request.state.session_payload`), when the signed cookie is older than 24 h since last refresh, re-issue it on the response with a fresh timestamp but the SAME `iat` (login time). Absolute cap: 90 days from `iat`, then log in again. Non-remember 12 h path stays as is. CSRF max-age follows the constant; check it still works.
3. Trusted device: new signed cookie `ubyhost_device` (httponly, Secure, lax, 30 days, refreshed on each successful login), payload = account id + random id, signed with the existing serializer machinery. Set in `_finish_login`. In `login_submit` (not the staging path), skip `turnstile.verify` only when the cookie is valid for an account matching the submitted e-mail AND the IP is not rate-limited (`login_link.request_blocked`). Otherwise Turnstile as today. The login page template must not render the widget for such a device is NOT required; keep it simple: the widget still renders, server accepts an empty token only for trusted devices. If the widget blocks submit without a token in the template/JS, make the widget auto-run and not block when the cookie exists (look at templates/login.html; minimal change).
4. Turnstile stays unchanged on signup, password reset, guest forms, admin and everything else.
5. Rotate: `_finish_login` already issues a fresh session; confirm no old session id survives. Logout clears the session cookie (keep `ubyhost_device`). "Log out everywhere" = existing `session_version` bump; if a host-facing button exists keep it, do not build new UI. Add `ubyhost_device` to also be cleared by that action (bump a field inside the device payload check: device cookie valid only if its stored `sv` equals the account's `session_version`).
6. Sensitive actions: do NOT add new flows. Only verify that change-password/e-mail, payments settings, data export and admin already require what they required before (existing PIN/passkey/2FA), and list in the report which ones rely only on the session. Do not change them.
7. Privacy: add `ubyhost_device` to `App/app/cookie_inventory.py` (purpose "Recognises this device so login needs no security check", lifetime 30 days, surface host) and `App/app/retention.py` if the privacy test requires it. No tracking.
8. Docs: one `decisions.md` line `[auth] 2026-11-04 persistent 30-day sliding session, 90-day cap, SameSite lax, trusted-device cookie skips login Turnstile`. Update docs/SECURITY.md session section in one paragraph.

## Tests (add to App/tests/test_login_session_persistence.py)
- Session cookie is SameSite=lax, httponly, Secure when secure cookies on.
- Cookie older than 24 h is re-issued with same `iat`; past 30 days idle or 90 days from `iat` rejected.
- Login without device cookie and without token fails with Turnstile on (monkeypatch `turnstile.required`); with valid device cookie for that e-mail passes; device cookie for another e-mail or stale `sv` fails.
- Signup still requires Turnstile.
Run test-map row: login/auth/security + `test_privacy_first.py test_cookie*.py`. Template change: also login browser/geometry tests, one 390 px screenshot.

## Report (docs/tasks/0911-report.md, short)
Lifetimes, what changed, which sensitive actions rely only on the session.
