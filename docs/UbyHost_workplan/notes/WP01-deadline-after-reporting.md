# WP01: Deadline shows the filing time once a stay is reported

Patch: `WP01-deadline-after-reporting.patch` (commit on top of `wpbase`, applies on `wpbase` alone; independent of WP02 and WP03).

## Summary
The deadline cell on the dashboard, the stays list and the stay page now depends on the stay status. Stays not yet finished keep the countdown. A reported stay shows "Reported 12.05. 14:32" (muted) when filed on time, or "Reported 6 h late" / "Reported 2 days late" (neutral grey) when filed after the deadline. A stay with only Czech guests shows no deadline. Cancelled or inactive stays keep the dash. Display only; nothing in filing changed.

## Files changed
- `App/app/reporting.py`: new `filed_at(progress)` and `deadline_cell(progress, check_in)`; `dashboard_rows` adds `deadline_cell`, `deadline_state`, `filed_at`, `late_hours` per row.
- `App/app/templating.py`: global `deadline_cell`.
- `App/app/templates/_components.html`: macro `deadline_badge(cell, tag, extra_class)`.
- `App/app/templates/dashboard.html`: uses the macro; `is-urgent` and the primary button follow the cell level, so a reported stay is no longer highlighted as urgent; "due by" note only while counting down.
- `App/app/templates/reservations.html`: uses the macro.
- `App/app/templates/reservation_detail.html`: uses the macro; the deadline metric is hidden for a Czech-only stay.
- `App/app/routes/admin.py`: removed the now unused `urgency_level` context value.
- `App/app/static/app.css`: `.deadline.done`, `.deadline.neutral`, `.metric-value.deadline.done`.
- `App/app/host_i18n.py`: `deadline.filed_at`, `deadline.filed_late_hours`, `deadline.filed_late_days` (+ `.one`, `.few`), EN and CS.
- `App/tests/test_deadline_after_reporting.py`: new.

## Tests added
`tests/test_deadline_after_reporting.py` (12 tests):
- filing time is the latest `submitted_at` of reportable guests, in Prague time;
- on time, late (whole hours, never "0 h"), countdown for every unfinished status, none for Czech-only;
- EN and CS wording for hours and days (Czech plural forms);
- page tests (dashboard, stays list, stay page): a reported stay past its deadline shows no "overdue"; a stay filed 6.5 h late shows "Reported 6 h late"; an unreported stay past its deadline is still `overdue` (red); a Czech-only stay shows no deadline badge.
The page tests shorten the window to one working day with `monkeypatch` so a stay inside the dashboard's 3-day window can be past its deadline on any weekday; they skip only in a 3-day holiday cluster.

## Test commands and results
From `App/`, with `/tmp/pr230/App/.venv/bin/python -m pytest -q`:
- `tests/test_deadline_after_reporting.py`: 12 passed.
- On `wpbase` + this patch alone: `test_deadline_after_reporting.py test_status_colours.py test_dashboard_queue.py test_host_i18n.py`: 41 passed.
- Related: `test_dashboard_*.py test_deadlines.py test_status_colours.py test_send_controls.py test_plural_helper.py test_signed_in_chrome.py test_p1_review.py test_notification_copy.py test_admin_route_split.py test_deadline_after_reporting.py`: 185 passed.
- Broad, on the final stack WP01+WP02+WP03, in chunks: `test_[a-e]*` 465 passed, 2 skipped; `test_[f-o]*` (no browser e2e) 923 passed, 1 skipped, 1 failed; `test_[p-s]*` 652 passed, 1 failed; `test_[t-z]*` 152 passed.
- The 2 failures also fail on `wpbase` without any patch: `test_host_geometry.py::test_the_month_filter_shares_its_page_edges` (Playwright cannot launch Chromium in this sandbox) and `test_stale_submission.py::test_a_running_batch_without_a_live_claim_becomes_outcome_unknown` (the known PR 230 item 2 issue).
- Guest browser e2e not run (no Chromium here). WP01 does not touch guest pages.
- Ruff (`E9,F63,F7,F82,F401,F841`): all checks passed.

## Deviations from the spec and why
- A stay with status `reported` but no `submitted_at` on any reportable guest (for example imported data) shows no deadline instead of a countdown. A countdown would call it overdue, which is what this WP removes.
- Late by less than one hour shows "1 h late", not "0 h late".
- "Late" uses hours below 48 h and whole days (`late_hours // 24`) from 48 h, matching the existing overdue countdown.
- The late badge carries the exact filing time as a `title` tooltip.
- The dashboard row's red highlight (`is-urgent`, primary button) now follows the cell level too. Without this a reported stay still got a red row. Queue grouping (`queue_groups`, `queue_counts`) is unchanged; it already used `FINISHED_STATUSES`.
- The guide sentence is left to WP03 (key `guide.reporting.filed`, plus `guide.overview.deadline` reworded there). Keeping all guide text in one commit avoids two patches editing the same guide section.
- CSS cache key (`app.css?v=`) not bumped, to avoid conflicts with other WPs that edit the same line in `base.html`, `auth_base.html` and `public_legal_base.html`. Without a bump, an old cached CSS shows the new badges in the plain bold `.deadline` style until the cache expires.

## What Cursor must verify or adapt when applying on the real main
- Bump the `app.css?v=` key in the base templates when merging, together with any other CSS change in the same release.
- Check after PR 230 item 2: the "reported" status still comes only from guests with `submit_state = 'sent'`, and `submitted_at` is still set on accept and on a code 150 duplicate (`guest["submitted_at"] or now`).
- If `routes/admin.py` on main still passes `urgency_level` elsewhere or a template uses it, keep it. It was only used by `reservation_detail.html` on `wpbase`.
- Look at the three pages once in the browser (EN and CS): a reported stay, a late-filed stay, an overdue unreported stay.

## Manual steps for the owner
None.
