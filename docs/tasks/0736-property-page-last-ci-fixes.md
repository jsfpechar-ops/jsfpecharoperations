# 0736: property pages: last CI fixes before merge
Status: todo
Depends on: 0735 (merge done) | Branch: claude/project-thread-819gyo
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective
Fix the failures left after 0547 so CI is green on the properties PR.

## 2. Context (orchestrator decisions)
1. `tests/test_host_unsaved_changes_browser.py::test_save_bar_discard_changes_button` line ~283 (`'Zapnuto' == ''`): `#sec-lock` is closed at load, so `inner_text()` is "". Read `loaded_status` after `page.locator("#sec-lock > summary").click()`. Test only.
2. `tests/test_property_navigation_browser.py` line ~464: after save from `section=automation`, the page returns to `section=reporting` (automation opens police, and police maps to reporting). Expect `section=reporting`. Test only.
3. `tests/test_a11y_guard_browser.py` on property pages:
   - Heading skip: `h3.property-section-title` right after `h1`. In `_property_editor.html` (and any other property partial with it), make those `h2` with the same class; if the class has a size rule, check the look stays the same.
   - `setup-continue` "Pokračovat" (`ui-btn-primary`, dark text on coral, contrast 3.72): on v2 in the page block of `App/app/static/app2.css`, give it `color:#fff` and a background that reaches 4.5:1 (use `var(--acc-text)` or the darker coral already in tokens.css; `grep -n acc tokens.css`).
   - Toast close 24x21 on smart-locks: make `.toast-stack .toast > [data-toast-close]` at least 24x24 at every width on v2 (the 44 px phone rule already exists near the top of app2.css).
4. Guest card overflow without JS at 360/390 (`div.guest-btns` and its copy buttons reach x=420). Without JS the copy buttons are wider; make `.guest-btns` children `min-width:0` and the buttons `max-width:100%` with text wrapping, below 1024. This must fix `tests/test_onboarding_wizard_browser.py::test_wizard_polish_and_overview_cards` [False-360-en, False-360-cs, False-390-cs].
5. `tests/test_0252_touch_sweep_browser.py` noCue on `/apartments` at ipad1024, 1180, desk2000 (demo rows). Read what "cue" the test needs (a chevron, an arrow or a hover style on a tappable row) and add it to the `/apartments` row in the page block, matching the computer mockup `props` view (`docs/design/mockup/ubyhost-redesign-v2.html`). If the mockup row has no cue, change the test to accept the v2 row (`a.card.prop` or the table row link) and say so.
6. `tests/test_host_property_controls_browser.py` line ~448: `#calendar-add #label_other` is not visible because `#sec-calendars` is closed. Open it first (`page.locator("#sec-calendars > summary").click()` or load `?view=bookings`). Test only.
7. `tests/test_0541_property_page_phone_browser.py`: add browser asserts for the 0547 behaviours: switch status text changes on toggle (seed a door-code lock as `tests/test_door_code_window_browser.py` does), an invalid required field in a closed section opens that section on submit, `?add_calendar=1` shows `#calendar-connect` without `is-collapsed`, and after save from the opened lock section the URL has `section=lock`.
8. `python3 scripts/design_lint.py`: fix any error it reports on our files (add a class to `docs/design/catalog.json`, or fix the rule). Report errors in other pages' files as not ours.

## 3. Files
The tests above, `App/app/templates/_property_editor.html` (heading level only), `App/app/static/app2.css` (page block; key bump in `App/app/templates/base.html`, then `--write`), `docs/design/catalog.json`.

## 4. Steps
1. Items 1, 2, 6 (tests). Commit.
2. Items 3, 4, 5 (CSS and heading); key bump, `--write`. Commit.
3. Items 7, 8. Commit.
4. Run section 6. Commit the report.

## 5. Do not touch
Routes, JS, other pages, the Overview and menu files. No new dependency.

## 6. Commands (from `App/`)
`export UBYHOST_REQUIRE_BROWSER=1 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers`, then each changed test file with `-k "not webkit" -q --tb=line -rfs -p no:cacheprovider 2>&1 | tail -8` (webkit is not installed; say so), then `tests/test_0534_property_page_v2.py tests/test_static_versions.py tests/test_0710_v2_mockup_match_browser.py tests/test_0503_page_inits_once_browser.py tests/test_0504_mixed_inits_once_browser.py`. Ruff `--select E9,F63,F7,F82,F401,F841` on app tests. From the repo root: design_lint and context_lint.

## 7. Acceptance
Every file named passes on chromium with 0 skipped, apart from not-ours failures listed with their failing line. The property page and list look the same at 390 and 1280 (one screenshot each in `docs/tasks/screenshots-0736/`, `?lang=cs`).

