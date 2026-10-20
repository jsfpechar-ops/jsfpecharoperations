# 0171: focus ring 2 px, date fields and signature file inputs

Status: in-progress
Depends on: 0169 | Branch: claude/project-thread-5hw8cf
Executor: Haiku 5.5 | Fits one session

## 1. Objective

After 0169, `test_keyboard_focus_is_visible_and_not_covered` reports 8 findings and one older test breaks:
- `focus-not-visible`: `input#cleaning-from`, `input#cleaning-to` (route `cleaning`), `input#stay_from`, `input#stay_to` (route `guest-new`), all date inputs.
- `focus-obscured`: `input#new_signature_file` (routes `operators`, `operator-add`), `input#edit_signature_file` (routes `operator-edit`, `invoice-settings`), file inputs.
- `test_host_controls_browser.py::test_host_interactions_geometry_copy_and_archive_controls` expects a 2 px focus outline on the skip link; the 0169 rule in `host2.css` made it 4 px.

Owner decision (orchestrator): the focus ring is 2 px, offset 2 px, colour `var(--coral-600)`. WCAG 2.2 AA needs a clearly visible ring, 2 px is enough.

## 2. Context

The 0169 rule is `.host-workspace :is(a, button, input, select, textarea, summary, [tabindex]):focus-visible { outline: var(--space-1) solid var(--coral-600) !important; outline-offset: var(--space-1); }`. The date inputs probably set their own `outline`/`box-shadow` with higher specificity or `outline: none`, or are styled in `app.css`/`host.css`/`host-design0123.css`. The signature file inputs are probably visually hidden (`sr-only` or `opacity: 0`) with a label as the visible control, so the ring must show on the label (`input:focus-visible + label`, or `:focus-within` on the wrapper) and the input must not be clipped by `overflow: hidden`. Find the real cause first: from `App/`, run the a11y focus test, then use `/tmp/claude-0/-home-user-jsfpecharoperations/38363728-17ed-5130-bb5b-482347d88982/scratchpad/probe.py <path> "<js>" 1280` (it starts a seeded server, loads the path, prints the JS result) to print `getComputedStyle(el)` outline, box-shadow, position, clip, opacity and the element's rect for each input. Do not guess.

## 2b. Orchestrator decisions after the first attempt (steps 1 done in 8b6f394)

1. Text-like inputs (including date inputs) may show the ring on `:focus` as well as `:focus-visible`: use `input:focus-visible, input:focus { outline: 2px solid var(--coral-600) !important; outline-offset: 2px; }` scoped under `.host-workspace`. `app.css:1046` (`input:focus { outline: none; ... }`) is overridden by `!important`; check nothing else sets `outline` after it.
2. The date inputs are reported with outline none and `:focus-visible` false in the guard's run, but a plain Tab probe shows a ring. Find out why: reproduce with the same Tab loop as `test_keyboard_focus_is_visible_and_not_covered` on `/cleaning` only (copy the loop and `FOCUS_JS` from `test_a11y_guard_browser.py` into a temporary script outside the repo), print for each stop `document.activeElement` tag, id, `matches(':focus')`, `matches(':focus-visible')` and its computed outline. Fix the CSS so the guard passes; if the cause is a guard bug, say so in the report and stop for that item.
3. For visually hidden file inputs (`sr-only`, clipped), the control the user sees is the label or button. Restructure nothing. Change the guard in `test_a11y_guard_browser.py` (`FOCUS_JS` only): for an input that is visually hidden (1 px box or clipped), skip the `obscured` check and instead require that its label (`input.labels[0]`, else the previous or next sibling `.btn`) shows a ring (outline width at least 2 px, or a box-shadow that is not `none`) while the input is focused. Add the matching CSS: `.host-workspace :is(label, .btn):has(+ input:focus-visible), .host-workspace :is(label, .btn):has(> input:focus-visible), .host-workspace input:focus-visible + :is(label, .btn) { outline: 2px solid var(--coral-600); outline-offset: 2px; }` (adapt to the real markup in `_entity_business_fields.html` line 82). This guard edit is the one allowed exception to "do not touch the guard".

## 3. Files

`App/app/static/host2.css`, `App/app/templates/base.html` (host2.css key), `App/tests/static_versions.json`, templates for the signature inputs only if CSS cannot fix it, `docs/tasks/0171-*`. Edit `test_a11y_guard_browser.py` `FOCUS_JS` only as in 2b item 3; never edit `a11y_guard.js` or any assertion.

## 4. Steps

1. Change the 0169 rule to `outline: 2px solid var(--coral-600) !important; outline-offset: 2px;` (S2 lint covers only margin, padding, gap, font-size). Run `python3 scripts/design_lint.py 2>&1 | tail -2` from the repo root. Expected: OK.
2. Diagnose the date inputs and the signature file inputs per section 2. Fix each in `host2.css` (append a `/* 0171 */` block, tokens only), so the guard's check passes: the ring is visible on the focused control (or its visible label for the file inputs) and no sticky bar or other element covers it.
3. Bump the host2.css key to one ending `-0171` in `base.html`, then from `App/`: `.venv/bin/python tests/test_static_versions.py --write && .venv/bin/python -m pytest tests/test_static_versions.py -q 2>&1 | tail -3`.
4. Tests from `App/` (foreground, timeout 600000, `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium`): `tests/test_a11y_guard_browser.py tests/test_host_controls_browser.py tests/test_design_guardrails_browser.py -q -rs 2>&1 | tail -8`. Then from the repo root: `git checkout -- docs/tasks/0102-evidence && git clean -fdq docs/tasks/0102-evidence`. Expected: only the 21 `field-button-misaligned` findings in the layout guard remain (brief 0170); everything else passes, 0 skipped. A finding that survives two attempts: report its computed styles and stop.
5. Commit: `git add App/app/static/host2.css App/app/templates App/tests/static_versions.json docs/tasks/0171-* docs/tasks/0169-* && git commit` with message "0171: focus ring 2 px, date and file inputs" and the two trailers given by the orchestrator.

## 5. Do not touch

`a11y_guard.js`, `design_guard.js`, test assertions (other than 2b item 3); hard rules 1, 3, 8.

## 6. Commands

As in each step.

## 7. Acceptance

- [ ] Focus test passes, controls test passes, key bumped, lint OK.

## 8. Stop and ask

An anchor is missing, or a finding survives two attempts.

## 9. Report

`docs/tasks/0171-report.md`, short; `Status: review`.
