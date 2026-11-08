# 0997 report: same patterns elsewhere (executor: Haiku 5.5)

Status: review
Branch: claude/project-thread-d67hsx (no push, no PR, per owner deviation)

## Files changed

- `App/app/host_i18n.py`: 12 strings changed, en `/` to ` of `, cs `/` to ` z ` (commit c50b584, step 1).
- `App/tests/test_notification_copy.py`: 3 expectations changed to `0 of 2` / `0 z 2` (commit de0d2d7, step 2).
- `docs/tasks/0997-report.md`: this file.

## Commands (last 5 lines)

- `.venv/bin/python -m pytest tests/test_*_i18n.py tests/test_no_em_dashes.py tests/test_copy_cleanup.py tests/test_notification_copy.py tests/test_flash_literals.py -q --tb=short -x`: `57 passed, 1 warning in 2.86s`
- `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_host_*.py tests/test_host_geometry.py -q -rs --tb=short -x`: `245 passed, 1 warning in 685.88s`, 0 skipped.
- `python3 scripts/context_lint.py`: `context lint: OK` (WARN lines only, not failures).

## Section 7 acceptance

- [x] Step 1 grep: no `notification.reason.*` or `dashboard.focus.*` line with `/%(expected`.
- [x] Section 6 commands pass, 0 skipped.
- [x] Steps 3 and 4 answered below.

## Step 3: stale-alert check (no edit)

Yes, it resolves, but keyed on check-in date, not `date_to`. `claim.py` (reminder sweep, about lines 812-816) resolves `guest_incomplete_checkin:<id>` once forms are complete or `date_from < today`. Gap not verified: the sweep only visits `status = 'active'` reservations, so an alert on a stay that leaves `active` first may stay open.

## Step 4: tooltips (no edit)

Present: `App/app/templates/dashboard.html` line 99 has `title="{{ bar.title }}"` on `a.bar`.

## Deviations

- Step 1 leaves 5 matching lines untouched, not 6 as the brief says: `mail.reminder_host.subject` (en, cs), `hint.missing_guests` (en, cs), `flash.guests.saved` (cs). The brief's list is correct; the count was off by one. No en `flash.guests.saved` exists.
- `test_send_controls.py` asserts `Guest forms: 1/3.` (`hint.missing_guests`, not in scope): left as is.
- `test_static_versions.py --write` not run: no static file changed.
- No template, CSS or guest-page change, so no screenshots (UX gate not applicable).

## Questions

- Step 3 gap above: should the sweep also resolve alerts for stays that are no longer `active`?

## Owner steps left

- Push `claude/project-thread-d67hsx` and open the PR when ready (not done here).
