# 0828 report: /guide search and folded topics

Status: blocked (4 red items below; executor tool-call cap reached, so the last ones were not diagnosed)

## Files changed (not committed, per owner instruction)
- App/app/templates/guide.html: 24 sections now `<details class="guide-section card ui-section ui-section-plain guide-topic" id=...><summary><h2>` (closed by default, ids kept). Search input `#guide-search` (hidden without JS) and `.guide-search-empty` line above the topics. Phone TOC removed; desktop TOC kept. `<script src="/static/guide.js?v=20261102-0828" defer>` added. Copy unchanged.
- App/app/static/guide.js (new, about 2.9 KB): debounced 100 ms search, accent-insensitive, Esc clears, opens and scrolls to the topic for a hash, handles hashchange and TOC clicks.
- App/app/static/app2.css: block `/* 0828 guide search (v2) */` appended at the end (15 rules). The 0803 block is untouched. Last rule hides closed topic bodies (needed: the 0800 geometry check otherwise measured hidden content).
- App/app/guide_i18n.py: keys guide.search.placeholder and guide.search.empty (en and cs). cs text is my draft, needs a native check.
- App/app/host_vi_i18n.py: the same two keys (vi). My draft, needs a native check.
- App/tests/test_0828_guide_search_browser.py (new): 9 browser tests at 390 and 1280.
- Screenshots (UBYHOST_SHOTS_0800=1): docs/tasks/screenshots-0800/guide-390.png and guide-1280.png. Not viewed by me; look at the 390 one before merge.

## Commands and last lines
1. `pytest tests/test_0828_guide_search_browser.py tests/test_0800_v2_remaining_pages_browser.py -k guide`: `31 passed, 84 deselected in 50.70s` (0 skipped).
2. `pytest tests -k "guide and not guest_guide"`: `1 failed, 107 passed, 5509 deselected`. FAILED tests/test_guide_coverage.py::test_every_guide_section_is_known_to_havel: its regex wants `<section class="guide-section...`, and the guide is now `<details>`. Not in the brief's file list, so not edited.
3. `pytest tests/test_static_versions.py tests/test_host_i18n.py tests/test_privacy_first.py`: `5 failed, 17 passed`.
   - test_static_versions (2): app2.css changed but still ?v=20261102-0812, and guide.js is not in the manifest. `--write` refuses: "app2.css changed but still has ?v=20261102-0812". Orchestrator: bump the app2.css key, then run `.venv/bin/python tests/test_static_versions.py --write`.
   - test_host_i18n (3): "no such table: user_account / apartment" (DB not initialised in this run). Not diagnosed; may be a pre-existing isolation issue. Check whether it also fails on main.
4. `python3 scripts/design_lint.py`: FAIL. `T3 class not in catalog: guide-topic` (the new classes guide-topic, and probably guide-search, guide-search-empty, are not in the design catalog). Fix is a catalog entry, not edited here.

## Ctrl K finding
Ctrl/Cmd K (app/static/app.js:1771) opens the command palette, fed by app/routes/api.py `/api/command-palette`. It lists nav pages, actions and apartments only. Guide topics are not searchable from it. Not built, per brief.

## Deviations
- No `NNNN step k` commits (owner said do not commit).
- Phone TOC removed (brief step e). Without JS there is no search field, and the topics still open on tap.
- The no-JS anchor behaviour (step d) was not tested.

## Owner or orchestrator steps left
- Bump app2.css cache key in templates to a new value, then run test_static_versions --write.
- Decide test_guide_coverage: change its regex to accept `<details class="guide-section`, or keep a section wrapper.
- Add the new classes to the design catalog, then rerun design_lint.
- Check test_host_i18n on main.
- Native review of cs and vi strings.
