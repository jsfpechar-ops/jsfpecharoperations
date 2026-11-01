# 0536: property page on v2, part 3: computer look matches the mockup
Status: todo
Depends on: 0534, 0535 (this branch) | Branch: claude/project-thread-819gyo
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective
The orchestrator compared `docs/tasks/screenshots-0535/app-1280.png` with `mockup-1280.png` (mockup view `prop`). The structure is right; the look is not. Fix the differences below so the page reads like the mockup: one clean column of cards with a 2-column field grid, short labels, no clutter, the "Náhled" aside on the right, the save bar bottom right.

## 2. Differences to fix (each is page CSS in the 0534/0535 blocks of `App/app/static/app2.css`, or a small template change in `apartment_form.html` / `_property_editor.html`)
1. Help toggle "Jak to funguje?" renders as a full-width bar with two chevrons. Make it the dashboard's compact form: read how `dashboard.html` + app2.css style `.ov-how` on the v2 dashboard and use the identical markup/classes; it must sit under the h1 as a small quiet link-like toggle, one chevron.
2. Setup-continue block ("Pokračovat v nastavení · 3 z 8 hotovo", coral button, underlined "Skrýt průvodce nastavením") is unstyled above the form. Move it into the aside as the first `.pv` card (title line + `btn sm` + quiet link), keep its form/inputs and behaviour.
3. "Pole označená * jsou povinná." line above the sections: on v2 give it `sr-only` (kept for screen readers, not shown).
4. Inside each section the old inner `<h2>` repeats the summary title (e.g. "Základní údaje" twice). On v2 make inner section headings that duplicate the summary visually hidden (`sr-only`); keep other inner h2 (e.g. "Čas příjezdu / Čas odjezdu", "Adresa ubytovacího zařízení") but at 14px/600 like mockup `summary b`.
5. Section body has no inner padding: fields touch the card edge. Give the details body `padding:0 16px 16px` (mockup `.fields`), and lay simple field blocks out in the mockup 2-column grid (`display:grid;grid-template-columns:1fr 1fr;gap:12px`) from 1024 px; textareas, long selects, address rows that should be full width get `grid-column:1/-1`. Labels 13px `--ink2` above the input, as mockup.
6. Help texts: every field shows a "?" button plus a long sentence inline next to the label. On v2: hide the "?" help-tip buttons (`.help-tip` trigger; keep the text), and show the hint as one small grey line under the input (12px `--ink3`, wrapping normally). Do not delete any hint text.
7. Save bar: "Uložit změny" is clipped ("Uložit zn") and the bar collides with the Havel chat bubble (bottom right). Let the buttons size to their text (`white-space:nowrap; width:auto`) and move the bar left of the bubble: `right:` = bubble width + 24 px (read the Havel bubble CSS in app2.css "v2 shared: Havel"), keep `bottom:20px`.
8. Guest card copy button shows "Zkopírováno" (copied state) on first load and is grey. Mockup: coral `btn sm` reading "Kopírovat". Find why the copied label shows initially (likely the v2 copy_button variant puts the copied text in the visible slot) and fix it in `_components.html` v2 branch; make the guest-card button `btn sm` (primary coral), list-row copy buttons stay ghost.
9. Chytrý zámek section is missing for a property without door codes. The mockup always shows it. Render the lock section always (its "set up / connect a lock" content when no lock), in mockup order between messages and fee.
10. The left sidebar background ends at ~770 px on a long page (white column stops). Check whether this also happens on the v2 dashboard with a long page; if yes it is shared: report it, do not fix. If only here, fix in the 0534 block.

## 3. Files
`App/app/static/app2.css` (0534/0535 blocks; key bump in `base.html`; `--write` the manifest), `App/app/templates/apartment_form.html`, `App/app/templates/_property_editor.html`, `App/app/templates/_components.html` (copy_button v2 branch only), `docs/design/catalog.json`, `App/tests/test_0534_property_page_v2.py` (asserts for items 2, 8, 9), section 8 tests. Report: new section "0536" in `docs/tasks/0534-report.md`. Screenshots `docs/tasks/screenshots-0536/`.

## 4. Steps
1. Items 1-4. Commit.
2. Items 5-6. Commit.
3. Items 7-10. Commit.
4. Tests; run section 6. Commit.
5. Screenshots app `/apartments/<first id>?lang=cs` at 1280 (full page) and 1024, method as in step 6 of 0535 (see its report). Commit.

## 5. Do not touch
Any JS file, routes, field names, POST handling, the wizard, other pages, shared rules (except a generic fix in the v2 form-controls block), the 0710 comparison logic. No new dependency.

## 6. Commands (from `App/`)
`export UBYHOST_REQUIRE_BROWSER=1 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers`, then
`.venv/bin/python -m pytest tests/test_0534_property_page_v2.py tests/test_0531_property_page.py tests/test_property_hub.py tests/test_property_readiness.py tests/test_validation_i18n.py tests/test_host_ux_acceptance.py tests/test_page_help_0277.py tests/test_ui_consistency.py tests/test_0300_copy_button.py tests/test_static_versions.py tests/test_0710_v2_mockup_match_browser.py tests/test_design_guardrails_browser.py -q --tb=short -rfs -p no:cacheprovider 2>&1 | tail -30`, ruff `--select E9,F63,F7,F82,F401,F841` on app tests tools, then design_lint and context_lint from the repo root. Restore stray tracked PNGs.

## 7. Acceptance
All pass, 0 skipped (shared known failures excepted and listed). Screenshot at 1280 shows items 1-9 fixed.

## 8. Stop and ask
Standing rule as in 0535 §8. Stop if a save/POST test fails or a hint text would be lost.

## 9. Report
Section "0536" in `docs/tasks/0534-report.md`. Stage by name, never `git add -A`; never commit `App/.venv`. Do not push. If out of calls, commit what passes and list what is left.
