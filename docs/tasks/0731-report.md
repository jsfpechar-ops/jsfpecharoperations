# 0731 report: Úklid phone, compact list

Status: review

## Files changed
- `App/app/templates/_cleaning_table.html`: phone block only. Week shows first 3 rows; the rest of "This week" and all of "Later" sit in `<details class="cleaning-more">` with summary "Show N more" (N = hidden count).
- `App/app/cleaning_i18n.py`: key `show_more` (cs/en).
- `App/app/host_vi_i18n.py`: key `show_more` (vi).
- `App/app/static/app2.css`: end of file, two rules below 1024 px (summary style; hide closed content).
- `App/app/templates/base.html`: `app2.css?v=20261101-0730b`.
- `App/tests/static_versions.json`: via `--write`.
- `App/tests/test_0540_cleaning_tables.py`: one new test (6 week + 1 later, 3 rows before details, "Zobrazit další (4)").
- `docs/tasks/screenshots-0731/cleaning-390.png`.

## Commands (last lines)
- `.venv/bin/python -m pytest tests/test_0540_cleaning_tables.py tests/test_cleaning.py tests/test_design_cleaning.py tests/test_static_versions.py -q --tb=line`: `51 passed in 11.70s`
- `UBYHOST_REQUIRE_BROWSER=1 ... pytest tests/test_0710_v2_mockup_match_browser.py tests/test_cleaning_browser.py -k cleaning -q -rs`: `34 passed, 22 deselected in 56.06s` (0 skipped)
- `python3 scripts/design_lint.py`: `design lint: OK`
- Screenshot run (`-k screenshots`): `1 passed, 33 deselected in 19.51s`

## Step 7 acceptance
- Steps 3 sets green: yes. Lint OK: yes. Screenshot shows today + 3 week rows + "Show 4 more" above the share bar: yes.

## Deviations
- The step 3 test was lost: a temporary `git checkout` of an older tree for the failure check reverted the uncommitted test file. It is re-added in commit "0731 step 3b" (the earlier report line claiming it was in step 3 was wrong).
- Step 1 commit was amended once (missing comma in cleaning_i18n.py caught by an import check; unpushed).
- Step 2: added a second CSS rule `.cleaning-more:not([open])>:not(summary){display:none}`. Without it the browser geometry check (`tests/v2_mockup.py`) counted rows inside the closed details and failed at 320/390/768 px ("main content ends under the tab bar"). The check passes with it.
- Key bumped to `0730b` after that fix.
- No PR opened: the brief said do not push.
- Done: steps 1 to 4. Left: none.

## Questions
- None.

## Owner steps left
1. Review commits `0731 step 1` to `0731 step 4` and this report on branch `claude/project-thread-c1h7ok`.
2. Push the branch, then merge with `scripts/merge-pr-on-green.sh` when green (AGENTS.md rule 8).
