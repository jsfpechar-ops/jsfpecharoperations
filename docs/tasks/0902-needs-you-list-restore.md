# 0902: Restore the old "What needs you" list on the dashboard

Status: review
Depends on: none | Base commit: 10091f2 | Branch: the current checkout (do not switch or create branches) | Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Owner (Josef) dislikes the two-column "What needs you" cards (`.todo` grid of `.needs-you-card-item`): with 3 items one card sits alone, and phone hides all but 2. Bring back the pre-redesign list: ONE full-width row per item, count badge in the heading, first 5 rows visible, the rest behind one "N more" toggle. Same on phone, tablet, desktop. Works for 1, 2, 5, 20 items.

## 2. Context

- Old markup: `git show 273026f^:App/app/templates/dashboard.html | sed -n 63,115p` (macro `needs_you_line` and `<section class="needs-you">`). Old CSS: `App/app/static/workflow.css` lines 68 to 128 (still loaded, classes `.needs-you`, `.needs-you-list`, `.needs-you-item`, `.needs-you-copy`, `.needs-you-actions`, `.needs-you-more`).
- Current markup: `App/app/templates/dashboard.html` macro `overview_card` (lines 16-44) and section `#needs-action` (lines 81-96).
- **Do not bring back the stretched link**: `workflow.css` lines 120-123 make `[data-needs-you-go]::before` cover the whole row. PR #756 (0901) removed that under `body.v2` (see `app2.css` near the `0901` comment and `App/tests/test_0901_hit_area_browser.py`). Only the button (and the X) may be clickable; no `::before`/`::after` overlay on the row. The "Send the report" button must stay clickable at 390/768/1280.
- Owner override of executor.md: **do not commit, push or open a PR.** Leave changes in the working tree; the orchestrator commits.
- Keep every data attribute: `id="needs-action"`, `data-needs-you-card`, `data-dashboard-refresh="stats"`, `data-needs-you="{{ line.kind }}"`, `data-needs-you-stay`, `data-notification`, `data-needs-you-go`, `data-notification-dismiss`, `data-paste-check`, the dismiss form `action="/alerts/{{ id }}/dismiss"` and its `aria-label`. Keep the phone `h1` headline and `ph-hide`/`cal-hide` behaviour on the section.
- Look: light mode, Manrope, our card style (white, 1px `var(--line)` border, radius like `.card`), left edge 4 px tone colour (red / amber / neutral), the `!` / `i` tone icon square from `overview_card` is optional; keep the row calm and tidy. 12 px minimum gap between neighbours. First row button primary (`btn sm`), others `btn sm ghost line`. Dismiss X sits in the row's right corner (reuse the existing `body.v2 .needs-you-dismiss` styling at app2.css ~2200, retarget its selectors to the new row class). Rows stack into one column; button below text on phone (full width, min-height 44), to the right on 768+.
- Copy: no new strings. Reuse `needs_you.title`, `needs_you.more` (`tp('needs_you.more', n)`), `needs_you.calm`.

## 3. Files

| Path | Action |
|---|---|
| `App/app/templates/dashboard.html` | edit: replace `overview_card` and the `#needs-action` section |
| `App/app/static/app2.css` | edit: append a `/* 0902 */` block; delete the 0722 phone-hide rules (3 lines at ~897-899, comment `0722`) and the other `.needs-you-card-item` / `.todo` rules that are now dead (grep `needs-you-card-item`, remove only those) |
| `App/app/templates/base.html` | edit line 21, app2.css cache key |
| `App/tests/static_versions.json` | regenerate: `cd App && .venv/bin/python tests/test_static_versions.py --write`, never by hand |
| `docs/design/catalog.json` | add any new class (CI `design_lint` fails otherwise) |
| tests named by `grep -rln "needs-you-card-item\|ny-sum\|overview_card" App/tests` | update only assertions of the old structure |
| `docs/tasks/screenshots-0902/` | 9 PNGs (3 widths x 1, 2, 5 items) |

## 4. Steps

1. `grep -n "needs-you-card-item\|ny-phone-only\|ny-sum" -r App/app App/tests docs/design | cut -c1-160 | head -40` to see everything that touches the old structure.
2. dashboard.html: delete `overview_card`. Add macro `ny_row(line, first=False)` producing `<li class="needs-you-item" ...>` (old `needs_you_line` shape: `.needs-you-copy` with `<strong>` subject + `<span>` text, paste-check `<details>`, `.needs-you-actions` with the button then the dismiss form). Section: `<h2 id="needs-you-title" class="sec ph-hide">` title plus `<span class="ui-badge ui-badge-action" data-tone="...">N</span>` when lines exist; `<ul class="needs-you-list">` with `ny_lines[:5]`; if more than 5 a `<details class="needs-you-more"><summary>{{ tp('needs_you.more', ny_lines | length - 5) }}</summary><ul class="needs-you-list">` rest `</ul></details>`; else the calm card as today.
3. app2.css: style `body.v2 #needs-action .needs-you-list` (grid, gap 12), `.needs-you-item` (white card, left tone border via `[data-tone]`, padding 16, relative, `padding-right:56px` when it has a dismiss), text column `min-width:0` with `overflow-wrap:anywhere`. No overlay pseudo-elements.
4. Bump the app2.css key in base.html line 21, then run `static_versions.py --write`.
5. Tests: `cd App && UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_needs_you_dashboard_0241.py tests/test_needs_you_0240.py tests/test_0375_needs_you_and_open.py tests/test_dashboard_phone_browser.py tests/test_0765_phone_today_window_browser.py tests/test_0901_hit_area_browser.py tests/test_design_dashboard.py tests/test_design_no_bang.py -q --tb=short -x 2>&1 | tail -30`. Update only old-structure assertions (counts of cards, 2-card phone limit, `.todo`). Never skip or weaken a geometry check.
6. Screenshots: seed a host with 1, 2 and 6 needs-you lines (reuse the seeding of `test_dashboard_phone_browser.py`), Chromium screenshots at 390, 768, 1280 into `docs/tasks/screenshots-0902/` named `ny-{1,2,6}-{390,768,1280}.png`. Open each and say in the report what you saw.
7. Run `cd App && UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_layout_lint_browser.py -q --tb=short 2>&1 | tail -30` and report the result.

## 5. Do not touch

Guest pages, `_host_alerts.html`, `needs_you.py`, the #756 hit-area rules.

## 6. Commands

See step 5 and step 7 above.

## 7. Acceptance

One full-width row per line, 5 rows then one "N more" toggle, same on 390/768/1280, lint green, 0 skipped.

## 8. Stop and ask

If a test needs a weakened geometry check, stop and report.

## 9. Report

Write `docs/tasks/0902-report.md`: files changed, test commands with pass counts and 0 skipped, lint result, one line per screenshot of what you saw, anything you could not finish.
