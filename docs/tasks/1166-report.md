# 1166 report: door-code host notices

Status: review

## 1. Files changed (`git diff --stat 83e0495b..HEAD`)

- App/app/mail_notify.py (reason `support`, `config` maps to it, `moved_failed` and `pin_unverified` variants)
- App/app/door_codes.py (`_tell_host_unverified`, `moved_failed` mail on a `lock_setup` move failure)
- App/app/host_i18n.py, App/app/host_vi_i18n.py (reasons, card, two mails; en, cs, vi)
- App/tests/test_door_code_host_notices.py (new, 15 cases)
- App/tests/test_ttlock_lock_setup.py, App/tests/test_alert_language.py (wording and `STORED_KINDS`)
- docs/TTLOCK.md, docs/plans/ttlock-door-codes.md

## 2. Commands (SQLite, from App/ unless noted)

- Step 4 set: `tests/test_door_code_host_notices.py tests/test_ttlock_lock_setup.py tests/test_0280_short_notifications.py tests/test_alert_language.py tests/test_host_i18n.py tests/test_go_host_i18n.py tests/test_no_em_dashes.py`
  - `87 passed, 1 warning in 5.33s`
- Step 5 bites: see section 4.
- Door-code and TTLock row: `tests/test_door_code*.py tests/test_ttlock*.py tests/test_smart_locks_page.py`
  - `375 passed, 2 skipped in 9.58s` (both skips: `No module named 'playwright'`)
- Ruff `--select E9,F63,F7,F82,F401,F841` on app and tests: `All checks passed!`
- Final set (orchestrator list): `55 passed, 1 warning in 3.88s`
- `python3 scripts/context_lint.py` (repo root): `context lint: OK`
- `git status --short`: empty after the bites and commits; no App/config.

## 3. Section 7 acceptance

- [x] Step 5 printed four `BITES` lines.
- [x] Unconfirmed code after three lookups: one warning card and one `pin_unverified` mail, no PIN; a lookup that works in time gives none.
- [x] First `lock_setup` move failure: one `moved_failed` mail, support in cc, reason shown; later failures none; hourly retry kept; busy cloud none.
- [x] `config:-4063` and `config:30008` read as the `support` reason (names `config.SUPPORT_EMAIL`) in en, cs, vi.
- [x] `lock_setup` reason has no colon or second sentence in en, cs, vi and still names the TTLock app.
- [x] No em dash in new copy (`test_no_em_dashes`); card titles at most 60 characters (`test_0280_short_notifications`).
- [x] Commands 1 to 5 pass; `git diff --stat` shows only the section 3 files.

## 4. Revert-bite lines

- `BITES unverified notice | 1 failed in 0.34s`
- `BITES move mail | 1 failed, 4 passed in 0.46s`
- `BITES config reason | 1 failed, 6 passed in 0.46s`
- `BITES lock_setup copy | 1 failed, 9 passed in 0.45s`

## 5. Deviations

- Brief scripts were extracted from the brief into the scratchpad directory, not `/tmp`, per the session rule. Contents unchanged.
- Step 1 `git switch -c` was skipped: the branch already existed and was checked out.
- The door-code row shows 2 skips for missing playwright. The brief calls these expected. Browser tests were not run with playwright installed (no new dependency added).
- Commits are `1166 step 2`, `step 3`, `step 4`, `step 6: docs`. Step 5 has no commit (bites restored with git checkout).

## 6. Questions

- None.

## 7. Owner steps left

1. Push the branch and open a draft PR.
2. After CI is green (including the Postgres leg), merge with `scripts/merge-pr-on-green.sh <PR number>`.
3. Orchestrator: update docs/context/status.md (lint warns it is behind by 7 commits touching App/).
