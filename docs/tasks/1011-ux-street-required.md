# 1011: Property street (`addr_street`) becomes mandatory, with the red star

Status: todo
Depends on: 1010 (PR 809, branch `claude/required-stars`, already holds `tests/test_required_stars.py`) | Base: branch `claude/required-stars` | Branch: `claude/street-required` (create it from `claude/required-stars`; `git checkout claude/required-stars && git checkout -b claude/street-required`)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Owner decision (Josef, 2026-11-08): the property street is mandatory, because Airbnb listings are rarely in villages without streets. A host cannot create a property, save the wizard property step or save the editor address without a street. The street field gets the red star and the HTML `required` attribute, like house number, postcode and municipality.

## 2. Context (audit done by the orchestrator; do not re-audit)

How the three other parts are enforced today:

| Layer | house number / postcode / municipality | street today |
|---|---|---|
| Template `_property_address_fields.html` lines 23-31: `address_input(..., required)` renders star, `required`, `aria-required`, and the `<p class="err-text" id="NAME-error">` | required=true (7th positional argument) | line 23: `true, 48, extra=...` = optional (5th argument `true`), no star |
| Server `_create_address_errors` in `App/app/routes/admin.py` ~line 1561: takes the issues `validate_apartment` raises for the fields in `_ADDRESS_ONLY_FIELDS` | yes, via `validate_apartment` (`validation.py` ~1045-1064) | no issue is raised, so nothing |
| Callers of `_create_address_errors` | create `POST /apartments` (admin.py ~1821), Settings/editor save (~2793, when any address field is posted), wizard property step (`setup_step == "property"`, same block) | same three callers |
| Messages | English in `validation.py`, Czech in `App/app/validation_i18n.py` (~line 103), Vietnamese in `App/app/host_vi_i18n.py` (~line 195), keyed by the English text | none yet |

### UbyPort decision (rule 1: filing correctness beats everything)

`validation.validate_apartment` is NOT only a form check. It is the UbyPort submit gate: `reporting.py` lines ~1959, ~2037 and ~2158 refuse to file when it returns errors, and `onboarding.py` `_apartment_issues` and the readiness lists in `routes/admin.py` use it too. `reporting.py` line 125 sends `uStr` as optional (`None` when empty), so a missing street never produced a wrong filing.

If `addr_street` were added to `validate_apartment`, every EXISTING apartment with an empty street would suddenly fail the gate and could no longer submit guest reports to UbyPort until the host edits it. That is a filing outage for working properties, caused by a form preference. Rejected.

Chosen: enforce the street only in `_create_address_errors` (admin.py), the one place that enforces house number for the create form, the Settings/editor address save and the wizard property step. `validate_apartment`, `reporting.py`, `onboarding._address_complete`, `property_setup.property_details_complete` and the readiness lists stay unchanged.

Consequences to state in the report:
- Existing apartments with an empty street: UbyPort reporting, readiness and wizard completion are NOT affected. They keep filing.
- Only a later save of the address (editor address section, or wizard property step) on such an apartment is refused until a street is typed. A save that posts no address fields (other editor sections) still works, unchanged.
- Villages without street names: the host types the village name as the street (what the police address register does). The old hint saying the house number alone is enough is now wrong and is replaced.

Pinned tests that must flip (comment citing "owner decision of 2026-11-08"): `tests/test_wizard_old_look_0953.py` line ~56 (loop over `addr_street`, `addr_orient_no`, `addr_obec_cast`, `addr_okres` unstarred) and `tests/test_required_stars.py` function `test_street_and_other_optional_address_fields_stay_unstarred` (~line 81). Also `tests/test_property_address_required.py`: `OPTIONAL_FIELDS` (line 14) lists `addr_street`, and the `_form` helper (line ~36) posts no street.

## 3. Files

| Path | Action |
|---|---|
| App/app/routes/admin.py | edit (step 1, `_create_address_errors` only) |
| App/app/validation_i18n.py | edit (step 1, one Czech line) |
| App/app/host_vi_i18n.py | edit (step 1 message, step 2 hint) |
| App/app/templates/_property_address_fields.html | edit (step 2, one line) |
| App/app/host_i18n.py | edit (step 2, EN and CS hint at ~8636 and ~8646) |
| App/tests/test_wizard_old_look_0953.py | edit (step 3) |
| App/tests/test_required_stars.py | edit (step 3) |
| App/tests/test_property_address_required.py | edit (step 3 and 4) |
| other tests that fail only because their POST lacks a street | edit, one line each (step 4) |
| docs/tasks/1011-report.md | create |
| docs/tasks/1011-ux-street-required.md | Status line only |

No CSS, JS or cache-key change. Do not touch `validation.py`, `reporting.py`, `onboarding.py`, `property_setup.py`.

## 4. Steps

Anchors: `grep -nF "<text>" <file>`. Not found: STOP (§8). Commit after each step with `1011 step k`.

1. **Server rule and messages.**
   a. `App/app/routes/admin.py`, in `_create_address_errors`, directly after the `for issue in ...: ... errors.setdefault(issue.field, issue.message)` loop and before `return errors`, add:
