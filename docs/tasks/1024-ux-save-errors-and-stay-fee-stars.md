# 1024: property editor: Stay fee stars, failed-save summary that opens and focuses the first error, clear Saved

Status: todo
Depends on: none | Base: `origin/main` (NOT the wolt branch) | Branch: `claude/save-errors` | No PR (push the branch only; the orchestrator opens it)
Executor: Haiku 5.5 may stall on step 4 (JS) and step 6 (browser tests); if it reaches 30 tool calls before step 7, hand over per workflow "at the cap". A bigger model (Sonnet 5.5) is recommended for this brief. Fits one session: 30 tool calls, 60k tokens (tight)

## 1. Objective

Josef's report (screenshots, property editor, Stay fee section):

(a) The footer hint "Add the variable symbol, the council account and the office name to create the report and the payment QR" asks for details, but Variable symbol, Council account and Council office name have no red star.
(b) When Save fails, the error ("This account number does not add up...") shows only far down inside the open Stay fee accordion. The host must scroll to find it and may think the property was saved. In the screenshot the error also sits between Variable symbol and Council account, so it reads as the Variable symbol's error.

Required behaviour:
1. Stars (and `aria-required="true"`) on exactly the stay-fee fields the app cannot continue without, in the editor (not the wizard, which already uses real `required`).
2. The account error renders directly under the Council account input, not above its label.
3. A failed save shows a summary near the Save bar ("Not saved: fix N fields"), opens the accordion holding the first error, scrolls to that field and focuses it. Server renders the section `<details open>` and the summary, so without JavaScript the page still shows the state; JS only adds scroll and focus.
4. A successful save shows a clear "Saved" confirmation.
5. Tests prove: a valid save persists; an invalid save stores nothing and never shows a success message.

## 2. Context (decided by the orchestrator; do not re-audit)

Facts found in the code (anchors; if one is gone, STOP):

- `App/app/templates/_stay_fee_fields.html`: `field_label(id, text, help, false, '', fee_required)` already takes a 6th `required` argument that draws `<span class="req-star">`; `fee_required` is true only in the setup wizard, so the editor shows no stars. Fields: `stay_fee_rate_czk` (1), `stay_fee_vs` and `stay_fee_council_account` (2), `stay_fee_authority_name` (3). The account error is `<p class="err-text small" id="stay-fee-account-error" role="alert">` rendered between the VS `.field` and the account `.field` (guarded by `{% if fee_account_error %}`).
- Server rule behind the footer hint, `App/app/templates/_property_editor.html` (grep `missing_warn`, about line 405): shown when `apartment.stay_fee_rate_czk > 0` and any of `stay_fee_vs`, `stay_fee_council_account`, `stay_fee_authority_name` is blank. `App/app/stay_fee.py` `report_issues` blocks a report on no VS (`stay_fees.issue.no_vs`) and no authority name (`stay_fees.issue.no_authority`); the account feeds the payment QR. The save itself does NOT refuse blank values (`apartment_update` saves and says what is missing), so these three are "needed to continue" only when the rate is above 0. The rate field is needed always (a stay fee without a rate is no fee); it already has `min=0 max=50`.
- Stars logic in the editor: star the three fields only while the rate is above 0. Server render: pass `required` to `field_label` as `apartment.stay_fee_rate_czk > 0` when not `fee_required`; JS toggles the star span and `aria-required` live when the rate input changes (small block in `app.js`). Use `aria-required="true"`, NOT the HTML `required` attribute: native `required` would block saving any other editor section for hosts whose fee is half-filled today. `tests/test_required_stars.py::test_every_star_has_a_required_control` accepts `aria-required` (`"aria-required" in t`).
- Save route: `POST /apartments/{id}` `apartment_update` in `App/app/routes/admin.py` (~line 2418) calls `_save_apartment_form`; refusals return a rendered page with status 400 and nothing written: `_refuse_apartment_save` (~2218; carries `operator_error`, `address_errors`, `shared_time_error`, `lock_times_error`) and `refuse_fee_save` (~2288; fee errors `link_error`, `operator_account_error`, `rate_error`, `setup_flash`, else account invalid). Both go through `_render_apartment_detail(..., extra={...})`; `refuse_fee_save` already puts `flash_error` and `settings_section: "reporting"` in `extra`. Success redirects with `?msg=` (`flash.apartments.saved` or `flash.apartments.saved_ready`: "Saved. This property is ready to report.").
- Accordions: `<details class="prop-sec" id="sec-basics|messages|police|fee|calendars|lock">` in `_property_editor.html`, opened by `inline_flash_section` or `settings_section`. Error elements today: `#controller-message`, address errors (basics), shared time error (basics), `#door-code-times-error` (lock), `#stay-fee-account-error`, `#stay-fee-guest-operator-error`, `#stay-fee-link-error`, `#stay-fee-rate-warning` (fee).
- Save bar: `<div class="savebar save-on-dirty" data-for="property-settings-form">` at the end of `_property_editor.html` (~line 502). JS: `initSectionNotice` in `App/app/static/app.js` (~line 2495: finds `[data-section-notice]`, `scrollIntoView({block:"center"})`, `focus({preventScroll:true})`; registered through `claimNode` and page hooks, so it works with Turbo) and the sticky-bar `keepClear` focusin handler (~line 2211). Reuse these patterns; do not add a library.

