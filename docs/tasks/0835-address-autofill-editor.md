# 0835 Address autofill on the property editor (shared component)

Status: todo

## 1. Objective

On the property editor (`_property_address_fields.html`) the host types a street and number, picks a suggestion, and street, č.p., č.o., PSČ, obec, část obce and okres fill in. Typing by hand always works. One shared JS component (owned by the wizard thread), reused by the setup wizard's address step (thread "Make onboarding wizard twice as fast").

## 2. Context

- Backend: `GET /apartments/ruian-suggest` and `App/app/ruian.py` from draft PR #731 (branch claude/project-thread-v21yd0, stacked on #702). Returns structured fields, host login, 60/h per user, `[]` on any error, switch `UBYHOST_RUIAN_ENABLED`. Not on this branch yet: merge or cherry-pick that branch's ruian files first; do not reimplement.
- UbyPort filing correctness comes first (rule 1): filled values are only suggestions, the host confirms by picking one, and the existing server-side validation stays unchanged.
- No new dependency, no third-party script (rule 2). Phone: fewer taps, one suggestion list under the street field.
- ČÚZK terms, endpoint and a decisions.md line are still open (#731); the UI must degrade to plain fields when the endpoint returns `[]` or the switch is off.

## 3. Files

`App/app/templates/_property_address_fields.html` (include the wizard thread's partial next to the addr_* fields), `App/app/static/app2.css` (one block `/* 0835 address suggest (v2) */`, editor-only spacing), one new test `App/tests/test_0835_address_suggest_browser.py`. The component itself (`App/app/static/ruian_suggest.js`, partial, data-ruian-suggest contract) is built by the wizard thread on top of #731; do not build a second one.

## 4. Steps

1. Wait until the component is on the branch (merge that branch). Keep addr_* ids/names unchanged.
2. Add `data-ruian-suggest` to the street input and include the partial in the editor's address block.
3. CSS: list under the field fits the two-column editor grid, 12 px gaps, no fine print.
4. Test at 390/768/1280 with the endpoint mocked: typing shows the list, picking fills the seven fields, `[]` leaves fields untouched, list inside viewport.

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
