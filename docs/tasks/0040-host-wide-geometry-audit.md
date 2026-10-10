# 0040: Correct the host design across screen sizes

Status: review
Depends on: 0032–0039 | Base commit: fd44e6acc0de4d082a32818efedfbd83b6c2b7fc | Branch: task/host-design-staging
Executor: owner-authorized Luna team; Codex reviews and coordinates.

## 1. Objective

The owner explicitly requested a full audit after staging screenshots showed
headers and filters starting farther left than results, misaligned controls,
narrow table tracks, and a notification covering actions. Correct these defects
throughout the redesigned host pages and demonstrate the result in Chromium.
Preserve the approved quiet design, expandable filters, calendar controls,
five-stay dashboard cap, labels and application behavior.

## 2. Context and reproduction

Read AGENTS.md and context/status.md, then the relevant host-design section and
DESIGN.md action geometry. The session exception authorizes Luna execution.
Working-tree anchors in App/app/static/host.css:

```css
.host-workspace .wrap.with-sidebar > * { max-width: 1080px; }
.host-workspace .wrap.with-sidebar > .page-header { max-width: none; }
.host-workspace .filter-toolbar { display:flex; align-items:center; flex-wrap:wrap; gap:10px 14px; margin:0 0 10px; }
```

The latter two rules disagree with the centered result lane at wide widths.
Existing browser coverage at 360/390/1280 missed the owner's wide-screen case.
Validate measurable alignment, not only absence of horizontal overflow.

## 3. Files and exclusive owners

| Owner | Allowed implementation files/regions |
|---|---|
| luna_properties | App/app/static/host.css; App/app/static/host-controls.css; shared page_header macro in App/app/templates/_components.html if necessary; property/entity/address template presentation in App/app/templates/ only after naming the exact files in its report |
| luna_filters | App/app/templates/_list_filter.html, reservations.html, stay_fees.html, invoices.html, housebook.html, submissions.html and filter sections in reservation_detail.html; App/app/host_i18n.py invoices.empty EN/CS body copy only, plus existing Cancel key use; App/app/static/app.js filter region only if a browser-proven geometry defect needs it |
| luna_dashboard | App/app/templates/dashboard.html; App/tests/test_host_quiet_dashboard_browser.py for independent dashboard state/row checks; no reporting/query logic changes |
| luna_invoice | App/app/templates/invoice_form.html, invoice_stay_picker.html, invoice_detail.html, invoice_settings.html; App/tests/test_host_invoice_items_browser.py actual runtime geometry/screenshots; no calculations, PDF or validation changes |
| luna_executor | App/app/static/app.js feedback/copy/search regions; App/app/templates/base.html feedback markup and changed-asset cache tokens; App/tests/test_host_feedback_browser.py feedback/manual-copy geometry checks; preserve persistent warning/Undo semantics |
| luna_validation | scripts/context_lint.py optional explicit Report path only, retaining the default numbered report check; App/tests/test_host_geometry.py, test_host_controls_browser.py, test_host_filter_panels_browser.py; App/tests/test_alert_stack.py obsolete fixed-corner expectation only, preserving alert semantics tests; App/tests/test_first_property_step.py Property table-header assertion only, allowing the new semantic column class while retaining the visible-word check; additional App/tests/test_host_wide_geometry_browser.py if clearer; browser artifacts under generated_images/host-wide-audit/ using synthetic records only |
| Codex | This brief, report filename/ref integration in existing host briefs/plans to avoid concurrent main doc collisions; docs/tasks/0040-report.md final review, docs/DESIGN.md, docs/HOST_APP_DESIGN.md, docs/context/status.md, ui-decisions.md, known-issues.md, docs/plans/host-design-application-review.md and host-design-staging-handoff.md; docs/plans/invoice-address-check.md source-access status only; docs/tasks/0040-evidence/ representative unmodified synthetic PNGs and index; outside-App review gallery helper and final delivery metadata |

All owners may read host templates/CSS/JS and existing tests solely for this
owner-requested audit. Only the shared CSS owner writes host CSS. Page owners
send required CSS selectors to that owner. No simultaneous edits of shared
regions. Reports: docs/tasks/0040-<owner>-report.md, at most 1,500 tokens each.

## 4. Steps

1. Validation owner reproduces the wide-screen defect on fresh synthetic host
   records before the CSS change, capturing DOM rectangles and before images.
   Include Dashboard, Stays, Properties, Invoices and fees, plus narrow forms.
2. Shared owner restores one centered working lane: page header, contextual
   navigation, filter toolbar/panel, results and empty states share edges.
   Retain deliberately narrower forms as internally aligned lanes. Avoid a
   blanket width rule that stretches dialogs, auth/public forms or print.
