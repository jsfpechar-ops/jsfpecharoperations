# 0151: guest-browser CI failures after 0147-0150

Status: todo
Depends on: 0150 | Base commit: 5b10d6a | Branch: claude/project-thread-td6fpc
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

Commit each step as `0151 step k`. Never push, never open a PR. Work on the current branch; do not create a new one.

## 1. Objective

The CI job `guest-browser` fails on 5b10d6a with 14 tests in four files (it had been skipped since the 0134 design work, so some failures are older than 0147). Three causes are in the app (step 1), the rest are tests reading the pre-0149 stays markup (step 2, every assertion kept). One assertion stays red on purpose and goes to the owner (§7, last line).

1. **App.** The phone bottom tab bar (MASTER 6.2, fixed, 56 px) covers a control that `scrollIntoView` parks at the bottom edge of the viewport; Playwright's click on "Add calendar" in the setup wizard at 360/390 px without JavaScript is intercepted by the `<a href="/cleaning">` tab. Keyboard focus has the same problem for a real user. Fix: `scroll-padding-bottom` on the document below 1024 px.
2. **App.** `host2.css` paints the desktop row hover on every `td` (`.ui-row:hover td`). The stays rows became `.ui-row` in 0149, and the one-surface rule (`test_rows_hover_as_one_surface_and_use_compact_menus`: the row paints, cells stay transparent) broke at 1440/1920/2048. MASTER 7.3: "whole-row hover `--surface-2`". Fix: paint the `tr`. Below 1024 the tr keeps `--surface-hover` (what `host-controls.css` gave it before; `--surface-2` is white there and would hide the hover).
3. **App.** Below 1024 the row menu is the bottom sheet of `host2.css` line 118 (`position: fixed; inset: auto 0 0 0`), but `app.js` still writes an inline `left`/`top` computed from the panel's width. The sheet is as wide as the viewport, so `left` becomes -8 px and the sheet 368 px wide at 360 px (`test_host_wide_lanes_align`: "popup x >= -1"). Fix: the JS leaves a sheet where CSS puts it.
4. **Tests.** 0149 made the stays date column `d. m.` (`date_short`, stays.md) and the desktop row actions 40 px (`--control-h`, MASTER 2.3 and 7.3; `test_host_stay_actions_browser.py` already moved from 42 to 40 in 0149-fix-1). `empty_state` renders `.ui-empty`, not `.panel.empty`. Two filter-panel tests still look for `10.03.2026` in the list text (the row's `aria-label` keeps `date_cz`); the wide-geometry tests still expect 42 px controls and the old empty-state class.

## 2. Context

Rules: AGENTS.md hard rules 6, 7, 8. Tokens only in CSS. Never weaken an assertion: each test edit below keeps what the test asserts (the stay is in the filtered list; every row control is one full control height; the result lane exists).

Anchor A, `App/app/static/host2.css` line 157 (one line):
```
.host-workspace .ui-table .ui-row:hover td, .host-workspace .ui-table .ui-row:focus-within td { background: var(--surface-2); }
```
Anchor B, `App/app/static/host2.css` line 233 (one line, inside `@media (max-width: 1023px)`):
```
  .host-workspace .ui-table .ui-row:hover td, .host-workspace .ui-table .ui-row:focus-within td { background: transparent; }
```
Anchor C, `App/app/static/host2.css` line 281 (one line, first rule of the `@media (max-width: 1023px)` block that also holds `.ui-tabbar { position: fixed; ... }`):
```
  .host-workspace .ui-sidebar, .host-workspace .sidebar-expand { display: none; }
```
Anchor D, `App/app/static/app.js` lines 442-443 (inside `function positionRowMenu(trigger, panel)`):
```
    panel.style.zIndex = "10000";
    var rect = trigger.getBoundingClientRect();
```
Anchor E, `App/tests/test_host_filter_panels_browser.py` line 169, and Anchor F, the identical line 354:
```
        assert "10.03.2026" in page.locator(".stays-view").inner_text()
```
(line 168 above E reads `assert "range=custom" in page.url and "archive_scope=1" in page.url`; line 353 above F reads `assert "archive_scope=1" in page.url and "range=archive" in page.url`.)

Anchor G, `App/tests/test_host_wide_geometry_browser.py` line 39 and line 57:
```
    "stays": ("/reservations", ".stays-view, .panel.empty"),
```
```
    "stays-archive": ("/reservations?range=archive", ".stays-view, .panel.empty"),
```
Anchor H, same file, line 392:
```
    assert trigger_box and trigger_box["height"] >= (44 if width <= 760 else 41), trigger_box
```
Anchor I, same file, line 596:
```
                        expected_action_height = 44 if width in MOBILE_WIDTHS else 42
```
Anchor J, same file, lines 680-682:
```
                        assert control["height"] >= 41, (control, more)
                        if not control["isCopy"]:
                            assert abs(control["height"] - 42) <= 1, (control, more)
```

The stays row (`App/app/templates/reservations.html`, do not edit) carries `aria-label="{{ stay_label }} · {{ reservation.date_from | date_cz }} – {{ reservation.date_to | date_cz }}"`, so the archived fixture stay (2026-03-10 to 2026-03-12) has `10.03.2026` in its `aria-label`. `--tabbar-h` is defined on `:root` in `tokens.css`, so `html` can read it. The row menu panel is `<div class="row-menu-panel ui-menu-panel" role="menu" hidden>` (`row_menu_begin` in `_components.html`).

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/static/host2.css | edit | Anchors A, B, C (step 1) |
| App/app/static/app.js | edit | Anchor D (step 1) |
| App/tests/test_host_filter_panels_browser.py | edit | Anchors E, F (step 2) |
| App/tests/test_host_wide_geometry_browser.py | edit | Anchors G, H, I, J (step 2) |
| docs/tasks/0151-report.md | create | step 4 |

No other file may change.

## 4. Steps

1. `App/app/static/host2.css`, three edits, each a whole-line replacement:
   - Anchor A becomes
     `.host-workspace .ui-table .ui-row:hover, .host-workspace .ui-table .ui-row:focus-within { background: var(--surface-2); }`
   - Anchor B becomes
     `  .host-workspace .ui-table .ui-row:hover, .host-workspace .ui-table .ui-row:focus-within { background: var(--surface-hover); }`
   - Anchor C stays and gets one new line directly under it:
     `  html:has(.host-workspace) { scroll-padding-bottom: calc(var(--tabbar-h) + env(safe-area-inset-bottom)); }`

   `App/app/static/app.js`, Anchor D: insert three lines between its two lines, so the block reads
   ```
       panel.style.zIndex = "10000";
       if (panel.classList.contains("ui-menu-panel") && window.matchMedia("(max-width: 1023px)").matches) {
         return; // 0151: below 1024 px the panel is the bottom sheet of host2.css; CSS places it
       }
       var rect = trigger.getBoundingClientRect();
   ```
   From the repo root: `python3 scripts/design_lint.py | tail -3` prints `design lint: OK`. Commit `0151 step 1`.

2. Tests:
   - Anchor E becomes
     `        assert page.locator('.stays-view tbody tr[aria-label*="10.03.2026"]').count() == 1`
   - Anchor F becomes the same line as E.
   - Anchor G: in both lines `.panel.empty` becomes `.ui-empty` (nothing else on the line changes).
   - Anchor H: `else 41)` becomes `else 39)`.
   - Anchor I: `else 42` becomes `else 40`.
   - Anchor J: `>= 41` becomes `>= 39` and `- 42) <= 1` becomes `- 40) <= 1`; the middle line is unchanged.

   From `App/`: `.venv/bin/ruff check --select E9,F63,F7,F82,F401,F841 tests/test_host_filter_panels_browser.py tests/test_host_wide_geometry_browser.py | tail -3` prints `All checks passed!`. Commit `0151 step 2`.

3. Browser run, from `App/`, one command (about 8 minutes; do not split it, do not add `-x`):
   ```
   UBYHOST_REQUIRE_BROWSER=1 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_SHOTS_DIR=/tmp/claude-0/-home-user-jsfpecharoperations/3c6f1ec6-a025-553c-863a-9c0748d5832e/scratchpad/shots/0151 .venv/bin/python -m pytest tests/test_onboarding_wizard_browser.py tests/test_onboarding_followup_browser.py tests/test_host_filter_panels_browser.py tests/test_host_wide_geometry_browser.py tests/test_host_stay_actions_browser.py -q --tb=short -rs 2>&1 | tail -30
   ```
   Expected: `1 failed, N passed`, 0 skipped, and the one failure is `test_host_wide_lanes_align` at `_assert_stay_track_content` with the message `stay content escapes .stay-col-dates > a cell` (en, 360 px). That failure is a design question, not yours (§7); copy its `E` lines into the report. Any other failure: run that one test id once more; if it fails again, stop (§8).

   Known flake, not yours: `test_phone_guest_sharing_and_clear_setup_actions[True-*]` can fail on `assert skeleton.is_hidden()` on a fast machine (`skeleton.js` keeps the skeleton 400 ms). If it is the only other failure, rerun that test id alone once and paste both outputs.

   The wizard tests rewrite tracked screenshots: from the repo root run `git checkout -- docs/tasks/0102-evidence` after the run and never `git add` that folder.

   Screenshots (390 px, rule 7), from the repo root:
   ```
   mkdir -p /tmp/claude-0/-home-user-jsfpecharoperations/3c6f1ec6-a025-553c-863a-9c0748d5832e/scratchpad/shots/0151 && cp docs/tasks/0102-evidence/22-calendar-platform-cs-390-no-js.png /tmp/claude-0/-home-user-jsfpecharoperations/3c6f1ec6-a025-553c-863a-9c0748d5832e/scratchpad/shots/0151/wizard-calendar-390.png
   ```
   (run this before the `git checkout` above, or run the checkout afterwards; the untracked `22-*` files survive the checkout). Then from `App/`: `UBYHOST_CAPTURE_0079=1 UBYHOST_REQUIRE_BROWSER=1 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers .venv/bin/python -m pytest tests/test_host_list_layouts_browser.py -k share_compact_row_menu -q --tb=line 2>&1 | tail -3` (passes), then from the repo root `cp docs/tasks/0079-evidence/stays-390-cs.png /tmp/claude-0/-home-user-jsfpecharoperations/3c6f1ec6-a025-553c-863a-9c0748d5832e/scratchpad/shots/0151/stays-390.png && git checkout -- docs/tasks/0079-evidence`.

4. By eye (Read tool), both screenshots, write what you saw in the report:
   - `wizard-calendar-390.png`: the "Přidat kalendář" button is whole and readable; nothing overlaps it.
   - `stays-390.png`: one card per stay, the menu button at the right edge, no horizontal scroll; note how many lines the stay name takes in the widest-badge card.

   Write `docs/tasks/0151-report.md` (Status review or blocked; `git diff --stat 5b10d6a`; the last 5 lines of each command; §7 ticked; the `E` lines of the expected lanes failure; by-eye list; screenshot paths; deviations; questions). Commit `0151 report`.

## 5. Do not touch

`reservations.html`, `dashboard.html`, `_components.html`, `app.css`, `host.css`, `host-controls.css`, `tokens.css`, `skeleton.js`, `catalog.json`, any Python under `App/app/`, any other test, `docs/tasks/0135-0137*`. No new dependency, no geometry limit relaxed beyond the 42-to-40 and 41-to-39 pairs above (40 px is the settled desktop control height, MASTER 2.3), no `pytest.skip`, no `-x` in step 3, no change to `_assert_stay_track_content` or to the 7.3 card grid.

## 6. Commands

As in steps 1 to 3. Every command ends with `| tail -N`.

## 7. Acceptance

- [ ] Step 1: `design_lint.py` OK; `git diff 5b10d6a -- App/app/static/host2.css` shows 2 changed lines and 1 added line; `App/app/static/app.js` 3 added lines.
- [ ] Step 2: ruff passes; `git diff 5b10d6a --stat -- App/tests` shows only the two test files.
- [ ] Step 3: 0 skipped; every test passes except `test_host_wide_lanes_align`, which fails only at `stay content escapes .stay-col-dates > a cell`; `docs/tasks/0079-evidence` and `docs/tasks/0102-evidence` show no tracked change.
- [ ] Step 4: both screenshots read as described, paths in the report.
- [ ] Owner decision pending (not for the executor): at 360 px the 7.3 card grid `minmax(0,1fr) auto 44px` gives the badge column its content width, so a long state badge ("! overdue by 4 days", cs "Připraveno (naplánováno)") leaves the primary cell 58 to 92 px: the dates (`nowrap`) escape the cell by 7 px and the stay name wraps to 4 or 5 lines. `_assert_stay_track_content` catches it. Options: a phone `max-width` for the badge column with badges allowed to wrap (changes MASTER 7.5), shorter phone labels, or moving the badge under the primary below 1024 (changes MASTER 7.3).

## 8. Stop and ask

Stop, and write the report as `blocked`, if an anchor is not found verbatim at the given line, if any test other than the two named in step 3 fails twice (quote the assertion verbatim with the test id, width and language), if a screenshot shows the button under the tab bar, or if you reach 25 tool calls.

## 9. Report

As in step 4. 600 tokens at most.

## Risk list (for the reviewer)

`App/app/static/host2.css` (2 lines changed, 1 added: the `html:has(.host-workspace)` rule applies to every host page below 1024 px, only to scroll-into-view and focus scrolling). `App/app/static/app.js` (3 lines: a sheet below 1024 px is no longer positioned by JS; every `.row-menu-panel` is also `.ui-menu-panel`).

## Owner steps

None now. After the report says review, decide §7's last line; CI on the branch re-runs `guest-browser`.