```python
    # Owner decision 2026-11-08: the street is mandatory on the forms. Deliberately NOT in
    # validation.validate_apartment, which is the UbyPort submit gate: existing apartments
    # without a street must keep filing (reporting.py sends uStr as optional).
    if not (payload.get("addr_street") or "").strip():
        errors.setdefault("addr_street", "Street is required.")
```
   Also extend its docstring by the words "and street".
   b. `App/app/validation_i18n.py`: directly after the line `"House number is required.": "Vyplňte číslo popisné.",` add `"Street is required.": "Vyplňte ulici.",`.
   c. `App/app/host_vi_i18n.py`: directly after the `"House number is required.": ...` line add `"Street is required.": "Tên đường là bắt buộc.",`.
   Run from `App/`: `.venv/bin/python -m pytest tests/test_validation_i18n.py tests/test_validation.py -q --tb=short -x 2>&1 | tail -30`.

2. **Star, `required` and hint.**
   a. `App/app/templates/_property_address_fields.html` line 23 becomes exactly:
```
  {{ address_input('addr_street', t('apartment.form.addr.street'), t('apartment.form.addr.street_hint'), false, 48, '', true, extra='data-ruian-suggest') }}
```
   b. Replace the hint (it says the street is optional) in three places, same key `apartment.form.addr.street_hint`:
      - `App/app/host_i18n.py` ~8636 (EN): `"Street name without the house number. For a village, type the village name."`
      - `App/app/host_i18n.py` ~8646 (CS): `"Název ulice bez čísla popisného. V obci bez ulic napište název obce."`
      - `App/app/host_vi_i18n.py` ~3719: `"Tên đường, không kèm số nhà. Ở làng không có tên đường, hãy nhập tên làng."`
      Change only these three string values.
   Run: `.venv/bin/python -m pytest tests/test_host_i18n.py tests/test_ruian.py -q --tb=short -x 2>&1 | tail -30`.

