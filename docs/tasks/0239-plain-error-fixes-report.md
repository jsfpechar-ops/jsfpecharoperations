# 0239 report

Status: review

## Files changed
- App/app/host_i18n.py, App/app/host_vi_i18n.py (steps 1-3)
- App/app/alerts.py (step 4)
- App/app/templates/_host_alerts.html (step 5)
- App/app/templates/reservation_detail.html (step 6)
- App/tests/test_plain_fixes_0239.py (new, step 7)
- App/tests/test_notification_copy.py, App/tests/test_alert_language.py, App/tests/test_send_controls.py (step 8, wording only, plus one non-wording change at test_notification_copy.py:147 as the reviewer allowed)

## Commits
7e7c0f8 steps 1-3, 1cb8db2 step 4, 3c05e82 step 5, 7d5f8d0 step 6, 03dd9cb step 7, 98169a8 step 8.

## Checks
- Step 1 counts: host_i18n.py 50, host_vi_i18n.py 25.
- `action_for({'kind':'feed_error','apartment_id':3})` gives `('notification.action.calendar', '/apartments/3?view=bookings#calendars')`.
- Step 5 grep: notification-link count 2.
- §6 command 1 (test_alert_stack.py first): `186 passed, 3 warnings in 6.90s`.
- §6 command 2: `context lint: OK`. Its WARN lines name other open briefs, not this change.

## Deviations
- Step 8 failures came from wording only. Test 147 in test_notification_copy.py changed to `"action_label_key" in text`, as the reviewer allowed.
- The DB-order "no such table" failures disappear when test_alert_stack.py runs first (per reviewer). They were pre-existing.
- Snippets for steps 2, 4 and 5 were written to /tmp/claude-0/, outside the repo. Not committed.

## Not run
- Browser, geometry and 390 px screenshot checks (hard rule 7). The brief's §6 does not list them. Reviewer to decide whether they are needed for the template change in step 5 and step 6.

## Questions
- Do you want the browser/geometry set and 390 px screenshots run for _host_alerts.html and reservation_detail.html before merge?

## Owner steps left
- None.
