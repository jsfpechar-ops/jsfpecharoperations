# 1132 report (executor: Haiku 5.5)

Status: blocked
Branch: claude/confident-cerf-0zow3i (no push, no PR)
Commits: 9af5dfda (step 1), 43d590f0 (step 2), 5fa3bbc1 (step 3), 580b532a (step 4), 6ffee98b (report), then this commit.

## Done
- Steps 1 to 4 as before. Decision A: env badge in the tablet rail shows the short "MOCK" (`.env-short`); full text from 1024 px. Decision B: test_0895 clicks `#app-sidebar .side-bottom a[href="/guide"]`. Decision C: app2.css bumped to `20261112-1132b` (tokens.css left at 1132a).

## Test commands (last line, App/)
- test_0895_sidebar_inert_heal_browser.py: `2 passed in 2.68s`. Skips 0.
- test_0705_v2_shell_browser.py: `9 passed in 4.67s`. Skips 0.
- test_layout_lint_browser.py: `4 passed in 235.91s (0:03:55)`. Skips 0.
- test_design_guardrails_browser.py + test_0710 (run separately, no -x for 0710): guardrails stopped at `1 failed in 30.63s`: `tap-target-small` guest-new 390 "Cancel" 43 px (needs 44). Not in the 1132 diff; not fixed (guest page is out of brief scope). 0710: `98 failed, 85 passed in 202.43s`; mostly `.side is 240 px wide, expected 220` (1024 to 1920 px).
- test_static_versions, test_wp07, test_design_*, test_host_i18n: `6 failed, 169 passed in 71.76s`. Seen: test_design_shell (`.tabs a.tab[href="/menu"]` at 820 px, tab bar now hidden 768 to 1023 as the brief asks, so the test is out of date); test_design_tokens (`--danger` defined twice in ROOT_BLOCK, tokens.css lines 42 and 155). Other failures not inspected.
- test_host_*.py + test_host_geometry.py: background run, last line: 

## UX gate (390 / 768 / 1280; full-page captures in App/data/shots/1132/gate/, not committed)
- `/`: 390 one column, bottom tab bar, no overflow. 768 88 px rail, "MOCK" short badge on one line, labels fit. 1280 240 px sidebar, full "MOCK · Nothing sent" badge, no wrap.
- `/reservations`: 390 chips wrap in two rows, cards readable. 768 rail as above, list cards fit. 1280 table fits, no horizontal scroll.
- Capture artifacts: fixed tab bar and rail background appear mid-page or stop at 900 px in full-page shots; not a layout defect.

## Deviations
- Done: steps 1 to 5 (decisions A to C), gate screenshots. Left: guest-new tap target (390), 0710 sidebar width (220 vs 240), test_design_shell tab-bar expectation, test_design_tokens --danger duplicate, host rows if still red.
- Gate screenshot script is in the scratchpad, not in the repo.

## Questions
1. Sidebar width: 240 px (current) or 220 px (0710 test)?
2. test_design_shell: update the expectation to "no tab bar 768 to 1023"?

## Owner steps left
None until the questions above are answered.

## Fix-up 2

Items applied (from the orchestrator fix list):

1. `tokens.css`: duplicate `--danger` removed; remaining line `--danger: #d0452d; --danger-bg: var(--red-100);`.
2. `app2.css`: `td small .guest-count{white-space:nowrap}` added (`app.css` already has nowrap on `.guest-count`; the 1024 overlap is still red, see below).
3. `test_design_shell_browser.py`: at 820 px assert `.tabs` hidden and `#app-sidebar` visible, then open `/menu?lang=en`; 390 keeps the Menu-tab click.
4. `v2_mockup.py`: sidebar 220 to 240 px; `.side .nav` and `.side .nav.on` overrides merged into the existing entries (no duplicate dict keys); 768 to 1023 px branch expects an 88 px `.side` and no visible `.tabs`. `test_0710_v2_mockup_match_browser.py`: `STYLE_PHONE_WIDTHS = PHONE_WIDTHS` (768 dropped).
5. `test_host_account_navigation.py`: Settings and Guide asserted absent from the account menu and present in `div.side-bottom`.
6. `test_host_redesign.py`: `/invoices` absence checked against `<nav class="side-nav">` only.
7. `test_host_unsaved_changes_browser.py`: Settings clicked via `#app-sidebar .side-bottom a[href="/settings"]` (both places).
8. `test_host_ux_acceptance.py`: Invoices reached through `#app-sidebar .me-menu` (summary, then `.me-menu-list a[href="/invoices"]`). That test has no Settings or Guide click, so none changed.
9. `base.html`: `tokens.css?v=20261112-1132c` and `app2.css?v=20261112-1132c`; `tests/test_static_versions.py --write` run (51 files).

