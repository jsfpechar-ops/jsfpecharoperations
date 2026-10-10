# 0033: Shared host filter panels and date-range controls

Status: review
Report: docs/tasks/0033-host-filter-report.md
Depends on: 0032 shared host feedback | Base commit: `6545d094f41b717e33ca053cb74e022fa291f5d6` plus reviewed shared changes | Branch: `task/host-design-staging`
Executor: Luna executor, owner-authorized | Fits one staging session

## 1. Objective

Implement the approved expandable filters and shared day/month date controls on Stays, Invoices, Stay fees and Guest register. Keep existing query scope, exports, permissions, legal records and no-JavaScript GET filtering intact.

## 2. Context

- Apply the approved behavior in `docs/DESIGN.md` under “Filters on demand”, and the inspected route inventory in `docs/plans/host-filter-audit.md`.
- Stays defaults to unbounded All dates with Active status; the closed summary is All properties · Active. Upcoming/current, Past, All and Archived remain explicit views. Only an explicitly applied custom date range appears in the summary. Invoices retain All dates · All properties. A date range counts once.
- Keep an inline expandable panel. Edits remain a draft until Apply filters; Cancel restores applied values. Keep page actions, view navigation and Export outside the panel. Without JavaScript, labelled native GET controls remain visible and usable.
- Stays and Guest register use one Stay dates range control, with labelled From/Until dates and one calendar. Either bound may be open; Clear dates clears both. Apply dates stages a draft. Escape/outside dismissal discards unconfirmed date edits; reversed bounds are announced and cannot apply.
- Invoices and Stay fees use the selected twelve-month grid with year arrows and soft coral selection. Invoices allow All dates; Stay fees require a reporting period. Keep server bounds, Prague current month and essential fee context visible.
- Exact current anchors:

```html
<form method="get" action="/reservations" class="filters panel" data-auto-submit>
```

```html
<form method="get" action="{{ filter_action }}" class="filters panel list-filter" data-auto-submit role="search">
```

```html
<form method="get" action="/housebook" class="filters panel" data-auto-submit>
```

```python
        date_range = "custom" if (date_from or date_to) else "upcoming"
```

```js
  function initAutoFilters() {
```

