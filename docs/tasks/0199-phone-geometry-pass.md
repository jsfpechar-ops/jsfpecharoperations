# 0199: Phone geometry pass on the stay page, Door lock tab and cleaning calendar

Status: done
Depends on: 0196-0198 | Base commit: 50a056d+ | Branch: claude/project-thread-xo8dql
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Josef finds the phone versions of these pages geometrically wrong in English and Czech. Fix the measured faults below so edges line up, rows have one height, and no label wraps inside a button.

## 2. Context

Rules: WCAG 2.2 AA (44x44 px targets on phone), no borderless controls, light mode. Every changed CSS file gets a new `?v=` key in every template that links it, then `.venv/bin/python tests/test_static_versions.py --write` from `App/`. Use existing tokens only. Phone = `@media (max-width:760px)`.

Faults seen at 360 and 390 px (screenshots: `/mnt/project-files/design-reset/checkpoint-6/mobile/`):

**Stay page** (`/reservations/<id>`, CSS `App/app/static/host-design0123.css`, 0196 phone block at the end):
- A. Next step panel (`.stay-command-panel`) content starts 44 px inside the card; other cards (Guests, Police reporting) start 17 px inside. Make the Next step panel content start at the same x as the "Hosté/Guests" heading (±1 px).
- B. Its actions squeeze three buttons into one row, so labels wrap ("Odeslat do UbyPortu" on 3 lines, "Upravit počet", "Vystavit fakturu" on 2). On phone: the FIRST child of `.stay-command-actions` takes the full row (`flex:1 1 100%`), the rest share the next row (`flex:1 1 0`), the ⋮ menu stays 44x44 at the row end; `flex-wrap:wrap`; all buttons 44 px tall, `white-space:nowrap`. Replace the existing 0196 phone rules for `.stay-command-actions` instead of stacking new overrides on them.
- C. Guests header (`#guests .ui-section-h .ui-form-actions`): on phone the two buttons share the row equally (`flex:1 1 0`), the group takes full width, 44 px tall.
- D. Stay settings: the inner "Save/Uložit" (expected guests) is full width but the bottom "Save/Uložit" is not. On phone make the bottom one full width too (find its selector inside `#stay-quick-edit`).

**Property Door lock tab** (`/apartments/<id>?view=settings&section=lock`, CSS `App/app/static/host.css`, near the 0195 rules at the end):
- E. The five settings chips (`.property-settings-nav`) wrap into a ragged 3-row block. Below the 860 px container width make it one row that scrolls horizontally (`flex-wrap:nowrap; overflow-x:auto;` chips `flex:0 0 auto`), staying inside the lane (no page overflow), like the stay page tab row.
- F. With no TTLock account there is a ~70 px empty gap between the "Optional…" intro and the "Digital door lock" panel. Make it at most 24 px at 360/390 (and keep <=30 px at 1280, see 0198). Find what makes the gap (hidden save bar margin, empty form group padding, grid gap) by measuring; fix only that.

**Cleaning calendar** (host `/cleaning`, shared `/cleaning/shared/<token>`, CSS `App/app/static/dashboard-calendar.css`):
- G. Host page: the calendar block ("Kalendář úklidů", selects, buttons) starts at x=20 while the page heading and "Přidat úklid" start at x=16. Align it to 16 (±1 px).
- H. Shared page: prev / Today / next are round pills, while the selects and segments next to them have 8 px corners. On phone (shared page, `.cleaning-page .dashboard-calendar`) give those three buttons the same 8 px radius and 44 px height the host page uses. Do not change the host page.

## 3. Files

| Path | Action |
|---|---|
| App/app/static/host-design0123.css | edit (A-D) |
| App/app/static/host.css | edit (E-F) |
| App/app/static/dashboard-calendar.css | edit (G-H) |
| App/app/templates/base.html, App/app/templates/_dashboard_calendar.html | `?v=` bumps (suffix `-0199`) |
| App/tests/static_versions.json | regenerate |

No template markup changes unless a selector truly cannot be reached; then stop and ask.

## 4. Steps

1. Read the end of each CSS file (`tail -40`) before editing.
2. Make A-H. Comment each block `/* 0199: ... */`.
3. Bump keys, regenerate the manifest.
4. Measure with Playwright (Chromium: `export UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium-1194/chrome-linux/chrome UBYHOST_REQUIRE_BROWSER=1`). Copy `App/tests/test_zz_mobile_capture_browser.py` (it already reuses the fixtures for all three pages) and add assertions for A-H at 360 and 390 in `en` and `cs`, including: no button whose text wraps (button height <= 46 px), no `document.documentElement.scrollWidth > innerWidth`. Save full-page screenshots over the same names in `/mnt/project-files/design-reset/checkpoint-6/mobile/` (`mkdir -p`, trailing slash). Also run once at 1280 to confirm desktop is unchanged for the stay page and Door lock tab.

## 5. Do not touch

Templates, Python, copy. No git commit/stash/checkout/reset/clean.

## 6. Commands

From `App/`: `.venv/bin/python -m pytest tests/test_static_versions.py tests/test_design_guardrails_browser.py tests/test_host_stay_detail_layout_browser.py tests/test_lock_navigation_browser.py tests/test_cleaning_browser.py -q --tb=line -rfs 2>&1 | grep -E "FAILED|passed|failed" | tail -8`

## 7. Acceptance

- [ ] A-H measured true at 360 and 390, en and cs; numbers in the report.
- [ ] Tests above pass, 0 skipped.

## 8. Stop and ask

If a fault needs markup changes, or a test outside the list fails, stop and report. Do not commit.

## 9. Report

[0199-report.md](0199-report.md)