3. Page owners audit their assigned routes at wide and narrow widths. Fix
   header/action/table geometry, long EN/CS labels, empty/populated/unset
   states, calendars, invoice accommodation/extras/VAT/Other, and visible
   action alignment. Preserve all values, endpoints, guards and accessible
   keyboard operation. Do not introduce horizontal label wrapping that
   breaks simple action names such as Open or the source portal arrow.
4. Feedback owner measures toast obstruction and recommends/fixes usable
   placement and compact composition with the shared CSS owner. Preserve
   actual outcome severity, actionable persistent failures and Undo.
   Use an aligned in-flow host feedback region after the safety notice so
   persistent cards cannot cover row actions. Actual asynchronous copy results
   remain visible on their originating button; do not invent save/report hooks.
   The screenshot's persistent corner reminder is a separate component:
   `_host_alerts.html` renders `.notification-stack`, already within main but
   still positioned fixed by host.css. Correct that stack to the centered
   page flow too, including mobile overrides. Verify actual persisted alerts,
   their stay/property links and dismissal rules; a toast-only fixture cannot
   prove this defect fixed. Preserve non-dismissible date/signature warnings.
   Direct main-child Back links also align with their header/results lane.
   Measured copy-success card insertion moves the originating control by 54px.
   Remove that redundant inline-copy card only: keep Copied/checkmark and one
   live announcement, with stable button/page positions. Preserve server
   Save/report/Undo notices and command-palette feedback.
   On an all-unconfigured fee list, show Property/Status/actions instead of
   empty numerical metric columns. Configured/mixed fee tables retain their
   metrics and existing calculations; unset cells must not distort tracks.
5. Validation owner tests 360, 390, 760, 1024, 1280, 1440, 1680, 1920 and
   2048 CSS-pixel widths. Representative expanded/collapsed sidebar and
   EN/CS states must be covered. Assert aligned shared edges within 2 CSS
   pixels, equal adjacent action heights/baselines, stable table tracks,
   readable labels and no viewport overflow. Include open filters/popovers,
   empty and unset fees, and notifications while performing actions.
6. Capture actual corrected pages and an indexed before/after geometry
   report. Do not publish staging guest/operator identity or real data.
7. After owners freeze changes, validation runs required browser/geometry
   checks with system Chromium and UBYHOST_REQUIRE_BROWSER=1, then the full
   application suite once. Report exact counts, zero browser skips, evidence
   paths and any unresolved issues. Do not call narrower old checks proof
   of the new wide-screen design.

## 5. Do not touch

No backend, auth, filing, deletion, legal requiredness, migrations, dependencies
or production changes. Keep the staging safety notice truthful; presentation
may become aligned but do not hide or misrepresent it. Never silently dismiss
persistent warnings to make a screenshot cleaner. Preserve no-JS forms.
Only Codex commits/pushes the feature branch and updates PR #338 after review.
If an implementation file outside the table needs changing, report it to
Codex for a concrete scope amendment. On repeated failures report the evidence
and diagnosis; no broad test weakening or implicit permission escalation.

## 6. Commands

From App/, validation runs affected tests with:

```sh
UBYHOST_BROWSER_EXECUTABLE=/usr/bin/chromium UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest -q tests/test_host_wide_geometry_browser.py
UBYHOST_BROWSER_EXECUTABLE=/usr/bin/chromium UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests -q
```

From the repository root Codex runs `python3 scripts/context_lint.py`.

## 7. Acceptance

- [x] Before evidence reproduces the shared lane mismatch at wide widths.
- [x] All audited pages have coherent working lanes and aligned controls.
- [x] Long-label, empty, populated and unset states remain geometrically sound.
- [x] Notifications permit action access and retain truthful outcome semantics.
- [x] Wide/mobile Chromium checks pass with no browser skips.
- [x] Final evidence and application validation are reviewed and PR updated.

## 8. Stop and ask

Report repeated failures, missing anchors or scope changes to Codex with a
concrete diagnosis. Codex coordinates routine corrections within the owner's
authorized full host audit. Never bypass checks or change business semantics.

## 9. Report

Each owner writes its 0040 report with changed paths, measured findings,
checks and evidence. Validation records before/after geometry, test counts,
skips and remaining limitations. Codex accepts only demonstrated outcomes.

Local acceptance: final required-Chromium coverage run passed 3,030 tests with
zero skips, seven warnings and 89.57% coverage (86% threshold). The refreshed
444-combination matrix records zero lane mismatches. See the
[validation report](0040-luna_validation-report.md) and
[representative captures](0040-evidence/README.md). PR #338 is the review
deliverable; CI and the owner's next staging deployment remain separate.

Concurrent main integration is documentation only: preserve host reports under
unique host names and explicit Report paths; retain legacy report checks.
Keep the tested App tree unchanged while resolving document merge conflicts.
