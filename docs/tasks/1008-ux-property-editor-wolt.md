# 1008: Wolt-style property editor (/apartments/{id}), CSS only

Status: blocked
Depends on: 1006 (shared classes in app2.css; uncommitted until the owner approved), 1007 | Base commit: HEAD of the current branch | Branch: current branch, do NOT create another
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Restyle the property editor to the Wolt company-settings look the owner approved in 1006: one narrow centred column, every section ONE thin-bordered card, quiet muted labels above inputs, 1 px dividers between field groups, no nested boxes, and Archive at the bottom in its own quiet card with a red outline button. CSS only: no template, JS, test or id change, because exact markup is pinned by tests (see §2).

Owner is asleep and authorised full execution: **commit locally, do NOT push, do NOT open a PR, do NOT merge.**

## 2. Context

Page: `/apartments/{id}`, template `App/app/templates/_property_editor.html` (506 lines, DO NOT EDIT). Verified structure, current tree:
- Line 125: `<div class="form prop-form-single property-detail">` is the root. Tests pin this exact string (`test_0534_property_page_v2.py:54,159`, `test_property_navigation_browser.py:352,635`, `test_property_preview_sticky_browser.py:21`). So scope all CSS under `body.v2 .form.prop-form-single`. Do NOT add `ui-page-narrow` in the template; copy its two declarations into the new rules instead.
- Line 127: `<form ... class="property-settings-form" id="property-settings-form" ...>` is `display:contents` (app2.css line ~378). Its children are grid items of `.form`.
- Six `<details class="prop-sec" id="sec-basics|sec-messages|sec-police|sec-fee|sec-calendars|sec-lock">`. Class string is pinned by `test_property_navigation_browser.py:177` (1006 tried adding a class and had to revert). Do not change it.
- Each details holds `<summary><span class="dot ..."><div><b>Title</b></div><small class="sec-state">..</small></summary>` then `<div class="fields-wrap">` then `<section class="panel property-section ui-section" id="basics|arrival-departure|address|notes-section|communication|ubyport|automation|stay-fee-settings|door-code|...">`. Inner sections are sub-groups; they have `<h2 class="property-section-title">` and sometimes `.field-label-row` with `help_tip`.
- Line 192: `<div class="prop-archive-row" id="sec-archive">` containing `.prop-archive-actions#archive` with `<button class="ui-btn ui-btn-secondary" ... formaction=".../archive" data-confirm ...>` plus `<span class="prop-archive-action">` and the `help_tip`. It is a grid item inside the display:contents form, located after `#sec-basics`.
- Savebar `.savebar[data-for="property-settings-form"]` is sticky, inside the form, near line 413 (grid-column 1/-1).

Current CSS (verified; line numbers of the working tree):
- 359-361: `body.v2 .form{display:grid;grid-template-columns:minmax(0,1fr);gap:20px;max-width:980px;margin:0 auto}`, `body.v2 details{background:var(--s);border:1px solid var(--line);border-radius:12px;margin-bottom:10px}`, `body.v2 summary{list-style:none;padding:14px 16px;cursor:pointer;display:flex;justify-content:space-between;align-items:center}`.
- 2836-2840 (prop-sec flattened to no box, chevron after summary): `body.v2 details.prop-sec{border:0;border-radius:0;background:transparent;margin-bottom:0;box-shadow:none}`, `body.v2 details.prop-sec>summary{padding-left:0;padding-right:0}`, `... :after` chevron, `[open]>summary:after` rotate, `body.v2 details.prop-sec:not([open])>:not(summary){display:none}`. Keep the chevron and the not-open rule untouched.
- 2644: `@media (min-width:1024px){body.v2 .form.prop-form-single{grid-template-columns:minmax(0,1fr)}}`; 2660-2662: at 1024px+ `.form.prop-form-single.property-detail` gets `max-width:980px;margin:auto;width:100%`.
- 2800-2806: `.prop-archive-row{padding:4px 0 8px}`, `.prop-archive-actions{display:flex;flex-wrap:wrap;align-items:center;gap:8px 12px}`, `.prop-archive-actions .ui-btn{min-height:44px}`, `.prop-archive-note`, `.prop-archive-action`.
- 978-985: inside a media query, `.property-section{display:grid;grid-template-columns:1fr 1fr;gap:12px}` (two-column fields on wide screens); keep.
- Tokens: `--line`, `--ink`, `--ink3`, `--bad` exist (`--bad: var(--red)` in tokens.css line 114). `--bg` exists (1006 uses it).
- Look to copy (1006 block at the end of app2.css, shared): card = white, `1px solid var(--line)`, radius 12, no shadow, padding 16; title 16px/700; labels 14px `var(--ink3)`; 16px gaps; dividers `1px solid var(--line)`; max-width 720.
- Reference screenshots (read-only, open them): `/root/.claude/uploads/19736c2f-d76f-5062-a390-a7e0df73a878/2ce8651b-Screenshot_2026-11-07_at_22.44.48.png`, `cf274203-Screenshot_2026-11-07_at_22.44.51.png`, `3d46b9f1-Screenshot_2026-11-07_at_22.44.59.png`, `b0364946-image.png`; current page: `/tmp/shots/layout-lint/property-detail-1280.png` (and `-390`, `-768`; the `property-detail-configured+open-*` shots show all sections open).

