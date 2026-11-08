# 1029: dated stay-fee rates, part 3 of 3: "applies from" date next to the rate in the property editor

Status: ready
Depends on: 1028 merged | Base: `origin/main` after 1028 | Branch: `claude/dated-rates-1029` | No PR (push only)
Executor: Haiku 5.5, one run, 30 tool calls. UI brief: rules 7 and 10 apply (browser and geometry tests for the changed page, 0 skipped, one 390 px screenshot, UX gate in the report; the orchestrator runs the UX gate before merging).

## 1. Objective

1028 already reads the form key `stay_fee_rate_from` (ISO date, default today, past clamped to today). Add the field. The rate lives in `App/app/templates/_stay_fee_fields.html` (`stay_fee_rate_czk`, used by the property editor and the setup wizard).

Behaviour:
- Property editor only (`not fee_required`) and only when the stored rate is above 0: a date input `stay_fee_rate_from`, value today, `min` today, label "Applies from", help "Nights before this date keep the old rate. Leave as today if the new rate starts now." The field is optional and works without JavaScript (plain `<input type="date">`).
- Wizard (`fee_required`) and rate 0: no field (first rate applies from the beginning).
- Server already ignores a past date; the `min` is only a hint.
- Copy rule: one explanation in one place, no sentence the button already says.

## 2. Files

| Path | Action |
|---|---|
| App/app/templates/_stay_fee_fields.html | edit: one `.field` in the `grid two` after the rate field (the cadence field is the sibling; keep the grid) |
| App/app/host_i18n.py, App/app/host_vi_i18n.py | edit: keys `apartment.form.stay_fee.rate_from_label` and `apartment.form.stay_fee.rate_from_help`, EN, CS and VI parity (find neighbours with `grep -nF "apartment.form.stay_fee.rate_help" App/app/host_i18n.py App/app/host_vi_i18n.py`) |
| App/app/routes/stay_fees.py | edit only if the editor render needs `today` passed: prefer computing in the template with an existing `today` variable (`grep -n "today" App/app/templates/_stay_fee_fields.html App/app/templates/_property_editor.html | head`); else pass `rate_from_default` where the editor context is built |
| App/tests/test_stay_fee_rate_field_1029.py | create |
| App/app/templates/base.html, App/tests/static_versions.json | only if a static file changed (none expected) |
| docs/tasks/1029-report.md, docs/tasks/screenshots-1029/ | create (390 px screenshot of the property editor Stay fee section) |

## 3. Steps

Conventions as 1027. Before editing, open `docs/design/design-system.md` checklist headings only (`grep -n '^## \|^- \[' ... | head -40`) and tick the relevant items in the report.

0. Clean tree; `git checkout -B claude/dated-rates-1029 origin/main`; confirm `grep -n "stay_fee_rate_from" App/app/routes/stay_fees.py` finds the 1028 helper, else STOP.
1. Tests first (`test_stay_fee_rate_field_1029.py`, reuse the HTTP helpers of `tests/test_property_form_save.py`): editor GET for a property with rate 30 contains `name="stay_fee_rate_from"` with `type="date"` and a `min` equal to today; for a rate-0 property it does not; the setup wizard page (`fee_required`) does not. POSTing the editor with a new rate and a future date stores a row with that date; the saved price of a night before that date stays at the old rate.
2. Template and i18n edit. Keep the existing markup style of sibling `.field` blocks (`field_label(...)` macro, `aria-describedby`). The label uses the same helper as the rate field with `required=false`.
3. Run: `.venv/bin/python -m pytest tests/test_stay_fee_rate_field_1029.py tests/test_required_stars.py tests/test_property_form_save.py -q --tb=short 2>&1 | tail -30`, then the host-page row from `docs/context/test-map.md` for the property editor (`grep -n "Property\|editor\|Host pages" docs/context/test-map.md | head`) including `test_layout_lint_browser.py` with `-rs` and 0 skipped, and the property-editor browser test (`tests/test_0833_property_editor_browser.py`).
4. Screenshot at 390 px of the open Stay fee section (copy the screenshot helper from `test_0833_property_editor_browser.py`), save under `docs/tasks/screenshots-1029/`, look at it once, describe in the report what you saw (field visible, label not clipped, no horizontal scroll). Do not retake.
5. Report, `Status: review`, push `claude/dated-rates-1029`. No PR.

## 4. Acceptance

- [ ] Date field appears only in the editor for a property with a rate above 0; none in the wizard.
- [ ] Works without JavaScript; no new JS, no new dependency.
- [ ] i18n parity EN/CS/VI (the i18n parity test passes).
- [ ] Layout lint and editor browser tests green, 0 skipped; 390 px screenshot in the report.

## 5. If unsure, STOP and report

- The fee fields partial is rendered somewhere with no `today` and no way to pass it without touching more than 2 files.
- An i18n parity or layout-lint finding appears: never silence it; report the finding text.
- A browser test is skipped (skipped means broken).
- 25 tool calls reached: commit, report `Status: blocked`.
