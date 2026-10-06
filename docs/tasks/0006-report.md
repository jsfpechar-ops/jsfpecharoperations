# 0006 report: harden e-mail login after the #288 review

Executor: the orchestrator, on the owner's "implement yourself". Also fixes the test pollution that made `main` red in pytest. Branch `claude/quirky-babbage-tr05vb` (PR #290).

## 1. Files changed

- `App/app/auth.py`: `set_account_email` retires every unused link of the account; `session_is_fresh` (10 minutes).
- `App/app/login_link.py`: `account_for` refuses an address-change link for the address the account already has.
- `App/app/db.py`: `is_unique_violation` (SQLite and Postgres). Used in `routes/admin_accounts.py` (3 places) and `signup.py`.
- `App/app/routes/admin_accounts.py`, `routes/passkeys.py`: fresh login needed to request an address change, add a passkey and delete a passkey.
- `App/app/passkeys.py`, `routes/passkeys.py`: `normalise_credential_id` for the clone-audit lookup.
- `App/app/host_i18n.py`: `auth.error.recent_login` (en, cs).
- `App/scripts/list_accounts_without_email.py` (new, read-only: id and role only).
- `App/tests/test_login_hardening.py` (new, 7 tests); step 0 removed 8 unused imports and variables in 5 test files.

## 2. Commands

- `ruff check app tests tools scripts --select E9,F63,F7,F82,F401,F841`: All checks passed.
- `pytest tests/test_login_hardening.py -q`: 7 passed.
- CI command (`UBYHOST_UBYPORT_ENV=mock UBYHOST_DEPLOYMENT=staging UBYHOST_ENABLE_SCHEDULER=0 pytest tests --cov=app --cov-fail-under=86`): 1 failed, 2798 passed, 4 skipped, coverage 90.39%. The one failure, `test_feed_dns_pinning::test_two_concurrent_fetches_do_not_cross_pinned_addresses`, also fails alone on the untouched tree in this sandbox (DNS or threads); CI decides whether it is real.
- Before the fix to `test_security_hardening.py` the same run had 86 failed and 164 errors, identical on `main` (98be550). Cause: `test_production_hosts_without_totp_are_let_in` leaves `require_login`'s acting user set, then deletes the account, so every later audit insert hit a FOREIGN KEY error. The test now resets it.

## 3. Findings

1 done. 2 done as "fresh login", see deviations. 3 not done, see deviations. 4 done. 5 done (script in `App/scripts/`, not repo-root `scripts/`). 6 done.

## 4. Deviations

- **Finding 2:** no TOTP code field and no notice mail on request. A code field is a template change (stop condition in §3), and a request notice needs a new mail kind. A session signed more than 10 minutes ago is refused with "log out, log in, repeat within 10 minutes". A thief inside the 10 minutes is not stopped; the completion notice to the old address and the audit row stay.
- **Finding 3:** not implemented. The proposed fix (count only real accounts) makes the 429 differ between known and unknown addresses, which lets the login form reveal who uses UbyHost. Logged as K-ML04.

## 5. Questions

None.

## 6. Owner steps left

1. ~~Set login e-mail for every account~~ — **done** (production, Oct 2026; phase 1 of task 0007).
2. Stop logging the query string of `/login/link` in the reverse proxy — **open** (verify live Caddy matches `deploy/lightsail/caddy/Caddyfile.cloudflare`: access logging off; see [0007](0007-post-magic-link-deploy-phase2.md) §C).