3. **Flip the pinned tests.**
   a. `tests/test_wizard_old_look_0953.py` ~line 56: move `"addr_street"` out of the unstarred loop into the starred tuple above it (`"addr_house_no", "addr_zip", "addr_obec"` list), so the loop reads `("addr_orient_no", "addr_obec_cast", "addr_okres")`. Add above it the comment `# Owner decision 2026-11-08: the street is mandatory (Airbnb listings are rarely in street-less villages).`
   b. `tests/test_required_stars.py`: rename `test_street_and_other_optional_address_fields_stay_unstarred` to `test_street_is_starred_and_other_optional_address_fields_stay_unstarred`; add a comment citing the owner decision of 2026-11-08; loop over `("addr_orient_no", "addr_obec_cast", "addr_okres")` for the unstarred check; and add a check that the `address_input('addr_street'` line contains `'', true,` (required passed). If the file has a "required id has star" check that treats `addr_street` as an exception, remove only that exception (do not add any).
   c. `tests/test_property_address_required.py`: in `OPTIONAL_FIELDS` remove `"addr_street"`; keep `FIELDS` unchanged (it drives tests that expect other parts' errors to be absent) and add `"addr_street": "Synthetic Street",` to the `_form` dict (line ~36) so existing cases still create. In `test_create_page_marks_the_three_parts_required_and_the_rest_optional` add a separate loop asserting the `addr_street` input tag has ` required` and `aria-required="true"` for `en` and `cs`, label without the "optional" word.
   Run: `.venv/bin/python -m pytest tests/test_required_stars.py tests/test_wizard_old_look_0953.py -q --tb=short -x 2>&1 | tail -30`.

4. **New rejection tests** (append to `tests/test_property_address_required.py`, reuse its helpers `_host`, `_form`, `_stored`, `_count`; look at `test_settings_save_clearing_the_house_number_is_refused_and_typed_values_echoed` ~line 141 for the exact edit call and copy its style):
   - `test_create_without_street_is_refused`: `POST /apartments` with `_form(host, addr_street="")` and with `addr_street="   "`: status 400, `id="addr_street-error"` in the body, `_count(host) == 0`; and the English text "Street is required." present with `?lang=en` if the helper makes that easy, else only the id check.
   - `test_forged_create_without_street_field_is_refused`: post `_form(host)` after `data.pop("addr_street")` (key absent): 400, `_count == 0`.
   - `test_editor_save_clearing_the_street_is_refused_and_nothing_changes`: `_stored(host, addr_street="Old Street")`, edit-post with `addr_street=""`, status 400, `id="addr_street-error"`, stored value still `Old Street`.
   - `test_existing_apartment_without_street_still_validates_for_ubyport`: `from app import validation`; call `validation.validate_apartment` on a dict with house number, zip, obec, valid police fields and `addr_street=""`; assert no issue has `field == "addr_street"`. This pins the choice in §2.
   - `test_save_without_address_fields_keeps_working_for_street_less_apartment`: `_stored(host)` (no street), post a body without any address field (copy the style of `test_a_save_without_address_fields_still_works_and_keeps_the_address`), not 400.
   Run: `.venv/bin/python -m pytest tests/test_property_address_required.py -q --tb=short -x 2>&1 | tail -30`.

5. **Fix fixtures that post without a street.** Run the test-map rows (§6). A test failing only because a create or address-save POST has no `addr_street` (response 400 with `addr_street-error`): add `"addr_street": "Synthetic"` to that POST data, one line, nothing else. Candidates (they contain `addr_house_no` but no `addr_street`): `test_property_form_save.py`, `test_calmer_forms.py`, `test_new_property_defaults.py`, `test_police_defaults.py`, `test_property_create_browser.py` (`_form`, line ~72), `test_host_controls_browser.py`, `test_validation_i18n.py`. Only touch a test that actually fails. A failure that is not about the street: STOP (§8).

6. **UX gate (rule 10).** Start the app as the screenshot helpers do (see `tests/test_host_geometry.py` for the `base` fixture; do not read other files), then take a 390 px screenshot of (i) the property create form `/apartments/new` and (ii) the editor address section of an existing property; open each once and describe what you see in the PR (star on Street, same look as house number, hint text fits, no overflow). Run the layout lint and geometry rows in §6 with 0 skipped. Tick the design-system checklist in the PR text.

7. **Report and PR.** `docs/tasks/1011-report.md` (600 tokens max, per `docs/context/executor.md`), set `Status: review`, open one PR against `claude/required-stars` (not `main`). Do not merge.

## 5. Do not touch

`validation.py` (street must NOT enter `validate_apartment`), `reporting.py`, `onboarding.py`, `property_setup.py`, readiness lists, CSS, JS, `static_versions.json`, any dependency. Do not make orientation number, `addr_obec_cast` or `addr_okres` required. No new migration: existing rows with an empty street stay valid.

## 6. Commands

Each ends in `| tail -30`, from `App/`:
- `.venv/bin/python -m pytest tests/test_validation_i18n.py tests/test_validation.py tests/test_host_i18n.py tests/test_ruian.py -q --tb=short -x 2>&1 | tail -30` (steps 1-2)
- `.venv/bin/python -m pytest tests/test_required_stars.py tests/test_wizard_old_look_0953.py tests/test_property_address_required.py tests/test_address_split.py -q --tb=short -x 2>&1 | tail -30`
- Test-map row "Onboarding, properties": `.venv/bin/python -m pytest tests/test_onboarding*.py tests/test_property_*.py tests/test_first_*.py -q --tb=short -x 2>&1 | tail -30`
- Test-map row "Host pages": `.venv/bin/python -m pytest tests/test_host_*.py tests/test_host_geometry.py -q -rs --tb=short -x 2>&1 | tail -30` (0 skipped)
- Test-map row "Any host template": `.venv/bin/python -m pytest tests/test_design_guardrails_browser.py tests/test_layout_lint_browser.py tests/test_0884_wizard_geometry_browser.py tests/test_wizard_old_look_0953_browser.py tests/test_0850_address_suggest_browser.py -q -rs --tb=short 2>&1 | tail -30` (0 skipped, zero host layout findings)
- From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`
No full suite.

## 7. Acceptance

- [ ] Create, editor address save and wizard property step all refuse an empty or blank street (400, `addr_street-error`, typed values echoed, nothing written); a POST with the field absent on create is refused.
- [ ] Street label shows the red star, input has `required` and `aria-required="true"`, in EN and CS; hint no longer says a village needs no street.
- [ ] `validate_apartment` unchanged; `test_existing_apartment_without_street_still_validates_for_ubyport` green; existing street-less apartments still report to UbyPort.
- [ ] Both pinned tests flipped with the comment citing the owner decision of 2026-11-08.
- [ ] Browser and geometry rows 0 skipped; layout lint zero findings; two 390 px screenshots described in the PR; checklist ticked.
- [ ] `git diff --stat` shows only §3 files.
- [ ] `python3 scripts/context_lint.py` OK.

## 8. Stop and ask

Stop, write the report as `blocked` with `Done: steps 1 to k. Left: steps k+1 to n.`, if: an anchor is not found; a test fails twice; a failing test is not a missing-street POST; you think `validation.py` must change; `test_required_stars.py` has no function with the named old title; you reach 25 tool calls or about 50k tokens; you would need push to `main`, merge, secrets or deploy.

## 9. Report

`docs/tasks/1011-report.md`: files changed, each command with its last 5 lines, §7 ticked, Deviations, Questions, owner steps left.

## Risk list (for the reviewer)

- Hosts with an existing street-less apartment hit a street error the next time they save its address (accepted; filing is unaffected).
- Many older tests post create forms without `addr_street` (step 5 patches only the failing ones).
- The Vietnamese and Czech strings are new copy; owner may want a native check.
- RUIAN suggest (`data-ruian-suggest`) still fills the street; `required` must not break the suggest dropdown (covered by `test_0850_address_suggest_browser.py`).

## Owner steps

1. Open the two 390 px screenshots in the PR and confirm the street star looks right.
2. Merge with `scripts/merge-pr-on-green.sh` when the checks are green (after PR 809, or retarget to `main` once 809 is merged).
