# 0500: smoother page-to-page navigation (light version)
Status: todo
Depends on: none | Base commit: origin/main | Branch: task/0500-smooth-navigation-light
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens
## 1. Objective
Owner wants the host app to feel as effortless as Wolt (2026-11-01). He chose the light route first: no page-swap library yet. The cross-fade (`@view-transition`, rail and tab bar held still) and press states already exist in `host2.css`. The missing piece is speed: load the next host page before the tap by prefetching on hover/press (Chrome Speculation Rules). Browsers without support behave exactly as today.
## 2. Context
- `base.html:251` loads `shell.js`; CSP `script-src` has `'unsafe-inline'` (`main.py:179`), so an inline `<script type="speculationrules">` is allowed. Same origin only: no new outbound request to a third party (rule 2), say so in the PR.
- Only plain GET page links may be prefetched. Never prefetch: logout, language switch, export/PDF/ZIP/download links, `/api/`, `/admin/` links from the host shell, links with `data-no-prefetch`, `target=_blank`, any link with a query that mutates (grep routes that change data on GET; there should be none, stop and ask if you find one).
- Prefetch carries the user's cookies and is same-origin, so private pages are fetched only for a signed-in user; the rules block is rendered only inside the `{% if show_nav %}` shell, never on guest, auth or public pages.
## 3. Files
Edit `App/app/templates/base.html` (rules block next to the shell.js include; bump `?v=` of any static file you change). Create `App/tests/test_navigation_prefetch.py`. Edit `App/tests/static_versions.json` only through the repo's own update script if a static file changes. Add one line to `docs/context/decisions.md` only if the lint cap allows (else skip, it is not a dependency).
## 4. Steps
1. In `base.html`, inside the shell condition, add `<script type="speculationrules">` with one `prefetch` rule: `where` = `href_matches "/*"` and `not` of (selector `[data-no-prefetch], [target=_blank], [download]`, href_matches for `/logout*`, `/lang*`, `/api/*`, `/admin/*`, and `*export*`, `*.pdf`, `*.zip`; check real paths with grep in `App/app/routes`), `eagerness: "moderate"` (hover 200 ms or pointerdown).
2. Add `data-no-prefetch` to any link in the shell templates that is a download or action but cannot be matched by path (grep `_shell_sidebar.html`, `_shell_tabbar.html`).
3. Test file: render `/` as a signed-in host (use existing fixtures from `test_design_shell.py`) and assert the block is present, valid JSON, and contains the exclusions; render `/login` and a guest page and assert it is absent. One browser test (use an existing browser fixture): clicking a sidebar link still navigates, 0 skipped.
## 5. Do not touch
Routes, Python in `App/app/` beyond templates, `app.js`, copy, translations, wizard, any page content. No new dependency.
## 6. Commands
From `App/`: `.venv/bin/python -m pytest tests/test_navigation_prefetch.py tests/test_design_shell.py tests/test_static_versions.py tests/test_privacy_first.py -q --tb=short -x 2>&1 | tail -15`; `.venv/bin/python ../scripts/design_lint.py 2>&1 | tail -15`; `python3 ../scripts/context_lint.py 2>&1 | tail -10`.
## 7. Acceptance
All pass, 0 skipped. In the report, show the rendered rules JSON and the exclusion list. No visual change, so no screenshots needed.
## 8. Stop and ask
Stop if any GET route mutates data, if CSP blocks the block in the browser test, or if a test other than those named changes result.
## 9. Report
`docs/tasks/0500-report.md`: test and lint tails, `git diff --stat origin/main`, the rules JSON.
