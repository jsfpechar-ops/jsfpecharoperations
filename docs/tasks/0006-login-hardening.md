# 0006: Harden e-mail login after the #288 review

Status: review
Depends on: none | Base commit: df939db | Branch: task/0006-login-hardening
Executor: Cursor local agent (composer, Kimi or GLM) | Fits one session

## 1. Objective

Close six findings from the review of PR #288, and make CI green again (step 0 below: `main` has been red since #288) (magic link, passkeys, login e-mail change). The two medium ones let a stolen session or a stale link take over or bypass 2FA on an account.

## 2. Context

Rules that apply: SQL only through `App/app/db.py` helpers, Postgres-portable; a schema change is a new `App/app/migrations/` file; no new dependency; new personal-data field needs a line in `App/app/retention.py`; tests from `App/` with `.venv/bin/python -m pytest tests -q`.

The orchestrator did not paste code excerpts. Before editing, open each file at the range given and confirm it matches the finding. If it does not, STOP (§8).

Findings, most severe first (review of commit 98be550; line numbers are approximate):

1. **Medium. Stale `email_change` links survive an address change.** `App/app/auth.py:556-569` (`set_account_email`) and `App/app/login_link.py` `account_for` (~line 128, skips the address-match check for the `email_change` purpose). Scenario: a thief with a session requests a change to their own address; the owner never confirms; the owner or an admin later changes the address to lock the thief out; the thief confirms the still-valid 1-hour link and takes the account.
   - Fix: in `set_account_email`, mark every unused `login_token` of that account as used (`used_at = now`) through a `db.py` helper. At confirm, also require that the token's target address differs from the current address.
2. **Medium. Sensitive changes need only a session cookie.** `App/app/routes/admin_accounts.py:475-514` (e-mail change) and `App/app/routes/passkeys.py:100-135` (passkey add and delete). Scenario: a stolen cookie adds a passkey; passkey login skips TOTP, so 2FA is bypassed for good.
   - Fix: these routes require a fresh proof: the TOTP code via `verify_second_factor` when TOTP is on, otherwise a login younger than 10 minutes (else redirect to login with `next`). Send a notice to the old address when an e-mail change is requested, not only when it completes.
3. **Low-medium. Anyone can burn a victim's link budget.** `App/app/login_link.py:75-90`, `request_blocked` (~line 138), `App/app/routes/admin_accounts.py:94-97`. Three requests per 15 minutes per address, and each one retires the older unused link.
   - Fix: count the per-address budget only for requests that really send mail to an existing account, and let a new link coexist with the previous one until used or expired. Keep the per-IP limit and Turnstile.
4. **Low. SQLite-only duplicate check.** `App/app/routes/admin_accounts.py` at ~549, ~709, ~753 match the text `"UNIQUE constraint failed"`; on Postgres that gives a 500, and in the confirm route the link is already spent.
   - Fix: add a helper in `App/app/db.py` that tells a unique violation for both drivers; use it in all three places.
5. **Low, deploy risk. Migration `0005_email_login.sql` wipes password hashes.** Accounts with a blank e-mail (allowed by migration 0003) cannot log in afterwards.
   - Fix: no migration change. Add a read-only script `scripts/list_accounts_without_email.py` (prints id and role only, no personal data) and a line in the Owner steps below. Do not add a startup backfill.
6. **Low. Clone-detection audit uses the raw id.** `App/app/routes/passkeys.py:166-170` looks the passkey up by the raw `rawId`, so padded or alternative base64 input skips the `passkey_clone_suspected` audit row.
   - Fix: normalise the id the same way `authenticate` does.

