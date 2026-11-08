<<<<<<< HEAD
# 1006 report: direct bookings host states

Status: review

## Files changed

`App/app/booking_direct.py` (decline under `db.immediate()` + `lock_key("booking_site_dates", apartment)` with a CAS `UPDATE ... WHERE status IN ('requested','expired')`, `rowcount != 1` -> `not_confirmable`; new `_mail_declined`, kind `site_booking_refunded`, key `site_booking:<id>:declined`), `App/app/booking_manage.py` (`can_retry` only for card rows, `status_key`), `App/app/templates/booking_site_setup.html` (badge uses `status_key`), `App/app/routes/payments.py` (direct flash on host cancel), `App/app/booking_webhook.py` (host confirm text `host_text_direct` for direct), `App/app/host_i18n.py` (5 keys EN + CS), `App/tests/test_booking_direct_0998.py` (4 tests).

## Commands

- Brief §6 (8 files): `144 passed, 2 warnings in 5.64s`.
- `UBYHOST_REQUIRE_BROWSER=1 pytest tests/test_layout_lint_browser.py tests/test_booking_site_host_browser.py tests/test_booking_manage_browser.py -rs`: `13 passed in 244.04s`, 0 skipped.
- One-off seeded browser run (not committed): requested, expired, confirmed (paid) and declined direct rows; layout guard, no side scroll, no small targets at 390; then host cancel of the paid direct row shows the new flash and the row is `cancelled`.

## §7

- [x] Decline after confirm returns `not_confirmable`, booking stays `paid` (`test_decline_after_confirm_keeps_paid`).
- [x] Declined direct row shows "Zrušeno", no "Retry refund" (screenshots `/mnt/project-files/pr803-review/after1006/booking-site-{390,768,1280}.png`).
- [x] Host cancel of a direct booking flashes the new text (asserted in the seeded browser run).
- [x] Declined guest gets one mail (`test_decline_mails_guest`).
- [x] Each new key appears twice in `host_i18n.py`.

## Deviations

- `test_direct_confirm_host_mail_not_paid` monkeypatches `booking_webhook._host_email` (the fixture apartment has no legal entity, so no host mail was sent and the test would pass vacuously).
- Running the browser tests rewrote committed screenshots in `docs/tasks/screenshots-0819/0821/0822`; reverted, not committed.
- The after-cancel 390 screenshot caught a page transition mid-fade; the flash text was asserted in the DOM.

## Questions

None.

## Owner steps

None.
=======
# 1020 report (executor, Haiku 5.5): blocked

Branch: claude/eloquent-mendel-vd8mfi (the owner's branch; the brief header names task/1020-backup-daily-s3, not used). Nothing committed or pushed: acceptance is not met.

## 1. Files changed (git diff --stat)

- App/tests/test_pg_backup_scripts.py (+45)
- deploy/lightsail/scripts/backup.sh (+20)
- deploy/lightsail/README.md (15 lines changed)
- docs/LIGHTSAIL.md (17 lines changed)
- docs/OPERATIONS.md (11 lines changed)
- docs/context/known-issues.md (+1)
- docs/tasks/1020-backup-daily-s3-ping-failclosed.md (Status: todo -> blocked)
- docs/tasks/1020-report.md (new)

## 2. Commands (last lines of output)

- `bash -n deploy/lightsail/scripts/backup.sh`: no output (pass).
- Guard order grep: "not running" (l.22) < `backup_data.sh` (l.26) < "UBYHOST_DATABASE_URL is unset" (l.33) < "stopped during the backup" (l.37) < `curl -fsS` (l.67) (pass).
- `cd App && .venv/bin/python -m pytest tests/test_pg_backup_scripts.py ...`: NOT RUN. `App/.venv` does not exist and system python3 has no pytest.
- `shellcheck -S error ...`: shellcheck not installed (reported, not run).
- `python3 scripts/context_lint.py`: FAIL. `ERROR docs/context/known-issues.md: ~2557 tokens > cap 2500`. The file was 10000 bytes at HEAD; the added K-BKP-S3-403 line (244 bytes) is the likely cause. Other lines are WARN only.
- Secrets grep: no output (pass).
- Step 11 grep: exactly the 7 expected matches (pass).
- Drive cron check: 0 added or removed lines contain `backup-gdrive.sh >>` (pass). The plain `git diff | grep -c` form prints 1 only because an unchanged context line is shown.

## 3. Section 7 acceptance

- [x] Guard order
- [ ] Three new tests and old tests pass (not run: no test environment)
- [x] Step 11 grep: seven matches
- [x] Drive cron unchanged (0 changed lines)
- [x] Secrets grep empty
- [ ] Lint passes (FAIL: known-issues.md token cap)
- [ ] shellcheck (not installed)

## 4. Deviations

- Every step anchor was found verbatim; all edits applied in one pass.
- The step 11 grep's expected "Drive" check reads 1 on the plain diff because of a context line; the changed-line count is 0.

## 5. Questions

- Accept the known-issues.md token cap failure, or compact that file? Compacting is outside this brief.
- Where is the App venv (`App/.venv`) to be set up? Creating it needs a dependency decision.

## 6. Owner steps left

- The brief's "Owner steps" (crontab change, healthchecks.io check, `.env` ping URL, S3 lifecycle rule). Not run by the executor.

## Fix-1 results (1020-fix-1)

- Files changed in this step: `docs/tasks/1020-backup-daily-s3-ping-failclosed.md` (Note line under Status), `docs/tasks/1020-report.md`, `docs/tasks/1020-fix-1.md` (Status).
- Venv: `App/.venv` created; `requirements-dev.txt` alone lacks runtime deps (`requests` missing in conftest), so `requirements.txt` was also installed from the repo's own pinned file. Deviation, no new dependency.
- `cd App && .venv/bin/python -m pytest tests/test_pg_backup_scripts.py -q --tb=short -x -rs 2>&1 | tail -30` last line: `13 passed in 0.41s` (0 skipped).
- `python3 scripts/context_lint.py 2>&1 | tail -5` last line: `context lint: OK`.
- `git status --short | grep -c '\.venv' | tail -3` prints `0`.
- §7: K-BKP-S3-403 count 0 [x]; backup tests 0 skipped [x]; lint OK [x]; commit and clean tree [pending commit].
>>>>>>> origin/main