Re-run final lines (from App/, `-q --tb=short -rs`):

- `tests/test_design_tokens.py tests/test_static_versions.py`: `6 passed in 0.18s` (0 skipped)
- `tests/test_design_shell_browser.py`: `15 passed in 20.76s` (0 skipped)
- `tests/test_0710_v2_mockup_match_browser.py`: `10 failed, 172 passed in 198.17s` (0 skipped). Still red, see below.
- `tests/test_host_account_navigation.py tests/test_host_redesign.py`: `30 passed in 6.66s` (0 skipped)
- `tests/test_host_unsaved_changes_browser.py tests/test_host_ux_acceptance.py`: `1 failed, 36 passed in 122.72s` (0 skipped). The one failure is the pre-existing item below.
- `tests/test_0895_sidebar_inert_heal_browser.py tests/test_0705_v2_shell_browser.py`: `11 passed in 6.69s` (0 skipped)
- `tests/test_layout_lint_browser.py`: `4 passed in 230.47s` (0 skipped)

Still red after the listed fixes (not fixed, stopped per the one-retry rule):

- `test_0710_v2_mockup_match_browser.py`, 9 cases at 768 px: `overview`, `cleaning`, `properties`, `stay_fees`, `stays`, `stay`, `submissions`, `invoices`, `housebook`. Cause: item 4c removes 768 from `STYLE_PHONE_WIDTHS`, so these cases fall through to the desktop mockup branch (example: `invoices at 768 px: .head h1 font-size app=30px mockup=24px; .head .btn missing in app`). The 768 layout (88 px rail, no tabs) has no matching desktop mockup, so the brief needs a decision: a 768 mockup, or excluding 768 from the desktop style cases. Assertions were not weakened.
- `test_0710_v2_mockup_match_browser.py::test_v2_page_geometry[stays-1024]`: overlapping text in `tr.clickable-row` ("Hosté: 1 z 1" against "Přímá rezervace"). Item 2 is in place and `.guest-count` already has nowrap, so this is not the nowrap issue. Needs a layout look.

Pre-existing on main, not fixed (as instructed):

- `test_host_ux_acceptance::test_every_page_family_fits_every_width_language_and_rail_state`: guide cs 390 help-tip (`help-tip-btn` past right edge, right 393 vs 390). Seen in this run.
- guardrails guest-new 390 Cancel 43 px and test_host_flash_outcomes sticky amber: not re-run in this session.

Not updated: the comment above `STYLE_PHONE_WIDTHS` in `test_0710_v2_mockup_match_browser.py` still says 768 is compared against the phone mockup, so it is stale.

## Fix-up 3

Items, each with the final line of its re-run:

