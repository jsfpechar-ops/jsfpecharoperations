# 0239 report

Status: blocked

## Done
- Steps 1 to 7 committed: 7e7c0f8 (steps 1-3), 1cb8db2 (step 4), 3c05e82 (step 5), 7d5f8d0 (step 6), 03dd9cb (step 7).
- Step 1 counts matched: host_i18n.py 50, host_vi_i18n.py 25.
- `action_for({'kind':'feed_error','apartment_id':3})` returned `('notification.action.calendar', '/apartments/3?view=bookings#calendars')`.
- `tests/test_plain_fixes_0239.py`: 4 passed.
- `_host_alerts.html` grep count of notification-link: 2. `tests/test_alert_stack.py`: 13 passed.

## Not done
- Step 8 (update old-wording assertions): not started; 11 failures in 3 files.
- §6 commands, §7 acceptance, screenshots: not run.
- Left: step 8, then rerun §6 command 1 and command 2.

## Test results (last lines)
- `tests/test_host_i18n.py`: `3 failed, 11 passed`. The same 3 fail on the base i18n files (`git stash` check): `sqlite3.OperationalError: no such table: apartment` / `user_account`. Environment DB setup, not the copy.
- Copy-pinning set (`test_notification_copy`, `test_alert_language`, `test_send_controls`): `11 failed`. Failures: (a) old-wording assertions, e.g. `test_alert_language.py:106,134,143,174,225` and `test_send_controls.py:729,751`; (b) `test_notification_copy.py:147` asserts `'notification.open_stay' in` the template source, a check that step 5 changed; (c) `no such table: guest` in several tests, the same DB-setup issue as above.

## Deviations
- Step 2 and step 4 temp snippets were written to /tmp/claude-0/ (not the scratchpad). They are outside the repo and not committed.
- Pre-existing DB failures (see above) were not treated as caused by this change.

## Questions
- Are the `no such table` failures a known need for a DB setup step when a test file runs alone? Brief §6 does not mention one.
- `test_notification_copy.py:147`: should step 8 change its expected string to the new action rendering?

## Owner steps left
- None.
