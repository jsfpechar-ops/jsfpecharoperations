# 0804 report: cleaning sub-pages on the v2 look

Status: review (not committed; orchestrator commits)

## Changed files
- App/app/templates/cleaning_edit.html: v2, nav cleaning, body_kind list, v2 .head with crumb back link and h1, form and card class.
- App/app/templates/cleaning_shares.html: same header pattern, share_intro as sub line, cards.
- App/app/templates/cleaning_properties.html: same header, one card with property rows.
- App/app/static/app2.css: appended block `/* 0804 cleaning sub-pages (v2) */`, all selectors under body.v2 and cl-v2-edit / cl-v2-shares / cl-v2-props.
- docs/design/catalog.json: added cl-v2-edit, cl-v2-shares, cl-v2-props.
- App/tests/test_design_cleaning.py: two assertions on the old markup of these three pages (cleaning.css order, ui-ph header) replaced with v2 checks.

## Tests
- `pytest tests/test_0800_v2_remaining_pages_browser.py -k "cleaning-new or cleaning-shares or cleaning-properties"`: 18 passed, 0 skipped. Tail: `18 passed, 72 deselected in 22.01s`.
- `pytest tests/test_design_cleaning.py`: 4 passed.
- `pytest tests/test_cleaning_browser.py tests/test_design_cleaning.py tests/test_0541_cleaning_header.py`: 29 passed before the test_design_cleaning fix, 1 failed (that test, now fixed).
- `pytest tests/test_cleaning.py tests/test_cleaning_browser.py tests/test_design_cleaning.py tests/test_0541_cleaning_header.py tests/test_0291_open_buttons.py tests/test_design_shell_browser.py`: 3 failed, 85 passed. One is the design_cleaning test (fixed). Two are `tests/test_design_shell_browser.py::test_more_preserves_each_page_kind_and_sheet_links_work` on /apartments/new at 390 and 820 px (the more-sheet click is not visible). That page is not mine (brief 0800), so I did not touch it.
- `python3 scripts/design_lint.py`: OK.

## Screenshots (390 and 1440 viewed)
docs/tasks/screenshots-0800/cleaning-new-{320,390,768,1024,1280,1440}.png, cleaning-shares-*.png, cleaning-properties-*.png

## Deviations
- Sdílení has no copy button and no QR in the template, so none was added. The link is styled as a read-only box.
- No sub line on the edit page and the properties page: no existing copy key fits without repeating body text. Owner may pick one.
- Form cards are capped at 680 px and left-aligned, not a centred 720 px column.
- Phone checkboxes on Sdílení are 44 px (tap rule); desktop 24 px.
- Help text is not hidden on phone (ph-hide not applied).

## Owner steps left
- None. Orchestrator commits and opens the PR.
