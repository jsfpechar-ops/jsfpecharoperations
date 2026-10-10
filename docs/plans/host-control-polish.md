# Host controls: filters, dashboard and form polish

Status: main UI choices approved 2026-10-10: filters/month grid, Quiet overview
(five stays/30 days), Delete-to-Archived, aligned address fields, visible operator actions,
current invoice layout/blank Cleaning unit and local property navigation.
Latest revision removes address reporting pills and adds shared copy/status feedback.
Current-source address verification remains open. The selected application design
is implemented by Luna on `task/host-design-staging`; local validation passed
(3,022 tests, zero skips). GitHub CI and staging deployment remain pending. The earlier review prototype remains historical evidence.
Added 2026-10-10.
Codex is the orchestrator/reviewer. The owner's later explicit authorization
assigns implementation and application checks to Luna executors for this task,
as recorded in [workflow](../context/workflow.md#owner-authorized-host-design-execution).
The numbered briefs below own execution; this plan is the design contract.

## 1. Scope

1. A month picker matching the existing host UI on Stay fees and Invoices.
2. Remove address reporting pills; align complete labels and input rows.
3. Make operator row actions predictable on Business & legal details.
4. Filters on demand across host pages, starting with Stays and Invoices.
5. Consistent hover/keyboard feedback and a simpler, bounded dashboard.
6. Discuss invoice extras and the scope of Property tools.
7. Rename existing host archive actions to Delete, retaining Archived behavior.
8. Adapt the supplied copy/checkmark and notification cards; review Search.
9. Verify all review-page button/control geometry at desktop and narrow widths.

Keep the light host palette, typography, borders, radii and existing tokens
from `App/app/static/host.css` and `App/app/static/tokens.css`. No new
dependency, database change or filing change. Global interaction feedback is
approved; page layout changes follow the ordered briefs below.

## 2. Month picker: chosen

The shared `App/app/templates/_list_filter.html` renders a native
`input[type=month]`. The browser owns the popup in the supplied screenshots;
its internals cannot reliably be restyled with the app's CSS.

Options presented to the owner:

- [x] **Compact month grid — owner-selected for Invoices and Stay fees:** keep previous/next-month controls;
   open a white popover with a year header and a 3-column, 12-month grid.
   Use soft coral for the selected month and a quiet "This month" action.
- [ ] **Month and year selectors:** separate selectors within the same action
   group, with matching heights and previous/next-month controls.
- [ ] **Recent months + Browse:** recent months as compact choices; Browse
   opens older periods. Responsive layout must not crowd adjacent filters.

The owner chose the compact month grid on 2026-10-10. Use one shared component for both pages.
Preserve `App/app/list_filter.py` behavior: invoice month is optional and
supports All dates; stay-fee month is required. Respect existing month
bounds, page defaults, GET parameters, other filters and Reset semantics.
Do not replace a reporting period with a day-calendar or a date range.

Implementation requirements for the chosen grid:

- One month/year trigger opens a white popover; keep the adjacent month arrows.
- A year heading and year arrows sit above twelve months in a 3-column grid.
- Soft coral fill and coral text/border identify the selected month.
- Disable out-of-range choices using the existing server bounds.
- "This month" selects the current Prague month; invoices also support
  "All dates", while Stay fees always retain a reporting month.
- Inside the chosen expandable filter panel, selecting a month changes the
  draft and closes only the month popover. Apply filters submits all edits once.
  This supersedes the earlier immediate-submit proposal. Year navigation
  alone does not change the selected reporting period.
- Keyboard behavior, visible focus, Escape, accessible names, a usable
  no-JavaScript fallback and viewport-safe mobile placement are required.
- Use existing tokens and vanilla JavaScript; do not add a picker library.

## 3. Address labels and pills

`App/app/templates/apartment_form.html` places the pill inline in the
`text_field` label. The screenshot shows the longer house-number label
wrapping its pill onto another line and pushing that input below its peers.

**Latest selected outcome:** remove all Needed to report pills. Keep aligned
complete labels/input tops, hints and natural mobile stacking. Plain optional
flags remain only on fields currently treated as optional; verify any legal
requiredness change first. The owner revised the earlier A selection after
reviewing the browser screenshots. Do not shrink or truncate labels.
Facility reporting badges do not define invoice address requirements; see
[invoice-address check](invoice-address-check.md).

Earlier alternatives (history; A's badges are now superseded):

1. **Aligned badges — initially selected, now replaced:** each field has a consistently aligned
   label area, followed by a separate badge line and then its input. Reserve
   equal space within each grid row, including fields without a reporting
   badge. Full labels may wrap; input tops remain aligned. Keep the literal
   Needed to report wording, avoiding a new symbol to learn.
2. **Small markers:** replace reporting pills with a marker on affected labels
   and one adjacent legend, "* Needed for reporting". Reduce repetition, but
   distinguish reporting readiness from fields required to save the form.
   Screen readers must receive the meaning on each affected field.
3. **Plain helper text:** keep aligned labels and inputs, placing Needed for
   reporting below the relevant inputs. Coordinate existing hints so reporting
   meaning remains visible without crowding the form.

All alternatives preserve field labels, reporting meaning, hints, validation
and optional flags. These are layout choices, not new reporting requirements.

## 4. Operator row actions: cause and selected behavior

Confirmed in `App/app/templates/entities.html`:

- Every active row has Edit and Invoice settings actions.
- The three-dot menu currently contains only Archive; the approved replacement
  label is Delete, with the same archive operation (see section 9a).
- `{% if not entity.apartments %}` removes that menu for linked operators.
- `App/app/static/components.css` reveals row actions on hover, keyboard
  focus within the row, or row selection on devices that support hover.

Thus the screenshots show conditional action availability, not evidence
that the second row's hover event failed.

The server in `App/app/routes/admin.py::archive_entity` independently
refuses archiving when a property references the operator as legal entity
or data controller. Preserve that guard and existing archive confirmation.

Owner-approved direction, 2026-10-10:

- Keep Edit, Invoice settings and the three-dot menu in consistent positions
  on every active operator row.
- Always show these actions on this page, so users need not hunt on hover.
- For an operator eligible to archive, retain the operation with the Delete label.
- For a linked operator, show Delete disabled in the open menu with visible
  explanatory text, for example "Move linked properties before deleting."
- The unavailable action must not submit a request. Its reason must be
  readable by keyboard and touch users, not just a hover tooltip.
- Scope operator action availability changes to this page. The separately
  approved global hover/focus feedback rule still applies.

Alternative for discussion: keep hover-revealed buttons but make the menu
consistent on every row, with the same explanation for unavailable Delete.
Owner selected the always-visible, consistent-menu direction. The hover-only
alternative above is not selected.

Plain-language explanation for the owner: these are the buttons at the right
of each company/person row. Always visible means users see them immediately;
hover-only means a mouse must move over the row before they appear. Recommend
consistent, always-visible actions for easier discovery and touch use. Example:
an unused operator can be deleted into Archived; an operator still linked to
a property cannot. The selected same-position menu shows Delete unavailable
and explains that its properties must be reassigned first. Disappearing menu
versus explained unavailability is the remaining decision, not a failed hover
event. Do not change the existing server guard.

## 5. Executor acceptance after design selection

The executor validates English and Czech at 360, 390 and 1280 CSS px. Include
screenshots using synthetic fixtures only, browser/geometry checks with
zero skips, keyboard and touch behavior, and actual command outcomes in
the report. Do not reproduce personal data from the owner's screenshots.

Check operator rows with and without linked properties, hover/focus/menu
states, and confirm that server-side archive protection remains effective.
Check that alignment changes do not alter field names or submitted values.
Check both month-filter pages, their different defaults and optionality,
month limits, filter preservation, Reset and the no-JavaScript fallback.

## 6. Invoice generator: requested fix and layout discussion

Owner requested that custom description appear only for Other and asked for
a clean and intuitive Items section. Owner selected keeping the current
structure, with custom description only for Other and blank Cleaning units
allowed. No broader redesign or physical widening is required. These changes
belong to an invoice-items brief, not the filter brief.

Confirmed: `App/app/templates/invoice_form.html` always renders
`item_description` in each extra row. Its inline JavaScript calculates totals
and clones/removes rows but does not condition description visibility on
`item_kind`. Thus Cleaning retains the unnecessary custom-text input.

Requested behavior:

- Show a clearly labelled Description field only for Other. Preserve typed
  text when switching kinds back and forth and preserve row submission mapping.

Owner-selected layout behavior:

- Keep existing rounded controls and overall row structure.
- Share one column grid across headers, Accommodation and every extra; reserve
  the removal track on every row. Align Quantity/Unit/Unit price, with identical
  price widths. Extra Other description never shifts its neighbors. On mobile,
  prices share a full-width position and Remove aligns with the selector.
- Cleaning's Unit may be blank; do not invent a value or impose a default.
- Preserve quantity/price/VAT and row mapping. No new totals/defaults/add-row
  redesign is required for the conditional-description correction.
- `invoices.py::_extras_from_form` already accepts blank units; preserve this.

Keep accommodation data, allowed extra kinds, VAT, limits and issued invoice
behavior governed by the existing stay-only-invoices plan. Hiding inputs must
not silently change values or detach them from the correct item row.

## 7. Filters on demand: chosen expandable panel

Owner selected the inline expandable panel for Stays and Invoices, superseding
the always-visible toolbar alternatives. The latest owner correction adds
one combined Stay dates control inside that panel. The shared principle
applies across host result-filter pages; initial execution covers these two
pages and the month grid shared with Stay fees. Policy lives in
`docs/DESIGN.md`, under Filters on demand.

Closed: Filters button, concise applied summary, results and ordinary page
actions. Open: white panel with labelled fields, Apply filters and Cancel.
No overlay, no nested accordion for ordinary fields. The panel pushes results
down, wraps to a single column on mobile, and has a visible keyboard indicator.
Keep Stay view tabs, Add stay/Generate invoice, Save view and Export accessible.
Show Clear/Reset only when relevant, preserving existing reset destinations.

Stays fields: Property, Stay state, one Stay dates control containing From and
Until. Preserve `apartment`,
`status`, `from`, `to`, `range`, existing range presets and saved views.
Retain the custom-range behavior of the submit action when editing dates.
Invoices fields: Month, Property when applicable, Status and Search. Preserve
month optionality, `q` length limits, status semantics and reset behavior.
Compact month grid selection changes the draft until Apply filters.

Scope the change in `App/app/static/app.js::initAutoFilters` to the disclosure
forms: these forms batch draft edits rather than submitting on every change.
Do not change unrelated auto-submit forms. Cancel restores applied values;
no-JavaScript users get visible fields and the normal GET submit. Applied
summary/count reflect the URL and page defaults, never unsubmitted edits.
Preserve export scopes; the Guest register exports have their own date dialogs.

Filter inventory from the targeted host-filter inspection:

| Surface | Current controls | Rollout |
|---|---|---|
| Stays `/reservations` | Property, state, date bounds, view presets | Expandable panel chosen; keep view navigation visible |
| Invoices `/invoices` | Month, optional property, status, search | Expandable panel + month grid chosen |
| Stay fees + period detail | Required month, property/status as applicable | Same inline panel/month grid, period visible when closed |
| Guest register `/housebook` | Property, From/Until, export | Same inline panel; Export outside with explicit scope |
| Archived `/settings/archived` | Type choices with counts | Quiet shared segmented view controls, visible directly |
| Settings audit | All/Support scope | Two shared segmented controls, visible directly |
| CSV/PDF export dialogs | Required export dates/property | Keep scope explicit inside the dialog |

Invoice seller/context selectors, invoice creation's stay selector, property
navigation, mutation forms and guest country search are not host result
filters. Reports `/submissions` has no filter bar; do not invent one.
The targeted [filter audit](host-filter-audit.md) specifies the remaining
route treatments. These use shared components while retaining their fields.
A shared direction does not authorize arbitrary replacement of every select.
In plain terms, remaining filter pages are Stay fees, Guest register, Archived
records and Settings' audit scope. The existing CSV/PDF export dialogs also
contain date/property controls; they are not additional filter pages and must
keep their explicit export scope. Two-choice audit scope and archive navigation
may remain visible where a disclosure would add a needless click.

## 8. Property tools: owner-selected local navigation

Owner questions the duplicate entry points on the property detail page.
Confirmed: `App/app/templates/_host_navigation.html` links Guest links,
Automation & UbyPort and, when enabled, Digital door lock. These routes offer
multi-property/account overviews; property cards lead to local details or
contextual anchors. The account lock connection is not a duplicate property
field. See `docs/HOST_APP_DESIGN.md` section 6.

Owner selected removing the duplicate menu from individual property detail
pages. For hosts with several properties, retain overview links on the Properties
landing page: viewing all guest links or automation states together saves
opening each property in turn. A single-property host gains little from that
extra menu. Retain local
cards, cross-property overviews, shared-lock setup, contextual anchors and
`return_to` behavior. Owner approved this navigation change on 2026-10-10.

## 9. Dashboard: simple, current and bounded

The owner selected **Quiet overview** from the earlier dashboard options and
accepted the recommendations below on 2026-10-10. This supersedes the later
photo-heavy concepts and the pending-cap proposal. No property photographs, decorative thumbnails,
extra statistics or additional card metadata. Generated mockup imagery is
not an approved feature. Follow Today in `docs/HOST_APP_DESIGN.md` section 4.

Approved layout and behavior:

- Plain Dashboard title and visible Add stay. Keep calendar update access.
- At most a small, useful status summary with real destinations: Needs action
  and Waiting for guests. No alarming zero-count red card. Additional statuses
  appear only when meaningful; colors do not imply a mutually exclusive funnel.
- Compact rows in Needs action and Current & next 30 days. Each stay appears
  once and shows property, dates, one truthful task/status label, Open stay,
  and a secondary menu only for real actions. No repeated explanatory prose.
- **Chosen cap: five unique stay rows total across all dashboard sections**,
  not five per group. A stay must not appear in both sections.
- Routine candidates are active current stays (arrival <= Prague today and
  departure >= today) or arrivals after today through today + 30 days inclusive.
  Far-future incomplete stays alone must not bypass this horizon.
- Prioritize real overdue/failed unresolved work even outside the routine date
  window, then current actionable stays, then the nearest arrivals. Preserve
  backend urgency within those groups; do not alter filing or deadline logic.
- Compute meaningful counts before truncating rows. When more actionable stays
  exist than fit, show one concise additional-count link to the full work list.
  Keep View all stays visible. No pagination or automatic expansion that defeats
  the initial cap. Empty states must respect any unresolved work outside it.
- Mobile uses the same compact vertical order. Readable text, plain labels,
  touch-friendly controls and clear hover/keyboard feedback are essential.

Confirmed feedback inconsistency: dashboard `host-task` articles have no row
hover/focus styling; Stays uses `clickable-row` feedback. Global feedback is
owner-approved. Whole-card navigation is a separate implementation decision:
preserve child actions, menus, text selection and keyboard semantics. Apply
interactive feedback only to genuine interactive targets.

Status-copy concern for review: the shared progress pill can label a scheduled
`awaiting_verification` stay Ready while the queue assigns it to needs action.
Queue groups/counts can overlap; do not infer a classifier defect from color or
labels. Clarify truthful copy separately without changing reporting state.
Use Quiet overview's restrained palette and existing semantic tokens. The
dashboard direction, five-row cap, 30-day horizon and overdue-first behavior
are approved; no further owner selection is needed for these choices.
The owner changed 14 days to 30 days on 2026-10-10; the cap stays five total.

## 9a. Delete label, existing archive operation: chosen

The owner chose Delete as the visible replacement for existing host Archive
actions on 2026-10-10. English Delete, Czech Smazat. Records still move to
Archived; existing routes, submitted archive actions, linked-record guards,
storage, restoration and retention behavior remain unchanged. Keep navigation
to Archived labelled for the destination, including archive-view tabs.

Confirmation copy: "This item will move to Archived." / "Tato položka se přesune
do archivu." Confirm button: Delete / Smazat. Success text must accurately
describe moving to Archived. Do not suggest permanent deletion. Do not change
true privacy erasure, permanent deletion or other remove operations merely
because their strings include Delete. Include EN/CS action, confirmation and
success states, eligible/ineligible records and destination access in acceptance.

The owner separately approved the consistent operator menu layout. The
executor brief must identify exact archive-only call sites and translation
keys; do not authorize an unscoped global string replacement.

## 10. Ordered briefs for Cursor

The owner has superseded the original Cursor-only execution assignment for
this staging task with multiple Luna 6.0 executors. Codex remains reviewer;
see the [scoped workflow exception](../context/workflow.md#owner-authorized-host-design-execution).
The actual implementation briefs are:

| Brief | Scope |
|---|---|
| [0032](../tasks/0032-host-copy-notifications.md) | Shared clipboard and notification feedback |
| [0033](../tasks/0033-host-filter-panels.md) | Uniform expandable filters, day range, month grid and applied summaries |
| [0034](../tasks/0034-host-quiet-dashboard.md) | Quiet dashboard, five total stays and thirty-day horizon |
| [0035](../tasks/0035-host-invoice-items.md) | Shared invoice columns and Other-only description |
| [0036](../tasks/0036-host-property-operator-controls.md) | Address alignment, visible operator actions and local property navigation |
| [0037](../tasks/0037-host-design-validation.md) | Combined application and environment validation |
| [0038](../tasks/0038-host-controls.md) | Default hover/focus, responsive action geometry and explicit copy/Delete labels |
| [0039](../tasks/0039-host-flash-outcomes.md) | Notification severity from reviewed save/result keys |

Shared feedback regions precede filter changes in shared files. Individual
page ownership is separate. Final validation runs only after shared code
settles; review reports and actual application screenshots before staging.

## 11. Final review set

The [interactive prototype](host-control-review.html) covers Dashboard, Stays,
Invoices, Stay fees/detail, Guest register, operators, invoice generation,
Properties/detail, address without reporting pills, Archived, Settings audit and retained
cross-property overviews. It uses fictional data and demonstrates final
controls; production records/validation/legal table contents must be retained.
[Chromium evidence](host-control-review-report.md) records review-only checks.
The user's chosen layout is light, extremely easy and intuitive, with relevant
information, visible familiar actions and uniform control behavior.

Open limitation: current-source [invoice-address verification](invoice-address-check.md).
This does not block documenting/reviewing the agreed UI and is not approval
to alter reporting rules, invoice validation or retention.

## 12. Revised geometry, copy and notification review

The owner's screenshot feedback revealed two prototype defects: variable
`auto` action columns shifted invoice prices between rows, and mobile presets
used viewport breakpoints instead of their own panel width. Both are corrected
in the standalone review. Open labels/arrows stay on one line and share
the same action-column width across dashboard sections; all reviewed button
groups share heights and have unclipped labels in EN/CS.

Dashboard summary is again the four small white Quiet overview cards from the
owner's third screenshot, using semantic dots/attention lines and neutral zero
states. The five-row/30-day policy, urgency ordering and hover/focus remain.

The owner requested all transient bubbles use the supplied feedback reference.
Approved: light cards, outcome colors, clipboard-confirmed checkmarks, readable
labels/messages, persistence for errors/partial results, accessible announcements
and reduced motion. Keep persistent states/errors, Undo, filing/receipt rules
and no-JS behavior. See [example analysis and mapping](host-feedback-review.md).
Search recommendation: retain the existing fuzzy/data-driven engine, borrow
cleaner visual selection/spacing; do not ship the demo's fake command actions.

The shared feedback and typed-outcome briefs above bind the existing host
messages without changing submit/retry/receipt logic. The supplied search
sample remains a visual reference; the existing command engine and endpoints
stay intact. Revised geometry and address rules govern all page briefs.

## 13. Final label/date corrections and staging review

Dashboard action is Open. Guest registration URL copy actions say Copy guest
form link; other copy targets retain their own explicit labels. The Stays
panel uses one Stay dates control with From/Until inside a shared calendar;
Apply dates edits the draft, and Apply filters commits it. Reversed ranges
cannot be applied; either bound may be blank. Reset clears both bounds.

Default summaries are All properties · Active on Stays and All dates · All
properties on Invoices. Dates appear only after explicitly choosing them.
The preview interprets the owner's “all the time” as an unbounded All dates
default; optional clarification received no answer. Upcoming/Past remain
separate views and their automatic bounds stay out of the chosen-date summary.

The earlier [filter prompt](host-filters-cursor-prompt.md) is a planning reference;
[0033](../tasks/0033-host-filter-panels.md) owns the actual filter implementation.
The latest preview run passed 1,059 checks with 128 screenshots and zero
JavaScript errors. These certify the standalone preview, not the application.

The owner requests staging review before production. See the concrete
[staging handoff](host-design-staging-handoff.md). Application implementation
is underway on `task/host-design-staging`; no deployment is claimed. Reviewed
application checks precede feature-branch push and a Render staging deploy.
