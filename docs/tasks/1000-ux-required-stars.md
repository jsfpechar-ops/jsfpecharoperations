# 1000: Required stars and legend, and the dashboard "?" next to the title

Status: todo
Depends on: none | Base commit: HEAD of main when you start | Branch: task/1000-ux-required-stars
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Make the required-field marker clear and consistent: a red `*`, a one-line legend that also shows on phones, and the marker on the add-stay and guest-details forms that have `required` inputs without one. Also put the dashboard "?" help icon inline after the "Dashboard" title instead of on its own line under it.

## 2. Context

Rules: light mode only; copy rule 9 (the legend text `common.required_legend` already exists, do not add copy); host-page UX gate (AGENTS rule 10). Read nothing else.

Checked by the orchestrator:

- The star is `<span class="req-star" aria-hidden="true">*</span>`, drawn by `field_label(... required=true)` in `App/app/templates/_components.html` and inline in some templates. Its rule is `app2.css` line 2741: `body.v2 .req-star{color:var(--red);font-weight:700;margin-inline-start:2px}`. Design-system danger token is `--danger` (tokens.css line 147).
- The legend is `<p class="required-legend">{{ t('common.required_legend') }}</p>` (en "Fields marked * are required.", cs "Pole označená * jsou povinná."), in `_property_editor.html:128`, `_entity_business_fields.html:128`, `setup_wizard/_layout.html:43`. Two rules hide it: app2.css line 961 makes it screen-reader-only everywhere, and line 994 (`@media (max-width:1023px)`) has `display:none`. Contexts `.wiz-page` (1330) and `.prop-new` (1426) restyle it.
- `reservations.html` add-stay panel (lines ~40-56): labels for `new_apartment`, `date_from`, `date_to` have `required` inputs and no star; there is no legend in that form.
- `guest_form_admin.html`: `surname` (line ~75) and `nationality` (line ~98) are `required` with no star; no legend.
- Dashboard: `dashboard.html` line 50 renders `<div class="ov-title-row"><h1 class="hl">...</h1><span class="ph-hide">{{ page_help('dashboard') }}</span></div>`. The `.ov-title-row` flex rule (app2.css line 925) exists only inside `@media (max-width:1023px)`, so on desktop the title row is a block and the help icon wraps under the `h1`; `.head h1:after` (app2.css line 79, a 28px red bar) is only removed under 1024px (line 451), so the "?" sits under the red underline. Screenshot: `/root/.claude/uploads/19736c2f-d76f-5062-a390-a7e0df73a878/26b0c5e9-image.png`.
- Layout lint rule `help-stranded` (tests/layout_lint.js lines ~251-252, brief 0790) fails a "?" that is on another line than its label or more than 32px away. The fix must make it green, not silence it.

Anchors (each must be found verbatim, else STOP):

`App/app/static/app2.css`:
```
body.v2 .required-legend{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}
```
```
  body.v2 .crumb,body.v2 .required-legend,body.v2 aside.preview{display:none}
```
```
body.v2 .req-star{color:var(--red);font-weight:700;margin-inline-start:2px}
```
`App/app/templates/reservations.html`:
```
          <label for="new_apartment">{{ t('stays.add_panel.apartment') }}</label>
```
```
          <label for="date_from">{{ t('stays.add_panel.arrival') }}</label>
```
```
          <label for="date_to">{{ t('stays.add_panel.departure') }}</label>
```
and `    <form method="post" action="/reservations">` followed by `      <div class="grid">`.
`App/app/templates/guest_form_admin.html`:
```
        <label for="surname">{{ t('guest.admin.surname') }}</label>
```
```
        <label for="nationality">{{ t('stay.detail.guests.nationality') }}</label>
```
and `    <div class="ui-pair">` (the first one, directly under `<h2>{{ t('guest.admin.identity.title') }}</h2>`).
`App/app/templates/base.html` line 22: `...href="/static/app2.css?v=...">` (match only up to `/static/app2.css?v=`).

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/static/app2.css | edit | star colour, visible one-line legend on all widths, desktop title row |
| App/app/templates/reservations.html | edit | 3 stars and one legend |
| App/app/templates/guest_form_admin.html | edit | 2 stars and one legend |
| App/app/templates/base.html | edit | bump app2.css cache key |

No other file may change (tests unchanged: no test asserts these label strings; check in step 7).

Deferred, not in this brief (list in the report): other `required` inputs without a star in `reservation_detail.html` (hand_filed_at), `_stay_fee_fields.html` (`fee_required`), `invoice_form.html`, `payments_new.html`, `settings.html`, and the public guest registration forms (guest pages follow the Arrival lane rules and need their own brief).

## 4. Steps

