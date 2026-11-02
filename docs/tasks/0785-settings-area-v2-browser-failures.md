# 0785 brief: browser-shard failures on PR #700 (settings area v2)

Status: todo
Executor: Haiku 5.5 (40 tool calls allowed for this brief), alone, on branch `claude/project-thread-vov8xp` (already checked out; do not switch branches, do not push). Run before 0786.

## 1. Objective

CI browser shards on PR #700 head f996b02 (run 41444479741) fail on the tests below. Every one passes on main (main CI green at #689). So each failure comes from this PR: the 0780-0784 changes to `App/app/static/app2.css`, `settings.html`, `entities.html`, `privacy_requests.html`, `settings_archived.html`, or a test that still points at a page this PR moved to v2. Make each pass.

Standing test rule (0780/0781): a test may be re-pointed or have an assertion on OLD markup updated to the v2 equivalent. Never weaken a geometry/behaviour check, never skip, never delete a test. A test that needs an old-shell page uses `/payments` (stays old until the Stripe rework), as 0784 did.

| Group | Tests | Likely cause and fix |
|---|---|---|
| A. Mockup style diffs on pages this PR did not touch | `test_0710_v2_mockup_match_browser.py::test_v2_page_matches_mockup_styles[stay-*, stays-320/390, overview-320/390, property-1024/1280/1440]`, `::test_v2_page_geometry[property-320/390/768]` (diffs: `.pill` / `.pill.p-warn` size, `.card.stay` / `.hs .card` / `.police-card` height, `.crumb` font-size 14 vs 12) | A rule added by 0780-0783 is not scoped to its page. Find it with `git diff origin/main -- App/app/static/app2.css` (look for bare `.pill`, `.card`, `.crumb`, `.police-card`, `h2`, `.sub` selectors, especially in the `/* v2 ports of shared ui-* classes */` block). Scope it to the settings-area pages (`body[data-page=...]` or the page's own wrapper class) so stay/stays/overview/property render exactly as on main. Do not change mockups or the other pages' rules. |
| B. Sidebar/motion tests | `test_design_shell_browser.py` (`test_collapsed_sidebar_keeps_dashboard_and_stays_lanes_aligned`, `test_sidebar_click_slides_the_rail_and_flips_the_toggle`, `test_sidebar_click_respects_reduced_motion`, `test_sidebar_restore_and_resize_never_animate`, `test_tablet_rail_toggle_slides_the_overlay_only`, `test_sidebar_search_has_a_border`) and any `test_motion_browser.py` / `test_0705` / `test_shell_lane_browser.py` failure | They used `/settings` (or `/entities`) as an old-shell page and look for the old `ui-sidebar` toggle. Point them at `/payments`, the way 0784 did for the unit tests. |
| C. Settings flat sections | `test_design_guardrails_browser.py::test_host_sections_are_bordered_panels` (`settings-account` etc: border 0) | The guard is for old-shell `.ui-section`. Settings is v2: either drop the old `ui-section` class from the v2 settings sections (they are `.card` groups now) or exclude v2 pages (`body.v2`) from that guard, whichever the guard's own docstring allows. A v2 `.card` must still have its border. |
| D. Entities (Společnosti) list | `test_host_list_page_layout_browser.py::test_list_panels_never_scroll_sideways_and_actions_stay_visible` (businesses: "no list panel"), `test_host_list_cards_browser.py::test_phone_rows_have_full_border_and_buttons_do_not_cover_names`, `::test_entities_list_fits_at_supported_lanes_and_languages` (en/1024 overflow 762 > 730), `test_host_wide_geometry_browser.py` "no business rows on /entities", `test_host_controls_browser.py::test_rows_hover_as_one_surface_and_use_compact_menus[1440/1920/2048-en/cs]` (timeout on get_attribute) | Update selectors that look for the old list panel/rows to the v2 entities markup, keeping every geometry check. The 1024 overflow is real: fix it in the `/* 0781 */` CSS block (table/columns must fit the 730 lane, no sideways scroll). |
| E. Layout guard on entities | `test_every_host_page_passes_the_layout_guard` (`cell-not-under-header` 6 on operators/invoice-settings at 390, `tap-target-small` 2), the `tap target 66x24 "Properties"` finding | Real geometry bugs: at 390 the phone card must not keep a table header row with misaligned cells (hide `thead` and use label/value rows, as other v2 phone lists do), and every tap target >= 44 px below 1024 (24 px min above). |
| F. Lanes and alerts | `test_host_wide_geometry_browser.py::test_host_wide_lanes_align` ("synthetic persistent date-change alert not rendered on operators/en/1024"), `::test_direct_fee_backlinks_align_with_page_lane` | `entities.html` must include `_host_alerts.html` the way `settings.html` now does (0784 row 2). Backlink lane: align with the page lane in the 0781 block. |

Shards 3 and 4 may add more rows: run every browser test file named above plus `tests/test_onboarding_wizard_browser.py tests/test_onboarding_followup_browser.py tests/test_havel_browser.py tests/test_host_help_browser.py tests/test_a11y_guard_browser.py tests/test_motion_browser.py tests/test_shell_lane_browser.py tests/test_0705_v2_shell_browser.py` and fix anything red the same way. If a failure also fails on a clean `origin/main` checkout (`git worktree add /tmp/wtmain origin/main`), it is not ours: write it in the report and leave it.

## 2. Context

0780-0784 briefs and `docs/tasks/0783-report.md`. CSS blocks: `/* 0780 … */`, `/* 0781 … */`, `/* v2 ports of shared ui-* classes */` in `App/app/static/app2.css`. Help-tip rules from 2f54815 stay as they are. Tablet layout: no phone-only rules at 768.

## 3. Files

The test files above; `App/app/static/app2.css`; `App/app/templates/entities.html`, `settings.html`; `App/app/templates/base.html` + `App/tests/static_versions.json` (cache key `20261102-0785a`). Nothing else.

## 4. Steps

1. Run the browser files (command below), note the failures.
2. Fix group by group, one commit per group (`0785: <group> …`), adding files by name (never `App/.venv`, never PNGs).
3. Cache key bump, then from `App/`: `.venv/bin/python tests/test_static_versions.py --write`.

## 5. Do not touch

`App/app/static/app.js`, Python routes, mockups, other pages' templates.

## 6. Commands

From `App/` (one file group at a time, they are slow):
`PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest <files> -q --tb=line -p no:cacheprovider 2>&1 | grep -E "^(FAILED|ERROR)|^E  |passed|failed" | cut -c1-240 | tail -40`
From the repo root: `python3 scripts/design_lint.py 2>&1 | tail -5`, `python3 scripts/context_lint.py 2>&1 | tail -5`.

## 7. Acceptance

All the files above pass, 0 skipped. `tests/test_design_settings.py tests/test_static_versions.py` still pass.

## 8. Stop and ask

A Python route or `app.js` change needed; a fix that would change how stay/stays/overview/property look compared with main; 40 tool calls.

## 9. Report

`docs/tasks/0785-report.md`: commits, counts per file, what each group needed, anything left and why.
