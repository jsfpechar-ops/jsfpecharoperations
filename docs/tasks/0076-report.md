# 0076 report: one business editor with invoice details

Status: review. Executor: Claude (owner-authorized), combined staging lane §2 mode.

- Start: `5a4744b` (coordinator branch `claude/quirky-lamport-9svmd1`). Code commit: `4843397`.
- Diff: 25 files, +894/−186 (7 PNGs included).

## Anchors (old → new)

- `invoices.py` `@router.get/post("/invoices/settings")` → moved to `admin.py` as legacy adapters `invoice_settings_legacy` / `invoice_settings_legacy_save`. The admin router is included before the invoices router, so "settings" is still never read as an invoice id.
- `entities.html` `<form ... action="/entities/{{ edit_entity.id }}" enctype=...>` is unchanged and now sits inside `#entity-business`.
- Property business card: `apartment_form.html` → `_property_overview.html`, which 0094 split out. That partial is not listed in §3. It holds the card, so I edited it there.

## What changed

- **One editor** (`/entities?edit={id}`): a "Used by" row lists the linked active properties, each linking to its Settings → Property information `#operator-picker`. A `?` tip says that changing the business used is done in that property's Settings. Under it are two sections with header bars:
  - **Business details** (`#entity-business`): the existing multipart form, with the same names and handler.
  - **Invoice details** (`#entity-invoice`): the 0075 `invoice_fields` + lookup `ico_field`, urlencoded, posting to the new `POST /entities/{id}/invoice`. Its hidden fields are the same as before: `_csrf`, `legal_entity_id`, `next`, `_invoice_account_existing`.
  - Each partial is rendered once. There is no invoice section for archived entities.
- **One implementation:**
  - `invoices.py` now holds `save_invoice_details`, `lookup_invoice_details`, `invoice_bank_view`, `owned_entity` and `builder_path`. These are the old handler bodies, unchanged in normalisation, BIC derivation and audit.
  - `admin.py` has `_entities_page`, the one renderer for GET, both ARES rerenders and 422s. It also has `_invoice_details_response`, which both the canonical and the legacy POST call. Imports go one way only (admin → invoices).
- **Legacy URLs:**
  - `GET /invoices/settings?entity=X[&next=]` → 303 to `/entities?edit=X&next=…#entity-invoice`. The default `next` is still `/invoices/new?entity=X`, the old default.
  - With one entity and no id, it opens that entity. With several and none named, or a foreign/unknown id, it goes to the `/entities` list and never opens an arbitrary record. With none, it goes to `/invoices/new` with the old error.
  - The legacy `POST` runs the same save/422/ARES path. It does not redirect away from submitted data.
- **Return paths:** `next` is validated by `security.safe_local_path`, so outside URLs are dropped. It is carried as a hidden field in both forms. A successful business save now returns to `next` when present, otherwise `/entities` as before.
- **Links retargeted:**
  - Property Overview card: `/entities?edit=X&next=/apartments/{id}`. With no business, it goes to the property's Settings `#operator-picker`.
  - Properties list: `&next=/apartments`.
  - Account settings `#settings-business`: `/entities?edit=X&next=/settings` with exactly one business, else `/entities`.
  - Invoice builder: the canonical URL with the builder as `next`.
  - Entity list "Invoice settings" button: `#entity-invoice`.
- `invoice_settings.html` deleted (no renderer uses it).
- `app.js` `initUnsavedForms`: when one form on the page is submitted or the page is left while the other form has unsaved edits, the browser asks first (`beforeunload`). This keeps a business draft from being lost by saving Invoice details.
- `host.css` `/* 0076 */` block. `host_i18n.py` `_ENTITY_EDITOR_0076_STRINGS` (5 keys, EN+CS).

## Decisions / behaviour changes

