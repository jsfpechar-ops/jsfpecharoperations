# WP10: Admin Operations page

## Summary
New read-only page `/admin/operations` for platform admins. It shows, across all workspaces, a count plus at most 50 rows for: filings needing attention, reports stuck in `running`, calendars needing attention, background job health, mail outbox problems and open host alerts by kind. No guest field is selected, nothing is decrypted, and no feed URL or mail recipient is read. The scheduler now records `job_last_ok:<job_id>` in `settings` on every successful run.

First of a stack: WP13, WP11 and WP12 patches build on this one (apply in order WP10, WP13, WP11, WP12).

## Files changed
- `App/app/admin_ops.py`: new. The aggregate queries behind the page.
- `App/app/routes/admin_accounts.py`: `GET /admin/operations`, behind `_require_admin`.
- `App/app/templates/admin_operations.html`: new page.
- `App/app/scheduler.py`: `job_intervals()` (one source for the intervals, also used by `start()`), `JOB_LAST_OK_PREFIX`, `_job_ok` writes `job_last_ok:<id>`.
- `App/app/host_i18n.py`: `_ADMIN_OPERATIONS_STRINGS` block, EN and CS.
- `App/app/templates/base.html`: admin menu link "Operations".
- `App/app/templates/_host_navigation.html`: `operations` added to the settings group.
- `App/app/templates/users.html`: `id="user-<id>"` on each row, so the page can link to a workspace.
- `App/tests/test_admin_operations.py`: new.

## Tests added
`tests/test_admin_operations.py` (6): host gets 403; signed-out visitor is redirected to login; admin sees all sections and the rendered HTML (EN) contains none of the demo seed's surnames, first names or document numbers while every seeded guest is in a failed state, plus the CS page renders; filings are one row per stay with the worst state; `_job_ok` stores the last success and late jobs are flagged; failed mail is listed without the recipient.

## Test commands and results
- `python -m pytest -q tests/test_admin_operations.py`: 6 passed.
- Related: `tests/test_scheduler.py tests/test_host_i18n.py tests/test_incident_register.py tests/test_admin_route_split.py tests/test_accounts.py tests/test_no_tracking.py tests/test_ui_consistency.py tests/test_signed_in_chrome.py` plus the new file: 126 passed.
- Broad run at this commit, three chunks: `tests/test_[a-f]*.py` 606 passed, 2 skipped; `tests/test_[g-o]*.py` (without the browser e2e) 774 passed, 1 skipped, 1 failed; `tests/test_[p-z]*.py tests/test_guest_browser_e2e.py` 789 passed, 4 skipped, 1 failed. Both failures also fail on `wpbase` without this patch: `test_host_geometry.py::test_the_month_filter_shares_its_page_edges` (Playwright in this sandbox) and `test_stale_submission.py::test_a_running_batch_without_a_live_claim_becomes_outcome_unknown` (passes alone, fails in that chunk; order dependent).
- Ruff (`E9,F63,F7,F82,F401,F841`): all checks passed.

## Deviations from the spec and why
- There is no `rejected` submission state. Per-stay state is derived from the guests: `outcome_unknown` (current submission is outcome unknown), `rejected` (guest `submit_state = 'blocked'`), `retry_cap` (an `error` guest with `submit_attempts >= SUBMISSION_MAX_AUTO_ATTEMPTS`, the retry bound), `error`. The PR 230 interrupted-batch retry has no state of its own; batches still `running` after 30 minutes are listed separately as "stuck".
- "No successful sync for more than 3 hours": no last-success time is stored per feed. `last_sync_at` moves on every attempt, so a feed is listed when `last_status` is not `ok`, or when it is `ok` and `last_sync_at` is older than 3 hours (then it is the last success).
- Links go to `/admin/users#user-<id>` (the workspace row). A stay link would only open inside impersonation, so the stay id is shown as text.
- The filings query scans `guest` (the `submit_state` index was dropped on purpose in `db.py`). Admin-only and fine at current size; noted rather than re-adding the index.
- Feed `last_error` and outbox `last_error` are not shown: they can contain a feed URL with its secret or a recipient address.

## What Cursor must verify or adapt when applying on the real main
- `admin_accounts.py` import list and route placement (before `POST /admin/incidents`). If WP04 or another WP adds an admin page-view audit, apply it to this route too.
- `host_i18n.py`: the new block sits just before `def normalise_language`. Other WPs add blocks at the same spot; resolve conflicts by keeping all blocks.
- `base.html` admin menu: WP10 and WP11 each add one link after "Security incidents".
- If WP06 moved the scheduler to its own process, `_job_ok` still writes to the shared database, so the page works unchanged. Check that `job_intervals()` matches the intervals WP06 uses.
- Re-check guest submission states on main in case PR 230 follow-ups added a new one.

## Manual steps for the owner
None. Job times show "Never" until each job has run once after deploy.
