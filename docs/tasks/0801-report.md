# 0801 report: setup wizard on the v2 look

Status: review (not committed; orchestrator commits)

## Changed files
- App/app/templates/setup_wizard/_layout.html: `{% set v2 = true %}`, empty page_title block, `wiz-page` on the wrapper, `wiz-title` block with h1.big below the progress.
- App/app/static/app2.css: appended block `/* 0801 setup wizard (v2) */` (all rules under `body.v2 .wiz-page`).
- docs/design/catalog.json: added `wiz-page`, `wiz-title`, `wiz-count`.
- App/tests/test_design_setup_wizard_browser.py: line asserting `.ui-ph h1` now `.setup-wizard h1`; geometry block skipped when `.wrap.with-sidebar` is absent (v2 shell).

## Tests
- `tests/test_0800_v2_remaining_pages_browser.py -k "setup-…"`: `36 passed, 54 deselected`, no skips.
- Wizard tests (test_design_setup_wizard_browser, test_wizard_friendly_0273, test_wizard_second_lock_0400, test_finish_moment_0274, test_times_required_0210): `23 passed`.
- `scripts/design_lint.py`: FAIL, but only on cleaning_edit/properties/shares.html (other threads). None on 0801 classes.
- `scripts/context_lint.py`: FAIL on docs/tasks/0804-cleaning-subpages-v2.md (missing Status line, other thread).

## Screenshots
docs/tasks/screenshots-0800/setup-{property,calendar,police,guest-link,stay-fee,done}-{390,1440}.png
Montages for viewing: /tmp/claude-0/-home-claude-jsfpecharoperations/8739e695-b169-5476-b8c2-e8780013d5b6/scratchpad/montage-0801-390.png and montage-0801-1440.png

## Deviations
- No separate sub line in the head: the step question stays as the h2 inside the card (test hooks `setup-wizard-question`, `data-step-tone` rely on it).
- Step-card pills fixed at 26 px height in the done checklist.
- Help-tip "?" buttons are 44 px below 1024 px (tap rule); they look large on phone.
- Screenshots reviewed as montages, not one by one.
- Route `setup-done` and all six pages render (no redirect for the rich host fixture).

## Owner steps left
- Commit (orchestrator) and review the two screenshot montages.
