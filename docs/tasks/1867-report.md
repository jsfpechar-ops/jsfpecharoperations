# 1867: Report

Status: review

## Files changed

```
 App/app/needs_you.py             |  8 ++++++--
 App/app/reporting.py             | 14 ++++++++++++++
 App/tests/test_needs_you_0240.py | 26 +++++++++++++++++++++++++-
 3 files changed, 45 insertions(+), 3 deletions(-)
```

## Commands

### Tests (from App/)

```
.venv/bin/python -m pytest tests/test_needs_you_0240.py tests/test_needs_you_dashboard_0241.py tests/test_0375_needs_you_and_open.py -q --tb=short -x 2>&1 | tail -5
```

Last 5 lines:
```
...............                                                          [100%]
15 passed in 1.38s
```

### Context lint (from repo root)

```
python3 scripts/context_lint.py 2>&1 | tail -5
```

Last 5 lines:
```
WARN  test_0705_v2_shell_browser.py::test_non_v2_dashboard_still_loads_the_old_stylesheets_and_sidebar is named by open briefs 0784-settings-area-v2-old-shell-tests.md, 0851-fix-725-ci-and-savebar.md; say which goes first
WARN  test_signed_in_chrome.py::test_the_support_line_is_not_part_of_the_legal_link_row is named by open briefs 0784-settings-area-v2-old-shell-tests.md, 0851-fix-725-ci-and-savebar.md; say which goes first
WARN  2 commit(s) touched App/ after the last status.md update. Orchestrator: update docs/context/status.md at review.
next free: task 2000 | goose migration 00023 (App/app/migrations/ is frozen)
context lint: OK
```

## Acceptance (§7)

- [x] `grep -nF '"files_with_ubyhost": _apartment_files_with_ubyhost(apartment),' App/app/reporting.py` finds one line.
- [x] `grep -nF 'row.get("files_with_ubyhost", True)' App/app/needs_you.py` finds one line.
- [x] The three new tests exist and the §6 pytest command passes (15 passed).
- [x] `git diff --stat` lists only the three files of §3 (plus the report).
- [x] No template, CSS or `go/` file changed (rule 7/10 gate not applicable).

## Deviations

None.

## Questions

None.

## Owner steps

1. Open the pull request when this report says `review`.
2. After the merge and deploy, open the dashboard of a host whose setup is unfinished: the card should say "Nothing needs you today." while the setup banner shows, with no "Police overdue" lines.
3. Open a property that has all three UbyPort login fields and an overdue stay: the red "Police overdue" line should still show.

## Git log (last 5 commits)

```
4aaa16c2b 1867 step 7
66382d29e 1867 step 3
36a13526d Brief 1867: no police nags in What needs you without UbyPort login
faa13a1fb Merge pull request #1184 from jsfpechar-ops/cursor/1999-python-retire-brief-dff7
a5cc69fc3 1999: align brief with template sections for context lint
```
