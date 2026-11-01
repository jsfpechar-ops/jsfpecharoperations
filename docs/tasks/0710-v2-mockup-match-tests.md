# 0710: shared mockup-match and geometry tests for every v2 page, all screen sizes
Status: todo
Depends on: 0709 | Base commit: claude/project-thread-50hyv5 | Branch: task/0710-v2-match-tests
Executor: Haiku 5.5 | Fits one session: 30 tool calls

## 1. Objective
One shared browser test that every redesigned (v2) page uses. For each registered page it (A) compares the app's computed styles with the approved mockup's, and (B) checks layout geometry at 320, 390, 768, 1024, 1280 and 1440 px. Overview (`/`) is the first registered page. This brief only builds the tests and reports what fails; fixes are brief 0711.

## 2. Context
- Owner, 2026-11-01 15:37: "Do rigorous geometry and ux ui design tests for all sessions"; 15:38: "phone tablet everything".
- The approved mockup is committed at `docs/design/mockup/ubyhost-redesign-v2.html` (names replaced, no web fonts). Its views are `<section class="view" data-v="KEY">`; only one has class `on`. To show a view in the test: `page.evaluate("k => document.querySelectorAll('.view').forEach(s => s.classList.toggle('on', s.dataset.v === k))", key)`. Open it with `page.goto(Path(...).resolve().as_uri())`. Block every non-file request with `page.route("**/*", lambda r: r.abort() if not r.request.url.startswith("file:") else r.continue_())`.
- v2 app pages use the mockup's own class names (`App/app/static/app2.css` is the mockup CSS; `App/app/templates/_shell_v2.html` is its sidebar). So the same selector finds the same element in both.
- Signed-in browser setup, demo data and Playwright launch: copy the fixtures from `App/tests/test_0709_v2_overview_shots_browser.py` (do not import from it). Use the existing `UBYHOST_REQUIRE_BROWSER` gate the same way that file does.

## 3. Files
- New `App/tests/v2_mockup.py` (helper, no tests in it):
  - `MOCKUP = Path(__file__).resolve().parents[2] / "docs/design/mockup/ubyhost-redesign-v2.html"`
  - `WIDTHS = (320, 390, 768, 1024, 1280, 1440)`; `DESKTOP = 1024` (box-layout checks only at widths >= DESKTOP; the phone mockup is not approved yet).
  - `STYLE_PROPS = ("font-size", "font-weight", "color", "background-color", "border-top-left-radius", "padding-top", "padding-right", "padding-bottom", "padding-left", "border-top-width", "border-bottom-color", "letter-spacing")`
  - `COLOR_OVERRIDES = {"rgb(212, 71, 47)": "rgb(208, 69, 45)", "rgb(138, 138, 132)": "rgb(107, 107, 101)"}` with the comment `# accessibility: mockup coral and --ink3 fail WCAG AA; app uses darker shades (2026-11-01)`. Before comparing, map the mockup value through this dict. Brief 0711 also changes nav.on text colour; leave that failing here.
  - `PAGES`: a list of dicts `{"name": "overview", "path": "/", "view": "today", "selectors": [...], "missing_ok": {}}`. Overview selectors: `.side`, `.side .nav`, `.side .nav.on`, `.head h1`, `.head .sub`, `.head .btn`, `main h2`, `.todo .card`, `.todo .ic`, `.todo .t`, `.todo p`, `.quiet`, `.card.cal`, `.cal .cd`, `.cal .cn`, `.cal .bar`, `main table th`, `main table td`, `main td small`, `main .pill`. `missing_ok` maps a selector to the reason it may be absent in the app (empty for overview).
  - `computed(page, selector, props)` returns a dict for the first visible match or `None`.
  - `geometry_findings(page, width)` runs ONE `page.evaluate` script and returns a list of strings, one per problem:
    1. horizontal page scroll: `document.documentElement.scrollWidth > innerWidth`;
    2. any visible element inside `main` whose right edge is past its nearest `.card` ancestor's right edge by more than 1 px (skip elements inside an `overflow-x:auto` container);
    3. overlapping text: inside each `.head`, each `.todo .card`, each `tr`, any two visible leaf text elements whose boxes intersect by more than 2 px;
    4. tap targets: visible `a, button, summary, [role=button], input, select` in the page smaller than 44x44 px when width < 1024, or smaller than 24x24 px otherwise (inline links inside a sentence `p` are exempt);
    5. text smaller than 12 px;
    6. not exactly one `h1`;
    7. width >= 1024: `.side` visible and 220 px wide (±1); width < 768: `.side` is a top bar no taller than 72 px;
    8. `.todo`: two columns at width >= 1024, one column at width < 768 (compare the `left` of the first two cards);
    9. open the last table row's menu (`main tr:last-child details summary`, click it if present), then its menu box must be inside the viewport; close it again.
- New `App/tests/test_0710_v2_mockup_match_browser.py`:
  - `test_v2_page_matches_mockup_styles[page-width]` parametrised over `PAGES` x `WIDTHS`: for every selector, compare `computed()` in the app with the mockup at the same viewport. Numbers ±1 px, colours exact after `COLOR_OVERRIDES`. A selector missing in the app fails unless in `missing_ok`. Collect all differences and assert once with the full list, formatted `selector prop: app=… mockup=…`.
  - `test_v2_page_geometry[page-width]`: `assert not geometry_findings(...)`, full list in the message.
  - `test_v2_screenshots`: only when `UBYHOST_SHOTS_V2=1`; for each page and width save `docs/tasks/screenshots-0710/<name>-<width>.png` (full page) and `docs/tasks/screenshots-0710/mockup-<view>-<width>.png`.
- Test-map: add one row in `docs/context/test-map.md` "v2 pages (any page with `{% set v2 = true %}`) | `tests/test_0710_v2_mockup_match_browser.py`", next to the existing browser rows.
- Report `docs/tasks/0710-v2-mockup-match-report.md`.

## 4. Steps
1. Read the 0709 shots test, `app2.css` (first 40 lines) and `_shell_v2.html`. Write `v2_mockup.py`. Commit `0710 step 1: v2 mockup helper`.
2. Write the test file. Run it (command below). It is expected to FAIL on some items; that is the point. Do not change app code, CSS or templates. Commit `0710 step 2: mockup-match and geometry tests`.
3. Test-map row. Run `UBYHOST_SHOTS_V2=1` once and Read the 390, 768 and 1280 PNGs of the app. Commit the screenshots.
4. Report: every failing item grouped by width, the exact finding text, and for each one whether it is (a) a real app difference to fix in 0711, or (b) a test bug you fixed. Commit.

## 5. Do not touch
`App/app/**` (no app, CSS or template edits), other tests, the mockup file.

## 6. Commands (from App/, `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers`)
`UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py -q --tb=line -rs 2>&1 | tail -40` (0 skipped required). Repo root: `python3 scripts/context_lint.py 2>&1 | tail -2`.

## 7. Acceptance
Both tests run for all 6 widths with 0 skipped. The report lists every remaining finding. No file outside section 3 changed (`git diff --stat claude/project-thread-50hyv5`).

## 8. Stop and ask
Stop if a selector matches nothing in the mockup's `today` view (a typo in this brief), or if a check gives more than 200 findings at one width (the check is probably wrong; report a sample of 10).

## 9. Report
`docs/tasks/0710-v2-mockup-match-report.md`: status, test tails, every finding by width marked fix-in-0711 or test-bug-fixed, screenshots, deviations.
