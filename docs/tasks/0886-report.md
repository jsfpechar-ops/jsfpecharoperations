# 0886 report: Invoice buyer switch

Status: blocked (tool-call checkpoint reached, and one test outside the brief's known list fails)

## Files changed (git diff --stat 83aea3e for these files)

- `App/app/routes/invoices.py`: step 1 (helper `_drop_guest_suggestion`, `buyer_kind` in `_form_state` and `_form_context`, ARES branch in `invoice_issue`). Anchor check: 8 lines.
- `App/app/templates/invoice_form.html`: step 2 (7 edits, choice cards, `data-buyer-only`, script). Anchor check: 7.
- `App/app/host_i18n.py`: step 3 EN and CS keys (6 lines).
- `App/app/host_vi_i18n.py`: step 3 VI keys added below `invoice.fill_guest.prefilled`, same flat-dict pattern as commit f7b1637 (3 lines, Edit tool).
- `App/tests/test_invoice_autofill.py`: step 4 (import, 4 tests, screenshot test).
- `docs/tasks/screenshots-0886/`: written by the screenshot test (UBYHOST_SHOTS_DIR set).
- Nothing committed or pushed.

## Commands (last lines)

1. `pytest tests/test_invoice_autofill.py tests/test_0293_invoice_form.py tests/test_design_invoices.py`: `19 passed, 2 skipped` (skips are the screenshot test without UBYHOST_SHOTS_DIR and one other test; not yet identified with -rs). Brief expects 0 skipped; this run did not set the env var.
2. Invoices row with UBYHOST_SHOTS_DIR and browser env: `245 passed in 49.75s`, 0 skipped.
3. Host row (`test_host_*.py`, geometry, guardrails browser), with -x: `1 failed, 197 passed`. Failure: `tests/test_host_ux_acceptance.py::test_page_families_through_rail_cards_search_and_back` at line 637, `#entity-business` not visible on `/entities?edit=N`. Reproduces alone. Not on the brief's known-failure list. The file that renders this page is not changed by 0886, but this is not proven pre-existing.
4. Copy row, with -x: `1 failed, 4 passed`. Failure: `tests/test_host_i18n.py::test_language_endpoint_sets_cookie_and_rejects_open_redirects`, which is on the brief's known list. Not rerun without -x.
5. Screenshot test: ran as part of command 2 and passed. Not run separately.

## Section 7

- [x] One entity hides the picker; two show it (test uses a stay with no pinned operator).
- [ ] Not verified: first-open Guest state and ARES replacement in a browser, beyond the tests above.
- [x] Typed values kept; lookup issues nothing (tests).
- [x] Without JS all fields render (test).
- [ ] Not checked: `git diff 83aea3e -- App/app/ares.py App/app/static` and the localStorage grep.
- [ ] Commands 3 and 4 not green (see above).
- [ ] Screenshots: four PNGs expected; the test wrote them, not checked by hand.

## Deviations

- Test fix: `test_two_entities_show_the_issuer_picker` used a stay pinned to an entity. `_form_state` then reduces the picker to that one entity (routes/invoices.py, the "no other choice" branch), so the test as written could not pass. The stay now has no pinned entity. This is a test-only change, not a code change.
- Step 3 script first truncated `host_vi_i18n.py` before its anchor check failed. Restored with `git checkout` to HEAD, then the keys were added with Edit.
- Step 1c indentation follows the brief literally (anchor at 8 spaces, inserted lines at 4).

## Questions

- Is `test_page_families_through_rail_cards_search_and_back` failing on the base commit too? Needs a run on 83aea3e.
- Should the picker rule (stay pinned to one entity) be the brief's intent? The brief says "two or more entities".

## Owner steps left

- None until the questions above are answered.
