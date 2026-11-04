# 0911 report: persistent login, Turnstile only on a new device

Status: blocked

## Done
- Step 1 (session cookie SameSite=lax): `App/app/auth.py`, `attach_session` and `clear_session` now use `samesite="lax"` (2 lines). httponly, Secure and path unchanged. `security.py` CSRF cookie untouched.

## Tests
- Not run. `App/.venv` does not exist and the system Python has no project dependencies (`itsdangerous`, `fastapi`, `pytest` missing). The brief's test command could not start. Step 1 is unverified; do not merge it before the test set passes.
- Test set to run once the venv exists: `tests/test_login_hardening.py tests/test_login_acceptance.py tests/test_security.py tests/test_security_hardening.py tests/test_privacy_first.py tests/test_cookie_inventory.py tests/test_staging_password_login.py`.

## Left (steps 2 to 8, not started)
- Step 2: sliding 30-day session, 90-day cap from `iat`, re-issue after 24 h.
- Step 3: `ubyhost_device` trusted-device cookie and Turnstile skip in `login_submit`.
- Step 4: Turnstile on signup, reset, guest forms unchanged (nothing to do yet).
- Step 5: rotation and "log out everywhere" check.
- Step 6: list of sensitive actions that rely only on the session (not yet checked).
- Step 7: `App/app/cookie_inventory.py` entry and `App/app/retention.py` if required.
- Step 8: `decisions.md` line and `docs/SECURITY.md` session paragraph.
- Tests in `App/tests/test_login_session_persistence.py` (file not created).

## Deviations
- Done: step 1 only. Left: steps 2 to 8. Not started because the test environment is missing.

## Questions for the owner
1. Step 2 says "current_user flow (or the existing middleware)". Which one? Notes: `auth.current_user` already reads `request.state.session_payload`, and `auth.issue_session` sets `iat`. Re-issuing needs a response object, which `current_user` does not have, so the middleware in `App/app/main.py` (`cloudflare_connecting_ip`) looks like the right place. Confirm before I write it.
2. Step 3 leaves the login widget behaviour open (renders but does not block vs. not rendered). Pick one.
3. Login is an e-mail link (`login_link.issue`, `login_submit` sends mail); the "Turnstile on every POST /login" finding matches this. Confirm the device cookie should skip Turnstile on sending the link, not on opening it.

## Owner steps left
- Create the test environment (`App/.venv` with `requirements-dev.txt`) or tell me the command to use.
- Decide questions 1 to 3.
