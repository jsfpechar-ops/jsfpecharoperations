# 0293 report

Status: review

## Files changed

- App/app/templates/invoice_form.html: supplier block and customer block replaced (steps 1-2); remove buttons now `ui-btn-quiet` (two places).
- App/app/host_i18n.py, App/app/host_vi_i18n.py: `invoice.buyer.or` added (en "or", cs "nebo", vi "hoặc").
- App/app/static/host2.css: 0293 block appended.
- App/app/templates/base.html: host2 key `?v=20261024-0293`.
- App/tests/static_versions.json: regenerated with `--write` (35 files).
- App/tests/test_0293_invoice_form.py: new, two tests (IČO before name; zip before city).
- App/tests/test_invoice_workspace.py: primary-count assertion scoped to `.invoice-actions` (see Deviations).
- docs/tasks/0293-report.md: this report.

## Test

Command (from App/): `.venv/bin/python -m pytest tests/test_0293_invoice_form.py tests/test_invoice_*.py tests/test_design_invoices.py tests/test_static_versions.py tests/test_design_guardrails_browser.py -q -rs --tb=short 2>&1 | tail -30`

Last lines:
```
SKIPPED [1] tests/test_invoice_autofill.py:300: set UBYHOST_SHOTS_DIR to capture acceptance screenshots
112 passed, 1 skipped, 1 warning in 44.45s
```

Before the scoped assertion, the same run gave: `1 failed, 111 passed, 1 skipped`. The failure was `test_issue_is_the_only_coral_primary_in_the_builder`, which counted 2 primaries (the new lookup button plus Issue invoice).

## Acceptance (brief §7)

- [x] Customer starts with the IČO lookup strip; guest-details button sits beside it when offered.
- [x] Name and street full width; postcode and city on one row; VAT ID and e-mail on one row (desktop). One column at 390 px by CSS (not screenshotted, per brief).
- [x] Remove buttons quiet; key bumped; tests run, failures listed.

## Deviations

- The brief's description of the old supplier block (an `invoice-supplier-row` wrapper and a trailing edit link) did not match the file exactly. The whole block between the anchors was replaced with the brief's step 1 text, so the result is what the brief specifies.
- Primary-count assertion: changed as the brief allows, now counting `ui-btn ui-btn-primary` inside `.invoice-actions` only.
- The one skip is `tests/test_invoice_autofill.py:300`, a screenshot capture gated by `UBYHOST_SHOTS_DIR`. Screenshots were skipped per brief, so this is not a browser geometry skip.
- Commit made locally on claude/project-thread-1am307 as one commit, not pushed. No PR opened, because the executor was told never to push.

## Questions

None.

## Owner steps left

None.
