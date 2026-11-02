# 0808 report

Status: blocked

## Files changed (uncommitted)
- `App/app/static/app2.css` only.
  - 0801 block: `body.v2 .wiz-page .setup-wizard-cards` grid (1 column, gap 16px) and `.setup-wizard-card` flex column (answers item 1).
  - 0801 block: `@media (min-width:1024px)` rule for `.setup-wizard-exit .ui-btn` and `.setup-wizard-foot .ui-btn` at `min-height:36px` (exit button; see Deviations).
  - New block `/* 0808 skeleton (v2) */` at the end: host2.css lines 198-219 ported, scoped `body.v2`, `var(--surface-2)`→`var(--side2)`, `var(--surface)`→`var(--s)`, plus phone media and reduced-motion `animation:none`.
- `docs/tasks/screenshots-0800/*.png`: regenerated (UBYHOST_SHOTS_0800=1).
- No template, test, base.html or commit changes.

## Step 0: done
- Cards side by side at >=1024, stacked below (from 0801 block, earlier session): done.
- Exit button 36 px at >=1024: done.
- Copy cards same row at 1280: done (answers item 1).
- Skeleton visible on v2 pages: done (cause: host2.css skeleton rules not loaded on v2; bones were empty spans).

## Steps a to d: not started
- a (help tip beside label), b (onboarding step group), c (guide text padding), d (Havel chat layout): not started; tests for them not added.

## Test tails
- `tests/test_onboarding_wizard_browser.py`: `85 passed in 156.88s`
- `tests/test_0800_v2_remaining_pages_browser.py` (after screenshot regen run): `90 passed in 133.36s`
- `tests/test_onboarding.py tests/test_design_setup_wizard_browser.py tests/test_quick_answers_browser.py` plus wizard file: `1 failed, 108 passed in 159.35s`. Failure: `test_quick_answers_browser.py::test_the_chips_are_big_full_width_and_show_their_state` (Page.wait_for_function timeout 3000 ms; fails alone too, 5.44 s). Not yet checked against the base commit.
- `pytest tests -k "havel or guide"`: `2 failed, 324 passed in 126.54s`. Failures: `tests/test_havel_palette.py::test_palette_carries_the_havel_row_only_when_on` and `::test_no_match_opens_havel_with_the_query` (`/guide?lang=en` lacks `data-sheet-open="havel-sheet"`). Server markup only; this change is CSS only, so probably pre-existing. Not verified.
- `python3 scripts/design_lint.py`: `design lint: OK`

## Deviations
- Exit button fix: the wizard test also checks `.setup-wizard-foot .ui-btn` (the Back link, ui-btn-quiet, 24 px), so the 36 px rule covers the footer too. Scoped to >=1024 because the `:where` 44 px rule applies below 1024 (an unscoped rule broke 18 tests at phone widths, now fixed).
- Done: step 0 (all items). Left: steps a to d, their tests, 0800 run after them, and the two red tests above.

## Questions
1. Is the quick-answers chip test and the havel palette failure already red on the base commit? (Not checked; no stash allowed.)

## Owner steps left
- Orchestrator: review app2.css diff and commit as `0808 step 0`.
- Next executor session: steps a to d (fresh session; the markup pointers are `_components.html` onboarding-step block ~line 461, `_ui.html` help-tip ~line 111, `_havel_thread.html`, `_havel_topics.html`, and `guide.html`).
