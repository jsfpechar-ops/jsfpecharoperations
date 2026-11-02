# 0790: v2 look for Odeslání, Faktury, Domovní kniha (shared rules for briefs 0791-0793)

Status: active. Orchestrator thread "Redesign guest book and invoices pages", branch `claude/project-thread-tluz48`.
Executors: three Haiku 5.5 runs in parallel in `/home/claude/jsfpecharoperations` (already checked out). Do not switch branches, commit or push. Edit only the files and lines your brief names; never revert changes you did not make. Re-read a shared file right before each edit (other runs change it too).

## Goal

Restyle only: each page moves from the old look (`host_page.html` without `v2`) to the v2 shell, built 1:1 from the existing v2 stays list (`App/app/templates/reservations.html`), so it looks like the rest of the redesigned app. No route, data, string meaning, form action, JS behaviour or download changes. Every link, button, menu item, form and dialog that exists today still exists and works.

## The pattern (copy it from reservations.html)

1. Top of the template: `{% set v2 = true %}`, then empty blocks `page_title`, `meta`, `primary_action`, `secondary_actions`, `tabs`, `toolbar` (see reservations.html lines 1-25). Keep `nav`, `how_key`, `body_kind`.
2. Body starts with the page head, reusing the stays classes (do not invent new head classes):
   `<div class="head stays-head"><div><h1 class="big">TITLE</h1> {how-to details exactly as reservations.html, with this page's how_key} <p class="sub ph-hide">ONE LINE</p></div><div class="stays-head-actions">BUTTONS</div>{phone add button if any}</div>`
   Head buttons use `class="btn"` (primary, at most one) and `class="btn ghost"` (secondary), as in reservations.html. Phone add button: `<a class="round stays-add ph-only" href="…" aria-label="…">{{ icon('plus', 22) }}</a>`.
   Exactly one visible `h1` per page.
3. No section tab strip (Josef's rule). The old `ui_section_tabs()` links that are not in the sidebar become a ghost head button (desktop) and a row in a `.list.plain` block at the bottom with class `ph-hide` removed only if the brief says so. Grep `page_tabs` in `App/app/` to see what each page's tabs were.
4. Desktop list (>= 1024 px): `<div class="card stays-desk"><table>…</table></div>`; plain `<th>`/`<td>`; secondary text in `<small>`; status as `<span class="pill p-ok|p-warn|p-bad|p-n">` (green done, amber needs action, red rejected/failed, grey neutral). Keep `tr.clickable-row data-href`, `row_open`, `row_menu_begin/end` and all menu items.
5. Phone list (< 1024 px): `<div class="stays-phone">` with optional `<h2 class="sec">` group labels and one `<a class="card stay" href="SAME HREF"><span class="sav">INITIAL</span><span class="in"><b>MAIN</b><small>SECONDARY</small>PILL</span>{{ icon('chevron-right', 20, 'chev') }}</a>` per row (see reservations.html ~154-182). Compact rule: phone shows only main line, one secondary line and one status pill; everything else is on the detail page or desktop. Extra phone-only blocks get `ph-hide` unless the brief says otherwise.
   Do NOT add any rule for 768-1023 px other than what the stays classes already do: a tablet layout is being designed separately.
6. Empty states: keep the existing `empty_state(...)` calls.
7. CSS: only in `App/app/static/app2.css` between your brief's `/* 079x … v2 (start) */` and `(end)` markers, every selector prefixed `body.v2` plus a page-specific wrapper class. Reuse stays/shared rules; add a rule only when the page looks wrong without it. No `!important`, no new colours (use tokens), light mode only. Do not edit any other part of app2.css, `base.html`, `catalog.json`, `static_versions.json` or `docs/design/mockup/` (the orchestrator bumps the cache key and catalog).
8. Strings: reuse existing i18n keys. If a new key is unavoidable, add it to every host i18n file (grep an existing key such as `stays.title` to find them) and list it in the report.

## Tests (from `App/`)

- Env for browser tests: `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_REQUIRE_BROWSER=1`. Do not install or upgrade playwright.
- 0710 mockup match: add your page's entry to `PAGES` in `App/tests/v2_mockup.py` (the brief gives it), then
  `… .venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py -k <name> -q --tb=short -x 2>&1 | tail -30`. Style failures mean wrong CSS or wrong classes: fix those, do not add overrides, except a text-dependent width/height, added as a page-scoped key `"<name>:selector@width"` in BOX_OVERRIDES with a reason.
- Then the page's old tests: `grep -ln '<route>' tests/*.py`, run those files `-q --tb=short 2>&1 | tail -30`.
- Standing rule: you may update assertions in those files that check only this page's old markup (old class names, tab strip, `ui-table`, `ui-badge`, `panel`, `filter-toolbar` wrappers) to the new markup. You may not weaken an assertion about content, links, actions, privacy or legal text. If an assertion is about behaviour, fix the template instead.
- Screenshot at 390 and 1440 px of the page as the rich test host (reuse the login/fixture helper in `test_0710_v2_mockup_match_browser.py`) into `docs/tasks/screenshots-0790/<page>-<width>.png`.

## Report

`docs/tasks/079x-report.md`: files changed, tests run with pass/fail/skip counts, assertions changed (file:line, old -> new, why), anything left. Stop at 30 tool calls and write the report with what is left.
