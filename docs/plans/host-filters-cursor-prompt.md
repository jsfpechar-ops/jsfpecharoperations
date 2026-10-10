# Cursor prompt: approved filters, range control and explicit links

Owner requested implementation of the approved designs on 2026-10-10. Codex
remains the orchestrator under AGENTS.md. Run the already prepared shared
feedback step first, then this scoped UI/filter step; wider dashboard policy
and other page layouts remain the ordered tasks in host-control-polish.md.

Paste into a fresh Cursor chat after 0032:

You are the executor. Read AGENTS.md. Create and execute the following brief
as `docs/tasks/0033-host-filter-panels.md`. If 0033 is already occupied, 0032
is not completed on your base, or an anchor is missing, stop and report it.
Do not implement from a prototype without this scoped brief.

<<<BRIEF
# 0033: Shared filter panels, one date range and explicit guest links

Status: todo
Depends on: 0032 | Base commit: 6545d094f41b717e33ca053cb74e022fa291f5d6 plus reviewed 0032 | Branch: task/0033-host-filter-panels
Executor: Cursor local agent (composer, Kimi or GLM) | Fits one session

## 1. Objective

Implement the approved Filters disclosure on Stays, Invoices, Stay fees/detail
and Guest register, with one date-range control on day-range pages and the
chosen twelve-month grid on month pages. Make dashboard Open and guest-form
copy wording explicit, preserving the actual target, routes and protections.

## 2. Context

Light-only, existing tokens/components, no new dependency or schema. Controls
share heights/columns and readable EN/CS labels. Draft editing, Apply/Cancel,
visible applied summary and GET URLs are required. Never change filing,
permissions, export scope, paid/status meanings, snapshots or retention.
Feedback/copy handling from 0032 remains the shared implementation.

Source-of-truth preview: `docs/plans/host-control-review.html`, pages stays,
invoices, fees, fee-detail, register; `rangeField`, `drawRange`, `rangeLabel`,
`filters`, `summary`, month calendar. Copy styles/components, not its fixtures,
fake current date, local demo actions or limited prototype query behavior.

Owner wording: dashboard button **Open**; guest registration URL action **Copy
guest form link** (CS: Otevřít; Kopírovat odkaz na formulář hosta). Copy messages,
PINs and identifiers keep their specific names. One Stay dates control replaces
two visible From/Until controls. Default Stays summary **All properties · Active**;
custom dates only, no implicit preset date/ellipsis. The owner's “all the time”
is interpreted as an unbounded **All dates** default; Upcoming/current and Past
remain explicit views. Invoice summary remains **All dates · All properties**.

Exact anchors:

`App/app/templates/reservations.html`:

```html
<form method="get" action="/reservations" class="filters panel" data-auto-submit>
```

```html
    <input type="date" id="from" name="from" value="{{ date_from }}">
```

`App/app/templates/housebook.html`:

```html
<form method="get" action="/housebook" class="filters panel" data-auto-submit>
```

`App/app/templates/_list_filter.html`:

```html
<form method="get" action="{{ filter_action }}" class="filters panel list-filter" data-auto-submit role="search">
```

`App/app/routes/admin.py`, GET Stays fallback only:

```python
        date_range = "custom" if (date_from or date_to) else "upcoming"
```

`App/app/static/app.js`:

```js
  function initAutoFilters() {
```

`App/app/templates/dashboard.html`:

```jinja
{{ t('dashboard.row.open_stay') }}
```

## 3. Files

