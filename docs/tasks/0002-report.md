<<<<<<< HEAD
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
=======
# 0002 report

Status: review

## 1. Files changed

`git diff --stat main...task/0002c-ubyport-severity` (last lines):

```
 docs/context/rules.md                       |    1 +
 docs/context/status.md                      |    3 +-
 docs/tasks/0002-bundle.patch                | 2289 ---------------------------
 docs/tasks/0002-police-downloads-stayfee.md |  128 ++
 41 files changed, 990 insertions(+), 2556 deletions(-)
```

## 2. Commands

`git am docs/tasks/0002-bundle.patch`:

```
Applying: Keep the page visible when a download starts
Applying: Show the town office one row per facility
Applying: Stop treating late filings as failures and stop resending refused records
Applying: Load the error severities and repair guests stuck on 112
```

`cd App && .venv/bin/python -m pytest tests -q` (tail):

```
-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
2803 passed, 2 skipped, 7 warnings in 485.48s (0:08:05)
```

`pytest tests/test_guest_browser_e2e.py tests/test_host_geometry.py tests/test_wp28_geometry.py -q` (tail):

```
-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
25 passed, 1 warning in 178.91s (0:02:58)
```

Known-main trio (tail):

```
FAILED tests/test_host_i18n.py::test_language_endpoint_sets_cookie_and_rejects_open_redirects
FAILED tests/test_mail_failed_alert.py::test_the_send_loop_stores_the_code_and_renders_a_name
FAILED tests/test_notification_copy.py::test_present_rebuilds_stay_title_with_czech_dates
3 failed, 1 warning in 0.73s
```

`python3 scripts/context_lint.py` (tail):
>>>>>>> origin/main

```
next free: task 0003 | migration 0005
context lint: OK
```

## 3. §7 Acceptance

<<<<<<< HEAD
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
=======
- [x] `git am` applied four commits cleanly.
- [x] Full suite green apart from the three known failures; browser and geometry files: 25 passed, **0 skipped**.
- [x] Downloads: `test_skeleton_loaders.py` (`DOWNLOAD_PATHS`, template coverage); stay-fee PDF/CSV: `test_stay_fee_adjustment.py` (no “Úprava výpočtu”, register line). See deviations for manual §6.
- [x] Stay-fee PDF one row per facility (pytest above).
- [ ] Three stacked PRs open with screenshots at 360/390/1280 on 0002a and 0002b — PRs opened; screenshots not attached (deviation).
- [x] `context lint: OK`.

## 4. Deviations

- **§6 manual browser** (`./run.sh`): not run end-to-end in this cloud VM. Automated coverage: skeleton download regex tests, stay-fee PDF/CSV assertions, guest browser e2e + geometry (0 skipped). Playwright screenshot script failed outside pytest env (session cookie); one partial 360 px capture is not suitable for PR.
- Full suite: **2 skipped** (`test_backup_data.py` — `age` not on PATH); unchanged from environment, not browser/geometry.

## 5. Questions

None.

## 6. Owner steps left

1. Merge **0002a → 0002b → 0002c** with `scripts/merge-pr-on-green.sh`.
2. Deploy production.
3. **Save and test connection** on each property (loads police severities).
4. Run `reconcile_accepted_codes.py` (dry run), verify guests in UbyPort, then `--apply` if correct.
5. September stay fees: **Start correction** if office still needs v3 layout.
6. Optional: repeat §6 download clicks on staging/production and attach screenshots to PRs if you want visual proof beyond CI.
>>>>>>> origin/main
