# 0721: v2 Overview passes the unit suite
Status: todo
Depends on: 0719 | Base commit: claude/project-thread-50hyv5 | Branch: task/0721-v2-unit-parity
Executor: Haiku 5.5 | Fits one session: 30 tool calls

## 1. Objective
A local run of the non-browser tests on 7ffde44 has 15 failures outside `test_endtoend.py`, listed below. Fix them so the CI `test` job goes green. Restore the feature wherever the v2 Overview lost it.

## 2. Context and decisions (orchestrator, 2026-11-01 18:50)
For each test, read the failing assertion first (`sed -n` that range), then:
- **Feature lost on `/`** (a banner, a line, a link or a button the host saw before): restore it in `dashboard.html` in the quiet v2 style, under the same condition as before. Use `git show origin/main:App/app/templates/dashboard.html` to find the old markup and condition. This covers the onboarding banner and finish card variants (`test_dashboard_empty.py`, `test_dashboard_order.py`), the missing-police-field line (`test_dashboard_missing_banner.py`) and the needs-you line for a stay arriving tomorrow (`test_signed_in_chrome.py`). Brief 0717 restored some of these; 0719 rewrote the todo cards, so check the 0719 markup didn't drop a branch. The "show more" threshold is 4 (0717 decision); keep the test at 4.
- **Markup renamed on purpose** (0719 uses the mockup's class names: `.card.need`, `.ic` plus a tone class, `b.t`, `small`): update the test's string to the new markup and keep its intent, e.g. `test_0375` (icon box and primary only on the first card).
- `test_navigation_prefetch.py`: the v2 shell's speculation-rules block lacks the exclusions the old shell has (`/admin/*` and others). Copy the old shell's exact rules block into `_shell_v2.html`, or include the same partial. One source is better: if the old shell uses an include, use it in both.
- `test_havel_palette.py::test_no_match_opens_havel_with_the_query`: the v2 search button must carry the old search's command-palette hooks (`data-command-open` and whatever else `_shell_sidebar.html` puts on its search). Copy the attributes; do not change app.js.
- `test_demo_seed.py`, `test_feed_dns_pinning.py` (OSError "Address family not supported" is this container's network), `test_reporting_help_0097.py`: first run each on origin/main in a temporary worktree (`git worktree add /tmp/wtmain0721 origin/main`; symlink App/.venv as in this worktree). If a test fails the same way there, note it as environment and leave it. Otherwise fix it.
- `test_endtoend.py` (18 local failures): run `-x` on origin/main the same way. If it fails there too, note it as environment. If it passes there, list the first failure in the report and stop.
- If you change app2.css, bump its key in base.html (`20261101-0721`) and `--write` the manifest.

Failing tests (local, 7ffde44):
```
test_0375_needs_you_and_open.py::test_needs_you_template_uses_icon_and_primary_only_on_first_line
test_dashboard_empty.py::test_without_a_calendar_the_empty_state_asks_for_one
test_dashboard_empty.py::test_the_finish_setup_panel_gives_way_to_the_banner
test_dashboard_missing_banner.py::test_one_short_line_opens_the_first_missing_police_field
test_dashboard_missing_banner.py::test_lines_past_the_fifth_wait_behind_show_more
test_dashboard_missing_banner.py::test_the_setup_line_is_in_czech
test_dashboard_order.py::test_an_overdue_stay_shrinks_the_finish_card_to_one_line
test_dashboard_order.py::test_the_one_line_finish_card_still_reaches_the_guest_link
test_dashboard_order.py::test_the_finish_card_keeps_its_room_when_nothing_is_overdue
test_demo_seed.py::test_seed_imports_stays_without_fetching_the_calendar
test_feed_dns_pinning.py::test_two_concurrent_fetches_do_not_cross_pinned_addresses
test_havel_palette.py::test_no_match_opens_havel_with_the_query
test_navigation_prefetch.py::test_signed_in_shell_renders_prefetch_rules_with_exclusions
test_reporting_help_0097.py::test_reporting_and_fee_list_geometry_and_tips_in_the_browser
test_signed_in_chrome.py::test_a_stay_that_needs_the_host_gets_one_line_with_one_button
```

## 3. Files
`App/app/templates/dashboard.html`, `App/app/templates/_shell_v2.html`, `App/app/static/app2.css` (only if needed), `App/app/templates/base.html` and `App/tests/static_versions.json` (key, only if app2.css changed), the failing test files (renamed-markup changes only), report `docs/tasks/0721-report.md`.

## 4. Steps
Test by test; run only that file (`-q --tb=short -x | tail -20`); commit every 2-3 fixes with explicit paths.

## 5. Do not touch
`app.js`, `_shell_sidebar.html`, `app/routes/*` (if a restore needs route data, stop and ask), app2.css phone block rules other threads rely on.

## 6. Commands (from App/)
Per file as above. Final: all listed files in one run, `-q --tb=line -rf 2>&1 | tail -25`. Ruff: `.venv/bin/python -m ruff check app tests tools --select E9,F63,F7,F82,F401,F841 | tail -3`. Also re-run `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py -q --tb=line | tail -5` if dashboard.html changed. Repo root: `python3 scripts/design_lint.py | tail -1; python3 scripts/context_lint.py | tail -1`.

## 7. Acceptance
Every listed test passes or is shown to fail identically on origin/main. 0710 stays green.

## 8. Stop and ask
Stop if a restore needs route or query changes, or if a test can't be sorted.

## 9. Report
`docs/tasks/0721-report.md`: per test, the cause, the change or the environment proof, and the test tails.