Design rules: tokens only, no raw hex, no `style=""`, no new JS. `scripts/design_lint.py` S1/S2 check the new CSS: copy numbers already used in the same properties (12, 16 px, radius 12 as in the 1006 block). Light mode only.

Anchors (each must be found verbatim, else STOP, §8):
- `App/app/static/app2.css`: line containing `body.v2 details.prop-sec:not([open])>:not(summary){display:none}`.
- `App/app/static/app2.css`: line containing `body.v2 .prop-archive-row{padding:4px 0 8px}`.
- `App/app/static/app2.css`: the 1006 block comment `/* 1006: Wolt-style section cards.`
- `App/app/templates/base.html` line 22: `app2.css?v=20261108-1003` (if 1007 bumped it, use the value that is there; bump by one step again).
- `App/tests/test_static_versions.py` line 10: mentions `--write`.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/static/app2.css | edit | append the 1008 block (§4 step 1) |
| App/app/templates/base.html | edit | bump `app2.css?v=` |
| App/tests/static_versions.json | edit | regenerate with `--write` (never by hand) |
| docs/design/pages/properties.md | edit | one line under "Property detail" (step 4) |
| docs/tasks/1008-report.md | create | report |
| docs/tasks/1008-ux-property-editor-wolt.md | edit | Status line only |

No other file may change. No new class names are introduced (everything is scoped selectors on existing classes), so `docs/design/catalog.json` stays untouched.

## 4. Steps

