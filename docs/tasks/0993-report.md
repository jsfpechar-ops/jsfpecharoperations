# 0993 report

Status: blocked

## Files changed (commits on claude/project-thread-d67hsx, not pushed)

- App/app/static/app2.css (steps 1, 2): h2.sec gap:8px; v2 impersonation bar styles; calendar legend and day-1 date styles. Deviation: `.impersonation-bar` background uses `var(--s)` because `--surface` is not defined in app2.css.
- App/app/templates/base.html (step 3): cache key `20261107-0993`.
- App/tests/static_versions.json (step 3, outside section 3): regenerated with `test_static_versions.py --write`, which the failing manifest test requires.
- App/app/needs_you.py + App/tests/test_needs_you_0240.py (step 4): no "guests not registered" line once date_to <= today; one test added.
- App/app/routes/admin.py (step 5): blocked placeholders read "Blocked", grey, full text in `title`.
- App/app/templates/dashboard.html (step 6): bar title, day-1 date hint, legend line.
- App/app/host_i18n.py (step 7): 4 keys in en and cs.

## Commands (last lines)

- `.venv/bin/python -m pytest tests/test_needs_you*.py -q` : `10 passed in 1.81s`
- `.venv/bin/python -m pytest tests/test_static_versions.py tests/test_*_i18n.py tests/test_no_em_dashes.py -q` : `35 passed, 1 warning`
- `python3 scripts/context_lint.py` : `context lint: OK`
- `UBYHOST_REQUIRE_BROWSER=1 ... pytest tests/test_needs_you*.py tests/test_host_geometry.py tests/test_layout_lint_browser.py -q -rs -x` : `1 failed, 12 passed`
  - FAILED test_every_host_page_passes_the_layout_lint: 4 findings, `text-overlap` between `span.l-ok "Reported"` (legend) and `a.ov-cal-link "Full calendar →"` on dashboard at 1024, 1280, 1440, 1920.

## Section 7 acceptance

- [x] Heading gap (CSS only, not screenshot-checked)
- [x] New test passes
- [ ] Preview banner at 390/768/1280: not screenshotted
- [ ] Blocked bars, tooltip, legend, day-1 hint: not screenshotted
- [ ] Layout lint zero findings: FAILED (4 findings, see above)
- [ ] Per-page 390/768/1280 observations: not done. Screenshots are in the scratchpad `shots/layout-lint/`, not yet opened.

## Deviations

- Created App/.venv and installed requirements.txt and requirements-dev.txt; installed playwright and chromium into the venv only (not committed).
- Screenshots directory is the session scratchpad, not /tmp/shots.
- Ran only needs_you, host_geometry and layout_lint browser tests. test_host_*.py and test_dashboard_calendar*.py were not run.
- Done: steps 1 to 7. Left: fix the legend/ov-cal-link overlap (brief §8 stop), then run the full §6 UX gate and screenshots.

## Questions

- The legend line `.cal-legend` (`ov-cal-block`) collides with the `ov-cal-more` "Full calendar" link on dashboard widths 1024 and up. The layout lint must be fixed, not silenced. The cause is not in section 3 (likely the `ov-cal-more` placement), so the brief author should decide the fix.

## Owner steps left

- None until the lint finding is resolved. Merge and deploy stay with the owner.
