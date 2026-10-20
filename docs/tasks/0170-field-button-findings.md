# 0170: clear the 21 field-button-misaligned findings

Status: todo
Depends on: 0167, 0169 | Branch: claude/project-thread-5hw8cf
Executor: Haiku 5.5 | Fits one session

## 1. Objective

The layout guard (check `field-button-misaligned`, added in 0167) flags a button and a field in one row whose bottom or centre lines differ by more than 2 px. After 0167 the remaining findings in `/tmp/ubyhost-layout-guard.json` are:
- routes `fee-setup`, `guest-links`, `automation` (12 findings): `select#copy_from` vs the "Copy" button, markup in `App/app/templates/_property_editor.html` lines 24-40 (`.copyrow`, `.field.grow`, plain `<label>`, a sibling `ui-btn`).
- route `stay-detail` (9 findings): `input#hand_reference` vs "Mark as filed by hand", `input#guest_email` vs "Save", `select#status` vs "Save", markup in `App/app/templates/reservation_detail.html` (around lines 372-386 and 436-456; the button sits in `.ui-form-actions` inside a `.settings-grid` form).

Fix the layout so the guard passes. Never loosen or edit the guard.

## 2. Context

`host2.css` loads last (tokens only; S1 no raw colours, S2 no bare px in margin, padding, gap, font-size). The 0167 block for `.cleaning-period` is the model: `align-items: flex-end` on the row, `margin: 0` on the field, button `align-self: flex-end`. For `.settings-grid` the likely cause is that the form is a grid and the actions cell sits beside a field on wide screens: make `.ui-form-actions` span the full grid row (`grid-column: 1 / -1`) with `justify-self: start`, so it is below the fields, not beside one. Measure first (run the guard, read the finding sizes), do not guess.

## 3. Files

`App/app/static/host2.css` (append), `App/app/templates/base.html` (host2.css key), `App/tests/static_versions.json`, templates above only if CSS alone cannot fix it, `docs/tasks/0170-*`.

## 4. Steps

1. From `App/`: `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium .venv/bin/python -m pytest tests/test_design_guardrails_browser.py -q -x -k every_host_page 2>&1 | tail -30` (foreground, timeout 600000). Then from the repo root: `git checkout -- docs/tasks/0102-evidence && git clean -fdq docs/tasks/0102-evidence`. Expected now: the 21 findings above (plus any 0169-era ones you did not cause; report those).
2. Append a `/* 0170 */` block to the end of `host2.css` that fixes the copy row (`.copy-property-form .copyrow { display: flex; align-items: flex-end; gap: var(--space-3); }`, field `margin: 0`, button `align-self: flex-end`) and the stay-detail form actions per section 2. Run `python3 scripts/design_lint.py 2>&1 | tail -2` from the repo root. Expected: OK.
3. Bump the host2.css key to `20261019-0170` in `base.html`, then from `App/`: `.venv/bin/python tests/test_static_versions.py --write && .venv/bin/python -m pytest tests/test_static_versions.py -q 2>&1 | tail -3`.
4. Re-run step 1. Expected: zero findings. If a finding remains after two attempts, report its text and stop.
5. Also run `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium .venv/bin/python -m pytest tests/test_design_guardrails_browser.py -q -rs 2>&1 | tail -6`, then clean 0102-evidence as in step 1. Expected: all passed, 0 skipped.
6. Commit: `git add App/app/static/host2.css App/app/templates App/tests/static_versions.json docs/tasks/0170-* && git commit` with message "0170: field and button rows line up" and the two trailers given by the orchestrator.

## 5. Do not touch

`design_guard.js`, any test assertion, anything else; hard rules 1, 3, 8.

## 6. Commands

As in each step.

## 7. Acceptance

- [ ] Guard test passes with 0 skipped and zero findings; key bumped; lint OK.

## 8. Stop and ask

An anchor is missing, or a finding survives two attempts.

## 9. Report

`docs/tasks/0170-report.md`, short; `Status: review`.