## 8. Stop and ask
Stop if a fix needs a route or JS change, or a save/POST does not save.

## 9. Report
Section "0736" at the end of `docs/tasks/0536-report.md`. Stage by name, never `git add -A`; never commit `App/.venv`. Do not push. Hand back with SubagentHandback; never post to the user.

## 10. Orchestrator answers after run 1 (1de31cd: item 2 done)
- Report file: keep `docs/tasks/0736-report.md`.
- Item 1: the test host has the door code enabled (the JS sets "Enabled" after reset, which is right). The open question is why `#door_codes-status` reads '' at load even with `#sec-lock` open. Diagnose first with one `page.evaluate` after the summary click: `document.querySelectorAll('#door_codes-status').length`, the element's `outerHTML`, `getComputedStyle(el).display` and `visibility`, and `el.closest('details')?.open`. Then: if the server text is there but the element is not rendered (for example a second `#sec-lock` or a closed parent), fix the cause in the template or the page CSS; if the status was meant to stay hidden while it equals the saved state, compare with `text_content().strip()` instead. Write what you found in the report.
- Item 6: `#label_other` must be hidden until "other" is picked. Find how the old page hid it: `git grep -n label_other App/app/static App/app/templates`, and `git show 7b3cee4 -- App/app/static/app.js | grep -n -i 'other' | head`. If the code that toggles it was removed in 0539, put that part back in `initPropertyPage` (a JS change is allowed for this one item only). If it uses `hidden` or a class that v2 does not style, add the page CSS. Then triage `test_property_and_operator_controls_render_and_work_in_browser` with `--tb=short`: fix it if it is our markup or flow; list it as not ours otherwise.
- Then continue with items 3, 4, 5, 7, 8 and section 6.

## 11. Orchestrator answers after run 2 (bec40cd, 181f2cd)
- Item 1 focus: this is a real bug. In `App/app/static/app.js` (~2111), add `.savebar [type=submit]` to the selector that gets focus after discard (keep the old selectors only if another page still uses them: `git grep -n 'host-property-save\|class="actions"' App/app/templates | head`; drop the dead one). JS change allowed for this line only; bump the app.js key in `base.html` and `--write`.
- Item 6 line ~232: the v2 properties list has no section tabs (the computer mockup `props` view has none). Change the test: on `/apartments` assert `.ui-tabs` count is 0 and drop the `aria-current` line. Keep the property page asserts below it.
- Then items 3, 4, 5, 7, 8, section 6, screenshots.

## 12. More CI failures (run on 0681ce3), orchestrator decisions
- `tests/test_ui_consistency.py::test_the_copy_button_keeps_its_icon_when_it_confirms`: since 0542 the v2 copy button keeps its copy icon (phone mockup). Assert `<svg` is in the button in both branches; drop the v2 "text only" comment.
- `tests/test_a11y_guard_browser.py::test_keyboard_focus_is_visible_and_not_covered`: `focus-not-visible` on `button "Copy link"` at properties 1280 (4 findings). Give `body.v2 .btn.copy-btn:focus-visible` a visible outline in the page block (`outline:2px solid #d0452d;outline-offset:2px`, as the v2 form controls use).
- `tests/test_0396_leon_opt_in_browser.py:40` (`test_overview_card_and_leon_page_at_390px`): the aside `a.r[data-leon-card="off"]` is hidden below 1024 by design. Check the card at 1280 (set the viewport before that part), keep the 390 checks of the Leon page itself.
- `tests/test_onboarding_wizard_browser.py:993`: `.host-property-card-static` is gone; scroll `section.guest-card` instead.
- `tests/test_havel_browser.py:138` (`test_phone_launcher_and_sheet`, `/settings` `[data-sheet-open='more-sheet']` click times out): passes on main. Run it on this branch with `--tb=short`, find what covers or hides the button (our CSS or the merge), fix that; if it is not ours, list it.

## 13. Shard 4 failures (0681ce3), orchestrator decisions
- `tests/test_design_guardrails_browser.py:325` (`test_setup_checklist_is_a_padded_card`): the overview cards are now the aside rows. Count `aside.preview .pv .r .dot` (at least 4) instead of `.host-property-grid ... .host-property-card-dot`. Keep the "no separate box" assert; point the `details` check at whatever now carries `[data-setup-status]` on the v2 page (read the template), and say what you chose.
- `test_every_host_page_passes_the_layout_guard` (174 findings, all on the property page at 1280 "open"):
  - `button-heights-differ`: the guest-link card row has `button.btn.sm.ghost` Copy (49 px) next to `a.ui-btn.ui-btn-quiet.ui-btn-compact` "Preview as a guest" (24 px, unstyled on v2). In the property templates, give that link the v2 classes the Copy button uses (`btn sm ghost`), so both are the same height.
  - `field-button-misaligned`: find the guard (`grep -rn field-button-misaligned App/tests | head -3`) and read how it pairs a field with a button. If the pairs are a field and a button of the fixed `.savebar` or the sidebar (`button.nav "Log out"`), that is a false pair: those are fixed and never share a row with a field. Make the guard skip elements inside `position:fixed` or `sticky` ancestors only if the guard has no such rule yet and the change is one line; otherwise list each real pair with its two selectors and stop.