| Path | Action | Scope |
|---|---|---|
| `App/app/templates/reservations.html` | Edit | Stays disclosure/summary/range, single canonical range input, Clear/default URLs and explicit guest-form copy label |
| `App/app/templates/_list_filter.html` | Edit | Shared month disclosure/grid, draft controls and summaries |
| `App/app/templates/_date_range.html` | Add | Reusable progressively enhanced labelled From/Until inputs and one range trigger/popover |
| `App/app/templates/housebook.html` | Edit | Same disclosure and day-range component; preserve legal table and export context |
| `App/app/templates/dashboard.html` | Edit only actions | Open text and explicit guest-form copy action in More; preserve all other row actions |
| `App/app/templates/reservation_detail.html` | Edit only invitation label | Guest-form URL copy wording; no form/state/layout changes |
| `App/app/static/app.js` | Edit scoped filters/ranges/months | Draft/Apply/Cancel, calendar behavior and existing saved-view serialization compatibility |
| `App/app/static/host.css` | Edit scoped host controls | Shared geometry, calendar/range styling, responsive/keyboard behavior |
| `App/app/host_i18n.py` | Targeted edit | EN/CS labels/summaries; dedicated guest-form copy key, no global Copy replacement |
| `App/app/routes/admin.py` | Edit GET fallback only | Default empty Stays query to All dates; preserve explicit ranges, owner SQL scope and operations |
| `App/app/list_filter.py` | Read only | Existing month/default/status/query model and bounds |
| `App/app/templates/_components.html` | Read only | Existing copy/menu/export contracts |
| `App/tests/test_host_filter_panels_browser.py` | Add | Browser/query/geometry coverage below |
| `App/tests/test_host_geometry.py` | Read only | Existing browser/fixture conventions |
| `App/tests/test_list_filter.py` | Read only | Existing period semantics |
| `docs/plans/host-control-review.html` | Read only | Approved visual/interaction reference |
| `docs/tasks/0033-host-filter-panels.md`, `0033-report.md` | Create/update | Brief, evidence and review status |

No other file may change. If existing tests require changes for the approved
default, identify the exact files/expectations in the report and stop for a
scoped amendment rather than weakening or silently skipping checks.

## 4. Steps

1. Confirm completed 0032, anchors and scope. Add shared filter enhancement to
   the existing plain JS bundle. Remove `data-auto-submit` only from the named
   genuine result forms; preserve automatic behavior in other forms.
2. Keep Filters, concise applied summary, navigation, primary page actions and
   Export outside the closed panel. Show all form fields and ordinary GET submit
   without JS. Filters exposes expanded state/controls; opening/closing alone
   never submits or changes results. Essential facility/required reporting
   period context stays visible on Stay-fee pages.
3. Retain original applied values separately from panel edits. Apply filters
   submits one GET form once with the existing canonical names. Cancel restores
   applied values and closes; Reset uses the correct page defaults. Save view,
   restored views, reload and back navigation retain the canonical query. Do not
   submit duplicate `range` values from a hidden input and named submit button.
4. Day filters use `_date_range.html`: one labelled Stay dates trigger and one
   popover containing From/Until selectors and a calendar. First pick selects
   From and advances to Until; either bound can be edited alone. Apply dates
   changes the panel draft only. Clear dates clears both draft bounds. Escape
   and outside dismissal discard unconfirmed picker edits; Cancel discards the
   entire panel draft. Reversed bounds have a readable announced error and a
   disabled Apply dates action. Do not silently swap dates or submit an invalid
   range. Preserve current inclusive overlap semantics and native-input fallback.
5. Use one month grid with twelve months, year arrows and soft coral selected
   state. Invoices allow All dates; Stay fees require a period. Keep backend
   period limits/defaults and actual Prague current month; no hardcoded 2026.
   Month-arrow and grid changes remain draft until Apply filters. Keyboard
   navigation, Escape and focus restoration work; selection stays on screen.
6. For Stays with no explicit range/date query, change only the GET fallback
   from upcoming to all. Do not alter SQL owner/status/archive protections.
   Existing Upcoming/current and Past links retain their scope; custom dates
   serialize as `range=custom`. Reset/Clear returns to All dates and default
   property/status. Existing saved views/explicit URLs still take precedence.
7. Summary is server-derived from the applied query/context. Stays: property
   and status, adding bounds only for explicit custom ranges. Single From or
   Until gets that label; never use an ellipsis. Preset-generated bounds do not
   appear as chosen filters. Count a date range once. Invoices and Stay fees
   keep their distinct optional/required period wording and status/search fields.
