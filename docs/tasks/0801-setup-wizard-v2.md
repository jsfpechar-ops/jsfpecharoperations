# 0801 brief: setup wizard on the v2 look (restyle only)

Status: ready
Executor: Haiku 5.5, alone, on the branch it is given. Routes: `setup-property`, `setup-calendar`, `setup-police`, `setup-guest-link`, `setup-stay-fee`, `setup-done`.
CSS block comment: `/* 0801 setup wizard (v2) */`

## Objective
The property setup wizard (`App/app/templates/setup_wizard/_layout.html` and its steps `property, calendar, police, guest_link, door_lock, stay_fee, automation, try_it, done`) is RESTYLE ONLY (owner's order): same steps, fields, buttons, copy and order. Put `{% set v2 = true %}` in `_layout.html` (children inherit it; check with the test). Its styles today live in `App/app/static/wizard.css` (and some in host.css/components.css), which v2 does not load: port only the rules the wizard markup actually uses into your app2.css block, rewritten to the v2 look:
- header: h1 + one sub line (mockup `.head`), progress as a small step strip or "Krok 2 z 8" line above the h1, not a full-width bar band;
- each step body is one white `.card` (mockup radius/ring), max width 720 px, left-aligned with the content edge;
- the step list / step cards use the mockup `data-v="welcome"` card (coral-soft number circle, bold title, grey line). Audit bug: step-card pills at different heights; make them one height;
- footer: Zpět/Přeskočit as secondary/link, Pokračovat as the one primary coral pill, right-aligned on desktop, full width on phone.
Do not touch `wizard.css` (old-shell pages may still use it); grep that no non-wizard template uses the classes you restyle under `body.v2 .wiz-…` scoping.

## Files
`setup_wizard/*.html` (markup changes only where a class is needed for scoping or an old wrapper must become a `.card`), `App/app/static/app2.css` (append), `docs/design/catalog.json`, tests that assert the old wizard markup (`grep -rl 'setup_wizard\|/setup' App/tests | head -30`). Routes are in `App/app/routes/onboarding_wizard.py` (read only). If a step route redirects for the rich host fixture, say so in the report instead of changing the route.

## Shared rules for briefs 0800-0804 (same text in each)

Goal: the page leaves the old look (old fieldsets, red header bar, narrow 720 px column, host.css) and uses the v2 shell like the finished pages (`/`, `/cleaning`, `/apartments`, `/reservations`). Restyle only: same routes, same form fields and names, same POST targets, same copy keys, same behaviour without JavaScript. No new features, no removed fields.

How v2 works (read, do not change):
- A template opts in with `{% set v2 = true %}` right after `{% extends %}` (see `App/app/templates/cleaning.html` lines 1-9). `base.html` then loads ONLY `tokens.css` + `app2.css` and the v2 sidebar `_shell_v2.html`. host.css, app.css, components.css, host2.css, wizard.css, workflow.css, cleaning.css are NOT loaded on v2 pages, so every class the page uses must be styled in `app2.css` (grep app2.css first; many generic ones exist: `.head`, `h1.big`, `.sub`, `.card`, `.btn`, `.btn.line`, `.btn.sm`, `.pill.p-ok|p-warn|p-bad|p-n`, `.ui-how*`, `.field`, `.fields`, inputs, labels, Havel, copy buttons).
- Page header = `<div class="head"><div><h1 class="big">Title</h1><p class="sub">one line</p></div>{one primary .btn on the right, optional}</div>` with empty `page_title`, `meta`, `primary_action`, `secondary_actions` blocks (as cleaning.html). Exactly one visible `<h1>` per page.
- Look reference: `docs/design/mockup/ubyhost-redesign-v2.html` (CSS at the top: `.head`, `h1`, `.sub`, `.card`, `.btn`, `.pill`, and the `data-v="welcome"` step cards and `data-v="prop"` form sections). Content is white `.card`s (radius, soft ring) on the grey canvas, left-aligned to the same content edge as `/cleaning`, not a centred 720 px column. Forms: label above input, inputs 40 px high, one primary coral pill button + one secondary, in a card.
- Phone (below 1024 px): compact. Reuse the shared phone v2 classes already in app2.css (blocks `0718`, `0729`, `0735`: `h2.sec`, `.card` radius 24, `.list.plain .row`, `.btn.line`). Long help text and secondary links get `ph-hide`. No sideways page scroll at 320 px. Do NOT write rules that target 768 px specifically (a tablet design is coming): only the existing `@media (max-width:1023px)` split.
- CSS: put ALL your new rules in ONE block appended at the END of `App/app/static/app2.css`, starting with the comment line given in your brief. Every selector starts with `body.v2 ` plus a page-scoping class you add to the page's outer wrapper (e.g. `body.v2 .wiz-page …`), so no other page changes. No `!important`. Never edit or delete existing app2.css lines (sibling threads edit them). Copy values from the mockup; reuse its custom properties (`var(--acc)`, `var(--line)`, `var(--ink2)` …).
- New class names: add each to `docs/design/catalog.json` (look at how existing entries are written; `python3 scripts/design_lint.py 2>&1 | tail -20` from repo root must pass if it exists).
- Do not bump the static cache key in base.html and do not touch `docs/tasks/screenshots-0710/` (orchestrator does both).
- Tests you may change: assertions in `App/tests/` that check only the OLD markup/classes of YOUR pages (grep the test folder for your template name, route path and old class names). Never change an assertion about another page, never skip or delete a test.

Test commands (from `App/`; never reinstall playwright):
- Main check: `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_0800_v2_remaining_pages_browser.py -k "<your route names joined by ' or '>" -q --tb=short 2>&1 | tail -40`. It checks: body.v2, exactly one visible h1, sidebar from 1024 px, and the shared geometry rules (no overflow, 44 px tap targets below 1024, 24 px from 1024, text ≥ 12 px, …) at 320/390/768/1024/1280/1440. Must be 0 failed. Fix CSS, never the test.
- Then the existing tests for your pages: `grep -rl "<template or route>" tests | head` and run those files, same env vars, `-q --tb=short 2>&1 | tail -30`.
- Screenshots: add `UBYHOST_SHOTS_0800=1` to the main check with `-k "<routes> and (390 or 1440)"`; PNGs land in `docs/tasks/screenshots-0800/<route>-<width>.png`. Open the 390 and 1440 PNG of each page (Read tool) and compare with the mockup look before you finish.

Finish: commit on the current branch with message `0801: <title>` (no push), and write `docs/tasks/0801-report.md`: changed files, test tails, screenshot paths, deviations. Stop at 30 tool calls and write the report with what is left.
