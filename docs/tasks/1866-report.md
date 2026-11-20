# 1866 report

Status: review

## Files changed (`git diff --stat`)
- `App/app/static/app2.css` | +8: `body.v2 .banner:not(.section-notice)` block (flex lane, radius 12, `--s`/`--warns`/`--bads`/`--oks`/`--info` tones) after the 0993 impersonation-bar rules.
- `App/app/templates/base.html` | 1 line: `app2.css?v=20261120-host-palette-1865b` → `…-1866a`.
- `App/tests/static_versions.json` | regenerated (`tests/test_static_versions.py --write`), app2.css entry only.
- `App/tests/test_0414_billing_banner_browser.py` | +12: button-inside-banner-box, `display:flex`, non-transparent background assertions at 390 and 1280.
- `docs/tasks/screenshots-1866/` | 6 new PNGs (dashboard, trial + overdue, 390/768/1280).

## Commands (last lines)
- `pytest tests/test_0414_billing_banner_browser.py tests/test_static_versions.py -q -x` → **4 passed** (Chromium 153, headless shell, UBYHOST_REQUIRE_BROWSER=1).
- Negative control: same test with the CSS/base/json changes stashed → **1 failed** (button outside box, display block) — the new assertions catch the bug.
- `pytest tests/test_billing_*.py -q` → **183 passed**.
- `pytest tests/test_host_geometry.py -q` → **2 passed**.
- `pytest tests/test_design_guardrails_browser.py -q` → **11 passed**, 0 skipped.
- `pytest tests/test_layout_lint_browser.py -q` → **4 passed**, 0 skipped.
- `pytest tests/test_0710_v2_mockup_match_browser.py -q` → 180 passed, 3 failed (`overview-320/390`, `properties-320`: `.seg a.on` width app=83px vs mockup=89px). **Verified failing on unmodified base too** — sandbox font metrics, not this change.
- `pytest tests/test_host_*.py -q` → 326 passed, 1 failed (`test_host_flash_outcomes.py::test_browser_renders_saved_warning_as_sticky_amber`, toast visibility timeout). **Also fails on unmodified base** — pre-existing/environmental.
- `pytest tests/test_design_*.py tests/test_dev_ui*.py -q` → **150 passed**.
- `ruff check App/tests/test_0414_billing_banner_browser.py --select E9,F63,F7,F82,F401,F841` → All checks passed.
- `python3 scripts/context_lint.py` → OK; `python3 scripts/design_lint.py` → OK.

## Acceptance
- [x] 0414 browser test green at 390/1280 incl. new geometry/display assertions.
- [x] static_versions green, json committed.
- [x] Screenshots opened: 1280 = amber (`--warns`) boxed lane, text left, red pill "Zaplatit fakturu" right, no overlap; 768 same row layout; 390 = boxed lane, button full-width on its own row (phone tap pattern), no sideways scroll (asserted in test).
- [x] `test_layout_lint_browser.py` green; design-system checklist ticked in PR.

## Deviations
- The brief's `page.evaluate("getComputedStyle(...)")` snippet does not serialize a CSSStyleDeclaration; the test returns `{display, bg}` via an arrow function instead. No behavioural difference.
- Sandbox needed local Chromium system libs + fontconfig (`LD_LIBRARY_PATH=/tmp/chromelibs/...`, `FONTCONFIG_FILE=/tmp/fonts-local.conf` wrapping `tests/fonts.conf`); not repo changes.

## Questions
- None.

## Owner steps
- Watch CI on the PR; merge with `scripts/merge-pr-on-green.sh` when green; spot-check staging admin preview at 1280/390.
