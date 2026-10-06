# 0002 login e-mail on every account — report

Status: review

## 1. `git diff --stat main` (last lines)

```
 App/app/auth.py                   |  50 +++++++++----
 App/app/host_i18n.py              |  50 +++++++++++++
 App/app/mail.py                   |   4 ++
 App/app/mail_notify.py            |  57 +++++++++++++++
 App/app/routes/admin_accounts.py  |  72 +++++++++++++++++++
 App/app/templates/users.html      |  28 +++++++-
 App/tests/test_account_emails.py  | 148 ++++++++++++++++++++++++++++++++++++++
 App/tests/test_claim_mail.py      |   2 +
 docs/tasks/0002-account-emails.md |  45 ++++++++++++
 9 files changed, 441 insertions(+), 15 deletions(-)
```

Applied via `git am docs/docs/plans/magic-link-passkeys/0001-0002-login-e-mail-on-every-account.patch` (commit `773bc29`).

## 2. Command output (tails)

**`pip install --require-hashes -r App/requirements.lock`** — exit 0 (no new deps in this task).

**`App/.venv/bin/python -m pytest tests -q`** (with `UBYHOST_REQUIRE_BROWSER=1`):

```
2796 passed, 2 skipped, 7 warnings in 470.96s (0:07:50)
SKIPPED [2] tests/test_backup_data.py:28: age/age-keygen not on PATH
```

**`tests/test_host_geometry.py`** (same env):

```
2 passed, 1 warning in 3.44s
```

**`python3 scripts/context_lint.py`**:

```
next free: task 0003 | migration 0005
context lint: OK
```

## 3. §7 Acceptance

- [x] Patch applied cleanly
- [x] Full pytest green; context lint OK (2 skips pre-existing: `age` not on PATH)
- [x] `test_host_geometry` 0 skipped; `/admin/users` screenshots at 360, 390, 1280 px (missing-e-mail banner visible)
- [x] PR open on `task/0002-account-emails`

### Screenshots

| Width | File |
|------:|------|
| 360 | `/opt/cursor/artifacts/screenshots/0002-admin-users-360.png` |
| 390 | `/opt/cursor/artifacts/screenshots/0002-admin-users-390.png` |
| 1280 | `/opt/cursor/artifacts/screenshots/0002-admin-users-1280.png` |

## 4. Deviations

- Plan path on disk is `docs/docs/plans/magic-link-passkeys/` (not `docs/plans/…`).
- Admin Users screenshots taken with Playwright + local uvicorn (same pattern as geometry tests); acceptance gate stubbed like pytest `conftest` so the page renders.

## 5. Questions

- None.

## 6. Owner steps

1. Review this PR; merge with `scripts/merge-pr-on-green.sh` when CI is green.
2. Deploy to production.
3. Open `/admin/users` and set login e-mail on every account (including admin) until the missing-e-mail banner is zero.
4. Only then start tasks 0003+0004 (e-mail link login + passkeys) from `HANDOFF.md`.

## Risks

- Admin must set e-mails before 0003 deploy guard runs.
- E-mail change notices go to old and new addresses (transactional mail).