1. `app2.css` line 2741: replace `color:var(--red)` with `color:var(--danger)` in the `.req-star` rule. Check: `grep -n "req-star{color:var(--danger)" App/app/static/app2.css | tail -30` shows one line.
2. `app2.css` line 961: delete the whole `body.v2 .required-legend{...sr-only...}` line. Line 994: change `body.v2 .crumb,body.v2 .required-legend,body.v2 aside.preview{display:none}` to `body.v2 .crumb,body.v2 aside.preview{display:none}`.
3. Append to `app2.css`:
```
/* 1000: required legend visible on every width, one line; desktop dashboard "?" inline after the title */
body.v2 .required-legend{margin:0 0 12px;font-size:13px;line-height:1.3;color:var(--ink3);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:100%}
@media (min-width:1024px){
  body.v2 .ov-head .ov-title-row{display:flex;flex-wrap:nowrap;align-items:center;justify-content:flex-start;gap:0 6px}
  body.v2 .ov-head .ov-title-row h1.hl{margin-right:0}
  body.v2 .ov-head .ov-title-row h1.hl:after{content:none}
  body.v2 .ov-head .ov-title-row>.ph-hide{display:inline-flex;align-items:center}
}
```
   If `.ov-head .ov-title-row h1.hl` does not exist on the desktop page, use the selector `body.v2 .ov-title-row h1` instead (check with `grep -n "ov-title-row" App/app/templates/dashboard.html | tail -30`). Keep the red underline bar out of the row only; other pages' `.head h1:after` stay as they are. If removing the bar makes the page-level rhythm look wrong at 1280, re-add it as `body.v2 .ov-head .ov-title-row{position:relative}` is NOT allowed: stop and say so instead.
4. `reservations.html`: for the three labels, add `<span class="req-star" aria-hidden="true">*</span>` directly before `</label>` (so `...{{ t('stays.add_panel.apartment') }}<span class="req-star" aria-hidden="true">*</span></label>`, same for arrival and departure). Directly after `<form method="post" action="/reservations">` add a line `      <p class="required-legend">{{ t('common.required_legend') }}</p>`. Check: `grep -c "req-star" App/app/templates/reservations.html | tail -30` prints 3 or more.
5. `guest_form_admin.html`: same for `surname` and `nationality` labels (star before `</label>`). Directly after `<h2>{{ t('guest.admin.identity.title') }}</h2>` add `    <p class="required-legend">{{ t('common.required_legend') }}</p>`. Do not add a star to any input that is not `required`, and do not change `required` attributes.
6. `base.html` line 22: set the value after `/static/app2.css?v=` to `20261107-1000`.
7. Check no test breaks on label text: `grep -rn "stays.add_panel.apartment\|'Apartment'\|get_by_label" App/tests/test_host_*.py | tail -30`. Playwright `get_by_label("...")` matches by substring and ignores an `aria-hidden` star, so none should break; if one fails, fix only the selector in that test and name it in the report.

## 5. Do not touch

`_components.html` (the macro already draws the star), `layout_lint.js` (never loosen `help-stranded`), `host_i18n.py` (no new copy), `app.css`, guest-facing templates, any `required` attribute. AGENTS rules: no new dependency, no new outbound request, no new personal-data field, no tracking cookies, light mode only.

## 6. Commands

From `App/`:
- `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots .venv/bin/python -m pytest tests/test_layout_lint_browser.py -q -x 2>&1 | tail -30` green, 0 skipped (covers `help-stranded`).
- `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_host_*.py tests/test_host_geometry.py -q --tb=short -x 2>&1 | tail -30` (the test-map row for host pages and CSS), 0 skipped. If it exceeds the tool limit, run only the files whose names contain `stays`, `reservation`, `guest_form`, `dashboard`, `property`, `wizard`, then say which.
- Screenshots at 390/768/1280 for: dashboard (with a property so the title row shows), stays page with the add-stay panel open, a guest-details page (`guest_form_admin`), and one page that already had the legend (property create, to confirm the legend is one line at 390). Read them.
- From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`.

## 7. Acceptance

- [ ] `.req-star` uses `var(--danger)`; stars show on the 3 add-stay labels and the 2 guest-details labels.
- [ ] `.required-legend` is visible at 390, 768 and 1280, on one line, on the pages that include it and on the two forms above.
- [ ] Dashboard at 1280: "?" sits on the same line right after "Dashboard", no red bar between; at 390 unchanged.
- [ ] `test_layout_lint_browser.py` zero findings (`help-stranded` green), host tests green, 0 skipped.
- [ ] PR body per page "390: ...; 768: ...; 1280: ..." and the design-system checklist ticked; one 390 px screenshot per changed page in the report; deferred files listed.

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt is not found;
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (report as `blocked`);
- a new dependency seems needed;
- a file outside §3 needs a change;
- §5 would be touched, or a layout-lint finding cannot be fixed inside §3 (never silence it);
- you need push, merge, secrets, SSH or deploy (hand to the owner with the exact command).

## 9. Report

Write `docs/tasks/1000-report.md` (600 tokens at most) and set `Status: review`. It has: files changed (`git diff --stat`), each command with the last 5 lines, §7 ticked, deferred files, deviations.
