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

## Steps a-e: done (executor session 2)

Status for steps a to e: done. Step 0 untouched.

### Files changed (uncommitted)
- `App/app/static/app2.css`: rules added inside the 0800 block (end, before `/* 0802 ... */`, marked `0808 step a` and `0808 step b`) and inside the 0803 block (end, before `/* 0804 ... */`, marked `0808 step c` and `0808 step d`).
  - a: `:is(.prop-new,.wiz-page) .field-label-row` flex row, label margin 0, `.help-tip` inline-flex beside the label, round "?" button; the tip text is hidden behind the "?" (shown on focus or `.is-open`), so it no longer sits as fine print on the page.
  - b: `.onboarding-step-group` flex row (gap 12 px, children nowrap, `Learn why` summary nowrap, 36 px desktop / 44 px below 1024); `.onboarding-step` gap 16 px; below 767 px the group wraps under the text with 52 px left padding.
  - c: `.guide-section` padding 20 px (16 px below 1024).
  - d: `.havel-msg` max-width 80%; `.havel-topics .havel-chips` vertical list, max 420 px, 8 px gaps; `.havel-chip` full width, left-aligned, 44 px min height, `var(--control-radius,10px)`.
- `App/app/templates/_components.html` (onboarding step card, ~line 473 and ~485): wrapper `<div class="onboarding-step-group">` around the status/dot, action link, manual link and "Learn why" details, emitted only when `v2` is true. Markup only, no text.
- `App/tests/test_0800_v2_remaining_pages_browser.py`: 4 new tests (below).
- `docs/tasks/screenshots-0800/*.png`: regenerated (`UBYHOST_SHOTS_0800=1`).

### New tests
- `test_help_tip_sits_beside_its_label`: 4 routes x 390/1280. Tip centre within 4 px of label text centre, 0 to 16 px right of the text.
- `test_onboarding_step_actions_are_one_grouped_row`: 390/1280. "Learn why" on one line, gap between group controls 8-16 px, text to group gap >= 16 px.
- `test_help_card_text_has_inner_padding`: `guide` and `guest-guide` x 390/1280. Every text child at least 16 px inside its card.
- `test_havel_is_a_stacked_chat_with_a_topic_list`: 390/1280. Topic buttons share x (+-1 px), stacked, max 420 px wide; no two messages share a row.

### Test tails
- `tests/test_0800_v2_remaining_pages_browser.py` (all widths, screenshots regenerated): `106 passed in 155.21s`, 0 skipped.
- Step-set run for the new tests only (`-k "help_tip or onboarding_step or help_card or havel_is"`): `16 passed in 22.25s`.
- Wizard set (`test_onboarding_wizard_browser.py test_onboarding.py test_design_setup_wizard_browser.py test_quick_answers_browser.py`): `1 failed, 108 passed in 164.60s`. Failure: `test_quick_answers_browser.py::test_the_chips_are_big_full_width_and_show_their_state` (same as before this session).
- `pytest tests -k "havel or guide"`: `2 failed, 330 passed in 126.73s`. Failures: `tests/test_havel_palette.py::test_palette_carries_the_havel_row_only_when_on` and `::test_no_match_opens_havel_with_the_query` (same as before; still not checked against the base commit).
- `python3 scripts/design_lint.py`: `design lint: OK`

### Deviations
- Help tip body text is hidden on /apartments/new and the wizard (it was visible inline as fine print). This is a CSS presentation change, not a text change; the owner asked for no fine print on main pages.
- Step b needed a wrapper `div` in the template (CSS alone cannot group the status, button and details into one flex row). The wrapper is v2-only.
- A stray empty file `/tmp/x` was created by a shell redirect in this session. It is outside the repo; delete it when convenient.
- A `rm` of a scratch file was blocked by the safety check (the command was never run; nothing deleted).

### Questions
1. The quick-answers chip test and the two havel palette tests are still red. Are they already red on the base commit? (Not checked; no stash or checkout allowed.)

### Owner steps left
- Orchestrator: review the diff in `app2.css`, `_components.html` and the test file, then commit as `0808 steps a-e`.
- Orchestrator: bump the app2.css cache key (the brief leaves this to you).
- Look at `docs/tasks/screenshots-0800/` (onboarding-390, havel-390, property-new-390) before the PR.
