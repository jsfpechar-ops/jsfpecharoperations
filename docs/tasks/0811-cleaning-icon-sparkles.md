# 0811: One cleaning icon everywhere: Lucide `sparkles`

Status: review
Depends on: none | Branch: claude/project-thread-0p5l4e (already checked out)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Owner decision (Josef, 2 Nov 2026, 12:34): the cleaning (Úklid) icon is ugly and does not read as cleaning. Use Lucide `sparkles` everywhere. Today there are two icons: a hand-drawn broom inline in the v2 desktop sidebar and Lucide `brush-cleaning` in the phone Menu row, the old shell and the cleaning share promo. After this task both become `sparkles`, and `brush-cleaning` is gone.

## 2. Context

The icon markup to use (Lucide `sparkles`), referred to below as SPARKLES:

```
<path d="M9.937 15.5A2 2 0 0 0 8.5 14.063l-6.135-1.582a.5.5 0 0 1 0-.962L8.5 9.936A2 2 0 0 0 9.937 8.5l1.582-6.135a.5.5 0 0 1 .963 0L14.063 8.5A2 2 0 0 0 15.5 9.937l6.135 1.581a.5.5 0 0 1 0 .964L15.5 14.063a2 2 0 0 0-1.437 1.437l-1.582 6.135a.5.5 0 0 1-.963 0z"/><path d="M20 3v4"/><path d="M22 5h-4"/><path d="M4 17v2"/><path d="M5 18H3"/>
```

Current places (grep `brush-cleaning`, `i-brush` and `M14 4l6 6` to confirm):
- `App/app/templates/_icons.html` line 10: the `'brush-cleaning': '…',` entry.
- `App/app/templates/_shell_v2.html` (~line 24): the `/cleaning` nav link has `<svg viewBox="0 0 24 24"><path d="M14 4l6 6M4 20l7-7M9 11l4 4M3 21c2-1 4-1 6-3l-3-3c-2 2-2 4-3 6z"/></svg>`.
- `App/app/templates/_shell_tabbar.html` line 11, `_shell_sidebar.html` line 19, `menu.html` line 16, `_cleaning_table.html` line 68: `icon('brush-cleaning', …)` or `'brush-cleaning'`.
- `App/tests/test_design_icons.py` line 11 (`MASTER_ICONS`), `App/tests/test_design_shell.py` line 30.
- `docs/design/MASTER.md` line 158: `| Cleaning | \`brush-cleaning\` (lucide-static 0.552.0, the vendored version) | …`.
- `docs/design/mockup/ubyhost-redesign-v2.html` line 111 (same hand-drawn path), `docs/design/mockup/ubyhost-phone-v2.html` line 176 (`<symbol id="i-brush" …>…</symbol>`).

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/templates/_icons.html | edit | replace the `brush-cleaning` entry with `'sparkles': '<SPARKLES>',` (same position) |
| App/app/templates/_shell_v2.html | edit | inner path of the cleaning nav svg becomes SPARKLES |
| App/app/templates/_shell_tabbar.html, _shell_sidebar.html, menu.html, _cleaning_table.html | edit | `brush-cleaning` → `sparkles` |
| App/tests/test_design_icons.py, App/tests/test_design_shell.py | edit | `brush-cleaning` → `sparkles` |
| docs/design/MASTER.md | edit | line 158 icon name → `sparkles` |
| docs/design/mockup/ubyhost-redesign-v2.html | edit | cleaning nav svg inner → SPARKLES |
| docs/design/mockup/ubyhost-phone-v2.html | edit | contents of `<symbol id="i-brush">` → SPARKLES (keep the id) |
| docs/tasks/screenshots-0811/ | new | 4 PNGs, step 5 |
| docs/tasks/0811-report.md | new | report |


## 4. Steps