1. **CSS.** Append exactly this at the very end of `App/app/static/app2.css` (after everything, including the 1006/1007 blocks):
```
/* 1008: Wolt-style property editor. CSS only, scoped to the editor root; markup is pinned by tests. */
body.v2 .form.prop-form-single{max-width:720px;margin-left:auto;margin-right:auto;width:100%;box-sizing:border-box;gap:16px}
body.v2 .ui-page[data-body-kind="detail"]:has(#property-settings-form) > .ui-body-detail > .form.prop-form-single.property-detail{max-width:720px}
body.v2 .form.prop-form-single details.prop-sec{margin:0;padding:0;background:#fff;border:1px solid var(--line);border-radius:12px;box-shadow:none;overflow:visible}
body.v2 .form.prop-form-single details.prop-sec>summary{padding:14px 16px;min-height:44px;box-sizing:border-box;gap:8px 12px}
body.v2 .form.prop-form-single details.prop-sec>summary b{font-size:16px;font-weight:700;line-height:1.3}
body.v2 .form.prop-form-single details.prop-sec[open]>summary{border-bottom:1px solid var(--line)}
body.v2 .form.prop-form-single details.prop-sec>.fields-wrap{padding:16px}
body.v2 .form.prop-form-single details.prop-sec .property-section{margin:0;padding:16px 0;background:transparent;border:0;border-radius:0;box-shadow:none;gap:16px 16px}
body.v2 .form.prop-form-single details.prop-sec .property-section:first-of-type{padding-top:0}
body.v2 .form.prop-form-single details.prop-sec .property-section:last-of-type{padding-bottom:0}
body.v2 .form.prop-form-single details.prop-sec .property-section + .property-section{border-top:1px solid var(--line)}
body.v2 .form.prop-form-single details.prop-sec .property-section-title{margin:0;font-size:16px;font-weight:700;line-height:1.3}
body.v2 .form.prop-form-single details.prop-sec .field-label-row{display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin:0 0 4px}
body.v2 .form.prop-form-single details.prop-sec .field > label,body.v2 .form.prop-form-single details.prop-sec .field-label-row > label{display:block;margin:0 0 4px;font-size:14px;font-weight:400;color:var(--ink3)}
body.v2 .form.prop-form-single details.prop-sec .field{margin:0 0 16px}
body.v2 .form.prop-form-single details.prop-sec .field:last-child{margin-bottom:0}
body.v2 .form.prop-form-single details.prop-sec .ui-details-box{margin:12px 0 0}
body.v2 .form.prop-form-single .prop-sec-missing{margin:0 0 16px;padding:10px 12px;background:var(--bg);border:0;border-radius:8px;font-size:14px;line-height:1.45;color:var(--ink3)}
body.v2 .form.prop-form-single #sec-archive{order:90;margin:0;padding:16px;background:#fff;border:1px solid var(--line);border-radius:12px;box-sizing:border-box}
body.v2 .form.prop-form-single #sec-archive .prop-archive-actions{gap:12px 16px;justify-content:space-between}
body.v2 .form.prop-form-single #sec-archive .prop-archive-actions .ui-btn-secondary{background:#fff;color:var(--bad);border:1px solid var(--bad);box-shadow:none}
body.v2 .form.prop-form-single .savebar[data-for="property-settings-form"]{order:100}
```
   Notes for the executor: (a) `.field` markup may differ per section; if a rule makes a section look worse in the screenshots, delete that single rule rather than adding more rules (max 1 fix round, §8). (b) `#sec-archive` has `order:90` so the grid shows it after Calendars and Lock (the form is `display:contents`; the details outside the form are also grid items of `.form`). Visual order changes only; DOM order, tab order inside each section and ids stay. If the screenshot shows Archive not last (before the savebar), delete the `order` lines and report it instead. (c) If `--bg` or `--bad` is not found by `grep -n "^\s*--bg:\|^\s*--bad:" App/app/static/tokens.css | tail -30`, use the page-background token that file defines. (d) If `python3 scripts/design_lint.py 2>&1 | tail -30` flags S1/S2 on a line of this block, replace that value with the nearest value already used in the same property elsewhere in app2.css.
2. **Cache key.** `App/app/templates/base.html` line 22: raise the `v=` of app2.css by one step (e.g. `20261108-1003` to `20261108-1004`). Then from `App/`: `.venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -30`; then `grep -rn "app2.css?v=" app/templates | tail -30` must show one value everywhere.
3. **Design lint.** From the repo root: `python3 scripts/design_lint.py 2>&1 | tail -30` prints OK.
4. **Doc line.** In `docs/design/pages/properties.md`, under the "## Property detail" bullet list, append one bullet: `- 1008: the editor column is 720 px; each \`details.prop-sec\` is one thin-bordered card (CSS only, scoped under \`.form.prop-form-single\`); Archive is its own quiet card last, red outline button; no nested boxes ("More details" keeps \`ui-details-box\`).` Then `python3 scripts/context_lint.py 2>&1 | tail -30` prints OK.
5. **Tests (from `App/`).** Property-editor tests found by grep for `prop-sec`, `sec-police`, `property_editor`, `test_host_property`:
```
.venv/bin/python -m pytest tests/test_static_versions.py tests/test_0534_property_page_v2.py tests/test_0952_lock_section.py tests/test_copy_cleanup.py tests/test_remove_legacy_actions.py -q --tb=short -x 2>&1 | tail -30
UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_property_navigation_browser.py tests/test_0833_property_editor_browser.py tests/test_0541_property_page_phone_browser.py tests/test_host_property_controls_browser.py tests/test_host_unsaved_changes_browser.py tests/test_property_page_audit_browser.py tests/test_property_settings_repetition_audit_browser.py tests/test_property_preview_sticky_browser.py -q --tb=short -x 2>&1 | tail -30
UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_host_geometry.py tests/test_host_wide_geometry_browser.py tests/test_design_guardrails_browser.py -q --tb=short -x 2>&1 | tail -30
UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots .venv/bin/python -m pytest tests/test_layout_lint_browser.py -q -x 2>&1 | tail -30
```
   Expected: all pass, `0 skipped` in the last line of the browser runs, layout lint zero host findings. A test that pins the old 980 px width or an old border counts as a failure: STOP and report it, do not edit tests. If a file in the list does not exist, drop it from the command and say so in the report; run `ls tests | grep -i 'property' | tail -30` once to see the real names.
