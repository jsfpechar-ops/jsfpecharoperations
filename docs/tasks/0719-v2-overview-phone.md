# 0719: Overview on phone = the approved "Dnes" screen
Status: todo
Depends on: 0717, 0718 | Base commit: claude/project-thread-50hyv5 after 0717 and 0718 merge | Branch: task/0719-v2-overview-phone
Executor: Haiku 5.5 | Fits one session: 30 tool calls

## 1. Objective
Below 1024 px, `/` looks like the phone mockup's "Dnes" screen (`docs/design/mockup/ubyhost-phone-v1.html`, `<section data-s="dnes">`), using the shared phone classes from brief 0718. Desktop (>= 1024) stays as it is.

## 2. Context and decisions (orchestrator)
- Owner rule 16:57: match the mockup 1:1. Use the mockup's own markup structure and class names for the phone parts; the only allowed departures are data we do not have (the greeting uses the page title, since no first name is stored) and the AA colour overrides. List every departure in the report.
- Read the mockup's Dnes screen markup and the 0718 phone classes in app2.css first.
- Top: below 1024 px hide the head's "Přidat pobyt" `.btn` and show a `.top` row with a `.round` "+" link to the same href (aria-label = the button's text). Title stays the page title (we store no first name), styled by 0718's `.head h1` phone rule; date line as `.sub`.
- "Potřebuje vás": heading gets the `.badge` count. Each todo card on phone = mockup `.card.need`: `.h` row (icon box + bold title + small line) and a full-width button below; the first card's button is the coral `.btn`, the others `.btn line`. Prefer adjusting the existing todo markup so one markup serves both sizes (desktop keeps its look); add phone rules in app2.css.
- Month line: keep as `.quiet` (mockup has the class).
- The 14-day calendar grid is hidden below 1024 px; the "Dnes" heading gets a right-side link "Kalendář" → `/?cal_view=calendar` (mockup `h2.sec a`), shown only below 1024.
- "Dnes" list: below 1024 px show the today stays as the mockup's horizontal `.hs` cards (`.kind.in` Příjezd / `.kind.out` Odjezd, `.av` initial, `.nm` name, `.meta` property · nights · guests, status pill using the 0715 tone mapping), each card a link to the stay. Desktop keeps the table; the table is hidden below 1024. Render the cards from the same `today_rows` loop data (a second small loop is fine).
- If there is nothing today and nothing needs you, show the mockup's `.allgood` line (find the existing empty-state text key).
- Tests: in `App/tests/v2_mockup.py` extend overview `phone_selectors` with `.top .round`, `.head h1`, `.head .sub`, `h2.sec` (or the app's h2 if it carries the phone rule), `.card.need`, `.need .ic`, `.need b`, `.need small`, `.card.need .btn`, `.hs .card`, `.kind`, `.av`, `.nm`, `.meta`, `.hs .pill`; data-dependent ones go to `missing_ok` with a reason. Keep every existing test green (update dashboard tests only where they check the table at phone width).
- Left over from 0718 (orchestrator read the 0718 screenshots, 17:40):
  - Below 1024 px `main` has no side padding, so headings, the help link, the month line and the logout link sit at x≈0. Give `body.v2 .main` the phone mockup screen's side padding (read the mockup's screen padding, about 20 px) below 1024 px, and remove any phone `.card` side margins that were compensating, so cards line up with the headings as in the mockup.
  - `/menu` at 320: `.card.me` is 117 px tall against 108 px in the mockup because the fixture name wraps. Keep the name on one line with ellipsis (`white-space:nowrap; overflow:hidden; text-overflow:ellipsis`, `min-width:0` on its flex parent).
  - Overview at 768 compares phone-styled elements with the desktop mockup. Decision: below 1024 px the phone design is the design. At 768 the style test compares the page's `phone_selectors` against the phone mockup (styles only: colours, fonts, radii, paddings; no box widths, because the mockup frame is phone-sized) instead of the desktop selectors. Geometry checks stay at all six widths.
  - Other pages may add `.marks` etc. to their own `missing_ok`; keep the helper generic.
- Bump the app2.css key to `20261101-0719` and `--write` the manifest.

## 3. Files
`App/app/templates/dashboard.html`, `App/app/static/app2.css`, `App/app/templates/base.html` (key), `App/tests/static_versions.json`, `App/tests/v2_mockup.py`, `App/tests/test_0710_v2_mockup_match_browser.py`, `App/app/templates/menu.html` (name line only), dashboard tests only if needed, screenshots `docs/tasks/screenshots-0719/` (overview 320, 390, 768 and mockup dnes 390), report `docs/tasks/0719-report.md`.

## 4. Steps
1. Top row, badge, todo cards. Commit.
2. Calendar hide + link, `.hs` cards, allgood. Commit.
3. Test selectors, key, manifest, screenshots (Read them), commands. Commit + report.

## 5. Do not touch
`_shell_v2.html`, `app.js`, other pages.

## 6. Commands (from App/, `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers`)
`UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py tests/test_0709_v2_overview_shots_browser.py tests/test_a11y_guard_browser.py tests/test_design_guardrails_browser.py tests/test_dashboard_queue_copy.py tests/test_0520_overview_today.py tests/test_design_dashboard.py tests/test_0252_touch_sweep_browser.py tests/test_static_versions.py -q --tb=line -rs 2>&1 | tail -30` (0 skipped). Repo root: `python3 scripts/design_lint.py | tail -1; python3 scripts/context_lint.py | tail -1`.

## 7. Acceptance
All listed tests pass, 0 skipped; screenshots at 390 look like the mockup's Dnes screen.

## 8. Stop and ask
Stop if a todo card type has no clear phone button text.

## 9. Report
`docs/tasks/0719-report.md`: status, test tails, screenshots, deviations.