Keep `App/app/routes/admin.py` changes within the Stays GET handler. Dashboard GET policy is owned by the dashboard agent.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/templates/reservations.html` | Edit | Stays summary/panel/range and explicit guest-form copy label |
| `App/app/templates/_list_filter.html` | Edit | Shared month panel, grid, summary and draft actions |
| `App/app/templates/_date_range.html` | Add | Shared progressively enhanced day-range control |
| `App/app/templates/housebook.html` | Edit | Guest register panel/summary and clearer Delete label for the existing soft-archive action; keep exports/table intact |
| `App/app/routes/admin.py` | Targeted edit | Stays GET fallback only: absent dates default to `all` |
| `App/app/host_i18n.py` | Targeted edit | Filter/date/copy labels plus keys queued by root for dashboard/properties agents |
| `App/tests/test_host_filter_panels_browser.py` | Add | Real browser query, interaction and geometry coverage |
| `App/tests/test_stay_fee_list.py` | Edit | Preserve fee month bounds/security while checking draft-only steppers |
| `App/tests/test_stays_empty_workspace.py` | Edit | Assert the current disclosure, native GET fields and primary Apply label |
| `App/tests/test_wp33_gates.py` | Edit | Prove default All stays is unbounded; keep Past exclusion scoped to Upcoming |
| `docs/tasks/0033-host-filter-panels.md` | Edit | This scoped implementation brief |
| `docs/tasks/0033-host-filter-report.md` | Add | Evidence and owner steps |

Shared `app.js` and `host.css` remain feedback-agent owned until root releases them. Dashboard/property templates belong to their agents. No other file may change.

## 4. Steps

1. Preserve each route’s actual query names and behavior: Stays `apartment`, `status`, `from`, `to`, `range`; invoices `month`, optional `apartment`, `status`, `q`; Stay fees retain their required month and current property/status fields; Guest register retains `apartment`, `from`, `to`. Keep saved views and export scope. In the register, label the existing guest soft-archive action Delete and explain it moves the row to Archived; preserve its POST route and Restore action.
2. Put the filter trigger, server-derived applied summary and page actions outside the closed panel. Keep all native fields and a normal GET submit available without JavaScript. Apply submits the complete form once; Cancel restores initial applied values.
3. Add one day-range component to Stays and Guest register. Use separate draft dates until Apply dates. Clear both dates together; block and announce reversed dates. Preserve inclusive overlap semantics. Keep panel and date-picker dismissal/focus behavior keyboard and touch usable.
4. Render twelve localized months with year arrows and existing server min/max bounds. All dates is available only to Invoices; Stay fees remain required. Year navigation and month selection remain draft until Apply filters.
5. Change only the Stays GET default: when no valid range and no date bound is present, use `all`; explicit range tabs and custom date URLs keep their scope. Do not alter owner/status/archive SQL predicates.
6. Add EN/CS Chromium coverage for real query submission, draft/apply/cancel, no-JS GET fallback, open-ended/cleared/reversed dates, Escape/outside and focus behavior, month bounds and one-request behavior. Update route/list tests for the progressive filter panel, draft-only month steppers, and unbounded Stays default without weakening ownership or archive checks. Measure control geometry at 360, 390, 471, 760, 850 and 1280 CSS px; save screenshots.
7. Run the focused and full test commands in §6 and repository context lint. Record actual output, screenshot paths, acceptance and deviations in §9; set this brief to `Status: review` when ready for root review.

## 5. Do not touch

Do not change database/schema, filing/reporting states, retention, legal register columns, invoice validation, Stay-fee mutations, permissions, export scope, guest-facing forms, endpoints, dependencies, secrets, production deployment, merge or push. Do not alter dashboard policy or property controls. No other auto-submit form may change.

## 6. Commands

From `App/`:

```sh
UBYHOST_BROWSER_EXECUTABLE=/usr/bin/chromium UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_host_filter_panels_browser.py tests/test_host_geometry.py tests/test_list_filter.py -q
.venv/bin/python -m pytest tests -q
```

Both browser runs execute with zero skips. From the repository root:

```sh
python3 scripts/context_lint.py
```

## 7. Acceptance

- [x] Empty Stays query includes past/current/future active stays; summary is All properties · Active. Explicit Upcoming/Past/All/Archived, property/status/archive/custom/saved-view scope remains correct.
- [x] One Stay dates control supports both bounds, open-ended and clear cases. Reversed bounds cannot apply. Escape/outside dismisses unconfirmed picker edits and restores focus.
- [x] Apply dates only stages; Apply filters sends exactly one GET. Cancel leaves URL/results unchanged. No-JavaScript native controls work.
- [x] Invoice optional and Stay-fee required month semantics and bounds are preserved; the twelve-month grid is keyboard accessible.
- [x] Stay-fee reporting context and Guest register legal table/export behavior remain intact.
- [x] Guest-register Delete posts to the existing archive route and leaves the guest row retained with `archived_at` set; it does not permanently delete the record.
- [x] EN/CS labels, controls and popovers fit at all §4 widths; touch targets are at least 44px, filter lanes have no overflow or clipping, and screenshots/query evidence are reported.

## 8. Stop and ask

Stop and report if a named anchor is missing, the reviewed 0032 integration changes a scoped anchor, a test fails twice, an out-of-scope edit or new dependency is needed, or query/legal semantics conflict. Do not substitute prototype evidence for application browser checks. Do not push, merge, deploy, use SSH or change secrets.

## 9. Report

Write `docs/tasks/0033-host-filter-report.md` (1,500 tokens at most) with the changed files, commands and final five output lines, §7 checked, screenshots/geometry/query evidence, deviations/questions, and remaining owner steps. Set this brief to `Status: review` when the scoped implementation is ready.

## Risk list

Stays default/query preservation; one canonical range value; optional versus required month semantics; no-JavaScript fallback; filter JavaScript interaction with unrelated forms; saved views; copy-label target; required browser checks executing with zero skips.

## Owner steps

1. Review the EN/CS screenshots, query behavior, geometry and test output.
2. Root reviews the scoped staging diff. Owner handles any merge or deployment separately.
