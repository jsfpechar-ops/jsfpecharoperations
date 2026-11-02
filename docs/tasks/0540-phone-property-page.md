# 0540: property page on the phone, as the approved phone mockup
Status: todo
Depends on: 0539 (this branch) | Branch: claude/project-thread-819gyo
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective
Below 1024 px, `/apartments/<id>` must look like the phone mockup screen `nemovitost` (`grep -n 'data-s="nemovitost"' docs/design/mockup/ubyhost-phone-v1.html`, about 20 lines). Owner rule: phone screens are compact. A phone shows only what its mockup screen shows, and everything else keeps working. Today's phone page (`docs/tasks/screenshots-0536/app-390.png`) has three problems: the copy button is clipped, the save bar covers the tab bar, and the page is very long.

## 2. Context
Mockup screen, top to bottom:
- Back round button (`.top` with `button.round`).
- `.big` name, then `.sub` address.
- `.card` guest link: small grey label, the URL at 16px/700, then `btn line` "Kopírovat odkaz" with the copy icon.
- `h2.sec` "Nastavení".
- `.list` of `.row`, one per section. Each row has a `.dot g|r|n`, a `.t` with `<b>` title and `<small>` short state, and a chevron.

Build it from the existing markup, no JavaScript beyond item 6:
1. Header below 1024 px: show a `a.round` back link to `/apartments` (the 0533 list uses the shared `.top`/`.round`; copy that pattern) and hide the crumb. h1 already gets the `.big` size on phone (shared 0718 rule). Add the address as `<div class="sub">` under the h1, with `address_text` or nothing.
2. Guest card below 1024 px: the URL on its own line at 16px/700, word-break anywhere, no clipping. The copy button full width as `btn line` (shared phone class). Keep the same button element; add the class or style it in the page block. From 1024 px it stays the coral `btn sm` from 0536.
3. Section summaries as rows below 1024 px: every `details.prop-sec > summary` shows a `.dot` and a short state. Add to each summary a `<span class="dot g|r|n" aria-hidden="true">` and a `<small class="sec-state">` with the state text. Hide both from 1024 px. Hide the existing sub line (`summary small`, the mockup desktop text) below 1024 px. Style the summary like the shared `.row`: min-height 76px, 16px bold title, 14px grey state, chevron right. The states come from the same values the aside uses (read the `aside.preview` block in `apartment_form.html`; reuse its variables and keys, add new i18n keys en/cs/vi only where none fits):
   - basics: address or "Adresa chybí", dot g if address present else r.
   - police: the police state, dot from the Policie chip (r when the aside shows a problem).
   - calendars: the count, dot g if at least 1 and no errors, r if errors, n if 0.
   - messages: the section's existing sub, dot n.
   - lock: Zapnuto/Vypnuto, dot g or n.
   - fee: rate or "nepoužíváte", dot g or n.
   - archive: no dot (`n`), existing sub.
   The `h2.sec` "Nastavení" goes above the first section, phone only. Use an existing key if one says "Settings"/"Nastavení".
4. Below 1024 px, hide the `aside.preview` (the rows carry the same state), the help toggle (`.ph-hide`, shared), the required-fields note, and the setup-continue card. Move the setup-continue card above "Nastavení" as one compact `.card` with its button, or hide it if it does not fit in one card. Report which you chose.
5. Save bar below 1024 px: show it only while a section is open, using `.form:has(details[open]) .savebar` or the equivalent for this markup. Put it above the bottom tab bar: read the 0718/0720 shared phone tab bar height variable, then set `bottom: calc(<tab bar height> + env(safe-area-inset-bottom) + 8px)`. Use full-width buttons. Hide the reset button text overflow ("Zahodit změny" was clipped): let the buttons wrap or shorten with existing keys. Nothing may overlap the Havel bubble or the tab bar.
6. Default-open basics: the server opens `basics` when no section is requested, so on phone the first row is expanded. The mockup shows all rows closed. Mark that default-only open state with `data-default-open` on the `details` (only when it was opened by default, not when requested). Add a tiny init in `App/app/static/app.js`: below 1024 px (`matchMedia('(max-width:1023px)')`), remove `open` from `details[data-default-open]` once on load. Follow how other init functions in app.js claim nodes (`claimNode`). Without JS the section stays open, which is fine.
8. Dead code in `App/app/static/app.js` `initUnsavedDialog`: `document.querySelector("[data-property-views]")` is always null now, because 0539 removed that markup. Remove `property`, `propertyBase`, `SETTINGS_SECTIONS` and the `if (property && propertyBase ...)` branch in `keepsDraft`, keeping its last line. Fix the header comment that mentions the "property Settings sub-nav". Do the same step 3 commit.
7. `.dot` is not a shared class yet. Add it in the page block, scoped to the property page: 10 px circle; g `var(--ok)`, r `var(--acc)`, n `#c9c9c3`, as in the mockup.