Design choices made here (flag to owner in the report):

- Stars are `aria-required`, not native `required` (above). Open question for the owner: should the server also REFUSE a save when the rate is above 0 and VS, account or office name is blank? Default in this brief: no, keep the current soft behaviour (save, then name what is missing). Do not implement a refusal.
- Summary text: "Not saved: fix N fields" is counted from server-detected errors only (each rendered error element carries `data-field-error`, step 3). One refusal produces one error today in most paths; N is honest, so "fix 1 field" is expected for the account case. Singular "Not saved: fix 1 field" needs its own key (plural via two keys: `one` and `other`; check how `_flash_plural` / `flash_plural` in `admin_helpers.py` does it and reuse that, do not invent a scheme).

## 3. Files

| Path | Action |
|---|---|
| App/app/templates/_stay_fee_fields.html | edit (steps 1-2) |
| App/app/templates/_property_editor.html | edit (steps 3-4: summary near Save bar, `details open`, `data-field-error` anchors) |
| App/app/routes/admin.py | edit (step 3: pass `save_errors` list from the refusal helpers; no behaviour change to what is stored) |
| App/app/static/app.js | edit (step 4: focus first error; live star toggle) |
| App/app/static/app2.css | edit only if the summary needs a rule (step 5) |
| App/app/host_i18n.py, App/app/host_vi_i18n.py | edit (step 3: new keys, EN, CS, VI) |
| App/app/templates/base.html, App/tests/static_versions.json | edit (step 8, cache keys via the script) |
| App/tests/test_required_stars.py | edit (step 1: new tests) |
| App/tests/test_property_form_save.py | edit (step 6: new tests; reuse its `host`, `_payload`, `_apartment` helpers) |
| App/tests/test_0833_property_editor_browser.py or a new `App/tests/test_1024_save_errors_browser.py` | edit/create (step 7, browser test; copy imports from `test_0833`) |
| docs/tasks/1024-report.md | create (step 10) |
| docs/tasks/1024-ux-save-errors-and-stay-fee-stars.md | Status line only |

## 4. Steps

Anchors: `grep -nF "<text>" <file> | tail -30`. Not found: STOP and report. Every command ends with `| tail -30`. Commit after each step with `1024 step k` (message ends with the two attribution lines from the system reminder).

0. **Branch.** `git status --short | tail -10` must be empty (if not, STOP: the tree belongs to another branch). Then `git fetch origin main 2>&1 | tail -3 && git checkout -B claude/save-errors origin/main 2>&1 | tail -3 && git log --oneline -1 | cat`. Confirm anchors: `grep -nF "missing_warn" App/app/templates/_property_editor.html | tail -5`; `grep -nF 'id="stay-fee-account-error"' App/app/templates/_stay_fee_fields.html | tail -5`; `grep -nF "function initSectionNotice" App/app/static/app.js | tail -3`.

