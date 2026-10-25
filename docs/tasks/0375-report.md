# 0375 report

Status: blocked

Files changed: App/app/static/host2.css, App/app/templates/dashboard.html, App/app/static/workflow.css, App/app/templates/base.html, App/tests/static_versions.json, App/tests/test_0375_needs_you_and_open.py (new), docs/tasks/0375-plain-open-and-needs-you.md, docs/tasks/0375-report.md.

Commands:
- §6 pytest (10 files, UBYHOST_REQUIRE_BROWSER=1): 23 passed, 0 skipped. Last line: `23 passed, 1 warning in 74.22s (0:01:14)`
- `python3 scripts/design_lint.py`: FAIL. `App/app/templates/dashboard.html: T3 class not in catalog: needs-you-icon`. Last line: `design lint: FAIL`

§7 acceptance: not ticked (lint fails).

Deviations: none in code. docs/design/MASTER.md already had uncommitted edits before this run; it is not in this commit.

Questions: add `needs-you-icon` to docs/design/catalog.json (classes), or should the class be renamed? Brief names no catalog edit.

Owner steps left: decide the catalog entry, then merge and deploy as usual. Not pushed.
