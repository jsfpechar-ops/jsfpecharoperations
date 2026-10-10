# Host design: application review

Owner-approved design, implemented on `task/host-design-staging`. This describes
the application changes, separately from the earlier standalone prototype.
Local application validation passed; GitHub CI and staging deployment remain pending.

| Page | Final selected design |
|---|---|
| Dashboard | Quiet white overview cards; amber action, taupe waiting, blue ready and red overdue; neutral zero counts. Five unique stays total, current stays and arrivals within thirty days, older unresolved urgent work first. Shared aligned Open/More actions; no property photos. |
| Stays | Filters open an inline panel. Property, state and one Stay dates control with From/Until in a shared calendar. Draft edits, Apply and Cancel. Closed default summary: All properties · Active; dates appear only when explicitly applied. Upcoming, Past, All dates and Archived remain views. |
| Invoices | Matching expandable panel with property/status/search and a compact twelve-month grid. Coral month selection and year arrows. Optional All dates. Default summary: All dates · All properties. |
| Stay fees and fee detail | The same month/filter family, retaining the required reporting period and each page's actual property/status fields and fee context. |
| Guest register | Matching property/date-range panel, with exports outside it and the existing legal register columns retained. |
| Invoice generator | Existing simple form, shared header/row columns, aligned Unit price inputs and reserved Remove track. Custom Description appears only for Other. Cleaning Unit stays blank. |
| Business & legal details | Edit, Invoice settings and More always visible. Linked operators have an unavailable Delete action with a visible explanation; backend guards remain. |
| Property address | Aligned complete labels and input tops; no Needed to report pills. Existing optional flags and validation retained pending source verification. |
| Properties | Local cards and settings remain; the duplicate Property tools dropdown is removed within an individual property. Cross-property tools remain on Properties and in Search. |
| Archived | Existing retained records and Restore remain. Delete actions move records here and explain that outcome; permanent deletion remains separate. |
| Shared controls | Clear hover and keyboard focus, visible touch actions, consistent button tracks. Copy guest form link names the target explicitly; successful copy shows Copied/checkmark without shifting the button. Failures expose a usable manual source. |
| Transient updates | Stacked white semantic cards, at most three visible. Save severity follows known outcomes. Errors, partial results and Undo persist; routine notices pause on hover/focus. Existing filing/receipt meaning remains. |

The product rule is extremely easy, intuitive use: familiar words, relevant
information, predictable placement and controls that work with touch and a
keyboard. [DESIGN.md](../DESIGN.md) is the shared design contract.

Application Chromium screenshots use synthetic fixtures in English and Czech
at mobile and desktop widths. The consolidated gallery is generated outside
the checkout at `/workspace/generated_images/host-design-application/index.html`.
Individual checks and captures are recorded in reports
[0032](../tasks/0032-report.md), [0033](../tasks/0033-report.md),
[0034](../tasks/0034-report.md), [0035](../tasks/0035-report.md),
[0036](../tasks/0036-report.md), [0038](../tasks/0038-report.md) and
[0039](../tasks/0039-report.md); [0037](../tasks/0037-report.md) owns final validation.

Final local validation: **3,022 passed, zero skipped**, including required
Playwright/Chromium checks; coverage **89.53%** against the 86% threshold.
The 39-page app/mock smoke passed three runs, including restart. CI-equivalent
lint/security results and baseline limitations are recorded in 0037. GitHub CI
is still required for the Docker image/health and Docker-based gitleaks checks;
feature push alone does not trigger CI, so a PR must be opened first.

Review the [174-image gallery](/workspace/generated_images/host-design-application/index.html)
or its [portable ZIP](/workspace/generated_images/host-design-application/host-design-review.zip).
All screenshots use synthetic data; they show the implemented application,
not an already deployed staging build.

The current legal-source check remains [open](invoice-address-check.md): the
facility address and invoice seller/customer addresses are different contexts.
No new legal requiredness is inferred from layout. The pasted search demo does
not replace the existing fuzzy command engine.

See [staging handoff](host-design-staging-handoff.md) for deployment state and
remaining access requirements. GitHub API/Render access needs the saved cloud
network draft published; a saved draft alone does not activate network access.
No main push, production merge or production deployment is authorized here.
