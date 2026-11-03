# 0803 brief: Průvodce (help guide) and Havel page on the v2 look

Status: review
Executor: Haiku 5.5, alone, on the branch it is given. Routes: `guide`, `havel`.
CSS block comment: `/* 0803 help guide + Havel page (v2) */`

## 1. Objective
1. `/guide` (`App/app/templates/guide.html`, 340 lines: read it in ranges): `{% set v2 = true %}`; header h1 + sub line; the table of contents is a sticky left (or right) column card from 1280 px and a closed `<details>` card above the text below that (audit: TOC column looked broken); each guide section is a white `.card` with an `h2`; readable text column max ~720 px; anchors (`/guide#overview` etc., used by `havel.py` and `ui-how-more` links) must keep working: keep every `id`.
2. `/havel` (`havel.html`, 15 lines; Havel styles are already in app2.css under "v2 shared: Havel"): `{% set v2 = true %}`, header h1 + sub line, the chat panel in a white card filling the content width with a sensible min-height; the empty state (audit: "empty chat") shows the existing topic suggestions/intro inside the card instead of a blank area (use what `_havel_topics.html`/`_havel_panel.html` already render; no new copy).
Phone: guide TOC closed by default, sections stacked; Havel input stays above the tab bar.

## 3. Files
`guide.html`, `havel.html` (and only if needed `_havel_panel.html`, `_havel_topics.html`: class additions only), `App/app/static/app2.css` (append), `docs/design/catalog.json`, tests asserting old markup (`grep -rl '"/guide"\|guide.html\|"/havel"\|havel.html' App/tests | head -30`).

## 4. Steps

Shared rules for briefs 0800-0804 (same text in each):

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

Finish: commit on the current branch with message `0803: <title>` (no push), and write `docs/tasks/0803-report.md`: changed files, test tails, screenshot paths, deviations. Stop at 30 tool calls and write the report with what is left.

## 2. Context

See section 4 (how v2 works) and docs/tasks/0800-report.md … 0804-report.md.

## 5. Do not touch

Other pages, existing app2.css lines, wizard.css, cleaning.css, the guest-facing pages, static cache key, screenshot folders other than screenshots-0800.

## 6. Commands

See the test commands in section 4.

## 7. Acceptance

`tests/test_0800_v2_remaining_pages_browser.py` 0 failed for the brief's routes; the existing tests of the pages pass; design_lint passes.

## 8. Stop and ask

Stop and report if a route redirects away from the page, a fix would need a change to another page, or you reach 30 tool calls.

## 9. Report

`docs/tasks/<number>-report.md`: changed files, test tails, screenshot paths, deviations.
