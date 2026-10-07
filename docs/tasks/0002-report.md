# Task 0002 reports (two briefs, one file)

Status: review

This file holds two different **task 0002** executions: magic-link account e-mails (PR #288) and the orchestrator police/downloads/stay-fee bundle (merged into the same PR).

---

## A. Login e-mail on every account (magic-link plan)

### 1. `git diff --stat` (0002 patch only)

```
 App/app/auth.py                   |  50 +++++++++----
 App/app/host_i18n.py              |  50 +++++++++++++
 App/app/mail.py                   |   4 ++
 App/app/mail_notify.py            |  57 +++++++++++++++
 App/app/routes/admin_accounts.py  |  72 +++++++++++++++++++
 App/app/templates/users.html      |  28 +++++++-
 App/tests/test_account_emails.py  | 148 ++++++++++++++++++++++++++++++++++++++
 App/tests/test_claim_mail.py      |   2 +
 9 files changed, 441 insertions(+), 15 deletions(-)
```

Applied via `git am docs/docs/plans/magic-link-passkeys/0001-0002-login-e-mail-on-every-account.patch`.

### 2. Commands (tails)

- Full pytest with `UBYHOST_REQUIRE_BROWSER=1`: **2796 passed**, 2 skipped (`age` not on PATH).
- `test_host_geometry`: **2 passed**, 0 skipped.
- `context lint`: OK.

### 3. Acceptance

- [x] Patch applied; admin `/admin/users` geometry screenshots at 360 / 390 / 1280 px (missing-e-mail banner).

### 4. Owner (after #288 merge)

- [x] Login e-mail on **every** active account (production, Oct 2026; task 0007 phase 1).

---

## B. Police answers, download skeleton, stay-fee row (orchestrator brief)

### 1. Files changed

Police bundle portion (now on `main` via #287 / #288):

```
41 files changed, 990 insertions(+), 2556 deletions(-)  (includes bundle removal)
```

### 2. Commands (tails)

- Full pytest: **2803 passed**, 2 skipped (police agent run).
- Browser + geometry: **25 passed**, 0 skipped.

### 3. Acceptance

- [x] Filing classification and stay-fee PDF row changes covered by pytest.
- [ ] Three stacked PRs — **superseded** by #287 / #288.

### 4. Owner steps left

1. ~~Deploy~~ — **done**. ~~Save and test connection on each property~~ — **done** (0007 §D, Oct 2026).
2. ~~`reconcile_accepted_codes.py` dry run~~ — **done** (0 guests; no `--apply`) (0007 §F).

---

## Combined PR note

See `docs/tasks/combined-magic-link-report.md` for full release scope.
