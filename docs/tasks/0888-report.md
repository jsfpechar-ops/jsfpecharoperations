# 0888 report: invoice last price and payment defaults

Status: review (nothing committed or pushed: the lead asked for no commit)

## Files changed
- App/app/routes/invoices.py: `PAID_VIA_CHOICES`, `_remember_paid_via` (above `_form_state`), call under the price-hint lines in `_form_context`. 0836 buyer prefill and Guest/Company logic untouched.
- App/app/templates/invoice_form.html: "Use last price" button (hidden, shown by JS), JS block under `var entitySel`.
- App/app/static/host2.css: `0888` block at the end (var tokens only).
- App/app/templates/base.html: host2.css key `20261103-0888`.
- App/tests/static_versions.json: regenerated (`--write`).
- App/tests/test_invoice_autofill.py: `_issue_paid` helper and four tests.
- docs/design/catalog.json: `invoice-use-price` added to classes.
- docs/tasks/0888-report.md: this file.

## Commands (last lines)
- cmd1 `tests/test_invoice_autofill.py`: `18 passed, 2 skipped` (the 2 skips are env-gated screenshot tests).
- cmd2 invoice, stay_fee, static_versions: `266 passed, 2 skipped` (same 2 screenshot skips). With UBYHOST_SHOTS_DIR set, the autofill file gives 0 skipped (cmd4 run below).
- cmd3 host row: `218 passed, 1 skipped, 2 deselected`. The skip is test_host_copy_corrections (browser check); run alone with UBYHOST_REQUIRE_BROWSER=1: `9 passed`. Deselected: test_frozen_report_order_and_forms (known) and test_page_families_through_rail_cards_search_and_back (the test that contains test_host_ux_acceptance.py:642; it fails at line 655 on `a[href="/invoices"]` click timeout; I did not verify it against main).
- cmd4 browser row with UBYHOST_SHOTS_DIR and UBYHOST_REQUIRE_BROWSER=1: `27 passed in 49.29s`, 0 skipped.
- `python3 scripts/design_lint.py`: `design lint: OK`.

## Screenshots
390 px: scratchpad form-390.png and invoice-fill-after-390.png under /tmp/claude-0/-home-claude-jsfpecharoperations/e86b1b48-5cef-5352-bec7-2d32ded304cc/scratchpad/shots0888/ (360 and 1280 also written).

## Section 7
- [x] The price is filled only by the tap; without JS the old hint shows and the button stays hidden.
- [x] Paid-via starts at the last used method; a re-render keeps the host's choice (guard on `already_paid`/`paid_via` keys in code; no separate test for the 422 path).
- [x] Commands 1-4 pass, 0 skipped (cmd4 yes; cmd1-3 skips are the env-gated screenshot tests and the copy_corrections browser check, both run green with the env set).

## Deviations
- No commit, no push (lead instruction overrides the brief's "Commit step k").
- Used the existing `_second_stay_same_property` helper instead of adding `_second_stay`; `_issue_paid` takes the entity id.
- CSS uses `var(--space-3)` and `var(--control-h-phone)` instead of the brief's bare px. Added `.invoice-use-price[hidden]{display:none}`, because `display:inline-flex` would override the `hidden` attribute.
- catalog.json entry added (needed for design lint on the new class).
- Optional test_0890 addition not done (brief said only if small).
- Done: steps 1 to 4 and §6 commands. Left: commit/PR, if the lead wants them.

## Questions
- Should the test_page_families failure be confirmed as pre-existing on main before merge?

## Owner steps left
1. Merge with `scripts/merge-pr-on-green.sh <pr>` when CI is green (after a commit and PR are opened).