1. **Stars (tests first).** In `App/tests/test_required_stars.py` add `test_editor_stay_fee_fields_star_follows_the_rate`:
   - static: in `_stay_fee_fields.html` the `field_label` lines for `stay_fee_vs`, `stay_fee_council_account`, `stay_fee_authority_name` each end with a required expression that is not the literal `false` (the file already passes `fee_required`; after this step it passes `fee_required or fee_needed` where `fee_needed` is defined once at the top of the file as `{%- set fee_needed = fee_required or ((apartment.stay_fee_rate_czk or 0) > 0) -%}`), and each of the three inputs carries `aria-required="{{ 'true' if fee_needed else 'false' }}"`.
   - Extend `TAIL` in that test file to also accept `fee_needed` (regex `(?:true|required|fee_required|fee_needed|not has_password)`; keep `fee_required` for the rate field). `test_every_star_has_a_required_control` must stay green.
   - runtime (TestClient, reuse the fixtures from `test_property_form_save.py` by importing its `host` fixture the way `test_0833` imports fixtures, or build the apartment the same way): `GET /apartments/{id}?lang=en&view=settings&section=reporting` with `stay_fee_rate_czk` 50 and the three blank has exactly three `req-star` spans inside the `#sec-fee` section for the VS, account and office-name labels, and the rate label star; with rate 0 the three have no star.
   Edit `_stay_fee_fields.html`: the three `field_label(..., false, '', fee_required)` calls get `fee_needed`; the rate keeps `fee_required` only (star always in editor? NO: decided: rate star shown when `fee_required` only, unchanged; the rate is optional, because 0 means no fee). Add `aria-required` as above on the three inputs (the wizard keeps `required`). Keep the `{% if fee_required %} required{% endif %}` as is.
   Check: `.venv/bin/python -m pytest tests/test_required_stars.py -q --tb=short -x 2>&1 | tail -30` from `App/`. Commit `1024 step 1`.

