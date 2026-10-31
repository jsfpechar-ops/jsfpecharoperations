# 0454 report

Status: review

## Files changed

- `App/app/templates/_shell_sidebar.html`: admin-only localized landmark label.
- `App/app/static/host.css` and `App/app/templates/base.html`: scoped action wrapping and cache-key bump.
- `App/tests/test_host_account_navigation.py`, `App/tests/test_design_guardrails_browser.py`, `App/tests/static_versions.json`.
- `docs/tasks/0454-host-ux-improvement.md` and the two screenshots below.

## Checks

- `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_host_account_navigation.py tests/test_design_shell.py tests/test_design_guardrails_browser.py tests/test_host_geometry.py tests/test_static_versions.py -q -rs --tb=short -x 2>&1 | tail -30` — `36 passed in 26.31s`, 0 skipped.
- Entity width/language regression: passed at 390, 820, 1024, 1180 and 1280 px in en/cs/vi.
- `.venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -30` — wrote `App/tests/static_versions.json` (39 files).
- `git diff --check 2>&1 | tail -30` — no output, exit 0.
- Baseline: `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_design_guardrails_browser.py::test_every_host_page_passes_the_layout_guard -q -rs --tb=short -x 2>&1 | tail -30` — reproduced 4 findings at unmodified HEAD. After the scoped fix, the complete focused command above passes.
- Baseline HEAD reproduced the original guardrail failure: 4 operator-route findings, panel scrollWidth 978 px vs clientWidth 976 px at 1280 px. Scoped wrapping fix removes them.

## Screenshots

- `docs/tasks/0454-admin-settings-390.png` — 390 × 5681.
- `docs/tasks/0454-entities-390.png` — 390 × 1969.

## Acceptance and deviations

- Host landmark stays Guide; admin landmark includes Admin only when that link is rendered.
- Operator controls wrap between links; no padding, touch target, button label or phone More change.
- No component changed, so the MASTER component catalog was not updated.
- No unresolved questions or owner steps. No commit, push, merge or deploy.