Also (no code): strip the query string of `/login/link` from the access logs of the reverse proxy; the secret sits in `?t=`. Owner step.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/auth.py` | edit | Finding 1 |
| `App/app/login_link.py` | edit | Findings 1 and 3 |
| `App/app/db.py` | edit | Findings 1 and 4 (helpers only) |
| `App/app/routes/admin_accounts.py` | edit | Findings 2, 3 and 4 |
| `App/app/routes/passkeys.py` | edit | Findings 2 and 6 |
| `scripts/list_accounts_without_email.py` | create | Finding 5 |
| `App/tests/test_security.py`, `test_stay_fee_detail.py`, `test_stay_fee_downloads.py`, `test_stay_fee_finalize.py`, `test_stay_fee_list.py` | edit | Step 0: remove unused imports and variables only |
| `App/tests/test_login_hardening.py` | create | One test per finding 1, 2, 3, 4, 6 |
| `docs/tasks/0006-report.md` | create | §9 |

No other file may change. Templates change only if finding 2 needs a code field on an existing form; then STOP and ask first, because a template change needs the browser and geometry tests plus screenshots.

## 4. Steps

0. **CI is red on `main` since #288** (step "Lint for runtime errors", `ruff check app tests tools --select E9,F63,F7,F82,F401,F841`, run from `App/`). Eight errors, all in tests: unused `import secrets` in `tests/test_stay_fee_detail.py`, `test_stay_fee_downloads.py`, `test_stay_fee_finalize.py`, `test_stay_fee_list.py`; unused local `login_token` at `tests/test_security.py` lines 51, 96, 133, 147. Remove them (do not skip or disable any test), then confirm the ruff command prints no errors. Make this the first commit so the PR shows green lint.
1. Branch `task/0006-login-hardening` from `df939db`. Run the full test suite once and note the result.
2. For each finding in order, write the failing test first, then the fix. Run only that test file after each.
3. Write `scripts/list_accounts_without_email.py` (read-only, through `db.py`).
4. Run the full suite and `python3 scripts/context_lint.py` from the repo root.

## 5. Do not touch

Migrations (no schema change), `retention.py`, the filing and UbyPort code, legal texts, templates (see §3), any dependency list. Hard rules 2, 4, 5 and 8 of AGENTS.md apply.

## 6. Commands

From `App/`: `.venv/bin/python -m pytest tests/test_login_hardening.py -q`, then `.venv/bin/python -m pytest tests -q`. Also `ruff check app tests tools --select E9,F63,F7,F82,F401,F841` (no output). From the repo root: `python3 scripts/context_lint.py`. Expected: all green, 0 skipped.

## 7. Acceptance

- [ ] Step 0: the ruff command above reports no errors.
- [ ] Finding 1: after `set_account_email`, an old `email_change` link is refused.
- [ ] Finding 2: passkey add, passkey delete and e-mail change are refused without a fresh proof; the old address gets a notice on request.
- [ ] Finding 3: repeated requests for one address do not block the real owner's first link; per-IP limit still works.
- [ ] Finding 4: a unique violation gives the normal "address in use" message on both drivers (test with a fake driver error).
- [ ] Finding 6: a padded `rawId` still writes the clone audit row.
- [ ] Full suite green, 0 skipped; lint passes.

## 8. Stop and ask

Stop, and write the report, if: an excerpt or range does not match the finding; a test fails twice; a new dependency seems needed; a file outside §3 needs a change; §5 would be touched; a step is unclear; you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/0006-report.md` (1,500 tokens at most) and set `Status: review`: files changed, each command with the last 5 lines, §7 ticked, deviations, questions, owner steps left.

## Risk list (for the reviewer)

`App/app/auth.py`, `App/app/login_link.py`, `App/app/routes/passkeys.py`, `App/app/routes/admin_accounts.py`. Auth code: read every line of the diff.

## Owner steps

1. Before the #288 deploy, run `python3 scripts/list_accounts_without_email.py` on the server. For every id listed, open `/admin/users`, and set the login e-mail.
2. In the reverse-proxy config, stop logging the query string of `/login/link`. Reload the proxy.
3. Merge only with `scripts/merge-pr-on-green.sh`; deploy by hand as usual.