1. From `App/`: `python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt -r requirements-dev.txt 2>&1 | tail -3`. Do not commit `.venv` (check `git status` before each commit).
2. Make the edits in §3. Afterwards `grep -rn "brush-cleaning\|M14 4l6 6" App docs/design | head` must print nothing.
3. Commit `0811: sparkles cleaning icon everywhere`.
4. Run §6 tests. On a failure, fix only what this task changed; if the failure is unrelated to the icon, write it in the report and go on.
5. Screenshots: from `App/` run
   `UBYHOST_SHOTS_V2=1 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py -q --tb=short -k screenshots 2>&1 | tail -5`
   then copy from `docs/tasks/screenshots-0710/`: `cleaning-1440.png`, `cleaning-390.png`, `menu-390.png`, `menu-1024.png` into `docs/tasks/screenshots-0811/`. Then `git restore docs/tasks/screenshots-0710` and `git clean -fdq docs/tasks/screenshots-0710` so no 0710 PNG changes.
6. Write the report, commit `0811: report and screenshots`. Do not push.

## 5. Do not touch

Any file not in §3, including `App/app/static/app2.css` (the existing `.nav svg`, `.ui-icon` and `.list.plain .row > svg` rules already style the icon).

## 6. Commands

From `App/`:
```
PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_design_icons.py tests/test_design_shell.py tests/test_0710_v2_mockup_match_browser.py tests/test_design_guardrails_browser.py -q --tb=short -rs -k "icon or shell or cleaning or menu or guardrail" 2>&1 | tail -30
```
0 skipped. From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -5`.

## 7. Acceptance

- No `brush-cleaning` or hand-drawn broom left in App/ or docs/design/.
- §6 green, 0 skipped.
- 4 screenshots in docs/tasks/screenshots-0811/ show the sparkles icon.

## 8. Stop and ask

A test fails for a reason the icon cannot explain, or a file outside §3 seems to need a change.

## 9. Report

`docs/tasks/0811-report.md`: Status: review, changed files, test command tails, screenshot paths, deviations.

## 10. Addendum (0811b): calendar cleaning chips

The calendar cleaning chips draw a third broom in `App/app/static/dashboard-calendar.js` line 229: `path.setAttribute("d", "M15 3l6 6M13 5l6 6M12 10l4 4-8 8H3v-5zM5 17v4M8 15v5M11 13v4");`.

1. Replace that `d` string with the five SPARKLES paths joined into one string: `M9.937 15.5A2 2 0 0 0 8.5 14.063l-6.135-1.582a.5.5 0 0 1 0-.962L8.5 9.936A2 2 0 0 0 9.937 8.5l1.582-6.135a.5.5 0 0 1 .963 0L14.063 8.5A2 2 0 0 0 15.5 9.937l6.135 1.581a.5.5 0 0 1 0 .964L15.5 14.063a2 2 0 0 0-1.437 1.437l-1.582 6.135a.5.5 0 0 1-.963 0zM20 3v4M22 5h-4M4 17v2M5 18H3`. Nothing else in the file changes.
2. In `App/app/templates/_dashboard_calendar.html` line 170 change `?v=20261023-clean-url` to `?v=20261102-0811`. Then from `App/`: `.venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -5`.
3. From `App/`: `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_static_versions.py tests/test_0710_v2_mockup_match_browser.py -q --tb=short -rs -k "static or cleaning" 2>&1 | tail -15` (0 skipped). Also `grep -rln "dashboard-calendar" tests | head` and run those files the same way.
4. Redo §4 step 5 for `cleaning-1440.png` only (copy to docs/tasks/screenshots-0811/, restore 0710 shots).
5. Append the results to `docs/tasks/0811-report.md`, commit `0811b: sparkles in calendar cleaning chips`. Do not push.

## 11. Addendum (0811c): one icon per nav destination

Owner decision (Josef, 13:09): the stay fee icon becomes a receipt with text lines and no "$" (`receipt-text`), everywhere. Same rule for every nav destination: the v2 desktop sidebar (`_shell_v2.html` `.side-nav`), the v2 phone tab bar (`_shell_v2.html` `.tabs`) and the phone Menu (`menu.html`) must show the same icon. Today they differ for Stays, Payments, Stay fees, Settings and Help. Overview/Today, Calendar, Properties and Menu already match: leave them.

Target icon per destination (all through the `icon()` macro from `_icons.html`; `_shell_v2.html` already imports it, it uses `icon('search', 16)`):

| Destination | Icon | Where to change |
|---|---|---|
| Stays | `users` | `_shell_v2.html` sidebar link (line ~22) and tab (line ~48): replace the inline `<svg …>…</svg>` with `{{ icon('users', 18) }}` (sidebar) / `{{ icon('users', 22) }}` (tab) |
| Payments | `credit-card` | `_shell_v2.html` sidebar link (line ~25) → `{{ icon('credit-card', 18) }}` |
| Stay fees | `receipt-text` (new key) | `_shell_v2.html` sidebar (line ~26) → `{{ icon('receipt-text', 18) }}`; `menu.html` line 17 `icon('receipt', 26)` → `icon('receipt-text', 26)`; `_shell_sidebar.html` line 18 and `_shell_tabbar.html` line 19 `invoice-slip` → `receipt-text` |
| Settings | `settings` | `_shell_v2.html` sidebar (line ~27) → `{{ icon('settings', 18) }}` |
| Help | `circle-help` | `_shell_v2.html` `/guide` link (line ~31) → `{{ icon('circle-help', 18) }}` |

Also replace the cleaning link's inline svg (line ~24, done in 0811) with `{{ icon('sparkles', 18) }}` so the sidebar uses one source.

1. `_icons.html`: add after the `'receipt'` line:
   `  'receipt-text': '<path d="M4 2v20l2-1 2 1 2-1 2 1 2-1 2 1 2-1 2 1V2l-2 1-2-1-2 1-2-1-2 1-2-1-2 1Z"/><path d="M16 8H8"/><path d="M16 12H8"/><path d="M13 16H8"/>',`
   Then delete the `'invoice-slip'` entry if `grep -rn "invoice-slip" App/app` shows no other use. Keep `'receipt'` (`_property_create.html` uses it).
2. Make the edits in the table. Existing CSS (`.nav svg`, `.tabs .tab svg`) sizes and strokes them; no CSS change.
3. Tests: `App/tests/test_design_shell.py` line 29 `invoice-slip` → `receipt-text`; `App/tests/test_design_icons.py` `MASTER_ICONS`: add `"receipt-text"`, `"credit-card"` if missing, and remove `"invoice-slip"` if it is listed and was deleted. `grep -rn "invoice-slip\|M6 3h12v18" App/tests` and fix any other hit.
4. `docs/design/MASTER.md` table in 6.1: `| Stay fees | \`coins\` |` → `| Stay fees | \`receipt-text\` |`.
5. Mockups, so they stay the reference: in `docs/design/mockup/ubyhost-redesign-v2.html` lines 109 (stays), 112 (pay), 113 (fee), 114 (settings) and the help link, replace the inner markup of each nav `<svg viewBox="0 0 24 24">` with the matching icon's paths from `_icons.html` (users, credit-card, receipt-text, settings, circle-help). In `docs/design/mockup/ubyhost-phone-v2.html` replace the contents of symbols `i-stays`, `i-receipt`, `i-card`, `i-gear`, `i-help` the same way (keep the ids).
6. Commands: `grep -rn "invoice-slip\|M6 3h12v18" App docs/design | head` prints nothing. Then from `App/`:
   `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_design_icons.py tests/test_design_shell.py tests/test_0710_v2_mockup_match_browser.py tests/test_design_guardrails_browser.py tests/test_0728_menu_geometry_browser.py -q --tb=short -rs 2>&1 | tail -30` (0 skipped; if a failure also fails on `git stash`-free main logic unrelated to icons, note it and go on).
   Also `grep -rln "_shell_v2\|side-nav\|class=\"tabs\"" tests | head` and run those files the same way.
7. Screenshots: redo §4 step 5 (all four files), then restore the 0710 folder: `git checkout -- docs/tasks/screenshots-0710` and delete any untracked file under it with `rm` (list them with `git status --short docs/tasks/screenshots-0710`).
8. Append results to `docs/tasks/0811-report.md`, commit `0811c: one icon per nav destination`. Do not push.
