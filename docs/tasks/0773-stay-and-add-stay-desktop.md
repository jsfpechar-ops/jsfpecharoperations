# 0773: Pobyt page and Přidat pobyt form: header actions, section spacing, form layout

Status: todo
Depends on: none | Base commit: <current main sha> | Branch: task/0773-stay-desktop
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Audit findings 12 and 13: on `/reservations/<id>` the header buttons have different widths and the kebab floats alone, and guests table, police heading and status strip have no spacing; on the add-stay form (`/reservations?new=1`) labels are glued to inputs, input heights are 38 vs 40 px and the form is not in a card.

## 2. Context

- `App/app/templates/reservation_detail.html`: `<div class="host-stay-detail">` (line ~23), `<div class="top stay-top">` (~28), kebab menu items `row-menu-item` (~78-83). CSS scope `body.v2 .host-stay-detail` in `App/app/static/app2.css` (~602-606).
- `App/app/templates/reservations.html` lines ~40-70: the add panel `id="add-stay-panel"`, `<form method="post" action="/reservations">` with `<div class="ui-field"><label for="new_apartment">`. Panel styles: `grep -n "add-stay-panel\|\.ui-field" App/app/static/app2.css App/app/static/components.css | head`.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/static/app2.css` | edit | header, spacing, field rules |
| `App/app/templates/reservation_detail.html` | edit only for a class | |
| `App/app/templates/reservations.html` | edit only for a class | wrap panel in the existing card class |
| `App/app/templates/base.html` | edit | cache key |

No other file may change.

## 4. Steps

1. **Verify the finding still reproduces first.** The audit (`/mnt/project-files/ux-desktop-audit/audit-report.md`, 2026-11-02, main 1bd2148) was made by reviewers from screenshots; every CSS cause below is an unverified guess. Render the page with the rich-host fixture (`App/tests/v2_mockup.py`), measure with a throwaway Playwright snippet in the scratchpad (not committed) using `getBoundingClientRect()` at the stated widths. Write the real cause (selector, computed value) in one line in the report. A finding that does not reproduce: skip its steps and say so. Measure at 1280: widths of each header button and the kebab; vertical gaps between guests table, police heading and status strip; label-to-input gap, input heights, and whether the panel has a border/radius.
2. Header: all actions `min-width:0`, same height (`var(--control-h)`), grouped in one flex row with `gap:var(--space-2)`; the kebab sits in the same row, same height, square. Do not set fixed widths. Commit `0773 step 2`.
3. Spacing: each section block under `.host-stay-detail` gets `margin-top:var(--space-6)` (one rule on the shared section selector, not three). Commit.
4. Form: `.ui-field label{display:block;margin-bottom:var(--space-1)}`, all inputs and selects in the panel `min-height:var(--control-h)` (one value), panel uses the card look of other v2 sections (`border:1px solid var(--line-strong); border-radius:var(--radius-md); padding:var(--space-4)`). Commit.
5. **Cache key.** In `App/app/templates/base.html` bump `app2.css?v=` (now `20261102-0743`) to today's date plus this brief number. If you changed another stylesheet, bump its key too (`grep -rn "<name>.css" App/app/templates | head`). Commit.


## 5. Do not touch

Anything outside §3. No new dependency, no new colour, no dark mode, no JS unless §4 says so. Use existing `ui-*` classes and tokens (`var(--space-*)`, `--control-h`), no new magic numbers where a token exists. No dead CSS: delete a rule you replace.

## 6. Commands

From `App/`, each ending `2>&1 | tail -30`:

1. `.venv/bin/python -m pytest tests/test_reservation_detail*.py tests/test_reservations*.py -q --tb=short -x 2>&1 | tail -30` (the stay rows of docs/context/test-map.md; use its exact files)
2. `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py -q -rs --tb=short -x 2>&1 | tail -30` (0 skipped; `App/tests/v2_mockup.py` holds the geometry helpers and the fixture).
3. Screenshots: Pobyt detail and the add-stay panel at 1024, 1280, 1440 and tablet 768, 820, plus 390 px. Put them in `docs/tasks/screenshots-NNNN/` and name each in the report with the measured value from §7. Look at each once.

Fixture caveat: the yellow demo banner and "UKÁZKA" sidebar chip appear only because the fixture account has demo data. Do not "fix" them.

## 7. Acceptance

- [ ] At 1280 all header action buttons on Pobyt have the same height (difference 0 px); the kebab has that height as width and height.
- [ ] Gap between guests table, police heading and status strip >= 24 px each.
- [ ] Add-stay form: label bottom to input top gap >= 4 px; all inputs/selects have equal height (difference 0 px); panel has a 1 px border.
- [ ] mockup browser test: 0 failed, 0 skipped. Screenshots attached (390 px unchanged in layout).

## 8. Stop and ask

Stop and write the report as `blocked` if: an anchor is not found; Step 1 shows the finding does NOT reproduce (report the numbers, change nothing); a test fails twice; you reach 25 tool calls; a file outside §3 needs a change; a step is unclear.

## 9. Report

`docs/tasks/NNNN-report.md`, 600 tokens at most: `git diff --stat`, each command with its last 5 lines, §7 ticked with measured numbers, Deviations, Questions, owner steps left. Set `Status: review`, open one PR. Never push to main.

## Risk list (for the reviewer)

The CSS diff in `App/app/static/app2.css` and any template named in §3.

## Owner steps

1. Review the PR, then merge with `scripts/merge-pr-on-green.sh`. Deploy is yours, manual.
