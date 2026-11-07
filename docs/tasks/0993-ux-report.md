# 0993 report

Status: review

## Files changed (commits on claude/project-thread-d67hsx, not pushed)

- App/app/static/app2.css (steps 1, 2): h2.sec gap:8px; v2 impersonation bar styles; calendar legend and day-1 date styles. Deviation: `.impersonation-bar` background uses `var(--s)` because `--surface` is not defined in app2.css.
- App/app/static/app2.css (fix): `.ov-cal-more{margin:0 0 28px}` (was -16px top; only dashboard.html uses it); `.cal-legend{margin:8px 0 6px}`.
- App/app/templates/base.html (step 3, bumped again for fix): cache key `20261107-0993b`.
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
- [x] Preview banner at 390/768/1280: seen in all three screenshots
- [ ] Blocked bars, tooltip, legend, day-1 hint: legend seen at 1280; no "Blocked" pill, tooltip or day-1 hint visible in the screenshots, so not verified
- [x] Layout lint zero findings: `test_layout_lint_browser.py` + `test_host_geometry.py` pass after the fix (6 passed, 0 skipped)
- [x] Per-page 390/768/1280 observations: written below (screenshots in /tmp/shots/layout-lint/)

## Per-width observations (dashboard)

- 390: banner "Nothing is being reported to the police" sits at the top with its select below; heading "2 things need you today" wraps to two lines; calendar is below the fold, so the legend and "Full calendar" link are not in this shot.
- 768: banner visible at top; heading "2 things need you today" on one line; calendar below the fold, not in this shot.
- 1280: banner visible with full text; "What needs you 2" heading; calendar legend "Reported / Needs you / Blocked or waiting" sits on its own line with "Full calendar →" directly below it, no overlap; no "Blocked" pill is visible in the calendar rows.

## Deviations

- Cache key is `20261107-0993b`, not `0993`, so the browser loads the fixed CSS; the manifest was regenerated with `python tests/test_static_versions.py --write` (pytest does not accept `--write`).
- Commit attribution uses the Haiku 5.5 Co-Authored-By line (the executor's model), not the Sonnet line in the brief.
- Created App/.venv and installed requirements.txt and requirements-dev.txt; installed playwright and chromium into the venv only (not committed).
- Screenshots directory is the session scratchpad, not /tmp/shots.
- Ran only needs_you, host_geometry and layout_lint browser tests. test_host_*.py and test_dashboard_calendar*.py were not run.
- Done: steps 1 to 7, plus the overlap fix (legend and "Full calendar" link).

## Questions

- None open. The overlap is fixed by the margin change above; the browser gate passed.

## Owner steps left

- Review and merge via `scripts/merge-pr-on-green.sh`. Deploy stays with the owner.
