# 0804 brief: Nový úklid, Sdílení and cleaning properties on the v2 look

Status: ready
Executor: Haiku 5.5, alone, on the branch it is given. Routes: `cleaning-new`, `cleaning-shares`, `cleaning-properties`.
CSS block comment: `/* 0804 cleaning sub-pages (v2) */`

## Objective
`App/app/templates/cleaning_edit.html` (/cleaning/new and edit), `cleaning_shares.html` (/cleaning/shares), `cleaning_properties.html` (/cleaning/properties) get `{% set v2 = true %}` and match `/cleaning` (already v2; read `cleaning.html` and the cleaning rules in app2.css for the header pattern). Their old styles are in `App/app/static/cleaning.css`, which v2 does not load: port only what their markup uses into your block, in the v2 look:
- header h1 + sub line + back link to Úklid like the other v2 detail pages; sidebar item Úklid active (`nav = 'cleaning'`);
- forms in a white card, labels above inputs, 40 px inputs, even field spacing (audit P3: Nový úklid field spacing);
- Sdílení: no native `fieldset`/`legend` look (audit item 20): fieldsets become borderless groups with a bold small title; the share link/QR and copy button use the shared v2 copy-button styles; buttons 40 px (audit: Sdílet 44 vs 38 px; below 1024 px 44 px is the rule);
- cleaning properties: one card with a row per property (name left, setting control right), like the properties table rows.
Phone: compact cards, primary button full width. Do not change `cleaning.html` or `_cleaning_*.html` (the cleaning page is done).

## Files
The three templates, partials they include only if they are not used by `cleaning.html` (`grep` first), `App/app/static/app2.css` (append), `docs/design/catalog.json`, tests asserting old markup (`grep -rl 'cleaning/new\|cleaning/shares\|cleaning/properties\|cleaning_edit\|cleaning_shares\|cleaning_properties' App/tests | head -30`).

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

Finish: commit on the current branch with message `0804: <title>` (no push), and write `docs/tasks/0804-report.md`: changed files, test tails, screenshot paths, deviations. Stop at 30 tool calls and write the report with what is left.
