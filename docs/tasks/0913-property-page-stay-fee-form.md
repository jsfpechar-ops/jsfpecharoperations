# 0913: Property page and stay fee form: no overflow, styled fields, quieter save bar

Status: todo. Source: UX review 2026-11-04 (findings 4 and 5; Properties, Property page, Property → Stay fee and Stay fees rows). Executor: Haiku 5.5, one run. Run after 0912 is merged.
Read first: AGENTS.md, docs/context/executor.md, docs/design/MASTER.md (forms section only) and `docs/design/pages/` for the property page (`ls docs/design/pages | grep -i prop`), this brief.

## 0. Before you start
PR #772 must be merged (this brief edits `app2.css`). Branch from a fresh `origin/main`. No guest, public or Payments file.

## 1. Objective
- The stay fee form stays inside its card.
- Every stay fee field looks like every other input.
- An empty signature is a single "Add signature" button.
- The save bar shows only after an edit.
- The property title keeps its "?" on the last word.
- Property names in the list use the free space.
- The Stay fees page loses its large gaps.

## 2. Context (verified 2026-11-04)
- `templates/_stay_fee_fields.html` (64 lines). Four inputs have no `type` attribute: line 44 `stay_fee_authority_name` (the "Council office name" from finding 5), 51 `stay_fee_authority_address`, 55 `stay_fee_authority_contact`, 59 `stay_fee_authority_databox`. The other inputs have `type="text"`/`"number"`.
- Stay fee section: `templates/_property_editor.html` 340-~380, `<details class="prop-sec" id="sec-fee">` > `<section class="panel property-section ui-section" id="stay-fee-settings">`. Save bar: `_property_editor.html` 389-393 `<div class="savebar">` with Cancel, `[data-unsaved-reset] hidden` and Save.
- Signature: `templates/_fee_signature_fields.html` calls `signature_fields('fee_', ...)` from `templates/_entity_business_fields.html` (`grep -n "macro signature_fields" App/app/templates/_entity_business_fields.html`).
- Properties list: `static/app2.css:341` (desktop `@media (min-width:1024px)`) contains `body.v2 .props-card > table td:nth-child(1),body.v2 .props-card > table td:nth-child(2){max-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}`.
- Stay fees page: `templates/stay_fees.html` (257 lines). The "Download PDF" / "send by data box" block uses keys `stay_fees.download_pdf` and `stay_fees.send.title` (`host_i18n.py` ~137, ~192).

## 3. Files
`templates/_stay_fee_fields.html`, `templates/_property_editor.html`, `templates/_entity_business_fields.html` (signature macro only), the template holding the property page `<h1>` (step 5), `templates/stay_fees.html`, `static/app2.css`, the JS file that un-hides `[data-unsaved-reset]` (step 4), `host_i18n.py`, `host_vi_i18n.py`, cache keys, tests.

