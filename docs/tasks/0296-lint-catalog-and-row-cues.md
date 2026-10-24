# 0296: Design lint knows the new classes; every clickable row keeps a visible cue

Status: todo
Depends on: 0295 | Base commit: the 0295 commit | Branch: claude/project-thread-1am307 (already checked out; commit here)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

After 0291-0294 two tests fail: the design lint (`tests/test_design_lint.py`) does not know the new classes and still says "one ui-btn-primary per template", while MASTER now says one primary **per button group**; and `tests/test_0252_touch_sweep_browser.py` finds clickable rows with no visible "Open" cue (it only looks for `.row-open`, and the property-summary rows lost theirs in 0294).

## 2. Context

- `scripts/design_lint.py` lines ~47-53: T3 allows `catalog["classes"] | catalog["hooks"] | legacy[rel]`; T4 is `if plain.count("ui-btn-primary") > 1: out.append(f"{rel}: T4 more than one ui-btn-primary")`. Docstring line ~10: `T4 at most one ui-btn-primary per template file (a template is one screen)`.
- `docs/design/catalog.json`: keys `classes` (list), `hooks`, `enforced_templates`, `legacy`, `enforced_stylesheets`, `class_notes`.
- Current lint findings (run `cd App && .venv/bin/python ../scripts/design_lint.py 2>&1 | tail -40`): T3 for `ui-btn-open`, `cleaning-property-row`, `invoice-supplier-edit`, `invoice-customer`, `invoice-lookup`, `invoice-lookup-ico`, `invoice-lookup-row`, `invoice-lookup-guest`, `invoice-buyer-fields`, `invoice-f-full`, `invoice-f-zip`, `invoice-f-city`, `invoice-f-half`, `fee-stepper`, `fee-stepper-item`, `fee-stepper-dot`, `fee-stepper-label`, `fee-figures`, `fee-figures-total`, `fee-step-actions`, `fee-qr-amount`, `fee-send-line`; T4 for invoice_form.html (and possibly stay_fees.html, reservation_detail.html).
- `App/tests/test_0252_touch_sweep_browser.py` line ~44: `if (!e.querySelector('.row-open, .host-property-card-open')) out.noCue.push(name(e));`
- `App/app/templates/apartments.html` property-summary table (line ~75): `<thead><tr><th>{{ t('apartments.table.property') }}</th><th>{{ t('property_nav.guest_link') }}</th><th>{{ t('guest_links.pin') }}</th><th>{{ t('automation.timing_title') }}</th></tr></thead>`; each body row ends with the `property-inline-timing` `<td>` then `</tr>`.

## 3. Files

| Path | Action | What |
|---|---|---|
| docs/design/catalog.json | edit | step 1 |
| scripts/design_lint.py | edit | step 2 |
| App/tests/test_0252_touch_sweep_browser.py | edit | step 3 |
| App/app/templates/apartments.html | edit | step 4 |

No other file may change.

## 4. Steps

1. catalog.json: append every class named in the T3 list above to `classes` (keep the list's existing order, append at the end, no duplicates). Add a `class_notes` entry `"ui-btn-open": "MASTER 7.1 open: soft-coral Open on list rows and cards (0291)"` (follow the existing `class_notes` shape; if it is a list, add an equivalent item).
2. design_lint.py: T4 becomes "at most one ui-btn-primary per button group". Replace the T4 check with:
   ```python
    # T4 (0291, owner 2026-10-24): one primary per button group. A group is a
    # run of buttons inside one element; two primaries in one tag's direct
    # children are flagged, a page may hold several groups.
    for m in re.finditer(r"<(div|form|p|td|li)\b[^>]*>((?:(?!</?\1\b).)*)</\1>", plain, re.S):
        if m.group(2).count("ui-btn-primary") > 1:
            out.append(f"{rel}: T4 more than one ui-btn-primary in one group")
            break
   ```
   and update the docstring line to `T4 at most one ui-btn-primary per button group (MASTER 1.2)`. If this still flags a template, read the flagged spot: if the two primaries sit in exclusive `{% if %}/{% else %}` branches, add the template path to a new catalog key `"multi_primary_ok": [...]` and skip T4 for templates in that list (`catalog.get("multi_primary_ok", [])`); report which.
3. test_0252: change the cue selector to `'.row-open, .host-property-card-open, .ui-btn-open'`.
4. apartments.html property-summary table: add `<th><span class="sr-only">{{ t('common.actions') }}</span></th>` as the last header cell, and in each body row add `<td class="nowrap row-actions" data-label="">{{ row_open() }}</td>` right after the `property-inline-timing` cell's `</td>`. (`row_open` is already imported in this template; check the `{% from "_components.html" import … %}` line.)

## 5. Do not touch

CSS, other templates, routes.

## 6. Commands

From `App/`:
```
.venv/bin/python ../scripts/design_lint.py 2>&1 | tail -5
.venv/bin/python -m pytest tests/test_design_lint.py tests/test_0252_touch_sweep_browser.py tests/test_0285_rows_browser.py tests/test_host_list_layouts_browser.py tests/test_design_*.py -q --tb=short 2>&1 | tail -30
```
And from the repo root: `python3 scripts/context_lint.py 2>&1 | tail -3`.

## 7. Acceptance

- [ ] design lint OK; listed tests pass or failures listed with the assertion line.

## 8. Stop and ask

As in TEMPLATE §8.

## 9. Report

`docs/tasks/0296-report.md` (300 tokens max), `Status: review`. One commit `0296: lint catalog, row cues`.

## Risk list (for the reviewer)

design_lint.py T4 regex.

## Owner steps

None.
