# 0789 report

Status: blocked

## Commits
- Step 1 (tests first): `0789 step 1: failing Airbnb settings geometry test at 390, 768, 1280 (en, cs)` in `App/tests/test_0786_settings_geometry_browser.py` (new test `test_0789_airbnb_settings_pattern_every_width`, 3 cases).

## Test results
- `test_0789_airbnb_settings_pattern_every_width`: 3 failed, 10 deselected (expected red: no `.airbnb-back` or `.airbnb-index-row` markup exists yet). Not a regression; the failures are the target.
- Other brief §6 tests: not run (no template change yet).

## Screenshots
- None. No UI change yet, so nothing to shoot. Target folder `/mnt/project-files/settings-area/airbnb/` not created.

## Deviations
- Done: step 1 (test first, red).
- Left: steps 2 to 5 (partials for back button, index row and pill tabs; `/settings` index; per-group sub-pages; restyle of `/settings/archived`, `/entities`, `/privacy-requests`; static cache bump; screenshots at 390, 768, 1280).
- Reason: `settings.html` is 505 lines with six groups. Moving each group into its own sub-page with the existing forms needs a full template split, which does not fit one executor checkpoint. Brief §9 allows splitting by page.
- Branch: the brief names `claude/project-thread-vov8xp`, but the work was done on the branch the orchestrator gave, `claude/project-thread-umes84`, as instructed.

## Questions
- Confirm the split: next part should be (a) the shared partials and the `/settings` index, then (b) one part per sub-page.

## Owner steps left
- None yet. No push, no PR.
