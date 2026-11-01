# 0495 report: redesign step 1 (shell)
Status: blocked

## Files
Added: App/app/static/fonts/Manrope-latin.woff2, Manrope-latin-ext.woff2, Manrope-vietnamese.woff2, LICENSE-Manrope.txt.
Edited: App/app/static/tokens.css (font-sans, 3 Manrope @font-face), App/app/static/host2.css (topbar rules removed, chip fill, title underline, row hover), App/app/templates/base.html (topbar include removed, latin preload, css versions), App/tests/test_design_shell.py, App/tests/test_host_feedback_browser.py (comment), docs/design/MASTER.md, docs/design/catalog.json, docs/design/pages/havel.md.
Deleted: App/app/templates/_shell_topbar.html.
Also in this commit: this report.

## Checks
- Glyph check (fontTools, throwaway venv): CZ and VI letters all present in the three subsets.
- pytest test_design_shell.py test_design_tokens.py test_privacy_first.py: 11 passed.
- design_lint.py: OK (after one fix: a bare 2px radius became var(--radius-pill)).
- context_lint.py: OK.
- Browser tests NOT RUN: test_host_geometry.py, test_host_feedback_browser.py, test_design_guardrails_browser.py skip (import playwright fails in App/.venv and in system python3; python3 has no pytest). 0 skipped is not met.

## Deviations
- Preload and tokens.css version bumped (tokens.css?v=20261101-0495) so cached CSS does not hide the font change.
- Phone main top spacing: no change needed, the existing phone rule for .wrap.with-sidebar already has padding-top space-6.
- Active nav coral (accent-soft, accent-ink, accent icon) already existed in host2.css; not changed.

## Not done
- Screenshots (390 and 1280 for / and /reservations, Vietnamese page): not produced.
- Browser tests: see above.

## Owner steps left
- Install Playwright for Python in App/.venv (or run the three browser tests in CI), confirm 0 skipped.
- Screenshots and a second look at the coral budget (MASTER 4 budget unchanged, not measured).

## Orchestrator follow-up (browser tests and screenshots)
Playwright 1.63.0 matches the installed Chromium. `test_host_geometry.py test_host_feedback_browser.py test_design_guardrails_browser.py`: 14 passed, 0 skipped. Title underline selector fixed to `.ui-ph h1::after` (the first selector matched nothing). Screenshots in `docs/tasks/screenshots-0495/` (dashboard, stays, properties in Vietnamese; 1280 and 390 px).