1. Tablet rail: `App/app/static/app.js` `NAV_BREAKPOINT` 960 → 767. Also changed the drawer media query `max-width: 960px` → `767px` in `App/app/static/app.css` (the `.sidebar` translateX block), otherwise CSS still hid the rail at 768-960. Remaining 960 couplings, left unchanged: `app.css` `@media (min-width: 960px)` (`.split.wide` grid) and `host.css` `@media (max-width: 960px)` (`.host-workspace .sidebar` width and margin). Not confirmed whether the host rule is drawer-related, so reported only.
2. Regression test added: `test_tablet_rail_is_usable_between_768_and_1024_and_drawer_stays_inert_at_390` in `App/tests/test_0895_sidebar_inert_heal_browser.py`. The existing compact test used 800 px, which is now in the tablet band, so its viewport moved to 390 px (assertion unchanged).
3. Stays row: `td small .source-badge{white-space:nowrap}` added in `App/app/static/app2.css`.
4. `STYLE_CASES` in `App/tests/test_0710_v2_mockup_match_browser.py` excludes width 768 from the style comparison. The 768 geometry coverage stays in `CASES`.
5. Static keys bumped to `20261112-1132d` in `App/app/templates/base.html` for app2.css, app.js and app.css (app.css also changed, so bumped too). `test_static_versions.py --write` regenerated `App/tests/static_versions.json`.

Re-runs (from App/):
- 0895, 0705, design_shell, static_versions, design_tokens: `33 passed in 28.75s` (first run had 1 failure, the 800 px viewport, fixed as in item 2)
- 0710 mockup match + 0506 last-inits: `174 passed in 193.04s (0:03:13)`
- host_unsaved_changes + host_ux_acceptance: `1 failed, 36 passed in 129.62s (0:02:09)`. The failure is the allowed pre-existing `test_every_page_family_fits_every_width_language_and_rail_state` (guide cs 390, help-tip past right edge).
- layout_lint_browser: `4 passed in 231.04s (0:03:51)`

Skipped count: 0 in every re-run.

## Fix-up 4

Items:
1. Tablet rail (768 to 1023 px): More link added after Cleaning (`rail-only`, `ellipsis` icon, label `nav.more`). Second nav group, Ask Havel, Settings, the side separator and the search button are hidden there (`rail-hide`). Help and the avatar stay.
2. CSS: `.rail-only` hidden globally, shown in the tablet query; `.rail-hide` hidden in the tablet query. The avatar summary has no border or background in the rail (`padding:4px`, centred).
3. `menu.html`: Booking site row added after the Payments row (`href="/booking-sites"`). The 0895 tablet test asserts the link on `/menu`.
4. Laptop (>=1024 px): env badge uses `width:fit-content`, `align-self:flex-start`, `margin-left:14px` (aligned with the nav label x).
5. Tests: 0895 tablet test extended (820: More visible, Stay fees and search hidden, More opens /menu; 1280: More hidden, Stay fees visible).
6. `app2.css` key bumped to `20261112-1132f`; `static_versions.json` rewritten.

Re-runs (App/, `-q --tb=short -rs`):
- Shell group (0895, 0705, design shell, static versions, host account navigation, host redesign, icons nav 1060): `61 passed in 35.47s` (0 skipped). Re-run after the last CSS edit with 0895, 0705, static versions: `15 passed in 9.21s` (0 skipped).
- `test_0710_v2_mockup_match_browser.py`: `172 passed in 189.59s` (0 skipped).
- `test_layout_lint_browser.py`: `4 passed in 233.65s` (0 skipped).

Rail comparison vs Figma "Tablet 820 / Dashboard (B)" (820 px screenshot against the Figma PNG):
- Dashboard, Stays, Properties, Cleaning, More: same order, same labels, same active coral box on Dashboard. Cleaning icon differs (ours is a brush, Figma a sparkle broom).
- Help: matches. Avatar: circle present, but ours still has a thin outlined box around it (Figma has none). The CSS override did not remove it; source of the box not yet found. Still open.
- Logo: ours is the mark image plus the MOCK env badge above Dashboard; Figma shows a coral "U" tile and no badge. The badge is kept on purpose (safety cue).
- No search button, no Stay fees / Payments / Booking site, no Settings, no Ask Havel in the rail: matches.

Screenshots (not committed, under App/data):
- /home/user/jsfpecharoperations/App/data/shots/1132/fix4/dashboard-820.png
- /home/user/jsfpecharoperations/App/data/shots/1132/fix4/dashboard-1280.png

Still open: avatar outlined box in the tablet rail (see above). Nothing red, nothing skipped in the re-runs.
