# 0034: Quiet host dashboard

Status: review

## 1. Objective

Implement the approved Quiet overview in the existing host dashboard. Keep
the change to `App/app/templates/dashboard.html`, dashboard-specific helpers in
`App/app/reporting.py`, and the handler at `App/app/routes/admin.py:273–325`.
Add focused coverage in `App/tests/test_host_quiet_dashboard.py` and
`App/tests/test_host_quiet_dashboard_browser.py`. Do not change filing state,
deadline calculations, scheduler behavior, shared CSS/JS, or `host_i18n.py`; send
new translation keys to the shared owner. Preserve truthful known guest counts
and filed deadline states in the compact rows. Its reservation-input typing
accepts both the actual `sqlite3.Row` query result and mapping-based policy
fixtures; type-only updates must not alter query, state, or dashboard logic.

## 2. Context

- `docs/DESIGN.md` § Dashboard: four small white semantic count cards; neutral
  zeros; Prague today; current stays and arrivals within 30 days; five unique
  stay rows total; older real overdue/failed work gets priority; counts precede
  truncation.
- `docs/DESIGN.md` § Interaction feedback and § Action geometry: quiet hover
  tint and visible keyboard focus on real interactive targets; shared action
  geometry and one-line Open label.
- `docs/HOST_APP_DESIGN.md` § Dashboard and
  `docs/plans/host-control-polish.md` §§ 9, 13: no photos, status/task context,
  Open plus More in a consistent action track, retain useful setup/legal/feed
  states, and staging review before any production action.

## 3. Files

- `App/app/templates/dashboard.html`
- Dashboard-specific policy helpers in `App/app/reporting.py`
- Dashboard handler only, `App/app/routes/admin.py:273–325`
- `App/tests/test_host_quiet_dashboard.py`
- `App/tests/test_host_quiet_dashboard_browser.py`
- Dashboard regressions in `App/tests/test_deadline_after_reporting.py`,
  `App/tests/test_overview_headcount.py`, `App/tests/test_host_language.py`,
  and dashboard selectors only in `App/tests/test_signed_in_chrome.py`
- `docs/tasks/0034-report.md`

## 4. Steps

- `App/app/routes/admin.py:273` starts the dashboard handler. It currently calls
  `reporting.dashboard_rows`, partitions via `reporting.queue_groups`, counts
  through `reporting.queue_counts`, then slices each bucket independently.
  Replace those per-section slices with a single candidate set and a five-row
  total allocation; counts must be computed from the complete candidate set.
- `App/app/reporting.py:472` partitions queue buckets, `:510` computes count
  cards, and `:704` builds/sorts dashboard rows using a 21-day forward and
  45-day backward system-date window. Preserve default behavior for callers
  outside the dashboard. Add a dashboard-scoped way to include current stays,
  arrivals through Prague today + 30 days, and older unresolved overdue/failed
  stays, while excluding routine far-future and old completed stays.
- `App/app/templates/dashboard.html:4` defines `queue_table`; it currently
  repeats four bucket sections, uses a host-task card, and provides an existing
  row menu with Add guest, guest-form URL, and archive action. Replace the row
  presentation with compact date/property/task/deadline context and aligned
  Open and More actions. Preserve the actual guest-form URL and menu actions.
  Use the existing `guest_count` macro so known headcounts remain visible and
  unknown empty counts stay quiet. Render the existing deadline badge for
  overdue and filed-on-time/filed-late states; never convert a filed state into
  overdue.
  Keep the onboarding, setup warning, empty/sync/no-feed, and actionable
  calendar controls that are needed to operate the service.
- Existing `dashboard.row.open_stay` is at
  `App/app/host_i18n.py:1132` and `:2639`; shared owner should translate it to
  “Open” / “Otevřít”. New copy keys must be sent to the shared owner.

1. Review the existing reporting and dashboard date/task behavior at the
   anchors above. Keep date calculations in Prague local time.
2. Build the full candidate set, compute counts before display truncation, and
   show no more than five unique rows with Needs action first, current stays
   before upcoming arrivals, then nearest arrivals.
3. Keep dashboard styling scoped to the template and use existing host tokens.
   Retain the setup, onboarding, empty, sync, and no-feed actions that support
   operating the host account.
4. Add policy tests for the 30-day boundary, five-row total, older unresolved
   urgency, and current-stay ordering. Add browser/geometry coverage and EN/CS
   screenshots at the required widths.
5. Record exact changes, checks, and screenshot paths in the report. Root
   reviews before any Render staging deployment; production remains manual.

## 5. Do not touch

Do not edit shared CSS/JS or translations. Do not change filing progress,
deadlines, scheduler behavior, legal logic, guest data handling, reservations
filters, or unrelated dashboard expectations. Do not deploy to production.

## 6. Commands

From `App/` run the focused Python policy and dashboard browser tests with the
repository virtual environment. Required Chromium runs use
`UBYHOST_BROWSER_EXECUTABLE=/usr/bin/chromium UBYHOST_REQUIRE_BROWSER=1` and
save screenshots under the review capture directory. From the repository root
run `python3 scripts/context_lint.py` after the brief and report are complete.

## 7. Acceptance

- Four small white semantic cards: Needs action amber, Waiting for guests
  taupe, Ready to send muted blue, Overdue red only when positive; zero counts
  remain neutral. Counts reflect the full candidate set before row truncation.
- At most five unique stay rows total across Needs action and Current & coming
  up, ordered by actual urgency; older unresolved overdue/failed work is not
  hidden by the date horizon or cap. Routine rows are current or arrive within
  30 days inclusive, using Prague today. Routine far-future incomplete stays
  do not appear. Show a concise link to extra actionable stays and View all
  stays when appropriate.
- Each row contains date range, property, one truthful task/status/deadline,
  Open, and More. Open and More occupy one aligned action track. More keeps
  existing actions and links to the reservation's real guest-form URL.
- Hover and keyboard focus feedback applies to the actual row links/actions;
  no nested links or whole-row keyboard trap. Test EN and CS at 360, 390, and
  1280px with browser/geometry coverage and screenshots; zero skipped checks.
- Add meaningful tests for the inclusive 30-day boundary, the five-row total
  cap, and older urgent work. Preserve existing filing tests and neighboring
  dashboard expectations unless the approved owner behavior replaces them.
  Update the dashboard selector in the Czech action-copy test and assert the
  Quiet stat-card classes and positive/neutral-zero state in signed-in chrome.
- No production deploy. Root reviews; staging is Render only after its review.

## 8. Stop and ask

Stop if the approved behavior requires changing filing state, deadline
calculation, or scheduler behavior, or if a change outside the listed files is
needed. Send the exact conflict and affected anchor to the owner.

## 9. Report

Write implementation results, test outcomes, screenshot paths, and known
limitations to `docs/tasks/0034-report.md`. Set this brief to `Status: review`
when the scoped implementation is ready for root review.
