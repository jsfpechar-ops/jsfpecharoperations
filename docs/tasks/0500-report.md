# 0500 report: prefetch host pages on hover

Status: review

## Files changed
- `App/app/templates/base.html`: one `<script type="speculationrules">` added inside the existing `{% if show_nav %}` condition, next to the `shell.js` include. No `?v=` bump (no static file changed).
- `App/tests/test_navigation_prefetch.py` (new): 2 render tests plus 1 browser test.

## Rules JSON (rendered only when show_nav is true)
```
{"prefetch": [{"where": {"and": [{"href_matches": "/*"}, {"not": {"or": [{"selector_matches": "[data-no-prefetch], [target=_blank], [download]"}, {"href_matches": "/logout*"}, {"href_matches": "/lang*"}, {"href_matches": "/api/*"}, {"href_matches": "/admin/*"}, {"href_matches": "/*export*"}, {"href_matches": "/*.pdf*"}, {"href_matches": "/*/pdf*"}, {"href_matches": "/*.zip*"}]}}]}, "eagerness": "moderate"}]}
```

Exclusions: `[data-no-prefetch]`, `[target=_blank]`, `[download]`, `/logout*`, `/lang*`, `/api/*`, `/admin/*`, `/*export*`, `/*.pdf*`, `/*/pdf*`, `/*.zip*`.

## Checks
- Mutating GET routes (step 3 stop check): none that the shell links to. `/account/email/confirm` GET only peeks a token; the POST consumes it. `/smart-locks` GET redirects. `/logout`, `/language` and the other lang/logout forms are POST only.
- Shell templates (`_shell_sidebar.html`, `_shell_tabbar.html`): no download or action link that the path rules miss, so no `data-no-prefetch` was added.
- Browser test: sidebar link `/reservations` navigates, no CSP or speculation console errors. Not skipped.

## Commands
`cd App && PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers .venv/bin/python -m pytest tests/test_navigation_prefetch.py tests/test_design_shell.py tests/test_static_versions.py tests/test_privacy_first.py -q --tb=short -rs -x 2>&1 | tail -30`
```
..............                                                           [100%]
14 passed in 13.94s
```

`.venv/bin/python ../scripts/design_lint.py 2>&1 | tail -15`
```
design lint: OK
```

`python3 scripts/context_lint.py 2>&1 | tail -10` (warnings are pre-existing briefs naming shared files, not from this change)
```
WARN  docs/privacy/RETENTION.md is named by open briefs 0347-guide-import-fetch.md, 0350-leon-core.md; say which goes first
WARN  2 commit(s) touched App/ after the last status.md update. Orchestrator: update docs/context/status.md at review.
next free: task 0622 | migration 0034
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
