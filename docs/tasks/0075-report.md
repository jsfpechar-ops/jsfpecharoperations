# 0075 report: shared business and invoice field ownership

Status: review. Executor: Claude (owner-authorized), combined staging lane §2 mode.

- Start: `ab0a2f1` (main), merged `claude/quirky-lamport-9svmd1` @ `afc874a` (merge `96da2a6`; clean, entity anchors unchanged).
- Commits: `0b5612c` equivalence tests, `01b2c60` WIP, `e8fcb8c` implementation, then this report/status commit.
- Diff vs `afc874a` (excluding evidence): admin.py 81, invoices.py 227, two new partials, entities.html, invoice_settings.html, new test file. All inside §3. host_i18n.py unchanged: no new strings were needed (EN+CS reuse existing keys).

## Anchors

`entities.html` `{% macro operator_fields(prefix, entity) %}` → moved to `_entity_business_fields.html` as `business_fields`. `invoices.py` "Presence-checked invoice details…" docstring → kept on the renamed `invoice_detail_payload`.

## Field matrix (current code)

| Field (name) | Entity create/edit (`/entities`, `/entities/{id}`) | Invoice settings (`/invoices/settings`) | Owner now |
|---|---|---|---|
| name | text, required, saved | not shown | business partial |
| seat | text, required, saved | not shown (summary only) | business partial |
| ico | text, required, saved; ARES button | text, maxlength 8, not required, **lookup only, never saved** | `ico_field(context='business'/'lookup')` |
| dic | text, optional, saved; ARES fills blank | not shown | business partial |
| contact_email / contact_phone | email required / text optional | not shown | business partial |
| signature_drawn / signature_file / signature_remove / signature_name | hidden, file (png/jpeg, multipart), checkbox only with stored image, text ≤80 | not shown | business partial; `_signature_payload` (admin) |
| account_prefix/number/bank | not posted | three fields (`invoice_` ids), IBAN-only shown as text | invoice partial + `_account_parts.html` |
| bank_account (legacy single field) | accepted if posted | accepted if posted | `apply_account_payload` |
| bic | accepted if posted | text, optional; "filled from bank code" hint | invoice partial; `derive_missing_bic` (settings only) |
| vat_status | accepted if posted | select non_payer/identified/payer; ARES may set payer | invoice partial; `invoice_detail_payload` |
| registry_entry | accepted if posted | text; ARES fills blank | same |
| invoice_prefix / invoice_next_number (+year) / invoice_due_days | accepted if posted | text ≤6 / number ≥1 / number 0–365 | same |
| ARES messages | above fields in both forms | under IČO, plus "VAT found" | `register_messages`; `register_lookup` |

Actions/encoding unchanged: `POST /entities` and `/entities/{id}` multipart; `POST /invoices/settings` urlencoded with `_csrf`, `legal_entity_id`, `next`, `_invoice_account_existing`.

## Ownership after the change

- Markup: `_entity_business_fields.html` (`register_messages`, `ico_field`, `business_fields`, `signature_fields`, `business_form_body`), `_entity_invoice_fields.html` (`invoice_fields`). The two pages hold no field macros; a test asserts each field name occurs in exactly one template.
- Normalisation: `routes/invoices.py` `invoice_detail_payload`, `apply_account_payload(accept_parts=…)`, `derive_missing_bic`, `register_lookup`, `register_filled_note`. `admin._entity_details_payload` and `_entities_ares_rerender` call them. One renderer `_settings_page` for GET, ARES and error rerenders.

## Intentional differences kept (explicit policy)

1. Only invoice settings composes the three account fields (`accept_parts=True`); the entity editor never posts them (`accept_parts=False`).
2. Only invoice settings derives a missing BIC from the bank code; the entity handler never does (tested).
3. Invoice settings IČO is lookup-only and not saved (current behavior; flagged for 0076 owner decision).
4. Entity errors (bad IČO, bad account, bad signature) still redirect with a flash.

## Behavior changes (acceptance §7 "rerenders retain typed values")

- Invoice settings invalid account now rerenders (422) with every typed value and the error above the account fields, instead of redirecting and losing input. Stored values unchanged.
- Invoice settings ARES rerender now keeps typed account parts (previously re-showed the stored account).

No redirects of entry URLs, no schema, dependency or new outbound request; ARES stays click-only with the existing 20/window limit and 24 h cache (tested: one HTTP call for two clicks, no call on GET/save). Issued invoice rows and `invoice_sequence` unchanged by both saves (tested).

## Commands and results (from `App/`, staging/mock/REQUIRE_BROWSER env)

- `pytest tests/test_entity_editor_fields.py` → 47 passed (before refactor: 43 passed, 3 target failures as expected).
- Brief §6 set + entities/invoice/ARES/signature/onboarding/privacy tests (34 files, excluding test_endtoend) → 416 passed, 1 skipped (`test_invoice_autofill.py:300`, needs `UBYHOST_SHOTS_DIR`; pre-existing, not browser/geometry).
- `test_endtoend.py` alone → 28 passed. Run after the other files it fails (19–20 failures) **identically on the pre-change base** `96da2a6`: an existing order dependency, not caused by 0075.
- Browser/geometry: test_host_geometry, test_host_wide_geometry_browser, test_wp28_geometry, test_host_controls_browser, test_host_property_controls_browser, test_host_invoice_items_browser, test_invoice_stay_browser, test_wp28_ui_sweep, guest nav/country picker → 69 passed, 0 skipped, 4 failed: 3 are listed baseline failures (`test_host_wide_geometry_browser` lanes/midwidth/collapsed); `test_wp28_geometry::test_calendar_remove_button_is_visible_without_scrolling` failed only in the combined run and passes alone, both here and on base (7/7).
- ruff (E9,F63,F7,F82,F401,F841) → clean. `scripts/context_lint.py` → OK.
- Full suite with coverage not run (coordinator instruction: focused tests only).

## Evidence

`docs/tasks/0075-evidence/`: `entity-edit-`, `entity-add-`, `invoice-settings-{360,390,1280}-{en,cs}.png` (18), captured once with `UBYHOST_CAPTURE_0075=1` by `test_entity_editor_fields.py::test_entity_and_invoice_editors_fit_every_width`. That test also checks for no horizontal overflow and that every control is inside the viewport and at least 40 px wide, at all six width/language combinations. Synthetic entity "Ukázka Pole s.r.o.", example.test mail.

## Risks / owner steps

- `admin.py` imports `routes.invoices` inside the entity section (no cycle: invoices imports only admin_helpers). Parallel admin.py edits elsewhere should merge cleanly.
- Owner: review this diff, then let the orchestrator continue with 0076. No push, PR or deploy was done.
