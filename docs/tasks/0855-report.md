# 0855 report (executor: Haiku 5.5)

Status: review

## Files changed
- App/app/templates/submissions.html, invoices.html, stay_fees.html, housebook.html: removed `ph-hide` from the help `<details>` (phone now shows the ?).
- App/app/templates/housebook.html: removed the footer `<p class="stays-count">` line under the list.
- App/app/host_i18n.py, App/app/host_vi_i18n.py: deleted `housebook.filter_footer` (now unused).
- App/app/static/app2.css: help summary is a 44x44 transparent hit area (`position:relative;isolation:isolate`), the visible 32x32 #efefeb circle is its `::before` (centred, z-index -1); chevron removed (`::after{content:none}`).
- App/app/templates/base.html: cache key `20261102-0819c`.
- App/tests/static_versions.json: rewritten by `test_static_versions.py --write`.

## Measured (Playwright, rich-host fixture, final)
- 390 and 1280, all four pages: summary (hit area) 44x44, visible circle 32x32 via `::before`, the svg "?" 16x16 centred, summary centre equal to h1 centre (157 at 390, 123 at 1280), no chevron, no footer.

## Commands
1. `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py -k "invoices or housebook or submissions or stay_fees" tests/test_motion_browser.py tests/test_page_help_0277.py -q -rs --tb=short` gives `48 passed, 91 deselected`, 0 failed, 0 skipped.
2. `.venv/bin/python -m pytest tests/test_static_versions.py tests/test_design_lint.py tests/test_design_reports.py tests/test_host_i18n.py tests/test_stay_fee_send_panel.py -q --tb=short` gives `26 passed`, 0 failed, 0 skipped.

## Deviations
- App venv lacked runtime deps. Ran `pip install -r requirements.txt` (the repo's pinned file).
- `--write` refused under the unchanged key, so the key went `20261102-0855` to `0819b` to `0819c` while the design changed.
- Geometry conflict (32 px vs 44 px tap target) resolved by the orchestrator's option (a): 44x44 hit area, 32 px visible circle.
- A temporary measuring test was created and deleted again.

## Questions
- None.

## Owner steps left
- None. Not committed or pushed.
