# Cursor prompts

Paste Prompt 0 at the start of each new chat, then the step prompt below it.

---

## Prompt 0: master rules

```
You are implementing the "stay fee remittance" feature in the UbyHost repo (FastAPI + Jinja2 + SQLite, ReportLab).
Before writing any code, read fully: docs/plans/stay-fee-remittance/PLAN_STAY_FEE_REMITTANCE.md (v2). It is the single source of truth.

Rules:
- HOST-ONLY calculator. Guests see or touch nothing. Do not edit guest-facing templates or reservation_detail.html.
- Rate per property; 0 = off and is the default.
- Do NOT edit docs/plans/stay-fee-remittance-design/DESIGN.md or the layout in stay_fee_remittance_pdf.py. Do not change stay_fee.py calculation logic unless the step says so.
- Follow existing patterns: db.py SCHEMA + ADDED_COLUMNS, _flash(request, key) with i18n keys only (no literal strings), EN/CS parity in host_i18n.py, CSRF, access.* owner scoping, one coral primary button per screen, light mode only.
- One branch and one PR per step. Do not push to main. Do not mix steps.
- Write the tests named in plan section 13 for the step. Run: cd App && .venv/bin/python -m pytest -q. No new failures versus the baseline on main (Python 3.12).
- Non-goals: no filing, no payments, no paid-status tracking, no municipality form clones, nothing guest-facing.
- If the plan and the code disagree, stop and tell me; do not guess.

Reply with: files changed, tests added, test result, anything you were unsure about.
```

---

## Step 2: property panel

```
Implement plan step 2 (branch feat/stay-fee-property-panel): plan section 9.4 (the #stay-fee-settings panel in apartment_form.html, inside the form after #communication and before Notes; _apartment_payload and _save_apartment_form changes; account validation via payments.normalise_account; copy-from JS) plus the section 12.2 apartment.form.stay_fee.* i18n keys in EN and CS.
Write App/tests/test_stay_fee_property_panel.py with exactly the cases listed under "Step 2" in plan section 13.
```

## Step 3: document type

```
Implement plan step 3 (branch feat/stay-fee-doc-type): plan section 9.5, the doc_type select on the HOST guest form (guest_form_admin.html) with the guest.doc_type.* keys. Default from stay_fee.default_doc_type (CZE -> OP, otherwise passport), editable by the host. The guest's own form must not change.
Write App/tests/test_stay_fee_doc_type.py per plan section 13 "Step 3".
```

## Step 4: entity signature

```
Implement plan step 4 (branch feat/stay-fee-entity-signature): plan section 8.3, signature upload (PNG/JPEG, max 300 KB, validated by content, stored encrypted) and typed signature name on legal entities (entities.html + route), keys entity.signature_* and flash.entities.signature_invalid.
Write App/tests/test_stay_fee_signature.py per plan section 13 "Step 4".
```

## Step 5: list page

```
Implement plan step 5 (branch feat/stay-fee-list): routes/stay_fees.py list route, template stay_fees.html, sidebar link, icon, command-palette entry, registration in main.py, and ALL section 12.1 i18n keys (EN + CS, including month.1..12).
Match docs/plans/stay-fee-remittance/stay-fees-list.html. Write App/tests/test_stay_fee_list.py per plan section 13 "Step 5".
```

## Step 6: detail page

```
Implement plan step 6 (branch feat/stay-fee-detail): the detail route and template, payment panel with QR (reuse payments.spayd / qr_data_uri), guest list, POST /stay-fees/guest-decision (exempt / charge / back to automatic; the reason must NOT go into the audit log), and CSS. Match docs/plans/stay-fee-remittance/stay-fees-detail.html.
Write App/tests/test_stay_fee_detail.py per plan section 13 "Step 6".
```

## Step 7: downloads

```
Implement plan step 7 (branch feat/stay-fee-downloads): GET /stay-fees/{id}/pdf (plan section 8.2, using stay_fee_remittance_pdf.render, blocked with report_blocked while the period is running) and the register CSV route (plan section 10). Both owner-scoped.
Write App/tests/test_stay_fee_downloads.py per plan section 13 "Step 7".
```

## Step 8: docs

```
Implement plan step 8 (branch docs/stay-fee): documentation only, exactly as described in plan section 13 row 8 (App/README.md, docs/plans/README.md, banner in PLAN_POPLATEK_Z_POBYTU.md, docs/OPERATIONS.md "Stay fee" subsection). No code changes.
```
