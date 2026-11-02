# 0835 Address autofill on the property editor (shared component)

Status: todo

## 1. Objective

On the property editor (`_property_address_fields.html`) the host types a street and number, picks a suggestion, and street, č.p., č.o., PSČ, obec, část obce and okres fill in. Typing by hand always works. One shared JS component, reused by the setup wizard's address step (thread "Make onboarding wizard twice as fast").

## 2. Context

- Backend: `GET /apartments/ruian-suggest` and `App/app/ruian.py` from draft PR #731 (branch claude/project-thread-v21yd0, stacked on #702). Returns structured fields, host login, 60/h per user, `[]` on any error, switch `UBYHOST_RUIAN_ENABLED`. Not on this branch yet: merge or cherry-pick that branch's ruian files first; do not reimplement.
- UbyPort filing correctness comes first (rule 1): filled values are only suggestions, the host confirms by picking one, and the existing server-side validation stays unchanged.
- No new dependency, no third-party script (rule 2). Phone: fewer taps, one suggestion list under the street field.
- ČÚZK terms, endpoint and a decisions.md line are still open (#731); the UI must degrade to plain fields when the endpoint returns `[]` or the switch is off.

## 3. Files

`App/app/static/app.js` (component `initAddressSuggest`), `App/app/static/app2.css` (one block `/* 0835 address suggest (v2) */`), `App/app/templates/_property_address_fields.html`, one new test `App/tests/test_0835_address_suggest_browser.py`.

## 4. Steps

1. Component: input `[data-address-suggest]` on the street field; after 3 chars and 250 ms debounce, fetch the endpoint; show a list (role listbox, keyboard up/down/enter/esc, 44 px rows on phone). Pick fills the named fields (`data-fill="street|cp|co|zip|town|part|district"`), moves focus to the next empty field. No result or error: list hidden, nothing else changes. Works without JS (plain fields).
2. Mark the editor's address fields with the data attributes; keep field names and ids.
3. CSS: list under the field, 12 px gaps, no fine print, no help text.

## 5. Do not touch

Wizard templates (the wizard thread wires its step to the component), settings pages, calendar, backend endpoint.

## 6. Commands

`cd App && .venv/bin/python -m pytest tests/test_0835_address_suggest_browser.py tests/test_0833_property_editor_browser.py -q --tb=short -x 2>&1 | tail -30` (mock the endpoint with Playwright route). Tests at 390/768/1280: typing shows the list, picking fills all seven fields, keyboard works, endpoint `[]` leaves fields untouched, list stays inside the viewport, 12 px neighbour rule.

## 7. Acceptance

Tests above pass with 0 skipped; 390 px screenshot of the open suggestion list; cache key bumped; `python3 scripts/context_lint.py` OK.

## 8. Stop and ask

If #731 changes the response shape or ČÚZK terms block the endpoint.

## 9. Report

Write docs/tasks/0835-report.md.
