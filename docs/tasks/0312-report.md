# 0312 report: Havel page /havel

Status: blocked

Done: steps 1 to 7. Step 8: test file written (committed as WIP), run blocked. Left: step 8 run, step 9 (browser guard, screenshots at 390 and 1280), report review.

## Files changed
- App/app/host_i18n.py: havel.* copy en and cs (step 1-2).
- App/app/routes/havel.py (new): route as in brief step 4.
- App/app/main.py: import `havel as havel_routes`, `include_router(havel_routes.router)` after the cleaning include.
- App/app/templates/havel.html, _havel_thread.html, _havel_form.html (new); _icons.html: `message-circle-question`.
- App/app/static/host2.css (appended), App/app/templates/base.html (cache key), App/tests/static_versions.json (regenerated, 36 files).
- docs/design/catalog.json (classes, enforced_templates), docs/design/pages/havel.md (new), App/tests/test_design_guardrails_browser.py (`"havel": "/havel"`).
- App/tests/test_havel_page.py (new, WIP).

## Commands (last lines)
- Step 4 import: `from app.main import app` loads; `/havel` in OpenAPI paths: `['/havel']`.
- Step 5 icon: `grep -c message-circle-question` = 1.
- Step 6 cache key: `grep -c 'host2.css?v=20261025-0312"'` = 1; `static_versions --write`: `wrote .../static_versions.json (36 files)`.
- Step 7: `design lint: OK`. Catalog 236 classes.
- Step 8 run: `1 failed` (see below).

## Deviations
- Step 4 check: `app.routes` items have no `.path` (`_IncludedRouter`), so the brief's one-liner errors. Used `app.openapi()` paths instead.
- Step 7 script saved in the session scratchpad, not `/tmp/claude-0/s/`.
- Step 8 test file: dropped the unused `rate_limit` import after the brief's simplification.
- Step 8 STOPPED: `AttributeError: 'State' object has no attribute 'lang'` at app/routes/havel.py line 35 (`_t` in `havel_page`). `request.state.lang` is set only inside `render()` (app/app/templating.py line 574), which runs after the route's `_t` calls. Brief §8 says ask.
- Not run: tests/test_havel_engine.py, tests/test_host_i18n.py (3 known pre-existing failures), test_no_em_dashes.py, design guardrails and a11y browser tests, screenshots.

## Questions
1. How should the route get the language before `render()`? Option A: `host_i18n.resolve_language(request, default="en")` (the same resolver `render()` uses) set on `request.state.lang` at the top of each handler. Option B: `normalise_language(request.query_params.get("lang"))`. Recommend A.
2. Confirm the 3 pre-existing test_host_i18n failures (no such table: apartment when the file runs alone) are accepted.

## Owner steps left
None until steps 8 to 9 are done.