Shared test: in `App/tests/v2_mockup.py` `property` entry, set `phone_view: "nemovitost"` and `phone_selectors` for `.big, .head h1` (or whatever the h1 matches in the overview entry's format), `.guest-card`, `.guest-card .btn`, `h2.sec`, `summary` rows, `.dot`. Read how the `properties` entry does it. For a value that differs on purpose (summary inside a card vs a bare list), add a `SELECTOR_OVERRIDES`/`BOX_OVERRIDES` entry with a reason, as 0533 did. Do not change the comparison logic.

## 3. Files
`App/app/templates/apartment_form.html`, `App/app/templates/_property_editor.html` (summary markup only, if the summaries live there), `App/app/static/app2.css` (0534 to 0539 page blocks; key bump in `base.html`; `--write`), `App/app/static/app.js` (items 6 and 8 only; key bump), `App/app/host_i18n.py`, `App/app/host_vi_i18n.py`, `docs/design/catalog.json` (new classes `dot`, `sec-state`), `App/tests/v2_mockup.py` (property entry), `App/tests/test_0534_property_page_v2.py` (asserts: every summary has a dot and a state; `data-default-open` only on default-opened basics), section 8 tests. Screenshots `docs/tasks/screenshots-0540/`: `app-390.png`, `app-320.png`, the mockup `nemovitost` at 390, and `app-390-open.png` with basics opened (for the save bar). Report: section "0540" in `docs/tasks/0534-report.md`.

## 4. Steps
1. Markup: header, guest card, summary dots and states, i18n. Commit.
2. CSS: items 1 to 5 and 7; key bump, `--write`. Commit.
3. JS items 6 and 8; key bump, `--write`. Commit.
4. Test entry and the asserts; run section 6. Commit.
5. Screenshots (temp-test method as in 0539, deleted after). Commit.

## 5. Do not touch
Routes, field names, POST handling, the wizard, other pages, the shared phone rules (read them, don't change them), the computer layout from 1024 px, the 0710 comparison logic. No new dependency.

## 6. Commands (from `App/`)
`export UBYHOST_REQUIRE_BROWSER=1 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers`, then `.venv/bin/python -m pytest tests/test_0534_property_page_v2.py tests/test_0531_property_page.py tests/test_property_hub.py tests/test_property_readiness.py tests/test_host_ux_acceptance.py tests/test_static_versions.py tests/test_0710_v2_mockup_match_browser.py tests/test_0503_page_inits_once_browser.py tests/test_0504_mixed_inits_once_browser.py tests/test_host_unsaved_changes_browser.py -q --tb=short -rfs -p no:cacheprovider 2>&1 | tail -30`, ruff `--select E9,F63,F7,F82,F401,F841` on app tests tools, design_lint and context_lint from the repo root. Restore stray tracked PNGs.

## 7. Acceptance
- At 320 and 390 the page matches the mockup screen: header, guest card, Nastavení, one row per section with its dot and state.
- No sideways scroll and no clipped button text.
- The save bar never covers the tab bar or the Havel bubble.
- 0710 `property` passes at every width, including 320/390/768.
- Tests pass with 0 skipped; list the known shared failures (0710 overview-320/390).

## 8. Stop and ask
Standing rule: tests that assert the old phone property layout may get new selectors (list each). Stop if a save/POST test fails, if a field would become unreachable on the phone, or if a shared phone rule looks wrong for this page.

## 9. Report
Section "0540" in `docs/tasks/0534-report.md`: status, tails, deviations from the mockup, section 8 list. Stage by name, never `git add -A`; never commit `App/.venv`. Do not push. If you run out of calls, commit what passes and list what is left.
