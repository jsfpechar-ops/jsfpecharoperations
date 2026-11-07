# 1005: Padding inside the "More details (optional)" disclosure box

Status: todo
Depends on: none | Base commit: HEAD of main | Branch: task/1005-ux-details-box-padding
Executor: Haiku 5.5 | Fits one session: 25 tool calls, 60k tokens

## 1. Objective

On the stay-fee form, section "3. Council and delivery", the "More details (optional)" box shows its fields touching the left, right and top borders, and the summary text is indented differently from the fields. Give the box one shared, reusable class with 16 px inner spacing so summary and fields line up.

## 2. Context

Rules: light mode only; host UX gate (AGENTS rule 10); no new dependency; CSS only in `App/app/static/app2.css`; copy untouched.

Root cause: the generic card is `body.v2 details{...border:1px solid var(--line);border-radius:12px;margin-bottom:10px}` with no padding. `body.v2 summary` has `padding:14px 16px`, but the `.field` children of `details.fee-more` have none. `fee-more` has no CSS rule anywhere.

Anchors (each must be found verbatim, else STOP):

`App/app/templates/_stay_fee_fields.html` line 47 starts with:
```
  <details class="fee-more"{% if apartment.stay_fee_authority_address
```
`App/app/static/app2.css` line 365:
```
body.v2 details[open] summary:after{transform:rotate(180deg)}
```
`App/app/templates/base.html` line 22:
```
<link rel="stylesheet" data-turbo-track="reload" href="/static/app2.css?v=20261107-1010">
```

Other disclosure boxes checked (none changed):
- `invoice-more` (`invoice_form.html`): borderless link-style toggle, no card; left alone.
- `payments-add` (`payments.html`): borderless row, already padded by its own rules; left alone.
- `prop-sec`, `cleaning-remove`, `needs-you-more`, `danger-zone`: own padding rules; left alone.
New cards that want this look add class `ui-details-box`.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/static/app2.css | edit | insert 5 lines after line 365 |
| App/app/templates/_stay_fee_fields.html | edit | add class on line 47 |
| App/app/templates/base.html | edit | bump `app2.css?v=` |

No other file may change.

## 4. Steps

1. `app2.css`: after the line `body.v2 details[open] summary:after{transform:rotate(180deg)}` insert exactly:
```
/* 1005: shared disclosure card; 16 px inside, fields full width of the padded area */
body.v2 details.ui-details-box{padding:0;overflow:hidden}
body.v2 details.ui-details-box > summary{padding:14px 16px;min-height:44px;box-sizing:border-box}
body.v2 details.ui-details-box > :not(summary){margin:0 16px 12px;min-width:0;max-width:calc(100% - 32px);box-sizing:border-box}
body.v2 details.ui-details-box > :not(summary):last-child{margin-bottom:16px}
body.v2 details.ui-details-box input,body.v2 details.ui-details-box select,body.v2 details.ui-details-box textarea{width:100%;max-width:100%;box-sizing:border-box}
```
   Check: `grep -n "ui-details-box" App/app/static/app2.css | tail -30` shows 5 lines.
2. `_stay_fee_fields.html` line 47: change `<details class="fee-more"` to `<details class="fee-more ui-details-box"`. Check: `grep -n "ui-details-box" App/app/templates/_stay_fee_fields.html | tail -30`.
3. `base.html` line 22: change `app2.css?v=20261107-1010` to `app2.css?v=20261107-1011`. If other templates carry `app2.css?v=`, bump them the same: `grep -rn "app2.css?v=" App/app/templates | tail -30`.

## 5. Do not touch

`App/app/static/app.css`, any other CSS file, `host_i18n.py`, other `details` rules, `tests/layout_lint.js`. No JS. No new dependency.

## 6. Commands

From `App/` (test-map rows "Invoices, stay fee" and host templates/CSS):
```
.venv/bin/python -m pytest tests/test_stay_fee*.py tests/test_host_geometry.py -q --tb=short -x 2>&1 | tail -30
UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots .venv/bin/python -m pytest tests/test_layout_lint_browser.py -q -x 2>&1 | tail -30
```
Expected: all pass, 0 skipped, zero host findings. From repo root: `python3 scripts/context_lint.py | tail -30` clean.

## 7. Acceptance

- [ ] Both pytest commands green, 0 skipped.
- [ ] Open `/tmp/shots/layout-lint/stay-fees-{390,768,1280}.png` (and a view with the box open; expand `details.fee-more` in a Playwright snippet if the lint shot shows it closed). Report per page: "390: ...; 768: ...; 1280: ...".
- [ ] Fields have 16 px space to left, right and top borders; summary text and field text start at the same x; gaps between fields 12 px; no horizontal scroll at 390 px.
- [ ] One 390 px screenshot attached to the report.
- [ ] Design-system checklist ticked in the PR.

## 8. Stop and ask

Stop, and write the report, if: an excerpt is not found; a test fails twice; you reach 25 tool calls; a file outside §3 needs a change; the lint reports a finding on the box that these rules do not fix; you need push, merge or deploy (hand to the owner).

## 9. Report

Write `docs/tasks/1005-report.md` (600 tokens at most), set `Status: review`: files changed, last 5 lines per command, §7 ticked, deviations.

## Extra request (owner, added later; do after the steps above)

Stay fees list page (grep `stay_fee` / "Stay fees" in `App/app/templates`): each property row ends with a circled arrow button to open it, while Properties and Stays open by clicking the row. Make it consistent: the whole row is clickable (reuse the exact row-link pattern the Properties table `props-card` uses, grep `props-card` in templates and `app2.css`, including the hover background and keyboard focus on the inner link), drop the separate circled arrow button, keep the ⋮ menu for extra actions. Keep the accessible name on the row link (property name). Update any test that clicks the arrow (grep tests for the arrow's class). Screenshot 390/768/1280. Report in `1005-report.md`.
