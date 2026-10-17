# 0042 report: optional browser imports in coverage CI

The CI collection failure was reproduced before editing. On archived head
`3ee5985`, collection without Playwright failed at unconditional imports in
`test_host_controls_browser.py`, `test_host_property_controls_browser.py`, and
`test_host_wide_geometry_browser.py`: 3 `ModuleNotFoundError`s, 12 skips, exit
2, before tests ran. This matched the coverage job, which installs
`requirements-dev.txt` without Playwright.

Each module now follows the existing contract: import Playwright when
`UBYHOST_REQUIRE_BROWSER=1`; otherwise use `pytest.importorskip`. The wide test
module’s existing required-browser flag now appears before its conditional
import. No test selection, assertions, application code, dependencies, or CI
workflow changed.

Patched verification used archived head `3ee5985`:

- Normal no-Playwright collection: 2,982 tests collected, exit 0.
- Full coverage: 2,980 passed, 17 skipped, 7 warnings; 89.50% coverage against
  the 86% threshold; exit 0. Fifteen skips were optional browser modules. Two
  backup-tool tests skipped because age tools were not on the default local
  `PATH`; with CI tools added to `PATH`, both passed (2 passed, 1 warning,
  exit 0).
- Required-mode missing-Playwright negative check: 3 collection errors as
  intended, exit 2. Required mode does not silently skip browser tests.
- Required installed-Chromium run of the three changed modules: 5 passed,
  3 failed, 0 skipped. Controls and property-controls modules passed. The three
  failures are existing wide stay-action clipping assertions at desktop/mid
  widths; these remain within the paused 0041 UI work and were not changed here.

Logs: `/tmp/ubyhost-ci-patched-3ee-full-coverage.log`,
`/tmp/ubyhost-ci-patched-3ee-age-tests.log`, and
`/tmp/ubyhost-ci-patched-3ee-required-negative.log`. Chromium output was
captured in the executor session; it reported the three geometry failures above.
No claim is made that the UI browser suite passes or that all browser coverage
ran in the no-Playwright CI job.
