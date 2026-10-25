# 0391: every "Open" button actually opens

Status: todo
Branch: claude/project-thread-by10nz (already checked out; commit here)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Owner (Josef, 2026-10-25): "open button on stay dont work when i click it then i click pill and its alright, so check all open buttons and fix it".

Cause (found by the orchestrator): `row_open()` in `App/app/templates/_components.html` renders a `<span class="row-open">`, not a link. It always sits inside `td.row-actions`. The row click handler in `App/app/static/app.js` (`initClickableRows`, the `event.target.closest("a, button, ... .row-actions, .dashboard-row-actions")` line) ignores every click inside `.row-actions`, so a click on Open does nothing. A second dead Open: the static "Guest links" card in `App/app/templates/_property_overview.html` is a `div` whose `open_pill` is a span.

Fix: Open is a real link to the same place the row opens. No look change: Open keeps the plain bordered style (MASTER 4, `ui-btn-open`/`.row-open`), same size, same position on desktop and on phone cards.

## 2. Steps

1. `_components.html`: change the macro to `row_open(href)` rendering
   `<a class="row-open" href="{{ href }}" tabindex="-1" aria-hidden="true"><span class="row-open-text">{{ t('common.open') }}</span></a>`.
   (The row or its `row-primary-link` is already the keyboard and screen-reader target, so the duplicate stays out of the tab order.) Keep the 0252 comment, update it in one line.
2. Pass the row's own target to every caller. Use the exact URL of the row's `data-href` (or its `row-primary-link` href) in the same template. Callers: `reservations.html`, `reservation_detail.html`, `apartments.html` (2), `submission_detail.html`, `submissions.html`, `entities.html`, `settings_archived.html` (3), `housebook.html`, `invoices.html`, `stay_fees.html`. `grep -rn "row_open()" App/app/templates` must return nothing when done. If a row has no `data-href`, stop and report it rather than guess.
3. `_property_overview.html`: the Guest links card. Make its `open_pill` a link to the same href as its `host-property-card-link` (`{{ base_url }}?view=settings&amp;section=guests#communication`), class `host-property-card-open`, `tabindex="-1" aria-hidden="true"`. Do not touch the other cards (they are already `<a>`).
4. CSS: an `<a>` must look exactly like the old span. In the existing `host2.css` rule that styles `.host-workspace .row-open` (around line 818) add `text-decoration: none; color: var(--ink);` and cover `:visited`/`:hover` text-decoration. No new hover rule: hover already lives in the 0284 block. Do not touch radio/option card rules (another branch changes them).
5. Bump cache keys in `App/app/templates/base.html`: `host2.css` to `?v=20261025-0391` (any other file you change too).
6. New test `App/tests/test_0391_open_buttons_click_browser.py`, modelled on `tests/test_0385_phone_card_open_browser.py` (same `_client()` with `demo.seed`, same fixtures). Parametrize widths 390 and 1280. For each page `/reservations?range=all`, `/apartments`, `/entities`, `/invoices`, `/stay-fees`, `/submissions`, `/housebook`, `/cleaning/properties`, and the first property overview (follow the first `/apartments` row link): find the first visible `.row-open` (or `.host-property-card-open` on the overview, the Guest links one), read its `href`, `click()` it, `page.wait_for_url` to that href, assert the URL changed. Skip a page only if it has no Open with demo data, and print which; at least 6 pages must be clicked. Use arrow functions in `wait_for_function`; call `settle_motion(page)` after `goto`.
7. Update `docs/design/MASTER.md` section that names `row_open` (grep it): one line saying Open is a real link to the row's target.

## 3. Tests (from App/)

`.venv/bin/python -m pytest tests/test_0391_open_buttons_click_browser.py tests/test_0291_open_buttons.py tests/test_0375_needs_you_and_open.py tests/test_0385_phone_card_open_browser.py tests/test_0252_touch_sweep_browser.py tests/test_design_guardrails_browser.py tests/test_host_geometry.py -q --tb=short -x 2>&1 | tail -30` with `UBYHOST_REQUIRE_BROWSER=1`. 0 skipped. Then `git checkout -- ../docs/tasks/*evidence* ../docs/tasks/screenshots-0*` if tests rewrote PNGs. From the repo root: `python3 scripts/context_lint.py`.

## 4. Report

`docs/tasks/0391-report.md`: files changed, test output tail, any row that had no target. Commit with a clear message. Do not push.

## 5. Continuation (session 2, after the cap)

Steps 1 to 5 are committed and reviewed. Do only this:

1. `App/tests/test_0391_open_buttons_click_browser.py`: demo data has NO rows on /entities, /invoices, /stay-fees, /submissions, /cleaning/properties (checked by the orchestrator), so drop them from the browser test. New list, every one REQUIRED (no skipping; fail if no visible Open): `/reservations?range=all`, `/apartments`, `/housebook`, the first property overview (as now), and the first stay detail (follow the first `/reservations?range=all` row's `a.row-primary-link`; its guests table has a row Open). Click with a real pointer: `locator.click(force=True)` instead of `dispatch_event`, so a covering overlay that sends the click elsewhere still has to reach the same href. Remove the "at least 6" rule; keep widths 390 and 1280.
2. New non-browser test in the same file: for every template in `App/app/templates` (glob `**/*.html`), each `row_open(` call has a non-empty argument (regex `row_open\(\s*\)` finds nothing), and rendering the macro gives `<a class="row-open" href=`. Also assert no `class="row-open"` `<span` remains in templates.
3. Brief step 7 (MASTER line), then the brief §3 test list, lint, `docs/tasks/0391-report.md`, commit. Do not push.
