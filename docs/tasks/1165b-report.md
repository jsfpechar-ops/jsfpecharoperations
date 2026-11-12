# 1165b report: host mail copy for TTLock kinds and docs

Status: review

## 1. Files changed (`git diff --stat b9fb8566..HEAD`)

```
 App/app/host_i18n.py                |  2 ++
 App/app/host_vi_i18n.py             |  1 +
 App/app/mail_notify.py              |  6 ++++++
 App/tests/test_ttlock_lock_setup.py | 17 +++++++++++++++++
 docs/TTLOCK.md                      |  5 +++--
 docs/plans/ttlock-door-codes.md     | 14 +++++++-------
 6 files changed, 36 insertions(+), 9 deletions(-)
```

Commits: `790b974c` (step 2, copy and test), `3c5dde17` (step 3, docs). This report and the brief status line are committed after them.

## 2. Commands (last lines of output)

- Step 2, test set (`test_ttlock_lock_setup.py`, short notifications, alert language, host i18n, go host i18n, em dashes): `72 passed, 1 warning in 5.18s`
- Step 3, `grep -c lock_setup`: `docs/plans/ttlock-door-codes.md:6`, `docs/TTLOCK.md:1`
- Step 4, revert-bite:
  - `BITES 1 reason key lock_setup known`
  - `BITES 1 config reads as no_account`
  - `git diff --stat` empty afterwards (files restored)
- §6.2 door-code mail tests: `154 passed, 1 warning in 2.17s`
- §6.3 test-map row (`test_door_code*.py test_ttlock*.py test_smart_locks_page.py`): `360 passed, 2 skipped in 9.82s`
- §6.4 ruff (`--select E9,F63,F7,F82,F401,F841`): `All checks passed!`
- §6.5 `git status --short`: clean, no stray `App/config`
- Context lint (repo root): `context lint: OK`
- Brief's final ruff and test commands: ruff `All checks passed!`; the test set above, `72 passed`.

## 3. Acceptance (§7)

- [x] Step 4 printed two `BITES` lines.
- [x] `lock_setup` reason names the gateway and the TTLock app; cs and vi differ from en (test asserts).
- [x] `config` reads as `no_account`; `bug` and `code_missing` read as the generic text; raw token kept (test asserts).
- [x] No em dash in the new copy (`test_no_em_dashes.py` passes).
- [x] Commands 1 to 5 pass; `git diff --stat` shows only the §3 files.

## 4. Deviations

- Step 1 skipped. The branch `task/1165b-errcode-host-copy` was already checked out (the brief expected `task/1165-errcode-review-fixes`), so `git switch -c` was not run. The 1165 check `grep -c LOCK_SETUP App/app/ttlock.py` returned `1`, not `2`: the constant is defined once and `test_ttlock_lock_setup.py` exists; the merge commit `b9fb8566` confirms 1165 is in. Continued on that basis.
- Scripts were written to the scratchpad, not `/tmp`, per the session instruction.
- The first attempt at the step 2 script failed with a syntax error because I dropped the closing `''')` line of the test append; nothing was applied (no partial edit). Fixed and rerun once.
- §6.3 shows 2 skipped: `tests/test_property_navigation_browser.py:20` and `tests/test_ttlock_setup_0954_browser.py:13`, both `No module named 'playwright'` in this venv. They are environment skips, not caused by this change. No template or CSS changed, so rule 7 does not apply. Not installed (no new dependency).
- §9 asks to set `Status: review` in the brief; done (line 3 of `docs/tasks/1165b-errcode-host-copy.md`), although §3 lists no other file to change.
- No PR opened and nothing pushed, as the lead instructed.

## 5. Questions

- None open. A native reader should check the cs and vi `lock_setup` sentences (brief risk list).

## 6. Owner steps left

1. Push the branch and open the PR (not done here).
2. After CI is green on the PR holding 1165 and 1165b, merge with `scripts/merge-pr-on-green.sh <PR number>`.
