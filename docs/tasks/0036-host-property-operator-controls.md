# 0036: Host property and operator controls

Status: review
Report: docs/tasks/0036-host-property-controls-report.md
Depends on: none | Base commit: 6545d094f41b717e33ca053cb74e022fa291f5d6 | Branch: task/host-design-staging
Executor: Luna (owner-authorized) | Fits one session

## 1. Objective

Remove reporting badges from property labels, align address fields, and make
operator actions predictable and accessible. Keep existing readiness,
validation and archive protections, while clarifying that Delete moves an item
to Archived and moving cross-property overview links to Properties.

## 2. Context

The owner authorized Luna agents to execute the repository's Cursor-only
implementation rule for this task and authorized staging review. The root
agent orchestrates and reviews. Preserve the owner-selected behavior in these
exact anchors:

- `docs/DESIGN.md#address-labels-aligned-fields-without-reporting-pills`
- `docs/DESIGN.md#operator-actions-visible-and-predictable`
- `docs/DESIGN.md#properties-local-work-first`
- `docs/HOST_APP_DESIGN.md#6-properties-and-first-setup`
- `docs/plans/host-control-polish.md#3-address-labels-and-pills`
- `docs/plans/host-control-polish.md#4-operator-row-actions-cause-and-selected-behavior`
- `docs/plans/host-control-polish.md#8-property-tools-owner-selected-local-navigation`
- `docs/plans/host-control-polish.md#12-revised-geometry-copy-and-notification-review`

Relevant decisions: remove every “Needed to report” pill; keep complete labels,
desktop input alignment and natural mobile stacking; mark only currently
optional values; preserve current validation and discoverability of missing
report data. Street is optional in the facility form. Online legal/address
verification is pending, so do not claim statutory requiredness or change
validation.

Operator rows always show Edit, Invoice settings and More. More is available
for linked operators too; their Delete action is unavailable with a readable
reason and does not submit. Keep the existing server archive guard. On
Properties, surface Guest links and Automation overview links, plus Digital
door locks when enabled; remove the Property tools dropdown from individual
property details. Keep shared-lock setup, property-specific links and return
paths.

