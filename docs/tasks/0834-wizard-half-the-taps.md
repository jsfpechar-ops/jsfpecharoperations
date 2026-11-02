# 0834 Setup wizard speed: baseline + RÚIAN lookup (scope narrowed)

## 1. Objective

Status: in-progress

**Scope now (coordinator, 18:04): do NOT edit any wizard template, wizard route, `property_setup.py`, CSS or wizard JS.** Josef's own wizard threads and PR #702 are in flight. Only: section A (baseline script + report) and section D backend (`ruian.py`, endpoint, tests, env doc). Sections B, C and the JS/UI part of D are the follow-up plan, parked until Josef names the wizard threads to align with.


Stacked on PR #702 (wizard restyle). Do not restyle; reuse the existing v2 classes. Read first: `App/app/property_setup.py`, `App/app/routes/onboarding_wizard.py`, `App/app/templates/setup_wizard/*.html`, `App/app/templates/_property_address_fields.html`, `App/app/ares.py`, `App/tests/wizard_walk.py`, `App/tests/test_onboarding_wizard_browser.py`. Do NOT touch signup, default check-in/check-out times or guest-link send (another thread owns them).

## Goal (measured, not guessed)
Today a host passes 8 steps (property, calendar, police, automation, stay_fee, door_lock, guest_link, try_it). Target: 4 required steps and about half the taps and typed fields. UbyPort filing correctness beats speed: nothing legal is auto-saved; every fill is a suggestion the host confirms.

## 2. Context
Stacked on #702. Parked parts B, C and the UI part of D wait for Josef's wizard threads.

## 3. Files
App/tests/wizard_taps.py, App/app/ruian.py, App/tests/test_ruian.py, one route in App/app/routes/admin.py, docs/ENVIRONMENT.md.

## 4. Steps

## A. Baseline first
Before any change write `App/tests/wizard_taps.py` (plain pytest, TestClient) that walks the wizard via `wizard_walk.py` with the cheapest answers and prints/asserts: number of steps visited, number of form fields marked required or empty-to-fill on each, number of POSTs. Record the "before" numbers in `docs/tasks/0834-report.md`, then the "after" numbers. Baseline only for now: no after-numbers, no halving assertion.

## B. Fewer steps (PARKED, do not build)
1. `STEPS` becomes: property, calendar, police, guest_link. (`TOTAL_STEPS` follows.)
2. automation: moves into the police step as the same choice cards, preselected "manual" (today's safe default). Saving the police step saves `automation_mode`/`submit_after_hours` with it; keep validation and the audit event identical. Remove the standalone automation template and route case; keep the stored value and the `automation` checklist row on the done page ("done" once the police step is saved).
3. stay_fee, door_lock, try_it stop being wizard steps. They stay optional and appear on the done page as three "Do next" cards (existing `host-property-card` look) linking to their existing pages (stay fees page, door lock settings, try-it). Their old `/setup/stay_fee|door_lock|try_it` URLs redirect to the done page. Existing saved marks for them stay valid (no migration: unknown marks are ignored, `legacy_state` and the checklist must not break).
4. Update `wizard_facts`, the checklist, `may_view_step`, progress "n of 4", and every test that hard-codes the 8 steps. `wizard_walk._ACTIONS` loses the removed steps.

## C. Less typing in the property step (PARKED, do not build)
1. Operator/ARES: in the property step, if the host has no entity, show one IČO field with a "Fill from ARES" button that reuses the existing `ares.lookup` endpoint used on Entities (find it with `grep -n "ares.lookup" App/app/routes/*.py`), prefilling the entity name, address and DIČ as editable values. Works without JavaScript (plain POST that re-renders). Same rate limit as today.
2. Address autofill (new, see D): a search box above the address fields; picking a suggestion fills street, house no., orientation no., ZIP, town, district part, okres as editable values. The seven fields stay and stay editable; manual entry is always available and is the fallback when the lookup is down or empty.
3. Copy the property's address to the operator address when the entity address is blank and the host ticks nothing (reuse existing fields, no new column).
4. Default check-in/check-out stay as the other thread decides; do not change them.

## D. RÚIAN address lookup (new outbound request)
- New `App/app/ruian.py`, `requests` only (no new package). Endpoints (ČÚZK public, no key): GeocodeSOE `suggest` for the typed text, then `findAddressCandidates`/the address-point record for the chosen id, and use its STRUCTURED attributes (street, číslo popisné, číslo orientační, PSČ, obec, část obce, okres). Never split the display string.
- Route `GET /apartments/ruian-suggest?q=` (host login required, CSRF not needed for GET, min 3 chars, 4 s timeout, 24 h in-memory cache keyed by lowercased query, rate limit 60/h per user via `rate_limit` like `ares.py`). Returns JSON list of at most 6 `{label, fields:{...}}`. Any error or empty result returns `[]`.
- (PARKED, do not build) JS: a small deferred function in the existing wizard JS file (find it with `grep -rn "data-copy" App/app/static/*.js`), progressive enhancement, 250 ms debounce, keyboard accessible listbox (`role="listbox"`), 16 px text, 12 px neighbour gaps. Without JS the plain fields work.
- Privacy: only the typed address text goes out (a property address, not guest data); nothing stored. Add the reason to the PR text. Add one line to `docs/context/decisions.md` ONLY as "proposed, awaiting owner" (the owner must confirm; ČÚZK terms not yet checked from this sandbox, outbound is blocked here). Gate the feature behind env `UBYHOST_RUIAN_ENABLED` (default `1` in code, document in `docs/ENVIRONMENT.md` one line).
- Tests mock `requests.get` (never hit the network): suggest happy path, empty, timeout, rate limit, structured fill (street+č.p./č.o. not parsed from a string).

## E. Tests and evidence
- Run only: `tests/test_ares.py`, `tests/test_onboarding*.py`, `tests/test_wizard_*.py`, `tests/test_design_setup_wizard_browser.py`, `tests/test_0800_v2_remaining_pages_browser.py`, the new tests, and `tests/test_static_versions.py` (rewrite with `--write` after bumping the app2.css/js cache key). Browser tests at 320/390/768/1024/1280/1440, 0 skipped, geometry rules (12 px gaps, targets 44 px).
- Screenshots 390 and 1280 of: property step with suggestions open, police step with automation cards, done page with "Do next" cards -> `docs/tasks/screenshots-0834/`.
- `python3 scripts/context_lint.py` from repo root.
- Do not commit; do not stage `docs/tasks/*evidence*`. Write `docs/tasks/0834-report.md` (before/after numbers, tests run, anything skipped).

## 5. Do not touch
Wizard templates, wizard routes, property_setup.py, CSS, wizard JS, signup, default times.

## 6. Commands
From App/: `.venv/bin/python -m pytest tests/test_ruian.py tests/test_ares.py tests/wizard_taps.py -q --tb=short 2>&1 | tail -30`; repo root: `python3 scripts/context_lint.py`.

## 7. Acceptance
New tests pass with 0 skipped; lint passes; baseline numbers in the report.

## 8. Stop and ask
If the ČÚZK URL or attribute names cannot be confirmed, say so in the report.

## 9. Report
docs/tasks/0834-report.md.