2. **Account error under its field.** In `_stay_fee_fields.html` move the `{% if fee_account_error %}<p class="err-text small" id="stay-fee-account-error" role="alert" data-field-error ...>` block inside the Council account `.field` div, after the `<input>`. Keep the id and the `aria-describedby` wiring. Add `aria-invalid="true"` already present. Same move for the guest operator error only if it also sits above its field (it sits above the input inside its `.field`'s parent: leave it unless the screenshot shows it under the wrong label; say what you saw). Commit `1024 step 2`.

3. **Server: error list and open sections.** In `admin.py`, in `_refuse_apartment_save` and `refuse_fee_save`, build `save_errors`: a list of `{"section": "<basics|police|fee|lock>", "target": "<element id of the input to focus>"}` and put it in `extra` (grep how `extra` is merged in `_render_apartment_detail`). Mapping: account invalid -> `fee`, `stay_fee_council_account`; link error -> `fee`, `stay_fee_guest_revolut_link`; operator account error -> `fee`, `stay_fee_guest_operator_account`; rate error -> `fee`, `stay_fee_collect`; each key of `address_errors` -> `basics`, that field's id; `shared_time_error` -> `basics`, the shared-time input id (grep it); `operator_error` -> `basics`, `legal_entity_id` (the operator select; grep the id); `lock_times_error` -> `lock`, `checkin_hour` (grep). Do not change what is stored or any status code (400 stays). In `_property_editor.html`:
   a. each `<details class="prop-sec" id="sec-X">` also opens when `save_errors` has an item with `section == 'X'` (append `{% if save_errors and save_errors|selectattr('section','equalto','X')|list %} open{% endif %}` to its `open` conditions; six sections, only those that can hold an error matter but keep all six uniform).
   b. every existing error element listed in section 2 keeps its markup; add `data-field-error` to the ones that are rendered only on error.
   c. summary directly above the `.savebar` div: `{% if save_errors %}<div class="banner err save-summary" role="alert" tabindex="-1" data-save-summary data-first-error="{{ save_errors[0].target }}"><span class="grow">{{ t('property_page.save_failed', n=save_errors|length) }}</span> <a href="#{{ save_errors[0].target }}">{{ t('property_page.save_failed_go') }}</a></div>{% endif %}`. The link works without JS. Use the plural mechanism noted in section 2 for N = 1 vs more.
   d. keys, all three languages in parity (EN in `host_i18n.py`, CS in its CS block, VI in `host_vi_i18n.py`; find the neighbouring `property_page.` keys with `grep -nF "property_page.strip.aria" App/app/host_i18n.py App/app/host_vi_i18n.py | tail -10`): `property_page.save_failed` EN "Not saved: fix %(n)s fields. Nothing was changed." with a singular form "Not saved: fix 1 field. Nothing was changed."; CS "Neuloženo: opravte pole (%(n)s). Nic se nezměnilo." plus a singular; VI equivalents (write plain Vietnamese: "Chưa lưu: hãy sửa %(n)s ô. Chưa có gì bị thay đổi."); `property_page.save_failed_go` EN "Go to the first one", CS "Přejít na první", VI "Đến ô đầu tiên". No em dashes. If the repo's key-parity test names other languages, run it (`grep -rl "i18n" tests | tail`, run the i18n parity test from the test-map) and fix what it reports.
   e. success: the existing `?msg=` flash ("Saved. This property is ready to report.") is the confirmation. In `_property_editor.html`, when `flash` is set and `inline_flash_section` is empty and the page is the editor, render it as `<div class="banner ok save-summary" role="status" tabindex="-1" data-save-summary>` above the `.savebar` as well (same place as the error one), so the host sees "Saved" next to the Save button. Check `base.html` lines ~93-101: the generic flash toast must not show the same text twice; if it would, suppress the base one on this page by the same mechanism `inline_flash_section` uses (read `templating.py` ~718: `?sec=`; simplest: have the save redirect add `&sec=` nothing; instead set a template variable `editor_flash_inline = True` in the `_render_apartment_detail` context and test it in base.html next to `not inline_flash_section`). State what you chose in the report.
   Commit `1024 step 3`.

4. **JS.** In `app.js` next to `initSectionNotice`:
   - `initSaveSummary()`: `var s = document.querySelector("[data-save-summary]"); if (!s || !claimNode(s, "initSaveSummary")) return;` if `data-first-error` is set: `var t = document.getElementById(s.getAttribute("data-first-error")); if (t) { var sec = t.closest("details"); if (sec) sec.open = true; t.scrollIntoView({block:"center"}); t.focus({preventScroll:true}); } else { s.scrollIntoView({block:"center"}); s.focus({preventScroll:true}); }`. For the success banner (no `data-first-error`) do not steal focus from nothing: `s.scrollIntoView({block:"nearest"})` only. Register it where `initSectionNotice` is registered (grep `initSectionNotice` in `app.js`; same list, so Turbo page loads run it). The sticky `keepClear` handler already keeps the focused field clear of the Save bar.
   - `initStayFeeStars()`: on `input` of `#stay_fee_rate_czk` (only when `#sec-fee` exists and the page is the editor, i.e. the form has `#property-settings-form`), for ids `stay_fee_vs`, `stay_fee_council_account`, `stay_fee_authority_name`: toggle `aria-required` and add or remove `<span class="req-star" aria-hidden="true">*</span>` at the end of the label's text (before the help tip button) when the rate is above 0. Idempotent.
   No new dependency, no inline script. Commit `1024 step 4`.

5. **CSS only if needed.** `.banner.err` and `.banner.ok` exist. Add a `body.v2 .save-summary{margin:0 0 12px}` style only if the screenshot at step 9 shows the banner glued to the bar; the Save bar is sticky, so the summary sits above it in flow (not inside it). Light mode only. Commit if changed.

6. **Server tests (`App/tests/test_property_form_save.py`; reuse `host`, `_payload`, `_apartment`, `_property_form`).** Add:
   - `test_a_valid_stay_fee_save_is_stored_and_confirmed`: POST `/apartments/{id}` with `_payload(stay_fee_rate_czk="50", stay_fee_vs="1342900493", stay_fee_council_account="19-2000145399/0800", stay_fee_authority_name="Mesto Test")`, `follow_redirects=False` -> 303; `Location` contains `msg=`; DB row has the VS and account (check the stored column names with `grep -n "stay_fee_council" App/app/routes/stay_fees.py | tail`); GET the redirect target (`follow_redirects=True`) shows `data-save-summary` with class `ok` and no `class="banner err save-summary"`.
   - `test_an_invalid_account_is_refused_and_nothing_is_stored`: first save a good fee as above, then POST the same with `stay_fee_council_account="123"` and a changed `internal_name="Changed Flat"` and `stay_fee_vs="9999999999"`; response 400; DB row unchanged (old name, old VS, old account); body contains `data-save-summary`, `data-first-error="stay_fee_council_account"`, the `account_invalid` text for EN ("This account number does not add up"), `Not saved: fix 1 field`, and the fee section opens (`id="sec-fee"` tag contains ` open`); body does NOT contain "Saved." as a banner (`'banner ok' not in body`). Also assert the error `<p id="stay-fee-account-error"` appears after the `stay_fee_council_account` input (string index of the input < index of the error) and after the label for that input, i.e. it is not between the VS and the account field.
   - `test_the_same_refusal_never_redirects_with_a_success_message`: same POST with `follow_redirects=False` has status 400 and no `Location` header.
   - `test_an_address_error_opens_basics_and_counts_fields`: post a payload with two bad address fields (copy the existing address-error test case: `grep -n "address_errors\|addr_" tests/test_property_form_save.py tests/test_*address*.py | tail -15`), assert `Not saved: fix 2 fields`. If no existing payload yields two errors, assert one error and say so.
   Run from `App/`: `.venv/bin/python -m pytest tests/test_property_form_save.py tests/test_required_stars.py -q --tb=short -x 2>&1 | tail -30`. Commit `1024 step 6`.

7. **Browser test** (`UBYHOST_REQUIRE_BROWSER=1`, 0 skipped). Add `test_1024_save_error_opens_scrolls_and_focuses` to `App/tests/test_0833_property_editor_browser.py` (reuse its fixtures; set viewport 390x844): open the editor with the Stay fee section closed, fill the rate 50, type `123` in `#stay_fee_council_account`, click the Save button `.savebar button`, wait for navigation; assert `document.activeElement.id == "stay_fee_council_account"`, `#sec-fee` has `open`, the error element's bounding rect is inside the viewport and not under the sticky Save bar (`rect.bottom <= savebar.top`), `[data-save-summary]` is visible. Second test `test_1024_saved_banner_is_visible_after_a_valid_save` for success. Then layout lint and the property editor browser tests: `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots .venv/bin/python -m pytest tests/test_layout_lint_browser.py -q -x 2>&1 | tail -30` and `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_0833_property_editor_browser.py tests/test_host_property_controls_browser.py tests/test_property_navigation_browser.py -q --tb=short -x 2>&1 | tail -30` (drop files that do not exist, say so). A failing existing test that pins old behaviour: STOP, report name and line; never silence a layout-lint finding. Commit `1024 step 7`.

8. **Cache keys.** Bump `app.js?v=` (and `app2.css?v=` only if step 5 changed it) in `App/app/templates/base.html` (anchors: `grep -nF "app.js?v=" App/app/templates/base.html | tail -3`; new value `20261108-1024`), then from `App/`: `.venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -10`; `.venv/bin/python -m pytest tests/test_static_versions.py -q 2>&1 | tail -10`. Commit `1024 step 8`.

9. **Screenshots (UX gate, rule 10).** Run the real app or the browser test fixture to produce, at 390, 768 and 1280 px: (1) the editor right after a failed save (invalid account) and (2) right after a valid save. Open each PNG with the Read tool (crop tall images with PIL into the scratch dir). Look at: error directly under Council account, red stars on VS, Council account and Council office name when rate > 0 (none when rate 0), summary above the Save bar readable and not covered by it, focused field visible, Saved banner visible. Save the six PNGs as `/mnt/project-files/ux-shots/save-errors/<failed|saved>-<390|768|1280>.png` (`mkdir -p` first, `ls -l` after). Tests may rewrite tracked PNGs: `git status --short | grep -i '\.png' | tail -30`, then for each listed path `git checkout -- <that exact path>`; never `git checkout -- docs/tasks`; never commit PNGs. Tick the design-system checklist (`docs/design/design-system.md`) in the report.

10. **Report and push (no PR).** Write `docs/tasks/1024-report.md` (600 tokens at most): `git diff --stat origin/main | tail -10`, last line of each test command, per page "390: ...; 768: ...; 1280: ..." for failed and saved states, the six screenshot paths, the open owner questions (section 2), deviations, the checklist ticks. Set this brief `Status: review`. `git add docs/tasks/1024-report.md docs/tasks/1024-ux-save-errors-and-stay-fee-stars.md && git commit -m "1024 report"`, then `git push -u origin claude/save-errors 2>&1 | tail -5`. Never push to `main`; if the push is refused, give the owner the exact command in the report. No PR.

## 5. Do not touch

Anything under `App/app/migrations/`, `db.py`, `retention.py` (no new personal data; no new outbound request), the wizard templates (`setup_wizard/`), `stay_fee.py` report logic, the HTML `required` attribute of any editor field, any test other than the three files in section 3, any file outside section 3. No new dependency.

## 6. Commands

Inside the steps. Test-map rows: `test_required_stars.py`, `test_property_form_save.py`, `test_0833_property_editor_browser.py`, layout lint browser, `test_static_versions.py`. Context lint at the end from the repo root: `python3 scripts/context_lint.py 2>&1 | tail -10`.

## 7. Acceptance

- [ ] With rate above 0, the editor shows stars on Variable symbol, Council account and Council office name (and none with rate 0); `test_required_stars.py` green with the new test.
- [ ] A refused save (HTTP 400) stores nothing, shows "Not saved: fix N fields" above the Save bar, renders the holding `<details>` open, and the account error sits under the Council account input.
- [ ] In the browser, after a failed save the first error field is focused, scrolled into view, and not under the sticky Save bar at 390 px.
- [ ] A valid save persists and shows one "Saved" confirmation next to the Save bar; no refused path ever renders a success banner or redirects with `msg=`.
- [ ] EN, CS, VI keys present; layout lint and the property editor browser tests green with 0 skipped; static versions test green.
- [ ] Six screenshots in `/mnt/project-files/ux-shots/save-errors/`; no PNG in `git status`; `git diff --stat origin/main` lists only section 3 files.

## 8. Stop and ask

- An anchor in section 2 or a step is missing, or `git status` is not clean at step 0.
- The `error id`/field id for the operator select, shared time or lock hours cannot be found with one grep each.
- A browser test or layout lint finding fails and cannot be fixed inside section 3 files.
- You are at 25 tool calls and step 7 is not done: commit, write what is left, hand over (workflow "at the cap").

## 9. Report

`docs/tasks/1024-report.md` as in step 10. Include the choice made for the duplicated flash (step 3e) and whether the guest operator error needed moving (step 2).

## Risk list (for the reviewer)

`admin.py` refusal helpers (the stored data must not change; status codes stay), `host_i18n.py` / `host_vi_i18n.py` key parity, `_property_editor.html` `open` conditions on six sections.

## Owner steps

None for the executor. Open design questions for Josef: (1) should a save with rate above 0 and a blank VS, account or office name be refused (hard) or stay soft (default here)? (2) Is "Not saved: fix N fields. Nothing was changed." the wording he wants?
