# 0705 report: v2 shell from the mockup

Status: review (not pushed; branch task/0705-v2-shell, local commits only)

## Files changed
- Created `App/app/static/app2.css` (mockup CSS, colours from tokens, phone top-bar rule, sidebar nav rules)
- Created `App/app/templates/_shell_v2.html` (mockup `aside.side` with real hrefs, t() labels, nav_badge, logout form)
- Edited `App/app/templates/base.html` (v2 branch only: head CSS, body class, `div.app` + `main.main`, shell include)
- Edited `App/app/host_i18n.py`, `App/app/host_vi_i18n.py` (`nav.property_count` keys)
- Edited `App/tests/static_versions.json` (`--write`)
- Created `App/tests/test_0705_v2_shell_browser.py`

## Commands (last lines)
- `.venv/bin/python -m pytest tests/test_0705_v2_shell_browser.py tests/test_static_versions.py tests/test_design_dashboard.py tests/test_privacy_first.py -q --tb=short -rs`: `14 passed in 11.26s` (0 skipped)
- `python3 scripts/design_lint.py`: `design lint: OK`
- `python3 scripts/context_lint.py`: `context lint: OK`
- `jinja2` parse of `_shell_v2.html`: parsed

## Acceptance (§7)
- Non-v2 pages: same CSS list and sidebar (tested on `/` with host_with_property).
- Tests pass, 0 skipped.

## Deviations
- `base.html` v2 branch adds `<div class="app">` around shell and main (mockup flex layout needs a parent); closed after `</main>`.
- v2 aside has `id="app-sidebar"` so existing scripts keep finding it.
- Added CSS classes not in the brief: `.side-nav`, `.side-bottom`, `.side-logout`, `button.nav`.
- Logout form has no CSRF field: the old sidebar has none either.
- Labels use `t()` keys, not the mockup's hard-coded Czech text. "Pomoc a Havel" is `nav.guide`.
- Phone rule hides `.search` only; `.org` stays visible.
- Route-level v2 test not possible yet (no v2 page). Test file has a TODO for 0706. Only Jinja parse covers `_shell_v2.html`.
- No page renders v2 yet, so no 390 px screenshot in this brief; 0706 owns it.
- i18n: en has base + `.one`; cs has base + `.one` + `.few`; vi has base only.

## Questions
- None.

## Owner steps left
- Push the branch and open the PR when the owner allows it (not pushed per instruction).
