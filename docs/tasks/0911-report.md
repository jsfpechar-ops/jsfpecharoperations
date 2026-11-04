# 0911 report: persistent login, Turnstile only on a new device

Status: review

## Lifetimes
- `ubyhost_session` (remember-me): 30 days without use. Each day of use re-signs it with the same login time (`iat`). Absolute cap: 90 days after sign-in, then sign in again. Non-remember 12 h path unchanged.
- `ubyhost_csrf`: follows the session constant, now 30 days.
- `ubyhost_device` (new, HttpOnly, Lax, Secure on HTTPS): 30 days, renewed at each successful login. Valid only while its stored `sv` equals the account's `session_version`.

## What changed
- `App/app/auth.py`: session cookie SameSite=lax (set and clear); sliding 30 d / 90 d cap; `refresh_session_cookie`; device cookie `attach_device` and `trusted_device`.
- `App/app/main.py`: middleware re-signs the session cookie (once a day). Skipped when the response already sets or clears the cookie.
- `App/app/routes/admin_accounts.py`: `_finish_login` sets the device cookie; `login_submit` skips Turnstile only for a trusted device whose IP is not rate-limited. Other paths unchanged (staging password path, signup, guest, reset).
- `App/app/cookie_inventory.py`, `App/app/guest_uk_i18n.py`: `ubyhost_device` row (EN/CS, guest DE/ES/FR, UK); session and CSRF lifetimes updated.
- `docs/SECURITY.md` (auth row and one paragraph), `docs/context/decisions.md` (one `[auth]` line).
- Tests: `App/tests/test_login_session_persistence.py` (new, 12 tests); updated `test_security.py`, `test_accounts.py` (SameSite), `test_privacy_first.py`, `test_cookie_inventory.py`.
- Template `login.html`: not changed. It has no submit-blocking JS, so the widget renders and the server skips the check for trusted devices.

## Tests
- `.venv/bin/python -m pytest tests/test_login*.py tests/test_auth*.py tests/test_security*.py tests/test_cookie*.py tests/test_privacy_first.py -q` (from App/): `127 passed`, 0 skipped.
- Brief's list plus signup and new file: `121 passed`, 0 skipped.
- Environment: `App/.venv` had no project packages; installed `requirements.txt` and `requirements-dev.txt` into it.

## Sensitive actions (not changed)
- Gated by a fresh session (`session_is_fresh`): 2FA setup (`/account/2fa/setup`), login-address change (`/account/email`), passkey add (`/account/passkeys`, options) and delete.
- Gated by a current authenticator code: `/account/2fa/disable`.
- Session only (no fresh or code check found): payment services and requests (`/payments/...`), workspace export (`/settings/workspace-export`), guest export (`/guests/{id}/export.json`), admin user export and e-mail (admin role only). `/account/2fa/move` not checked.

## Deviations and questions
- Session refresh runs only on requests where `current_user` ran, so a page that does not load the user does not extend the session.
- Privacy test literal: `ubyhost_device` added to the strictly-necessary set, because every first-party cookie row is in it. Owner to confirm.
- `App/app/retention.py` not changed: the test does not require a line, but the rule for new personal-data fields may. The cookie holds account id and a random id. Owner to decide.
- No "log out everywhere" button exists; SECURITY.md describes the session_version bump only.
- Browser and geometry tests not run: no template change.

## Owner steps left
- Confirm the two questions above (privacy set, retention line) before merge.
