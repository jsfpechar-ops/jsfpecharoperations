# Revised host designs: browser review

Date: 2026-10-10 (Europe/Prague). Owner requested a final page-by-page design
set supported by Playwright and Chromium. This review covers the standalone
[prototype](host-control-review.html), not the running UbyHost application.
No App files were edited and no application test suite was run. Cursor remains
the executor for production implementation and application verification.

## Review links

- Interactive HTML: `docs/plans/host-control-review.html`. Page, language and
  viewport controls live outside the product preview. Try Filters/Apply/Cancel,
  both calendar types, Other/Cleaning, operator menus, Delete and Restore.
  Feedback and Search review pages show the adapted pasted examples.
- Self-contained screenshot gallery, with embedded PNGs and EN/CS switches:
  `/workspace/generated_images/host-control-review/index.html`.
- Captures and machine-readable outcomes:
  `/workspace/generated_images/host-control-review/` and `checks.json`.
- Reproduction helper: `docs/plans/host-control-review-capture.py`.

The gallery is the visual review record; fixtures are fictional. The preview
does not file police reports, issue invoices, export real records or change a
workspace. Preserve actual record columns, validation, routes and business
behavior in production; representative content is not a table-redesign brief.
The existing application navigation shell remains outside this design scope.

## Approved page set

| Page / component | Approved result |
|---|---|
| Dashboard | Four small white Quiet overview cards with semantic dots/attention lines and neutral zero states; aligned Open/More; five unique stays total; current and next 30 days; overdue first; no photos |
| Stays | Inline expandable Filters, one Stay dates control, draft/Apply/Cancel; default All properties · Active across all dates; dates enter the summary only when chosen; range views, Save view and Export accessible |
| Invoices | Same panel/field/action design; invoice search/status choices and optional compact month grid/All dates |
| Stay fees and detail | Same filter family and compact month grid; required reporting period remains visible; save/correct actions retain their purpose |
| Guest register | Same property/date controls and inline panel; separate explicit export scope; legal record columns retained |
| Operators | Edit/Invoice settings/More visible on all rows; consistent menu; disabled Delete explained for linked operators |
| Invoice generator | Shared header/row columns and reserved removal track; aligned Quantity/Unit/Unit price; identical price widths; blank Cleaning unit; custom description only for Other |
| Properties/detail | Local property cards first; duplicate Property tools removed inside a property; cross-property overviews still accessible on landing/Search |
| Property address | Reporting badges removed, superseding earlier A; aligned complete labels/input tops; plain optional flags and natural mobile layout; validation preserved pending source check |
| Archived and Settings audit | Quiet segmented view controls matching the filter family; no unnecessary disclosure for short type/scope navigation |
| Delete and export dialogs | Delete explains move to Archived; preserve Restore. Exports show their own dates/property scope using matching controls |
| Everywhere interactive | Consistent hover context, visible keyboard focus, readable labels and touch-friendly controls |
| Copy and notifications | Actual clipboard write before checkmark; unchanged button geometry; light semantic cards, queued overflow, persistent failures/partial warnings, accessible announcements and reduced motion |
| Search review (recommendation) | Keep the current engine and permission-scoped data; borrow cleaner input/results/highlight geometry. Standalone search demonstration uses fictional local items |

## Browser evidence

Chromium **154.0.8037.57**, automated through Python Playwright.

- **1,059 preview checks passed, zero failed; zero JavaScript page errors.**
- **128 screenshots**, including EN/CS desktop 1280px and mobile 390px page
  views and expanded filters, plus interaction states and a 360px day calendar.
- Geometry/overflow checks at **360, 390, 471, 760, 850 and 1280px**, in both
  languages, across **22 review pages**. Embedded 390px mobile previews also
  checked inside a 1280px browser.
- Confirmed five unique dashboard rows, 30-day label/window and older urgent
  priority, hover tint and visible keyboard focus.
- Confirmed draft filtering, Cancel restoration, Apply summary/close behavior,
  twelve month choices, future-month disablement, invoice-only All dates,
  required Stay-fee month and Escape.
- Confirmed a single From/Until calendar control, draft-only Apply dates,
  reversed-range error/disabled confirmation, open-ended range summaries,
  one filter count per range, and reset to unbounded All dates. Preset dates
  do not appear as explicitly selected dates. The gallery includes the open
  Stays date-range picker.
- Confirmed address input alignment and absence of reporting badges, identical filter
  control heights (42px desktop, 44px mobile), viewport-safe calendar placement
  and 44px mobile day-selection targets.
- Confirmed operator actions visible without hover, explained disabled Delete,
  explicit archive confirmation and prototype archive/restore mapping.
- Confirmed Cleaning's blank unit, hidden custom description, and retained
  description when switching Other → Cleaning → Other.
- Confirmed local property context and retained multi-property overview links;
  exports retain explicit date/property controls.
- Measured a shared Open x-position/width/height across both dashboard
  sections; labels/arrows do not clip or wrap. All four summary cards have equal
  height, including wrapped Czech mobile labels; zero counts are neutral.
- Measured common Unit price x-position/width across Accommodation, Cleaning
  and Other, including mobile/embedded previews; desktop headers/control tops
  and mobile Remove/selector tops align.
- Checked horizontal and vertical button-label clipping and grouped action
  heights on every review page, including expanded filters. These assertions
  are part of the current 1,059-check run.
- Tested real synthetic-link clipboard success, stable confirmation geometry,
  denial without false success and manual-copy fallback. Confirmed persistent
  errors, success timeout, focused dismissal restoration, queue cap, partial
  warning treatment and reduced-motion notification behavior.
- Tested demonstration Search filtering, selection/navigation, shortcut,
  Escape and focus restoration. This does not certify the production engine.

The owner's review exposed shifting invoice columns and a viewport-dependent
mobile preset missed by the earlier checks. Shared fixed action/removal tracks
and container-responsive layout correct these in the prototype; the checks now
measure those specific failures. Browser sandbox local
socket restrictions required an approved Chromium run outside the sandbox;
managed file-URL restrictions required a temporary localhost preview server.
These are design-review tools, not application server setup or deployment.

To reproduce in this cloud workspace, serve the plan directory on loopback
port 8765, then run the helper with Playwright and `/usr/bin/chromium` installed:

```sh
python3 -m http.server 8765 --bind 127.0.0.1 --directory docs/plans
```

In another terminal:

```sh
UBYHOST_REVIEW_ARTIFACTS=/workspace/generated_images/host-control-review python3 docs/plans/host-control-review-capture.py
```

## Remaining verification

Current-source [facility/invoice address verification](invoice-address-check.md) is
blocked by network access (TLS/proxy errors and browser tunnel failures).
The code confirms separate property/seller/buyer addresses and a blank-unit
path; statutory references are documented without claiming fresh verification.
The renewed Police/ČÚZK/government-mirror requests were also blocked. Street is
currently optional in the facility form/validator; this is not fresh legal
verification. Potential VAT buyer-address validation needs a separate verified compliance
assessment. No legal validation changes are included in this design work.

Cursor must still implement from scoped briefs and run actual application
browser/geometry checks with the required EN/CS screenshots and zero skips.
Prototype checks do not certify production behavior, filing or tax compliance.
The [first Cursor prompt](host-feedback-cursor-prompt.md) covers the shared
notification/copy component. The [second prompt](host-filters-cursor-prompt.md)
covers shared filters, dates and explicit action labels. Wider page changes
and result-specific route binding remain separate implementation briefs.
The owner authorized a staging review; the [staging handoff](host-design-staging-handoff.md)
records the deployment path and the remaining application implementation.
