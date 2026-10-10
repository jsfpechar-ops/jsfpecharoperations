# Host design: application review

Owner-approved design, implemented on `task/host-design-staging`. This describes
the application changes, separately from the earlier standalone prototype.
The owner's staging review exposed shared layout defects at wide screen sizes.
The previous 3,022 passing tests did not adequately check aligned content edges.
[0040](../tasks/0040-host-wide-geometry-audit.md) now owns the full design audit,
correction and measured wide/mobile browser evidence. [PR #338](https://github.com/jsfpechar-ops/jsfpecharoperations/pull/338) remains the review branch.

| Page | Final selected design |
|---|---|
| Dashboard | Quiet white overview cards; amber action, taupe waiting, blue ready and red overdue; neutral zero counts. Five unique stays total, current stays and arrivals within thirty days, older unresolved urgent work first. Shared aligned Open/More actions; no property photos. |
| Stays | Filters open an inline panel. Property, state and one Stay dates control with From/Until in a shared calendar. Draft edits, Apply and Cancel. Closed default summary: All properties · Active; dates appear only when explicitly applied. Upcoming, Past, All dates and Archived remain views. |
| Invoices | Matching expandable panel with property/status/search and a compact twelve-month grid. Coral month selection and year arrows. Optional All dates. Default summary: All dates · All properties. |
| Stay fees and fee detail | The same month/filter family, retaining the required reporting period and each page's actual property/status fields and fee context. An entirely unconfigured list shows Property, Status and setup actions; configured/mixed tables retain aligned metrics. |
| Guest register | Matching property/date-range panel, with exports outside it and the existing legal register columns retained. |
| Invoice generator | Existing simple form, shared header/row columns, aligned Unit price inputs and reserved Remove track. Custom Description appears only for Other. Cleaning Unit stays blank. Preview/Issue sit after the form so they cannot cover fields. |
| Business & legal details | Edit, Invoice settings and More always visible. Linked operators have an unavailable Delete action with a visible explanation; backend guards remain. |
| Property address | Aligned complete labels and input tops; no Needed to report pills. Save sits after the form so it cannot cover focused address fields. Existing optional flags and validation retained pending source verification. |
| Properties | Local cards and settings remain; the duplicate Property tools dropdown is removed within an individual property. Cross-property tools remain on Properties and in Search. |
| Archived | Existing retained records and Restore remain. Delete actions move records here and explain that outcome; permanent deletion remains separate. |
| Shared controls | Clear hover and keyboard focus, visible touch actions, consistent button tracks. Copy guest form link names the target explicitly; successful copy shows Copied/checkmark without shifting the button. Failures expose a usable manual source. |
| Transient updates | Aligned white semantic cards in the page flow after the safety notice, at most three visible. Persistent stay/property alerts use the page flow too, preserving their links and dismissal rules. Errors, partial results and Undo persist; routine notices pause on hover/focus. Inline copy confirms on its button with one live announcement. Existing filing/receipt meaning remains. |

The product rule is extremely easy, intuitive use: familiar words, relevant
information, predictable placement and controls that work with touch and a
keyboard. [DESIGN.md](../DESIGN.md) is the shared design contract.

The original implementation checks and captures are recorded in reports
[0032](../tasks/0032-host-feedback-report.md), [0033](../tasks/0033-host-filter-report.md),
[0034](../tasks/0034-host-dashboard-report.md), [0035](../tasks/0035-host-invoice-items-report.md),
[0036](../tasks/0036-host-property-controls-report.md), [0038](../tasks/0038-report.md) and
[0039](../tasks/0039-host-flash-outcomes-report.md); [0037](../tasks/0037-host-validation-report.md) owns final validation.

Those earlier 3,022 passing tests and 174 captures are historical evidence,
not acceptance of the wide-screen correction. The 0040 audit reproduced
header/filter offsets of 38px at 1440, 158px at 1680, 278px at 1920 and 342px
at 2048 CSS pixels. It also found clipped Czech row actions, a mobile invoice
action bar covering a field by 35.1px, a property Save bar covering postcode by
35.6px, and a duplicate copy confirmation moving the source control by 54px.
The enhanced All dates month control also retained a dashed fallback wrapper
around its solid trigger. It now uses one outline while the no-JavaScript
control remains available. Long overdue and scheduled labels crossed table tracks; a ready-row Send
button was 36px beside a 42px More control. The corrected labels wrap within
their tracks, with readable rounded backgrounds and matching action heights.

The final lane matrix covers **444 combinations**: 28 named host views in
English and Czech at six desktop widths, plus 18 representative views at
360, 390 and 760 pixels. It records **zero lane mismatches** and a maximum
header/results edge difference of **0px**. Focused checks include actual
non-dismissible persisted warnings, collapsed sidebars, direct Back links,
focused address inputs and every visible Stays row action. The final full suite rechecked the current CSS and visible-text collector:
**3,030 passed, zero skipped**, seven warnings and **89.57% coverage**, above
the 86% threshold. Required Chromium was enabled. Runtime Ruff, ShellCheck
and JavaScript syntax checks also passed.

The complete review gallery contains **413 unmodified captures**, including
40 baseline images and 373 corrected-state images; its manifest includes
SHA-256 hashes and the before/after measurement files. Exact validation
coverage is recorded in
[the 0040 validation report](../tasks/0040-luna_validation-report.md).
Review the [new before/after gallery](/workspace/generated_images/host-wide-audit/review/index.html)
or its [portable ZIP](/workspace/generated_images/host-wide-audit/host-design-audit-review.zip).
All captures use fictional fixtures in English and Czech. The live application
CSS is unchanged during capture; no screenshot-only layout correction is used.
Representative unmodified images are also [included in this PR](../tasks/0040-evidence/README.md).
These local browser captures do not establish the commit running on staging.

The current legal-source check remains [open](invoice-address-check.md): the
facility address and invoice seller/customer addresses are different contexts.
No new legal requiredness is inferred from layout. The pasted search demo does
not replace the existing fuzzy command engine.

See [staging handoff](host-design-staging-handoff.md) for deployment state and
the exact feature commit and deployment review. GitHub access works. The owner
will redeploy the corrected branch to their existing Render staging service.
GitHub CI still needs to establish the Docker/gitleaks results; the cloud
workspace cannot access a Docker daemon. A saved environment draft alone does
not activate network access or deploy the app.
No main push, production merge or production deployment is authorized here.
