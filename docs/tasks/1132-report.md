# 1132 report (executor: Haiku 5.5)

Status: blocked
Branch: claude/confident-cerf-0zow3i (no push, no PR)
Commits: 9af5dfda (step 1), step 2, step 3, 580b532a (step 4). Report commit follows.

## Done
- Step 1: tokens added in `tokens.css`; `app2.css` `:root` maps to `--page-cream`, `--coral-red*`. Contrast: #b83d28 on #fdece8 4.91; on #faf6f0 5.22; white on #d0452d 4.59; #6b6b65 on #faf6f0 4.98 (all >= 4.5).
- Step 2: `brush-cleaning`, `wallet`, `chevrons-up-down` added; paths checked against lucide-static 0.552.0 (identical). Icons swapped in `_shell_tabbar.html`, `menu.html`. `test_icons_nav_1060.py`: "1 passed in 0.10s".
- Step 3: `_shell_v2.html` aside rewritten (org box and Ctrl K removed, two nav groups, bottom block with Ask Havel, Help, Settings, avatar row with first name; Smart locks and Invoices moved to account menu). No JS used `data-command-shortcut`.
- Step 4: sidebar CSS block, tablet rail (768-1023), tab bar media query moved to max-width 767, MASTER.md section 2 line, base.html cache bumps to `20261112-1132a`.

## Test commands (last lines)
- Step 4, run 1: `test_0705_v2_shell_browser.py` failed on `assert "--acc:#d0452d" in css`. Changed to `--acc:var(--coral-red)`.
- Step 4, run 2: `1 failed, 9 passed in 36.24s`. `test_0895_sidebar_inert_heal_browser.py` clicks `#app-sidebar .me-menu-list a[href="/guide"]`, now moved. Changed selector to `.side-bottom`; the open account menu's `.support-link` then intercepts clicks. Second failure: test edit reverted, test left red.
- Layout lint: `56 layout-lint findings {'word-per-line': 56}`. Cause: `span.env-badge` "MOCK · Nothing sent" wraps to 4 lines (55 px wide) in the 88 px tablet rail, 768 px. Not fixed.
- Not run: `test_design_guardrails_browser.py`, `test_0710_v2_mockup_match_browser.py`, `test_static_versions.py`, the `test_host_*` set, `test_design_*`.

## Deviations
- Done: steps 1 to 4 (CSS/docs), partly. Left: fix the 0895 test flow, fix env-badge in rail, rerun section 6, screenshots at 390/768/1280 for `/` and `/reservations`, PR body.
- Token grep expected 9 or more lines; actual 5 lines (4 in tokens.css, 1 in app2.css). All tokens are present.
- Booking site icon: `external-link` (`globe` is not in `_icons.html`).
- Dashboard badge removed from sidebar (brief: no badge).
- Logo mark is a PNG and cannot be recoloured by CSS; only the wordmark colour was set.
- Help, Settings and Ask Havel in the sidebar bottom render only for logged-in users.

## Questions
1. Env badge in the 88 px rail: hide it below 1024 px, or allow it to span the rail width?
2. `test_0895`: the flow opens the account menu and clicks Guide. Guide now sits in the sidebar bottom. Which selector or order should the test use?

## Owner steps left
None until the two questions and the layout lint are resolved.

## Screenshots
Not captured yet. The layout lint run wrote its output to `App/data/shots/1132/layout-lint/`.
