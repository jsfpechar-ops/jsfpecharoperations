# 0771: Úklid page: calendar chips, tall cell, left edge, header links, Sdílet button

Status: todo
Depends on: 0770 | Base commit: <current main sha> | Branch: task/0771-cleaning-desktop
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Fix the desktop defects on `/cleaning` (audit finding 2, P1; 11 and P3 notes): truncated calendar chips at 1024/1440, one oddly tall cell (2 Nov), cramped overflow links, content left edge 290 px vs the 256 px used elsewhere, tiny header links, "Sdílet" button 44 px vs the 38 px standard.

## 2. Context

- `App/app/templates/cleaning.html` line 10: `<div class="head cleaning-head">` with `<p class="ov-links"><a class="ov-link" href="/cleaning/new" ...>` and `<a class="btn" href="/cleaning/shares">{{ ct('share_cleaner') }}</a>`.
- Calendar partials: `_cleaning_calendar.html`, `_cleaning_screen.html`; styles `App/app/static/cleaning.css`, `dashboard-calendar.css`, `app2.css` (`.ov-link` at 149-155).
- Left edge 290 vs 256: find the wrapper that adds the extra 34 px (`grep -n "cleaning" App/app/static/app2.css | head -20`).
- If 0770 is merged, reuse its link style; if not, do not wait, use `ui-btn-quiet`.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/static/cleaning.css` | edit | chip overflow, cell height, links |
| `App/app/static/app2.css` | edit | left edge, button height |
| `App/app/templates/cleaning.html` | edit | header link/button classes |
| `App/app/templates/base.html` | edit | cache key |

No other file may change.

## 4. Steps

1. **Verify the finding still reproduces first.** The audit (`/mnt/project-files/ux-desktop-audit/audit-report.md`, 2026-11-02, main 1bd2148) was made by reviewers looking at screenshots; every CSS cause below is an unverified guess. Render the page with the rich-host fixture (see `App/tests/v2_mockup.py`), measure with a throwaway Playwright snippet in the scratchpad (not committed): `getBoundingClientRect()` of the named elements at the stated widths. Write the real cause (selector and computed value) in one line in the report. If a finding does not reproduce, skip its steps and say so. Measure at 1024 and 1440: chip `scrollWidth` vs `clientWidth`, height of every day cell in the same row (find the 2 Nov cell and what makes it taller: probably an expanded overflow list or a long chip), `.cleaning-head` left edge, "Sdílet" height.
2. Chips: allow the chip label to use the cell width (`min-width:0; overflow:hidden; text-overflow:ellipsis` stays, but remove any fixed `max-width` and the property prefix if it causes the cut); at 1024 fewer columns of text is acceptable, but "Úklid" plus a property initial must remain readable. Commit `0771 step 2`.
3. Cells in one week row share one height (`grid-auto-rows:1fr` or equal `min-height`); overflow ("+N") is a quiet link with >= 24 px height and `var(--space-1)` padding. Commit.
4. Left edge: remove the extra margin/padding so the content starts at the same x as Pobyty (256 px at 1280+, rail layout at 1024). Commit.
5. Header: "+ Úklid" and "Nastavení" become `ui-btn-quiet` links (36 px at 1024+); "Sdílet" gets the standard `ui-btn` height (38 px), same as the Pobyty header button. Commit.
6. **Cache key.** In `App/app/templates/base.html` bump the `app2.css?v=` value (now `20261102-0743`) to `20261102-0770` style: today's date plus this brief number. If you changed `dashboard-calendar.css` or `cleaning.css`, bump the key of that file in the template that links it (`grep -rn "dashboard-calendar.css\|cleaning.css" App/app/templates | head`). Commit.


## 5. Do not touch

Anything outside §3. No new dependency, no new colour, no dark mode, no JS unless §4 says so. Use existing `ui-*` classes and tokens (`var(--space-*)`, `--control-h`), never new magic numbers where a token exists. No dead CSS: delete a rule you replace.

## 6. Commands

From `App/`, each ending `2>&1 | tail -30`:

1. `.venv/bin/python -m pytest tests/test_cleaning*.py -q --tb=short -x 2>&1 | tail -30` (the cleaning row of docs/context/test-map.md; use its exact files)
2. `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py -q -rs --tb=short -x 2>&1 | tail -30` (0 skipped; `App/tests/v2_mockup.py` holds the geometry helpers and the fixture).
3. Screenshots (8 total unless §4 says otherwise): Úklid (`/cleaning`) at 1024, 1280, 1440 and tablet 768, 820, plus 390 px. Put them in `docs/tasks/screenshots-NNNN/` and name each in the report with the measured value from §7. Look at each once.

Fixture caveat: the yellow demo banner and "UKÁZKA" sidebar chip appear only because the fixture account has demo data. Do not "fix" them; a real host never sees them.

## 7. Acceptance

- [ ] At 1024 and 1440 no calendar chip has `scrollWidth > clientWidth + 1` except a label longer than the cell by design; "Úklid" plus the property initial is fully visible.
- [ ] All day cells in one week row have equal height (difference 0 px).
- [ ] `.cleaning-head` left edge equals the Pobyty page's left edge at 1280 (difference 0 px).
- [ ] "Sdílet" height equals the Pobyty header button height (38 px).
- [ ] Header links are >= 36 px tall at >= 1024.
- [ ] mockup browser test: 0 failed, 0 skipped. Screenshots attached.

## 8. Stop and ask

Stop and write the report as `blocked` if: an anchor is not found; Step 1 shows the finding does NOT reproduce (report the measured numbers, change nothing); a test fails twice; you reach 25 tool calls; a file outside §3 needs a change; a step is unclear.

## 9. Report

`docs/tasks/NNNN-report.md`, 600 tokens at most: `git diff --stat`, each command with its last 5 lines, §7 ticked with the measured numbers, Deviations, Questions, owner steps left. Set `Status: review`, open one PR. Never push to main.

## Risk list (for the reviewer)

The CSS diff in `App/app/static/app2.css` and any template named in §3.

## Owner steps

1. Review the PR, then merge with `scripts/merge-pr-on-green.sh`. Deploy is yours, manual.
