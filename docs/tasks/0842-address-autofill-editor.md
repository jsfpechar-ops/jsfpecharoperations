# 0835 Address autofill on the property editor (shared component)

Status: todo

## 1. Objective

On the property editor (`_property_address_fields.html`) the host types a street and number, picks a suggestion, and street, č.p., č.o., PSČ, obec, část obce and okres fill in. Typing by hand always works. One shared JS component (owned here), reused by the setup wizard's address step (thread "Make onboarding wizard twice as fast").

## 2. Context

- Backend: `GET /apartments/ruian-suggest` and `App/app/ruian.py` from draft PR #731 (branch claude/project-thread-v21yd0, stacked on #702). Returns structured fields, host login, 60/h per user, `[]` on any error, switch `UBYHOST_RUIAN_ENABLED`. Not on this branch yet: merge or cherry-pick that branch's ruian files first; do not reimplement.
- UbyPort filing correctness comes first (rule 1): filled values are only suggestions, the host confirms by picking one, and the existing server-side validation stays unchanged.
- No new dependency, no third-party script (rule 2). Phone: fewer taps, one suggestion list under the street field.
- ČÚZK terms, endpoint and a decisions.md line are still open (#731); the UI must degrade to plain fields when the endpoint returns `[]` or the switch is off.

Alignment (2026-11-02): backend and baseline are 0834 (#731). Property copy-from on /apartments/new is 0839 (#734), runs after this; do not build it. Fewer editor fields: after a pick the seven address fields are filled (the host types only street and number), focus jumps to the next empty field, and the editor does not add steps or fields.

## 3. Files

`App/app/static/ruian_suggest.js` (new, plain JS, loaded with defer by the partial), `App/app/templates/_ruian_suggest.html` (partial: script tag only), `App/app/templates/_property_address_fields.html` (include partial, add `data-ruian-suggest` to the street input), `App/app/static/app2.css` (one block `/* 0835 address suggest (v2) */`), new test `App/tests/test_0835_address_suggest_browser.py`. Do not edit app.js.

## 4. Steps

1. Contract (the wizard thread reuses it unchanged): an input with `data-ruian-suggest` inside a form that holds inputs named `addr_street, addr_house_no, addr_orient_no, addr_zip, addr_obec, addr_obec_cast, addr_okres`. After 3 chars and 250 ms debounce fetch `/apartments/ruian-suggest?q=<text>` (credentials same-origin) returning `[{label, fields:{<those seven names>}}]` (max 6). Show a listbox under the input (role listbox, up/down/enter/esc, 44 px rows on phone). Picking sets the seven inputs as ordinary editable values and focuses the next empty one. Empty list, error or 404: hide the list, change nothing. Without JS the plain fields work. Fill only names present in the form.
2. Backend comes from draft PR #731 (not on this branch): do not implement it; tests mock the endpoint with Playwright `page.route`.
3. Include the partial in the editor's address block; keep addr_* ids and names.
4. CSS: list fits the two-column editor grid, 12 px gaps, no fine print, list inside the viewport.

## 5. Do not touch

Wizard templates (the wizard thread wires its step to the component), backend, settings pages, calendar, backend endpoint.

## 6. Commands

`cd App && .venv/bin/python -m pytest tests/test_0835_address_suggest_browser.py tests/test_0833_property_editor_browser.py -q --tb=short -x 2>&1 | tail -30` (mock the endpoint with Playwright route). Tests at 390/768/1280: typing shows the list, picking fills all seven fields, keyboard works, endpoint `[]` leaves fields untouched, list stays inside the viewport, 12 px neighbour rule.

## 7. Acceptance

Tests above pass with 0 skipped; 390 px screenshot of the open suggestion list; cache key bumped; `python3 scripts/context_lint.py` OK.

## 8. Stop and ask

If #731 changes the response shape or ČÚZK terms block the endpoint.

## 9. Report

Write docs/tasks/0835-report.md.