## 4. Steps
1. **Shared input style (finding 5).** Add `type="text"` to the inputs on lines 44, 51, 55 and 59 of `_stay_fee_fields.html`.
2. **No overflow (finding 4).** Find the rule file with `grep -n "prop-sec\|property-section" App/app/static/app2.css | head`. Append: `body.v2 #stay-fee-settings :is(input, select, textarea){max-width:100%;box-sizing:border-box}` and `body.v2 #stay-fee-settings :is(.ui-field, .field, .field-row, .grid > *){min-width:0}`. If the property page has a preview column (`grep -n "preview" App/app/templates/_property_editor.html | head`), give its grid parent's columns `minmax(0,1fr)`. Check the 1280 and 768 shots: no field edge past the card.
3. **Empty signature becomes a button.** In `signature_fields`, when the macro's preview argument is empty, wrap the drawing area in `<details class="signature-add"><summary class="ui-btn ui-btn-secondary">{{ t('signature.add') }}</summary> ...existing drawing area... </details>`. When a signature exists, render as today. New key `signature.add`: en "Add signature", cs "Přidat podpis", vi "Thêm chữ ký". Check first that no such key exists: `grep -n "\"signature\.\(add\|draw\)\"" App/app/host_i18n.py`. If one does, reuse it. The business page uses the same macro, which is intended.
4. **Save bar only when dirty.** `grep -n "data-unsaved-reset" App/app/static/*.js` gives the place that un-hides Discard when the form changes. At that place, also add the class `is-dirty` to `closest(".savebar")`, and remove it where Discard is hidden again. CSS: `html.has-js body.v2 .savebar:not(.is-dirty){display:none}`. Without JS the bar stays visible. `has-js` is set at `app.js:38`.
5. **Title keeps its "?".** `grep -rn "<h1" App/app/templates/_property_editor.html App/app/templates/apartment_form.html App/app/templates/property_*.html | head` finds the property page title that ends in `page_help`/`help_tip`. Render the name as `{% set parts = (name).rsplit(' ', 1) %}{% if parts|length == 2 %}{{ parts[0] }} {% endif %}<span class="nowrap">{{ parts[-1] }}{{ <the existing help call> }}</span>`. Add `.nowrap{white-space:nowrap}` only if `grep -n "\.nowrap" App/app/static/app2.css` finds none.
6. **Stray "?" in "Checklist details".** Run `grep -n "Checklist details" App/app/host_i18n.py` to get the key, then grep the key in templates. Move the `help_tip` so it comes after the label text, inside the same `field-label-row`, like line 343 of `_property_editor.html`.
7. **Property names use the space.** In `app2.css:341`, remove `body.v2 .props-card > table td:nth-child(1),` from that selector so only column 2 truncates. Give the name cell `title="{{ apartment.internal_name }}"` if it has none (grep `props-card` in `templates/apartments.html`).
8. **Stay fees gaps.** In `stay_fees.html`, find the block with `stay_fees.download_pdf` and `stay_fees.send.title`. Give each step's container `display:flex; flex-direction:column; gap:12px`, and remove any `margin-top` or empty `<p>` spacer between the text and its button. Step spacing in the stay fee section of the property page: 24 px between steps, 12 px inside a step.
9. Bump the cache keys you changed. Follow `test_static_versions.py`.

## 5. Do not touch
`_components.html`, `base.html`, `dashboard.html`, guest/public templates, Payments, invoice logic.

## 6. Commands (from `App/`, `2>&1 | tail -30`)
- `.venv/bin/python -m pytest tests/test_property_*.py tests/test_onboarding*.py tests/test_stay_fee*.py tests/test_invoice_*.py tests/test_host_*.py tests/test_host_geometry.py tests/test_design_guardrails_browser.py tests/test_static_versions.py tests/test_wp07_cache_heartbeats.py -q --tb=short -x -rs`, 0 skipped.
- Copy row: `test_*_i18n.py test_no_em_dashes.py test_flash_literals.py`.
- UX gate: `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots .venv/bin/python -m pytest tests/test_layout_lint_browser.py -q -x -rs`, 0 skipped, zero host findings. Open the 390/768/1280 shots of: the property page with the Stay fee section open, Properties, Stay fees, and the business page (shared signature macro). If the lint does not open `#sec-fee`, add that to a new `tests/test_0913_stay_fee_layout_browser.py`: Chromium at 390/768/1280 asserting every input in `#stay-fee-settings` has `right <= card.right`, with screenshots under `/tmp/shots/0913/`. PR body: per page "390: ...; 768: ...; 1280: ...".
- `python3 scripts/context_lint.py`.

## 7. Acceptance
- [ ] No stay fee field overflows at any width. The council office fields match the other inputs.
- [ ] An empty signature shows one "Add signature" button.
- [ ] Cancel/Save are hidden until a field changes (JS on), and visible without JS.
- [ ] The "?" sits on the title's last word and the "Checklist details" label.
- [ ] Names are not cut while the row has free space (1280).
- [ ] 12 px neighbour rule, light mode only, no new dependency.

## 8. Stop and ask
An anchor is missing; the signature macro has no preview argument; the dirty-state JS is shared with guest pages (then STOP: guest pages stay untouched).

## 9. Report
`docs/tasks/0913-report.md` with the 390 px shots.