Delete is a label for the existing soft-archive operation. Confirm that the
item will move to Archived. Keep Archived navigation and restore controls
named for their purpose, and keep permanent deletion and privacy erasure
wording distinct. The shared translation owner provides `host.delete`,
`host.delete_to_archived.confirm`, `host.delete_to_archived.success`, and
`entities.delete_linked_help` in English and Czech.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/host_i18n.py` | Edit | Keep EN/CS `host.property_tools` labels used by the global navigation menu. |
| `App/app/templates/apartment_form.html` | Edit | Remove report badges; align address labels/inputs; change archive-only button label and confirmation. |
| `App/app/templates/entities.html` | Edit | Keep actions visible; explain unavailable Delete for linked operators; use scoped archive-only labels. |
| `App/app/templates/apartments.html` | Edit | Change only the existing property archive label/confirmation. |
| `App/app/templates/_host_navigation.html` | Edit | Surface overview links on Properties; remove duplicate dropdown from property details. |
| `App/tests/test_host_property_controls_browser.py` | Add | Synthetic browser coverage for EN/CS, 360/390/1280, keyboard/touch actions and navigation. |
| `App/tests/test_properties_table_chips.py` | Verify | Keep the localized global Property tools menu test; the duplicate menu remains removed only from property detail context. |
| `App/tests/test_property_readiness.py` | Update | Assert reporting badges are absent while all eight localized reporting labels and controls and existing readiness checks remain. |
| `docs/tasks/0036-host-property-operator-controls.md` | Add | This scoped task. |
| `docs/tasks/0036-host-property-controls-report.md` | Add | Browser results and screenshot links. |

Optional synthetic screenshots are written outside the repository to
`/workspace/generated_images/host-design-application/properties/` when
`UBYHOST_CAPTURE_PROPERTY_CONTROLS=1` is set.

## 4. Steps

1. Remove the `report` presentation argument and `req-report` output in
   `apartment_form.html`; remove only the calls supplying that argument.
   Preserve optional booleans, field names, values, readiness and validation.
2. Add a local `.property-address-grid` label-height rule that gives desktop
   rows aligned input tops and clears the reserved label height below 700 px.
3. In `entities.html`, render the existing More menu for every active row.
   Eligible Delete keeps `/entities/{id}/archive`; linked Delete is an
   `aria-disabled` menu item with a visible, associated explanation. Use local
   `.entities-page` styles for always-visible actions and explanation legibility.
4. Change only property/operator archive action labels and confirmations to
   `host.delete` and `host.delete_to_archived.confirm`. Keep route actions,
   `return_to`, archived-list controls and restore actions intact.
5. In `_host_navigation.html`, put global overview links on `/apartments` and
   omit the Property tools dropdown on individual `/apartments/{id}` pages.
6. Keep the shared Property tools menu's EN/CS labels available for global
   navigation contexts, while Properties uses direct overview links.
7. Run the focused browser test with required Chromium. Capture synthetic
   screenshots in EN/CS at 360, 390 and 1280 px; record commands and outcomes
   in `0036-host-property-controls-report.md`.
8. Keep the property-navigation and readiness tests aligned with the approved
   UI: retain translated global Property tools labels and routes, remove only
   the duplicate property-detail menu, and assert no reporting pills while all
   eight localized reporting labels and controls remain in both languages.
   Preserve existing readiness/checklist and validation assertions.

## 5. Do not touch

Do not edit shared stylesheets, `app.js`, route handlers, reporting, validation,
migrations, UbyPort behavior or database code. In `host_i18n.py`, limit the
change to restoring the existing global `host.property_tools` label in EN/CS.
Do not
change any legally required validation or make a statutory proof claim. Do not
globally replace Archive/Delete copy. Do not alter deletion, retention,
restoration, entity eligibility, legal-entity/data-controller references, or
any existing deep link or shared lock setup behavior. No secrets, real host
identities or production data in screenshots.

## 6. Commands

Run from `App/` with installed Playwright and local Chromium:

```sh
UBYHOST_BROWSER_EXECUTABLE=/usr/bin/chromium UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_host_property_controls_browser.py -q
```

Expected: focused browser test passes with zero skips. If capturing review
images, add `UBYHOST_CAPTURE_PROPERTY_CONTROLS=1`. The orchestrator runs
`python3 scripts/context_lint.py` from the repository root after all agents'
briefs and reports meet the template.

## 7. Acceptance

- [ ] No reporting badge remains in the property form; labels, field names,
  values, optional status and readiness/validation behavior remain intact.
- [ ] Address input tops align within desktop grid rows; mobile fields stack
  without clipping at 360 and 390 px.
- [ ] Edit, Invoice settings and More are visible at 360, 390 and 1280 px in
  English and Czech. Linked Delete has a visible explanation and cannot submit;
  eligible Delete keeps the guarded archive route.
- [ ] The linked operator remains protected by the route guard.
- [ ] Properties provides all enabled overview links; individual property
  details have no duplicate Property tools dropdown and retain local links.
- [ ] Only archive actions use Delete and the confirmation says the item moves
  to Archived; restore/permanent-delete/privacy-erasure copy remains distinct.
- [ ] Browser screenshots and command results are linked in `0036-host-property-controls-report.md`.
- [ ] Navigation and readiness regression tests cover the selected behavior in
  English and Czech while keeping the global tools labels and removing only
  detail-page duplication; all eight form labels and controls remain without
  reporting pills.

## 8. Stop and ask

Stop and write the report if the existing UI or route no longer matches these
requirements, validation behavior would need to change, a shared file outside
§3 needs edits, the browser test fails twice, or a translation key is missing.
Do not push, merge or deploy; staging review is coordinated by the root agent.

## 9. Report

Write `docs/tasks/0036-host-property-controls-report.md` (1,500 tokens maximum) with the files changed,
each command and its final output lines, acceptance items checked, screenshots,
deviations, questions and owner steps. Set this brief's status to `review` when
implementation and browser validation are complete.

## Risk list (for the reviewer)

Read the four templates in §3, the focused browser test and `0036-host-property-controls-report.md`.
Pay particular attention to the linked-operator disabled state and the
property archive action callsites.

## Owner steps

1. Review the synthetic screenshots linked from `0036-host-property-controls-report.md`.
2. Continue with the root agent's staging review before production.
