# Host filter audit and shared design

Reviewed 2026-10-10. Scope: host result filters and export-scope controls, not
an application-wide audit. The initial read-only audit led to the owner-approved
uniform design below. Luna implements it under briefs 0033 and 0038; actual
application evidence is separate from the prototype.

Latest correction: Stays and Guest register share **one Stay dates range control**
with a start/end selector and one calendar inside its popover. Apply dates
stages the panel draft; Apply filters commits it. Allow open-ended ranges,
clear bounds, reject reversed ranges and restore values on Cancel/Escape.
Month-filter pages keep the approved compact month grid.

Stays' collapsed summary defaults to **All properties · Active**. Only explicitly
selected date bounds appear, never implicit preset bounds or `…`. A date range
counts as one filter. The revised preview interprets “all the time” as an
unbounded **All dates** default; Upcoming/current and Past remain views. Keep
invoices' **All dates · All properties** summary and each page's own fields.

## Findings and selected treatment

| Page / files inspected | Current difference | Selected treatment | Preserve |
|---|---|---|---|
| Stays: `reservations.html`, `app.js::initAutoFilters` | Separate chips, exposed native selects/date fields; changes auto-submit; Save view/export mixed into filter row | Shared closed Filters bar and inline panel; draft edits, Apply/Cancel; shared day-calendar appearance | `apartment`, `status`, `from`, `to`, `range`; Upcoming/Past/All/Archived navigation; Clear defaults, saved view and CSV access |
| Invoices: `invoices.html`, `_list_filter.html`, `list_filter.py` | Native month popup; exposed status/search; selects auto-submit but search does not | Same panel/bar/actions as Stays; compact month grid and matching select/search fields | Optional month/All dates, property visibility, status options, `q` max 60, URL/reset semantics |
| Stay fees: `stay_fees.html`, `_list_filter.html` | Shares month form with Invoices but requires a period | Same panel and compact month grid; period always visible in the collapsed applied summary | Required month, server bounds/current Prague month, rate/saved-period behavior, page defaults |
| Stay-fee detail: `stay_fee_detail.html`, `_list_filter.html` | Shared period controls beside unrelated POST decision forms | Same period/filter family, retaining the facility and reporting period visibly | Save/correct/adjust/exemption/scope-ruling actions are mutations, not hidden result filters |
| Guest register: `housebook.html` | Exposed property/date bar, auto-submit, export placed among fields | Shared inline panel, Apply/Cancel, matching day-calendar and property select; Export stays outside | Legal register columns and contents, date/property parameters, exports and inspection scope |
| Archived: `settings_archived.html` | Five type links as chips with counts | Keep direct type choices visible, styled as the shared quiet segmented view controls | `type=all/stays/properties/housebook/entities`, counts, restore and retention information |
| Settings audit: `settings.html` `data-audit-filter` | All/Support appear as bare text links/strong text | Two labelled, directly selectable controls in the same segmented family | `audit=support`, default All, `#settings-audit`, existing audit records |
| CSV export: `base.html` and export menu helpers | Separate date-scoped modal controls | Matching field/label/button geometry and day-calendar styling; explicit dates and relevant property scope | Existing endpoint, required bounds, scope, confirmation and output |
| Inspection PDFs ZIP: `housebook.html` | Separate property/date modal | Same export-dialog layout and field components | Existing limits, warnings, dates/property and ZIP contents |

Archived types, Stays range views and the two audit choices remain directly
selectable: hiding short navigation groups would add a click. Their visual
tokens, selection treatment, focus and wrapping match the rest of the system.
Uniformity means predictable controls, not forcing identical field sets or
an accordion onto every group of links.

## Shared contract

- One Filters trigger, with a visible applied summary and an optional count of
  departures from that page's defaults. Required reporting periods stay visible.
- Inline white panel, existing warm borders and radius, labelled fields,
  identical spacing and control height: 42px desktop, at least 44px on mobile.
- Draft edits; Apply filters commits the entire form once. Cancel restores the
  applied values. Reset restores existing page defaults. Unrelated forms retain
  their current behavior. GET forms/URLs, deep links and saved views survive.
- Same property select and status-field styling. Domain-specific option sets
  remain different. Invoices alone keep their invoice search where supported.
- Month selection uses the approved 12-month grid, year arrows and coral-soft
  selected state. Day selection uses matching popover typography, arrows,
  borders, focus and selected state, with a normal seven-column calendar.
  Month bounds are not applied to day-date filters accidentally.
- Keep page actions, view navigation and Export reachable outside the panel.
  Export dates remain explicit and are not silently inherited from a list.
- No-JavaScript GET filtering remains usable; keyboard, touch, visible focus,
  Escape, reduced motion and EN/CS labels are required in the executor's delivery.
- Do not shorten labels, remove legal table columns, change validation or
  introduce a date-picker dependency to achieve visual consistency.

## Exclusions confirmed

`invoice_stay_picker.html` selects what to invoice; `invoice_settings.html`
selects the seller's settings context. They are not result filters. Property
navigation, guest country search, mutation forms, privacy-request actions and
command Search are different controls. Reports `/submissions` has no filter
bar to redesign. No extra filtering capability is invented by this audit.

## Review and execution

The earlier [interactive prototype](host-control-review.html) demonstrates
the selected controls with fictional data; its checks validate that prototype
only. The [application review](host-design-application-review.md) describes the
implemented design. Briefs 0033 and 0038 require actual browser/geometry checks,
EN/CS screenshots at 360, 390 and 1280px and zero skipped required checks;
0037 records the combined validation. No production data was used.
