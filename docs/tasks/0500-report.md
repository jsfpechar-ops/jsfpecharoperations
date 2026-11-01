# 0500 report: prefetch host pages on hover

Status: review

## Files changed
- `App/app/templates/base.html`: one `<script type="speculationrules">` added inside the existing `{% if show_nav %}` condition, next to the `shell.js` include. No `?v=` bump (no static file changed).
- `App/tests/test_navigation_prefetch.py` (new): 2 HTML tests (rules present with exclusions on the signed-in shell; absent on /login).
- `App/tests/test_navigation_prefetch_browser.py` (new): 1 real-Chromium test (sidebar link to /reservations still navigates, no CSP or speculation console errors). Uses the feedback browser pattern (UBYHOST_REQUIRE_BROWSER, chromium_launch_kwargs).

## Rules JSON (rendered only when show_nav is true)
```
{"prefetch": [{"where": {"and": [{"href_matches": "/*"}, {"not": {"or": [{"selector_matches": "[data-no-prefetch], [target=_blank], [download]"}, {"href_matches": "/logout*"}, {"href_matches": "/lang*"}, {"href_matches": "/api/*"}, {"href_matches": "/admin/*"}, {"href_matches": "/*export*"}, {"href_matches": "/*.pdf*"}, {"href_matches": "/*/pdf*"}, {"href_matches": "/*.zip*"}]}}]}, "eagerness": "moderate"}]}
```

Exclusions: `[data-no-prefetch]`, `[target=_blank]`, `[download]`, `/logout*`, `/lang*`, `/api/*`, `/admin/*`, `/*export*`, `/*.pdf*`, `/*/pdf*`, `/*.zip*`.

## Checks
- Mutating GET routes (step 3 stop check): none that the shell links to. `/account/email/confirm` GET only peeks a token; the POST consumes it. `/smart-locks` GET redirects. `/logout`, `/language` and the other lang/logout forms are POST only.
- Shell templates (`_shell_sidebar.html`, `_shell_tabbar.html`): no download or action link that the path rules miss, so no `data-no-prefetch` was added.
- Browser test: sidebar link `/reservations` navigates, no CSP or speculation console errors. Not skipped (run with UBYHOST_REQUIRE_BROWSER=1).

## Commands
`cd App && PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_navigation_prefetch.py tests/test_navigation_prefetch_browser.py tests/test_design_shell.py tests/test_static_versions.py -q --tb=short -rs -x 2>&1 | tail -30`
```
.........                                                                [100%]
9 passed in 6.38s
```

`.venv/bin/python ../scripts/design_lint.py 2>&1 | tail -15`
```
design lint: OK
```

`python3 scripts/context_lint.py 2>&1 | tail -10` (warnings are pre-existing briefs naming shared files, not from this change)
```
context lint: OK
```

## Deviations
- Added `/*/pdf*` to the exclusions. The brief's `*.pdf` does not cover `/stay-fees/{id}/pdf`.
- `/lang*` is kept as the brief says. The real route is `/language`, which is POST only.
- Guest-page check: only `/login` is asserted to be absent. No guest route fixture was used.
- The decisions.md line was skipped (not a dependency).
- Not pushed, no PR opened (the launch message said do not push).

## Questions
- None blocking.

## Owner steps left
- Review the branch `task/0500-smooth-navigation-light`, then merge with `scripts/merge-pr-on-green.sh` once a PR is opened. Push and PR were not done in this session.
