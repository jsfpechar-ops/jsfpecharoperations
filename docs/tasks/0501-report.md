# 0501 report
Status: review

## Files changed
- App/app/static/app.js: shared binder uses a module-level registry (hostBindings, claimNode, visitBinding); start-up moved to initPage, exposed as window.UbyHost.initPage.
- App/app/templates/base.html: app.js?v=20261101-0501.
- App/tests/static_versions.json: regenerated with --write.
- App/tests/test_0501_bind_once_browser.py: new.

## Commands (last lines)
- node --check App/app/static/app.js: SYNTAX_OK
- pytest test_0501_bind_once_browser.py (step 3): 1 passed
- pytest 6 named files (brief §6): 23 passed, 0 skipped
  `23 passed in 25.85s`
- python3 scripts/context_lint.py: `context lint: OK` (WARN lines are about open briefs and status.md, not errors)

## Steps
- [x] 1 binder registry (e212b65)
- [x] 2 initPage (8928f6e)
- [x] 3 browser test (commit "0501 step 3")
- [x] 4 version key and static versions (commit "0501 step 4")
- [x] 5 acceptance: named tests 0 skipped; diff touches only section 3 files

## git diff --stat origin/main
```
 App/app/static/app.js                    | 47 +++++++++++---------
 App/app/templates/base.html              |  2 +-
 App/tests/static_versions.json           |  4 +-
 App/tests/test_0501_bind_once_browser.py | 73 ++++++++++++++++++++++++++++++++
 docs/tasks/0501-host-bind-once.md        | 70 ++++++++++++++++++++++++++++++
 5 files changed, 173 insertions(+), 23 deletions(-)
```
(docs/tasks/0501-host-bind-once.md is the brief itself, already on the branch.)

## Deviations
- Not pushed and no PR opened: the run instructions forbid pushing. Owner or orchestrator to push and open the PR: `git -C /tmp/wt0501 push -u origin task/0501-host-bind-once`.
- Test: seed and open_page helpers are written locally, not imported from test_dashboard_rows_browser.py.
- No screenshots (no visual change).

## Questions
None.

## Owner steps left
- Push the branch and open the PR, then merge with scripts/merge-pr-on-green.sh.
