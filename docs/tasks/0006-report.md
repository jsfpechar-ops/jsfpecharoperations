# 0006 report: harden e-mail login after the #288 review

Executor: the orchestrator, on the owner's "implement yourself". Branch `claude/quirky-babbage-tr05vb` (PR #290).

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
- `pytest tests -q`: 86 failed, 2549 passed, 4 skipped, 164 errors. The pristine tree gives the identical 250 failing ids and 2542 passed (the difference is the 7 new tests). See K-T01.

## 3. Findings

1 done. 2 done as "fresh login", see deviations. 3 not done, see deviations. 4 done. 5 done (script in `App/scripts/`, not repo-root `scripts/`). 6 done.

## 4. Deviations

- **Finding 2:** no TOTP code field and no notice mail on request. A code field is a template change (stop condition in §3), and a request notice needs a new mail kind. A session signed more than 10 minutes ago is refused with "log out, log in, repeat within 10 minutes". A thief inside the 10 minutes is not stopped; the completion notice to the old address and the audit row stay.
- **Finding 3:** not implemented. The proposed fix (count only real accounts) makes the 429 differ between known and unknown addresses, which lets the login form reveal who uses UbyHost. Logged as K-ML04.

## 5. Questions

Should a follow-up brief fix K-T01 (test pollution)? It hides every regression on `main` once lint is green.

## 6. Owner steps left

1. On the server, from `App/`: `.venv/bin/python scripts/list_accounts_without_email.py`; set an e-mail for each id in `/admin/users` before the #288 deploy.
2. Stop logging the query string of `/login/link` in the reverse proxy.