8. Dashboard Open text uses the existing destination/return link. Add Copy guest
   form link to More only when an authorized usable invitation exists. Use the
   existing guest URL contract, including slug/token and reservation ID:
   `public_base_url ~ '/l/' ~ (reservation.permalink_slug or reservation.permalink_token) ~ '/' ~ reservation.id`.
   Preserve Add guest, Open guest form and guarded archive/other existing menu
   actions. Use 0032's actual copy outcome handling; never copy the host detail
   URL, regenerate tokens or store/log the link. Give existing invitation copy
   controls in Stays/detail the same explicit label, not a global generic Copy
   rename. Keep copied messages/PINs/identifiers semantically distinct.
9. Verify shared action heights, readable labels and no overflow at EN/CS 360,
   390, 471, 760, 850 and 1280px. Dates fit one control; calendar targets are
   at least 44px on touch; popovers remain inside the viewport. Scoped JS must
   not affect POST forms, exports, report operations or unrelated auto-filters.
10. Run §6, capture both languages and write the report. Open a draft PR if
    available. No merge, main push, SSH, secret or deployment operation.

## 5. Do not touch

No database/reporting/worker/claim/UbyPort/retention/invoice validation changes.
Do not change the legal Guest register table, explicit export scope, report
result/receipt states, guest-facing forms, permissions, address requiredness,
dashboard queue policy or other page layouts. No new dependency or endpoint.

## 6. Commands

From `App/`:

```sh
.venv/bin/python -m pytest tests/test_host_filter_panels_browser.py tests/test_host_geometry.py tests/test_list_filter.py -q
.venv/bin/python -m pytest tests -q
```

Both pass with browser/geometry executing and zero skips. From the repository
root, `python3 scripts/context_lint.py` passes. Record normal CI/format output.
The orchestrator checked the prototype only, not this application implementation.

## 7. Acceptance

- [ ] Default Stays includes past/current/future active stays; explicit preset,
  property/status/archive/custom/saved-view scope remains correct.
- [ ] Default Stays summary All properties · Active; invoice summary All dates ·
  All properties; dates appear only after an explicit applied range.
- [ ] One day-range control, open-ended/clear/reversed-range cases, keyboard,
  Escape/outside dismissal and focus restoration work.
- [ ] Apply dates edits a draft; Apply filters issues exactly one GET request;
  Cancel changes neither URL nor results; restored/saved queries round-trip.
- [ ] Month grid has twelve choices and correct page-specific bounds/All dates;
  Stay-fee required periods and reporting context remain visible.
- [ ] Export parameters/legal columns remain intact and scope explicit; no POST
  is triggered by filtering, calendar selection or reset.
- [ ] Dashboard Open and Copy guest form link are exact, localized and target
  the correct authorized form URL; other copy targets/actions/guards are intact.
- [ ] No-JS GET controls work, no shared-label/button clipping or document overflow,
  and EN/CS screenshots/geometry evidence are included at required widths.

## 8. Stop and ask

Stop and report if a named anchor is missing, dependencies/base drift, a test
fails twice, a dependency/out-of-scope edit seems needed, the real guest URL
cannot be obtained through its current authorized contract, or query/filing
semantics conflict. Never replace application checks with prototype evidence.

## 9. Report

`docs/tasks/0033-report.md` (≤1,500 tokens): files changed, commands and final
five output lines, acceptance ticked, screenshots/geometry/network evidence,
deviations/questions, draft PR link and owner steps. Set Status: review.

## Risk list

GET Stays default/query preservation; saved views; single canonical range value;
optional vs required month semantics; scoped auto-submit removal; guest-form URL
construction/authorization; keyboard/no-JS behavior and real executed checks.

## Owner steps

1. Review EN/CS screenshots, query behavior and test output in the PR.
2. Merge only on green using the repository merge script. Deploy remains manual.
BRIEF>>>
