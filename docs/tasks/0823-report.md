# 0823 report

Status: review

Files changed: `App/app/templates/housebook.html` (removed `{% include "_host_alerts.html" %}` under `{% block body %}`). No test changed (no housebook test asserts the alert stack).

Command (from `App/`): `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_host_wide_geometry_browser.py tests/test_0710_v2_mockup_match_browser.py -k "wide_lanes or housebook" -q -rs --tb=short`
- Before: 1 failed, 12 passed (`test_host_wide_lanes_align`, housebook en 1024 alertStack present).
- After: 13 passed, 0 failed, 0 skipped.

Acceptance (§7): ticked.

Deviations: none. Not committed (per brief and owner).

Questions: none.

Owner steps: review and commit on `claude/project-thread-v4nqi5`, then `scripts/merge-pr-on-green.sh`.