- `test_every_host_page_on_phone_ipad_and_desktop` is item 5 (noCue on `/apartments`).

## 14. Run 4 scope
Do these in order, commit after each: (a) section 12; (b) the a11y heading findings: print the 12 `heading-level-skipped` findings (selector and levels) and fix them in our property templates (headings must go 1, 2, 3 without skips; a section summary title is h2, a heading inside a section is h3); (c) the guest-card overflow at 360/390 on `?view=settings&section=guests`: probe with one `page.evaluate` that lists every element whose `getBoundingClientRect().right > innerWidth` (tag, class, id, width), then fix the widest one in the page CSS; (d) section 13; (e) items 7, 8 and section 6. Revert any screenshot PNG a test rewrites outside `docs/tasks/screenshots-0736/` (`git checkout -- <path>`); never commit those.

## 15. Run 5 scope (after run 4: a, b done)
- (c) The failing cases are the `javascript=False` ones (`[False-360-en]`): the page overflows only with JS off. Probe in a context with `java_script_enabled=False` at 360 on `/apartments/<id>?view=settings&section=guests&lang=en`, list the elements past `innerWidth`, fix the widest in the page CSS (it must not rely on JS-set classes or `scripting: enabled`). Then run the wizard file with `-k "wizard_polish or review_fixes"`.
- Then section 13, items 7 and 8, section 6, and the two screenshots. Same PNG rule as section 14.

## 16. Run 6 scope (after run 5: c done)
1. Close the `@media (scripting: enabled) {` block in `App/app/static/app2.css`. It came from main (Overview, brief 0700s) and never closes, so every later rule only applies with JS on. Its last inner rule is the `@media (prefers-reduced-motion: reduce) { @view-transition ...; ::view-transition-group ... }` block; add the single `}` right after that inner block's `}` and before the next top-level `@media (prefers-reduced-motion: reduce) { body.v2 *, ...` line. Check with a brace count that depth is 0 at the end of the file. Key bump, `--write`. Then run `tests/test_0710_v2_mockup_match_browser.py tests/test_0541_property_page_phone_browser.py tests/test_onboarding_wizard_browser.py -k "not webkit and (wizard_polish or 0710 or 0541 or overview or property)"`, and say which no-JS rules now apply that did not before (any 0700-0729 Overview rule that changes no-JS layout: list it, do not change it).
2. `tests/test_onboarding_wizard_browser.py:995` (`test_review_fixes_in_the_browser`, `a[href*='section=guests']` count 0 on `?view=overview`): the v2 overview rows link to `#sec-messages`. Count `a[href="#sec-messages"]` instead (keep the check that it exists).
3. Section 13.
Then stop and report; items 7, 8, section 6 and the screenshots are run 7.

## 17. Run 7 scope (after run 6: brace closed)
1. Line 995: the check means "the overview shows the guest link". On v2 that is the guest card's copy button. Assert `page.locator("section.guest-card [data-copy='property-guest-url']").count() >= 1`. Run `-k "review_fixes"`.
2. Section 13.
Then stop and report; items 7, 8, section 6 and the screenshots are run 8.

## 18. Run 8 scope (after run 7)
1. Setup checklist test (`test_design_guardrails_browser.py:325`): on v2 the setup health is the green/red `.dot` on each section summary (owner: setup shown as green/red statuses). Count `details.prop-sec > summary .dot` (at least 4). Keep the other two asserts, pointed at the v2 elements.
2. Field-button pairs at 1280 "open": in the 2-column field grid from 1024 px, a lone action button (Generate a new PIN, Add signature, Generate a new link, the Copy next to `checkout_hour`) sits in a grid cell beside a field. Read the markup of each and, in the page block, make that button's wrapper span the full grid row (`grid-column:1/-1`) so it sits under its fields, left-aligned. Check that 0710 `property` still passes at 1280 and 1440.
3. Button heights: measure why the Copy button is 48 px (`getComputedStyle` min-height, padding). Make `.btn.sm` buttons and links in the same row the same height, using the copy button's value; do not shrink the copy button below 44 px on phone.
Then stop and report; items 7, 8, section 6 and the screenshots are run 9.