6. **Screenshots.** Layout lint wrote `/tmp/shots/layout-lint/property-detail-{390,768,1280}.png` and the `property-detail-configured+open-*` set. Open each of `property-detail-390.png`, `-768.png`, `-1280.png` and one `property-detail-configured+open-1280.png` with the Read tool (images; they are tall, crop with `python3 -c` PIL if the viewer downsamples: save the top 1600 px as `/tmp/crop_<size>.png` and open that). Check against the reference: one centred column, cards with thin border, title left with "?" beside it, labels muted above inputs, dividers, no box inside a box, Archive last with red outline, savebar not overlapping, no horizontal scroll at 390. Then:
```
mkdir -p /mnt/project-files/ux-shots/wolt && cp "/tmp/shots/layout-lint/property-detail-configured+open-390.png" /mnt/project-files/ux-shots/wolt/property-restyled-390.png && cp "/tmp/shots/layout-lint/property-detail-configured+open-1280.png" /mnt/project-files/ux-shots/wolt/property-restyled-1280.png && ls -l /mnt/project-files/ux-shots/wolt | tail -30
```
7. **Report.** Write `docs/tasks/1008-report.md` (600 tokens at most): `git diff --stat`, last 5 lines of each command in steps 3-5, per page "390: ...; 768: ...; 1280: ... " (what you saw), the two screenshot paths, deviations (deleted rules, `order` kept or removed). Set this brief `Status: review`.
8. **Commit locally, no push.** `git add App/app/static/app2.css App/app/templates/base.html App/tests/static_versions.json docs/design/pages/properties.md docs/tasks/1008-ux-property-editor-wolt.md docs/tasks/1008-report.md && git status --short | tail -30` (only these files staged; leave 1006/1007 files as they are) then commit with message `1008: Wolt-style property editor (CSS only)` ending with the two lines:
```
Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Cjmb7NmwKqNNoY1XVAeQbg
```
   Do NOT `git push`. If `app2.css`, `base.html` or `static_versions.json` also contain uncommitted 1006/1007 changes, stage them anyway only if 1006 and 1007 are not yet committed, because this commit then depends on them; say so in the report.

## 5. Do not touch

`_property_editor.html` and every other template, `app.js` (initPropSectionLinks, deep links `#sec-*`, section open/close), tests, `tests/layout_lint.js`, `scripts/*`, `catalog.json`, i18n files, routes, filing/police/UbyPort logic and field names/ids/data attributes. No JS, no `style=""`, no new dependency, no new outbound request. Hard rules: light mode only; auth forms work without JavaScript; never push to `main`; no card in a card (the `.property-section` inner groups are flat, divided by 1 px lines, not boxes).

## 6. Commands

See §4 steps 2-5, each ends in `| tail -30`. No full suite.

## 7. Acceptance

- [ ] `python3 scripts/design_lint.py` OK and `python3 scripts/context_lint.py` OK.
- [ ] Step 5 commands green; browser runs and layout lint show `0 skipped`; zero host layout findings.
- [ ] `git diff HEAD --stat -- App/app/templates | tail -5` prints nothing (no template change).
- [ ] Screenshots opened and described per size (390/768/1280): all six sections still open and close, `/apartments/{id}#sec-police` still opens police, Archive is its own card last with a red outline button.
- [ ] `/mnt/project-files/ux-shots/wolt/property-restyled-390.png` and `property-restyled-1280.png` exist.
- [ ] One local commit exists (`git log -1 --stat | tail -12`), nothing pushed.

## 8. Stop and ask

Stop, and write the report as `blocked`, if:

- an anchor excerpt is not found;
- a test fails twice or a layout-lint finding remains after one fix round;
- a test pins the old look and would need an edit;
- you reach 25 tool calls or about 50k tokens;
- a template, JS or file outside §3 seems needed;
- you would need push, merge, secrets, SSH or deploy (hand it to the owner with the exact command).

## 9. Report

`docs/tasks/1008-report.md` as in §4 step 7.

## Risk list (for the reviewer)

`App/app/static/app2.css` (the appended 1008 block only; check `#sec-archive` `order` and `.field > label` rules against the unsaved-changes savebar and the two-column `.property-section` grid at 1024px+).

## Owner steps

1. Look at the two screenshots `property-restyled-390.png` and `property-restyled-1280.png` in the ux-shots/wolt folder.
2. If you like them: tell the orchestrator, and ask for a push/PR brief (the commit stays local until then).
