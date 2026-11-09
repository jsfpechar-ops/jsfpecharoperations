# 1053 Stay fee card rows and a centred property editor

Status: review. Executor: Claude (orchestrator subagent, owner asked for the fix in chat). Report: `docs/tasks/1053-report.md`.
Branch: `claude/stayfee-card-rows`. Do not touch PR #830's files (`list-filter-compact.css`, `_list_filter.html`).

## 1. Objective
Owner screenshot of the Stay fee card in the property editor (>=1280 px): ugly rows. Fix, tokens only, light mode:
1. Step 1: "Rate per person per night (Kč)" wraps and the rate input sits lower than the period select. Labels of a row end on one line, inputs share one top line.
2. One "?" rule everywhere in the card: 8 px (`--space-2`) after the label text, centred on it, never at the row end.
3. Step 4: "How guests can pay" glued under the switch: same gap as between fields (`--space-4`).
4. Signature block: on the field edges (full width of both columns), padding `--space-4`, the same gap above it as between steps.
5. No void under step 3 when step 4 is taller.
6. (added by coordinator) On wide screens the whole editor (header row, pills, notices, section card) is ONE column centred beside the sidebar.
7. (owner standing rule, 2026-11-09) No text glyphs for icons: the card's "?" marks and the More details chevron are Lucide SVGs from `_icons.html`.

## 2. Context
The card is `section#stay-fee-settings` inside `details#sec-fee`; its fields come from `_stay_fee_fields.html`, shared with the setup wizard (wizard layout must not change).

## 3. Files
`_property_editor.html`, `_stay_fee_fields.html`, `_components.html`, `_entity_business_fields.html`, `app2.css`, `base.html`, `tests/static_versions.json`, new browser test.

## 4. Steps
- `_property_editor.html`: wrap the stay-fee include in `<div class="fee-grid">` (wizard unchanged).
- `_stay_fee_fields.html`: step 1 order is rate, period, then "Applies from" (rate and period share row 1).
- `app2.css` (end, `1053` blocks):
  - `.fee-grid`: one column, `--space-6` gaps; >=1024 two columns, gap `--space-8`. With step 4: steps 1-3 stack on the left, step 4 spans the right (`grid-template-rows:auto auto auto 1fr auto`, the `1fr` row absorbs step 4's extra height, so no void on the left); signature row 5, full width. Without step 4 (guest pay off): plain 2 x 2.
  - Step 1 from 768 px: two columns; each field is a 2-row subgrid, labels align to the row bottom, inputs share one line.
  - "?": wrapper margin `--space-2`; >=1024 a 24 px borderless button holding the 18 px icon, 44 px invisible hit area; <1024 a 44 px box (0833 test) with the icon at its left edge, negative margins keep the label line short.
  - Editor column (>=1024): `.ui-body-detail` of the editor page `max-width:min(var(--lane), 100% - 128px)`, `margin-inline:auto`; children full width. 64 px each side keeps the sticky Save clear of the help bubble. <1024 unchanged.
- `_components.html`: `help_tip(..., svg=false)` and `field_label(..., svg=false)`; `svg=true` renders `icon('circle-help', 18)` in the button instead of "?". The editor sets `help_svg = true` before the stay-fee include, so every help mark in the card (and the copy row and signature legend) uses the icon; other pages and the wizard unchanged. More details summary gets `icon('chevron-down', 16)`, turned 180 degrees when open.
- Cache key `app2.css?v=20261109-1053a` in `base.html` and `tests/static_versions.json`.

## 5. Do not touch
`list-filter-compact.css`, `_list_filter.html` (PR #830); the wizard layout; other pages' help marks.

## 6. Commands
From `App/`: `.venv/bin/python -m pytest tests/test_stay_fee_card_rows_1053_browser.py tests/test_layout_lint_browser.py tests/test_a11y_guard_browser.py -q --tb=short 2>&1 | tail -30`.

## 7. Acceptance
`tests/test_stay_fee_card_rows_1053_browser.py`: at 1280 and 768 the rate input and period select have equal top y and every "?" is 0-12 px after its label text and vertically centred (+-3 px); at 1440 and 1800 the editor column's left and right gaps inside `main` differ by <= 24 px. `UBYHOST_SHOTS_1053=<dir>` writes card shots (390/768/1280/1440/1800, plain and all-open) and page shots (1440/1800).
Also: `test_layout_lint_browser.py`, `test_a11y_guard_browser.py`, the stay-fee and property browser tests, `test_static_versions.py`.

## 8. Stop and ask
A test outside the stay-fee card or the editor column fails because of this change and the fix would touch another page: stop and report.

## 9. Report
`docs/tasks/1053-report.md`, 600 tokens max: files changed, tests run with counts, per-width screenshot notes.
