# 0833 Property editor: help "?", duplicate heading, subtitles, width

Executor: Haiku. Branch claude/project-thread-wkaqmz (stacked on PR #725). Read only AGENTS.md, docs/context/executor.md, this brief, and the files named here.

## Problem (Josef's screenshot partC-property-detail-1280.png)
On `/apartments/<id>?view=settings` (templates `_property_editor.html`, `_property_identity_fields.html`, `_property_address_fields.html`):
1. Help "?" renders as a default square button and its text is always visible, overlapping labels ("Name of the apartment", "Street"). Cause: the `.help-tip*` rules in `App/app/static/app2.css` (lines ~1251-1261) are scoped to `body.v2:has(.settings-lane,.pr-lane,.entities-page,.archive-type-filters)`; the property page has none of those.
2. "Basic details" appears twice (summary `<b>` and `<h2 class="property-section-title">` inside the open section, `apartment.form.basics.title`). Same duplicate may exist in other sections (Police, Stay fee, Calendars, Messages, Lock): remove the inner h2 when it repeats the summary title; keep it only if it adds a different title.
3. Each accordion summary shows `<small>` subtitle under the title (`property_page.sec.*.sub`). Remove the `<small>` from every `prop-sec` summary (keep `.sec-state`). No fine print.
4. Form is narrow (fields ~260 px, `max-width:420px` selects). At >=1024 let the fields fill the card: two-column grid, inputs full column width.

## Do
- app2.css: append ONE block `/* 0833 property editor (v2) */` at the end. Add `.property-settings-form` to the `:has(...)` list for help-tip rules by overriding in your block: `.help-tip{display:inline-flex}`, `.help-tip-btn` 18px round plain icon (no big box; tap target via `::after{inset:-13px}`), `.help-tip-body{display:none}` popover that shows on `.is-open`/hover/focus-within exactly like the settings rules (copy them, scoped `body.v2 .property-settings-form`). The "?" must sit on the same line right after its label (label inside `.field-label-row` or `label` with a `.help-tip`), >=12 px from the label text and from neighbouring controls. Beat the `details .help-tip-btn{display:none}` rule only if it matches (it does not on this page; check).
- Templates: items 2 and 3 above. Delete i18n keys only if unused elsewhere (grep); otherwise leave.
- Do not touch settings pages, calendar, or other pages' CSS.

## Tests (add to `App/tests/test_0830_airbnb_pages_browser.py` or a new `App/tests/test_0833_property_editor_browser.py`, reuse its fixtures)
At widths 390/768/1280 on the property editor with the Basic details section open:
- every `.help-tip-btn` box is 16-26 px square, round, and its `.help-tip-body` is not visible (display none) until clicked; after click, body visible and inside viewport.
- each `.help-tip-btn` is on the same row as the previous label/heading (vertical centres within 10 px) and the gap to the label text >= 12 px (use the existing 12 px neighbour helper).
- no two visible headings (summary b, h2, h3) in the same section with identical text.
- no `prop-sec > summary small` visible.
- at 1280 the first text input is at least 400 px wide.
- no overlap between a help button's rect and any label/input rect.
Run: `cd App && .venv/bin/python -m pytest tests/test_0830_airbnb_pages_browser.py tests/test_0833_property_editor_browser.py -q --tb=short -x 2>&1 | tail -30`. If `.venv` missing: python3 -m venv .venv; .venv/bin/pip install -r requirements.txt -r requirements-dev.txt playwright==1.63.0 (foreground). Also run tests/test_property_navigation_browser.py. Do not commit; write a 10-line report to docs/tasks/0833-report.md. Do not stage docs/tasks/screenshots-0387/*.
