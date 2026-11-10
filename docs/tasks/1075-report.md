# 1075 report

Status: review (unblocked by 1075-cont-1)

## Files
payments.py, payments_new.html, admin.py, _entity_business_fields.html, setup_wizard/property.html, _entity_invoice_fields.html, host_i18n.py, host_vi_i18n.py, _smart_lock_share.html, tests/test_1075_prefill_more_options.py (new). The brief was updated in step 0 (review) and in step 6.

## Commands (last line)
- step 1 test_payments_dashboard: 15 passed
- step 2 entity editor fields + navigation: 68 passed
- step 3 wizard 0884 + 0273: 14 passed
- step 4 entity fields, i18n, em dashes, test_host_help_browser (REQUIRE_BROWSER): 78 passed, 0 skipped
- step 5 ttlock 0954 + smart locks page: 39 passed
- step 6 test_1075: 6 passed, 0 skipped
- step 7 shots script: all 21 shots taken, 0 px sideways scroll on every page, fold summary 52 px, tip at 1280 not clipped. The scratch script's cleanup hit a FOREIGN KEY error (local test DB only).
- step 7 layout lint, test_host_* / geometry / guardrails, context lint: NOT finished (cap).

## Step 7 finding (blocking)
`/tmp/shots/1075/operator-edit-fold-open-390.png`: inside "More invoice options" the next-number help text shows inline under the label and is cut off at the right edge ("...invoices th", "UbyHost invoic"). The fold's `overflow:hidden` and 16 px inset clip it. 1280 is fine (measured, not clipped). The brief says stop: the allowed fix is dropping `overflow:hidden` from the fold, and only if the design-system allows it. Needs the orchestrator.

## Visual per page (390 checked by eye; 768/1280 taken but not reviewed)
- payments new (stay): 390: guest e-mail filled, clean.
- entities add: 390: account e-mail prefilled, clean.
- entities edit, fold closed: 390: registry entry visible, closed fold with one chevron, due days below, clean.
- entities edit, fold open: 390: help text clipped (see above).
- wizard property: 390: 15:00 shown, clean.
- lock tab: 390: name, steps, then both warnings, clean.

## Deviations
- The step 6 share test uses the Door lock tab, not /smart-locks: /smart-locks has no share section, and "Open your lock in TTLock." is not the EN step text.
- The wizard door-lock step is retired (0884). The lock tab covers it.
