# 0189 report (executor, Haiku 5.5)

Status: blocked

Files changed: App/app/static/host2.css (.ui-section bordered panel, .ui-section-plain, phone padding, split override), App/app/static/host.css (.stay-metrics gap, .detail-metric tile borders), App/app/templates/base.html (host2.css and host.css ?v=20261020-0189a), App/tests/static_versions.json (regenerated), docs/tasks/0189-bordered-sections.md (rewritten to 1-9 template, Status blocked).

Commands:
- `python3 scripts/context_lint.py 2>&1 | tail -30` -> context lint: OK
- `cd App && .venv/bin/python -m pytest tests/test_static_versions.py -q --tb=short` -> 3 passed
- `cd App && .venv/bin/python -m pytest tests/test_design_shell_browser.py tests/test_design_shell.py tests/test_static_versions.py -q -rs` -> 6 passed, 6 skipped (Chromium 1248 missing; browser tests not run)
- Browser run with UBYHOST_REQUIRE_BROWSER=1 failed: headless shell binary not found under /opt/pw-browsers/chromium_headless_shell-1194 (find returned nothing).

Done: steps 1, 2 (CSS), 6 (version pin). Left: steps 3 (guide.html ui-section-plain), 4 (flat-pattern audit and template changes), 5 (guardrail test on 6+ pages), screenshots at 390/1280/2000, 0-skipped browser run.

Deviations: Browser tests not run (no headless shell binary); 6 skipped in shell tests. Stat tile change not visually checked.
Owner steps left: none yet; install the Playwright headless shell 1194 or point UBYHOST_BROWSER_EXECUTABLE at it, then continue.
