# Cursor handoff: audited stay fee on the new host UI

This repository branch contains the **working source code**, the legal audit, and the selected host-app redesign together. Read `LEGAL_AUDIT_IMPLEMENTED.md` for the law and data rules and `docs/HOST_APP_DESIGN.md` for presentation. The older `PLAN_STAY_FEE_REMITTANCE.md` is historical. The UX package under `docs/plans/host-app-redesign/` remains an independently installable baseline artifact; **do not run its installer on this combined branch**, because its baseline fee files predate this audit.

## What Cursor should do

1. Start from this branch or its review PR. Inspect the current code before changing it. Do not regenerate fee PDF/CSV from live data after a period has been saved.
2. Preserve these fee contracts: counted days are `(arrival, departure]`; the exact 60-night boundary needs a recorded written office ruling; minor status is evaluated on each counted day; one report and register per facility; restricted guests keep complete statutory identity in the protected register; exemption reasons use controlled categories; finalization saves encrypted versioned copies; actual collected amounts are recorded separately from calculated due.
3. Use the new host UI layer (`host.css`, `host.js`, `host_design_i18n.py`, the navigation and alert partials). The fee detail page has one primary Save period action before finalization, frozen downloads afterward, and links from blockers to the record or setting that fixes them. Keep native form labels, the collected-amount confirmation, and correction state. Keep Stay fees in the rail when a saved historical period remains after the rate is disabled.
4. Preserve owner checks and CSRF on every fee endpoint. Cross-owner and cross-facility guest decisions must fail. The guest export must include only that guest's rows from saved fee registers. Workspace export must include all saved report/register versions.
5. Keep the deadline-sensitive DPA, privacy policy and guest notice updates in this branch. Before release, have the controller document an Article 9 GDPR condition and safeguards for disability-related reasons; do not state that Article 6(1)(c) alone covers special-category data.

## Verification already encoded in tests

- `App/tests/test_stay_fee.py`: day/month boundary, birthday, 60-day scope, per-facility reports, frozen versions, cadence overlap, CSV identity, encryption migration, retention, workspace export and guest access export.
- `App/tests/test_stay_fee_detail.py`: blockers, written ruling/reference, controlled exemptions, actual collection confirmation, correction and host rendering.
- `App/tests/test_stay_fee_downloads.py`: exact frozen PDF/CSV, zero period, restricted identity and cross-owner access.
- `App/tests/test_host_redesign.py` and the rest of `App/tests/`: host layout and cross-feature regressions.

From `App/`, run the repository's complete gate:

```bash
.venv/bin/python -m pytest tests -q
.venv/bin/ruff check app tests tools --select E9,F63,F7,F82,F401,F841
```

Also inspect the fee detail at desktop and phone widths in English and Czech: open and closed collected-amount disclosure, error and blocked states, a 60-night ruling, saved downloads, and a versioned correction. Check that payment copy is shown only for a saved amount and never implies a bank transfer or municipal filing occurred.

## Release decisions that code cannot make

- Obtain the affected office's written interpretation of an exactly 60-night stay and store its date/reference on each relevant facility.
- Confirm the controller's Article 9 condition, necessity and safeguards for disability-related exemption categories. The documents are updated in code; publishing them does not complete that legal assessment.
- Decide with counsel whether the live housebook plus period snapshots meets § 3g(3)'s permanent chronological-entry requirement. If UbyHost must be the sole evidenční kniha, build an append-only guest-entry journal before making that claim.
- Review consecutive bookings for the same guest/provider, unpaid or interrupted stays, and later stay extensions before filing. The current model does not automatically reconcile those cases.

No route submits a hlášení, confirms municipal receipt, or confirms payment. A saved PDF and CSV are **prepared documents** for the host to review and send.