1. **Invoice-details IČO stays lookup-only** (0075 open question, decided conservatively). It fills a blank registry entry and proposes VAT payer, and is never saved. As a result, the editor shows a second, lookup-only IČO input under Invoice details. **Owner decision:** keep it, replace it with a button that uses the stored IČO, or merge.
2. **Forged legacy POST:** a `legal_entity_id` that is not the host's active entity is now refused (`/entities?err=`). Before, it fell back silently to the host's first entity and saved there.
3. Business-form errors (bad IČO/account/signature) still redirect with a flash, as 0075 left them.
4. `invoice_detail.html`, `invoices.html`, `invoice_stay_picker.html`, the invoices sub-nav and the command palette still link `/invoices/settings`. These files are outside §3, and the adapter resolves the right entity. The palette test pins that URL.

## Files outside §3

- `_property_overview.html` (moved anchor, see above).
- Tests, each intentional change with a replacement assertion: `test_entity_editor_fields.py` (per-form contracts; the template-ownership test now asserts `invoice_settings.html` is gone), `test_invoice_settings.py`, `test_host_invoice_navigation.py` (builder link is canonical), `test_property_hub.py` (settings link pattern), `test_property_navigation_browser.py` (card `next`), `test_host_wide_geometry_browser.py` (`invoice-settings` route lane = `.entity-form`).

## Commands (from App/, staging/mock/REQUIRE_BROWSER, pinned Chromium)

```
pytest tests/test_entity_editor_navigation.py -q -rs                → 17 passed
pytest <58 files touching entities/invoice settings/properties/settings/search> tests/test_property_readiness.py -q -rfEs
   (UBYHOST_SHOTS_DIR set so test_invoice_autofill does not skip)   → 826 passed, 2 failed, 1 skipped
   failures fixed (property card next, wide-lane selector) → both files: 17 passed
   skip: test_dashboard_missing_banner.py:174 evidence-capture gate (pre-existing, not browser/geometry)
pytest tests/test_endtoend.py -q                                    → 28 passed
pytest tests/test_security.py -q                                    → 1 failed (test_security_headers_on_healthz, known order-only alone)
ruff (E9,F63,F7,F82,F401,F841) → All checks passed   context_lint → OK
```

The full suite with coverage was not run (coordinator: focused tests only).

## §7 evidence

- [x] One edit destination and one save/render implementation: `test_editor_has_both_sections_and_the_linked_properties`, `test_legacy_post_saves_through_the_same_implementation`.
- [x] Correct entity, safe next, legacy GET/POST, 422 typed values: the `test_legacy_*`, `test_canonical_post_*` and `test_editor_keeps_a_safe_return_path_only` tests.
- [x] Two properties sharing one entity show the new business, and the issued invoice row and `invoice_sequence` stay identical: `test_shared_business_change_reaches_both_properties_but_not_issued_invoices`.
- [x] Cross-owner forged ID and external return URL rejected; list actions kept: `test_forged_and_archived_entities_are_refused`, `test_legacy_post_refuses_a_foreign_entity_without_saving`.
- [x] Browser: no overflow and all controls inside the viewport at 360/390/768/1280/1440/2048 EN/CS, with the rail expanded and collapsed at ≥1024. The legacy URL lands on `#entity-invoice` in view. An unsaved business draft prompts before Invoice details is saved.
- [ ] CI on the task head: not run (no push).

## Evidence

`docs/tasks/0076-evidence/entity-editor-{360,390,1280}-{en,cs}.png` and `legacy-invoice-settings-1280-en.png` (`UBYHOST_CAPTURE_0076=1`; synthetic "Ukázka Pole s.r.o.", example.test). At 360/390 the sticky top bar covers the editor heading in the element screenshot; the live page is unaffected.

## Owner steps

1. Look at `entity-editor-1280-en.png` and `entity-editor-390-cs.png`.
2. Decide the lookup-only IČO under Invoice details (decision 1).
3. On staging: open a property → Business card → change the phone → Save; you return to the property.
