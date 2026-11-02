# 0532: Ubytování list rebuilt on the v2 shell from the mockup
Status: todo
Depends on: 0530 (chips data, this branch), 0705-0710 (v2 shell, app2.css, shared mockup test; merged into this branch from claude/project-thread-50hyv5) | Branch: claude/project-thread-819gyo
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective
Owner decision 2026-11-01 14:33: pages are rebuilt from the approved mockup's own HTML and CSS, not by restyling old components. Rebuild `/apartments` exactly like the mockup view `props` in `docs/design/mockup/ubyhost-redesign-v2.html` (search `data-v="props"`), the way 0706 rebuilt the Overview (`App/app/templates/dashboard.html`, read lines 1-20 and the `<table>` near line 94 as the pattern). Then add the page to the shared mockup test and make it pass at 320, 390, 768, 1024, 1280 and 1440 px.

## 2. Context
- Template `App/app/templates/apartments.html` (0530 version: chips in `row.chips`, each `{key, state, href}`, state `ok|bad|off`; `row.link_url`; empty states). Route unchanged.
- v2 opt-in: `{% set v2 = true %}` at the top plus empty `page_title`, `meta`, `primary_action`, `secondary_actions`, `tabs`, `toolbar` blocks, as dashboard.html does. Only `tokens.css` + `App/app/static/app2.css` load on v2 pages; old classes (`ui-*`, `table-cards`, `panel`, `list-cards`) have no styles there.
- Mockup markup to copy: `<div class="head"><div><h1>…</h1><p class="sub">…</p></div><a class="btn" href="/apartments/new">…</a></div>` then `<div class="card"><table><thead>…</thead><tbody>…</tbody></table></div>`. Columns: Name, Address, Setup, (copy link button), (row menu). Setup cell: `<div class="setup">` with `<a class="st g|r|n" …>` per chip (ok → `g`, bad → `r`, off → `n`), keep `data-setup-chip`, `data-state`, the sr-only state text and the hrefs.
- Mockup chip CSS is not in app2.css yet: copy the mockup's `.setup{…}`, `.st{…}`, `.st.g`, `.st.r`, `.st.n` rules (mockup lines ~72-74) to the end of app2.css, with a `.st` `text-decoration:none`.
- Copy link: `copy_button` in `_components.html` (~line 302) renders old `ui-btn` classes, unstyled on v2. Use a plain `<button class="btn sm ghost" type="button" data-copy="guest-url-{{ id }}" data-copy-label=… data-copied-label=…>` next to a hidden `<input class="sr-only" id="guest-url-{{ id }}" value="{{ row.link_url }}" readonly tabindex="-1" aria-hidden="true">` (same data attributes as the macro, so the existing copy JS works). Tap target at 390 px must be ≥ 44 px high (the guardrail test checks it): add a phone rule in app2.css if `.btn.sm` is lower.
- Row: keep `class="clickable-row" data-href=… tabindex="0" role="link" aria-label=…`, the name link to `/apartments/<id>`, the inactive marker as `<small>`, and the existing `row_menu_begin()/row_menu_end()` menu (v2 styles exist for it).
- Remove from this page: the section tabs (Ubytování / Firma; the business page stays reachable from Settings), the count toolbar, the "Jak to funguje?" how-box, the `row_open` "Otevřít" button, the onboarding banner only if dashboard.html also dropped it (check; else keep it).
- Copy: sub line = new key `apartments.sub` en "Green done · red missing · grey not used. Click a row.", cs "Zelená hotovo · červená chybí · šedá nepoužíváte. Klikněte na řádek.", vi "Xanh: xong · đỏ: thiếu · xám: không dùng. Bấm vào một dòng."; button = existing `apartments.add`.
- Shared test: `App/tests/v2_mockup.py` `PAGES` and `App/tests/test_0710_v2_mockup_match_browser.py`. Add one entry: name `properties`, path `/apartments`, view `props`, selectors for `.side .nav.on`, `.head h1`, `.head .sub`, `.head .btn`, `main table th`, `main table td`, `.setup .st`, `tbody tr .btn.sm.ghost`. The test's seed must give the host at least two properties (read how the overview entry is seeded; extend the seed, not the comparison rules).

## 3. Files
Edit `App/app/templates/apartments.html`, `App/app/static/app2.css` (append; bump its `?v=` key in `base.html`), `App/app/host_i18n.py`, `App/app/host_vi_i18n.py`, `App/tests/v2_mockup.py` (PAGES and seed only), `App/tests/static_versions.json` (via `--write`), `App/tests/test_0530_properties_chips.py` (selectors only). Screenshots `docs/tasks/screenshots-0532/`. Report `docs/tasks/0532-report.md`.

## 4. Steps
1. Template rebuilt as above. Commit `0532 step 1`.
2. app2.css chip rules and the phone tap-target rule; bump key; `tests/test_static_versions.py --write`. Commit `0532 step 2`.
3. Copy keys. Commit `0532 step 3`.
4. Shared test entry; run it until it passes. Commit `0532 step 4`.
5. Run section 6; update existing tests under section 8. Commit `0532 step 5`.
6. Screenshots of `/apartments?lang=cs` at 390, 768 and 1280 plus the mockup `props` view at the same widths (the 0710 test can save them; check how) into `docs/tasks/screenshots-0532/`. Commit `0532 step 6`.

## 5. Do not touch
Any JS file, the route, the property page and its partials, the wizard, other templates, old stylesheets, the 0710 comparison logic. No new dependency.

## 6. Commands (from `App/`; browser tests SKIP SILENTLY without the env vars)
`export UBYHOST_REQUIRE_BROWSER=1 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers`, then:
`.venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py tests/test_0530_properties_chips.py tests/test_properties_table_chips.py tests/test_host_properties_navigation.py tests/test_host_ux_acceptance.py tests/test_operator_naming.py tests/test_status_colours.py tests/test_0300_copy_button.py tests/test_no_dead_internal_links.py tests/test_static_versions.py -q --tb=short -rfs -p no:cacheprovider 2>&1 | tail -30`
then `.venv/bin/python -m pytest tests/test_design_guardrails_browser.py tests/test_host_list_page_layout_browser.py tests/test_0285_rows_browser.py tests/test_0284_states_browser.py tests/test_0385_phone_card_open_browser.py tests/test_onboarding_wizard_browser.py tests/test_0502_page_inits_once_browser.py -q --tb=short -rfs -p no:cacheprovider 2>&1 | tail -30`
then from the repo root `python3 scripts/design_lint.py | tail -3` and `python3 scripts/context_lint.py 2>&1 | tail -3`. If a run rewrites tracked PNGs outside `screenshots-0532/`, `git checkout -- <those paths>`.

## 7. Acceptance
All pass, 0 skipped. The 0710 test passes for `properties` at all six widths. `git diff --stat HEAD~N` (your commits) lists only section 3 files plus section 8 tests.

## 8. Stop and ask
Standing rule: an existing test that asserts old list markup on `/apartments` (`ui-ph`, `ui-tabs`, `table-cards`, `properties-table`, `row-open`, `ui-badge` on chips, `lc-properties`, the count line, the how-box) may be updated to the v2 markup (that assertion only; list each in the report). Stop if a test about another page fails, or if the 0710 comparison needs a rule change rather than a page fix.

## 9. Report
`docs/tasks/0532-report.md`: status, tails, diff stat, screenshot paths, deviations. Stage files by name, never `git add -A`; `App/.venv` must never be committed. Do not push.
