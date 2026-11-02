# 0541: phone property page: fixes after the 0540 screenshots, then finish 0540 steps 4 and 5
Status: todo
Depends on: 0540 (this branch) | Branch: claude/project-thread-819gyo
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective
The orchestrator compared `docs/tasks/screenshots-0540/app-390.png` and `app-390-open.png` (untracked, taken after 0540) with `mockup-390.png`. Fix the differences below, then do 0540 step 4 (test entry and asserts) and step 5 (screenshots).

## 2. Context
Differences, all below 1024 px:
1. The guest-card copy button is an empty outlined box with no label. The 0536 copy-label CSS (`body.v2 .copy-btn ...`, `copy-label-default`) and the 0540 `btn line` style together hide the text. The button must read "Kopírovat odkaz" with the copy icon, ink text, full width, as in the mockup. Check 1024+ still shows the coral `btn sm`.
2. The help toggle "Jak to funguje?" still shows on the phone. 0536 scoped `body.v2 .ov-how[data-how="property"]{display:inline-block}`, and it beats the shared `.ph-hide`. Add `display:none` for it below 1024 px in the page block.
3. Basics is still open on load. `initPhoneDefaultClosed` (0540 step 3) does not close it before the page settles. Check that it is called in the init list where the other inits run, that it runs on DOMContentLoaded, and that the selector matches `details[data-default-open]`. Test it with a browser assert in step 4.
4. Rows should look like the mockup list, not cards. Below 1024 px, each `details.prop-sec` loses its card border, radius, shadow and background. Rows are separated by a 1px `var(--line)` bottom border (none on the last one). Summary padding is `12px 0` and the min-height 76px stays. The dot sits at the left edge, as the mockup `.row`. An open section shows its fields under the row, with no card.
5. The save bar shows "Zahodit změny" (reset) while nothing changed. Its `hidden` attribute is overridden by a `display` rule. Add `body.v2 .savebar [hidden]{display:none}`. Also lay out the bar on phone as one row: Zrušit (ghost) and Uložit (coral), equal width, 8 px gap. When reset is visible it replaces Zrušit, so both are never shown at once below 1024 px. Use `:has([data-unsaved-reset]:not([hidden]))`, or keep three in one row if that is simpler, but always in one row.
6. The address `.sub` under the h1 is empty for a property without an address. Then render nothing, with no empty gap. Check the markup does not leave an empty element with margin.

## 3. Files
`App/app/static/app2.css` (0540 block; key bump in `base.html`; `--write`), `App/app/static/app.js` (item 3 only, if needed; key bump), `App/app/templates/apartment_form.html` and `_components.html` copy_button v2 branch (only if item 1 needs markup), `App/tests/v2_mockup.py` (property entry: `phone_view: "nemovitost"`, phone selectors as in brief 0540 section 2), `App/tests/test_0534_property_page_v2.py` (asserts from brief 0540 section 3, plus a browser assert that at 390 px no `details.prop-sec` is open after load when the URL has no section), `docs/design/catalog.json`. Screenshots `docs/tasks/screenshots-0540/` (overwrite the untracked ones): `app-390.png`, `app-320.png`, `app-390-open.png` (after clicking `#sec-basics > summary`, viewport only), `mockup-390.png`. Use the temp-test method from 0539 and `_open_phone` from `tests/test_0710_v2_mockup_match_browser.py` for the mockup. Report: section "0541" in `docs/tasks/0534-report.md`.

## 4. Steps
1. Items 1, 2, 4, 5, 6 CSS (and markup if needed); key bump, `--write`. Commit.
2. Item 3. Commit.
3. Test entry and asserts; run 0710 for `property` at all widths and test_0534. Commit.
4. Screenshots; look at them yourself and confirm items 1 to 6 in the report. Commit.

## 5. Do not touch
Routes, field names, POST handling, other pages, shared rules, the computer layout from 1024 px. `tests/test_host_unsaved_changes_browser.py` belongs to another brief; do not touch it. No new dependency.

## 6. Commands (from `App/`)
`export UBYHOST_REQUIRE_BROWSER=1 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers`, then `.venv/bin/python -m pytest tests/test_0534_property_page_v2.py tests/test_0531_property_page.py tests/test_static_versions.py tests/test_0710_v2_mockup_match_browser.py -q --tb=line -rfs -p no:cacheprovider -k "property or not v2_page" 2>&1 | tail -20`, ruff `--select E9,F63,F7,F82,F401,F841` on app tests tools, design_lint and context_lint from the repo root.

## 7. Acceptance
Screenshots show items 1 to 6 fixed. 0710 `property` passes at 320, 390, 768, 1024, 1280 and 1440. test_0534 passes with 0 skipped.

## 8. Stop and ask
Stop if a save/POST test fails, if a field becomes unreachable on the phone, or if a shared rule must change.

## 9. Report
Section "0541" in `docs/tasks/0534-report.md`. Stage by name, never `git add -A`; never commit `App/.venv`. Do not push. If out of calls, commit what passes and list what is left.
