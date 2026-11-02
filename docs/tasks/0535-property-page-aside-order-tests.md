# 0535: property page on v2, part 2: section order, preview aside, tests on the new markup
Status: todo
Depends on: 0534 (this branch, report sections 0534a/0534b) | Branch: claude/project-thread-819gyo
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective
Finish the computer layout of `/apartments/<id>` against mockup view `prop` (`docs/design/mockup/ubyhost-redesign-v2.html`, `grep -n 'data-v="prop"'`): mockup section order, the "Náhled" preview aside on the right, the readiness list moved into the aside, and the old-markup tests moved to the new page.

## 2. Context
- Read the 0534 report sections 0534a and 0534b first: what exists, deviations, failing tests.
- Order (mockup): basics, police, calendars, messages, lock, fee, then archive last. Calendars has its own forms, so it stays after the settings `<form>` in the DOM. Show it in mockup order with CSS: the left column is a flex column (`display:flex;flex-direction:column`), the settings `<form>` gets `display:contents` so its children join the column, and each section `details` gets `order` (basics 1, police 2, calendars 3, messages 4, lock 5, fee 6, archive 7, lock-account 8). Tab order then differs from visual order for calendars only; note it as a deviation.
- Archive: move the archive section out of the basics group into its own details `sec-archive` (it is already keyed `property_page.sec.archive.*`).
- Aside (mockup `.form` grid `minmax(0,1fr) 300px`, `.preview`, `.pv`, `.pv .r`; mockup CSS lines ~51-63): `<aside class="preview"><h3>Náhled</h3>` with two `.pv` cards built from data the template already has (read `_property_overview.html`, the health cards `hc.*`, `feeds`, `feed_errors_count`, `door_code`, `apartment.stay_fee_rate_czk`, `address_text`): card 1 "Základní údaje" rows Název, Adresa; card 2 "Napojení" rows Policie (pill ok/bad: use the page's police health state), Kalendáře (count, red text if errors), Zámek (on/off), Poplatek (rate or "nepoužíváte"). Each row links to its section (`#sec-<key>`). Then the readiness block from `_property_overview.html` (the checklist the failing `tests/test_property_readiness.py` asserts: invite list, reporting list, validation reason) as a third `.pv` "Co chybí" shown only when something is missing. Move that markup, do not rewrite its logic. New i18n keys only where no existing key fits.
- After this, `_property_overview.html` is no longer used: delete it and any keys/CSS only it used (grep each).
- Below 1024 px the aside goes under the sections (one column); the phone layout itself is 0536.
- Phone overflow from 0534b: at 360 px "28 buttons past the right edge" on the property page (test_host_ux_acceptance fits test). Fix with page CSS (likely `.fields` grid to one column below 640 px, long inputs `min-width:0`, button rows wrapping) so the page fits at 320-1023 px without sideways scroll.
- 0710 PAGES entry `property`: paths in `App/tests/v2_mockup.py` are concrete. Add a `{first_property}` placeholder in PAGES paths with ONE mechanism shared with the stays thread: in `test_0710_v2_mockup_match_browser.py` build the URL as `spec["path"].format(**placeholders)` where `placeholders` holds `first_property` (first apartment id of the seeded host) and, if the stays thread's `stay_id` is already in the file, `stay_id` too. Do not add a second URL helper. Agreed with the test owner. Entry: name `property`, path `/apartments/{first_property}`, `view: "prop"`, selectors `.crumb`, `main h1`, `.guest-card`, `details`, `summary b`, `summary small`, `.preview h3`, `.pv`, `.pv .r`, `.savebar .btn`, `phone_view` the same way `menu` marks no phone screen (0536 adds it).

## 3. Files
`App/app/templates/apartment_form.html`, `App/app/templates/_property_editor.html`, `App/app/templates/_property_overview.html` (delete at the end), `App/app/static/app2.css` (0534 block; key bump in `base.html`; `--write` the manifest), `App/app/host_i18n.py`, `App/app/host_vi_i18n.py`, `docs/design/catalog.json`, `App/tests/v2_mockup.py` (property entry + placeholder), `App/tests/test_0710_v2_mockup_match_browser.py` (placeholder resolve only), `App/tests/test_0534_property_page_v2.py` (order + aside asserts), `App/tests/test_validation_i18n.py` (restore the positive readiness asserts, now in the aside), section 8 tests. Report: new section "0535" in `docs/tasks/0534-report.md`. Screenshots `docs/tasks/screenshots-0535/`.

## 4. Steps
0. After the 0719 merge, 0710 properties-320/390 fail on side margins: `.big, .head h1` and `.card.prop` margin-left/right app 0px vs mockup 20px. 0719 moved the 20 px side room to `body.v2 .main` padding on purpose. Add these two selectors to `SELECTOR_OVERRIDES` in `App/tests/v2_mockup.py` the same way 0719 overrides its own phone cards (same reason text). Run 0710; properties must be green again. Commit `0535 step 0`.
1. Order + archive details + `display:contents` form + flex order CSS. Commit.
2. Aside with the two `.pv` cards and the readiness card; delete `_property_overview.html` and its now-dead keys/CSS. Commit.
3. Phone/tablet overflow fix. Commit.
4. Tests: test_0534 (visual order via the `order` CSS is fine to assert by computed style or DOM ids), restore test_validation_i18n positives, `tests/test_property_readiness.py` pointed at the aside (selectors only), `tests/test_host_ux_acceptance.py` tests that click `.property-tabs` rewritten to open the matching `<details>` (summary click) or to follow the old `?view=…&section=…` links and assert the right details is `open`; the operator-name test (line ~478) pointed at where the operator name now shows. Section 8 rule applies. Commit.
5. PAGES `property` with the placeholder; run 0710 until `property` passes at 1024, 1280, 1440. Commit.
6. Screenshots app `/apartments/<id>?lang=cs` and mockup `prop` at 1280 and 1024. Commit.

## 5. Do not touch
Any JS file, routes, form field names and POST handling, the wizard, other pages, the 0532/0533 blocks, shared rules other than the v2 form-controls block (fix generic control issues there if needed), 0710 comparison logic (only the placeholder). No new dependency.

## 6. Commands (from `App/`; browser tests SKIP SILENTLY without the env vars)
`export UBYHOST_REQUIRE_BROWSER=1 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers`, then
`.venv/bin/python -m pytest tests/test_0534_property_page_v2.py tests/test_0531_property_page.py tests/test_property_hub.py tests/test_property_readiness.py tests/test_validation_i18n.py tests/test_host_ux_acceptance.py tests/test_no_dead_internal_links.py tests/test_static_versions.py tests/test_0710_v2_mockup_match_browser.py -q --tb=short -rfs -p no:cacheprovider 2>&1 | tail -30`
then `grep -l "/apartments/" tests/*browser*.py` and run those, then `.venv/bin/ruff check app tests tools --select E9,F63,F7,F82,F401,F841 | tail -5`, then from the repo root design_lint and context_lint. Restore tracked PNGs a run rewrites outside `screenshots-0535/`. Known not yours: test_host_i18n cookie/Vietnamese "no such table" (pre-existing), 0710 failures on other pages.

## 7. Acceptance
All pass, 0 skipped, except the known items. 0710 passes for `property` at 1024/1280/1440 and for `properties` everywhere it passed before.

## 8. Stop and ask
Standing rule: tests that assert the removed property tabs, views, settings groups, overview health cards or old class names on the property page may be updated to the new markup (assertion/selector only; list each). Stop if a save/POST test fails, an old link anchor no longer resolves, or a test about another page fails.

## 9. Report
Section "0535" in `docs/tasks/0534-report.md`: status, tails, section 8 list, deviations. Stage by name, never `git add -A`; never commit `App/.venv`. Do not push. If you run out of calls, commit what passes and list exactly what is left.
