# 0040 host-wide geometry validation report

**Status:** review
**Executor:** Luna validation
**Branch:** `task/host-design-staging`

I added regression coverage and runtime evidence in `App/tests/test_host_wide_geometry_browser.py`, `App/tests/test_host_filter_panels_browser.py`, `App/tests/test_alert_stack.py`, and `App/tests/test_first_property_step.py`. No app implementation files were changed by this executor.

The first full CI-equivalent run completed with **3026 passed, 2 skipped, 2 failed**, 89.57% coverage. The failures were stale test contracts: `test_notifications_float_in_the_corner` mirrored the old fixed-position CSS, and the Property heading check required a bare `<th>Property</th>` despite the same visible text now carrying a semantic class. I replaced the CSS mirror with rendered alert placement/link/non-dismissibility checks, and made the heading check independent of attributes while retaining the Property text and Apartment exclusion. The two skips were age-backed backup tests; the CI utility directory was missing from PATH. The final run adds the verified tools to PATH and reports zero skips.

The final browser matrix covered **444 combinations**: 28 routes × EN/CS × six widths (1024–2048), plus 18 selected routes × EN/CS × 360/390/760. The measured widths were 360, 390, 760, 1024, 1280, 1440, 1680, 1920, and 2048. It recorded 444 route rectangles and **0 lane mismatches**; the maximum header/result edge delta was 0px. The audited routes cover dashboard, stays/archive/detail, property/operator lists and forms, invoice list/generator/settings/detail, unset/configured fees/setup/detail, guest register, submissions/detail, guest links, automation, archive, settings, and smart locks. Public guest/auth flows and external services are outside this UI audit.

The synthetic browser fixture uses an isolated host, mock UbyPort, scheduler off, and a post-startup persistent date-change alert. Guards cover global alert flow and link placement, narrow invoice form lanes, filters and month controls, visible stay text and actions, focused address fields, and collapsed sidebar geometry. A synthetic overdue badge initially spilled into adjacent tracks; after the scoped wrapping and shape fixes, EN/CS Stays checks passed at 1024/1280. The refreshed Czech 1280 view shows the full overdue label inside its red badge and Copy/Send/More controls aligned. The optional enhanced month trigger now fills its wrapper; no-JS fallback and required/selected-month behavior remain covered.

Validation commands and results:

- `PATH=/tmp/ubyhost-ci-tools/usr/bin:$PATH UBYHOST_UBYPORT_ENV=mock UBYHOST_DEPLOYMENT=staging UBYHOST_ENABLE_SCHEDULER=0 UBYHOST_REQUIRE_BROWSER=1 UBYHOST_BROWSER_EXECUTABLE=/usr/bin/chromium XDG_CONFIG_HOME=/tmp/ubyhost-wide-xdg-config XDG_CACHE_HOME=/tmp/ubyhost-wide-xdg-cache XDG_DATA_HOME=/tmp/ubyhost-wide-xdg-data .venv/bin/python -m pytest tests -q -rs --cov=app --cov-report=term-missing --cov-fail-under=86` — **3030 passed, 0 skipped, 7 warnings; 89.57% coverage; exit 0**. Full log: `/tmp/ubyhost-final2-full-coverage.log`.
- Required Chromium Stays midwidth run — **1 passed, 0 skipped** at EN/CS 1024/1280. Log: `/tmp/ubyhost-stays-midwidth-after-final-css.log`.
- Filter geometry plus no-JS fallback — **2 passed, 0 skipped**. Log: `/tmp/ubyhost-filter-geometry-final.log`.
- Rendered alert and Property heading contracts — **2 passed**. Log: `/tmp/ubyhost-postsuite-unit.log`.
- `ruff check app tests tools --select E9,F63,F7,F82,F401,F841` — passed.
- `shellcheck -S error deploy/lightsail/scripts/*.sh App/scripts/*.sh docker-entrypoint.sh App/run.sh App/render_start.sh render_start.sh` — passed.
- `node --check App/app/static/app.js` — passed.

Evidence is under `/workspace/generated_images/host-wide-audit/before/` and `/workspace/generated_images/host-wide-audit/after/`; the refreshed month view is `after-invoices-cs-390.png`, and the Czech overdue example is `after-stays-actions-cs-1280.png`. Final matrix JSON and mismatch data are `rectangles.json` and `lane-mismatches.json` in the `after/` directory.

These are local synthetic checks. GitHub CI status for the corrected commit is not established locally; PR #338 is open and updated by Codex. Docker image/health checks and Docker-based gitleaks remain CI checks. The owner reviews and redeploys the corrected branch.

Owner steps: review the indexed before/after gallery and report, confirm CI for the corrected commit, then redeploy the corrected branch.
