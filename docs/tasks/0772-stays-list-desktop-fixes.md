# 0772: Pobyty list: header overflow at 1024, filter chip style

Status: todo
Depends on: none | Base commit: <current main sha> | Branch: task/0772-stays-list-desktop
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

On `/reservations` at 1024 the header buttons run ~20 px past the content edge and "Jak to funguje?" wraps to two lines (audit finding 3, P1); the filter chips mix dashed and solid borders. Fix both without touching the phone list (0750).

## 2. Context

- `App/app/templates/reservations.html` line ~27 `<details class="ui-how stays-how ph-hide" data-how="stays">`; line ~33 `<div class="stays-head-actions">` holding send-all, `btn ghost` housebook download and `btn` add stay; lines ~96-101 `<div class="chips stays-chips">` with `<a class="chip ...">` and `chip ph-hide`.
- CSS: `App/app/static/app2.css` around 463 (`.stays-how`) and `grep -n "stays-head-actions\|\.chip\|stays-chips" App/app/static/*.css | head`.
- The "Jak to funguje?" style itself is brief 0775; here only fix its wrapping (`white-space:nowrap`) and do not restyle it.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/static/app2.css` | edit | header wrap, chip border |
| `App/app/templates/reservations.html` | edit only if a class must change | |
| `App/app/templates/base.html` | edit | cache key |

No other file may change.

## 4. Steps

1. **Verify the finding still reproduces first.** The audit (`/mnt/project-files/ux-desktop-audit/audit-report.md`, 2026-11-02, main 1bd2148) was made by reviewers looking at screenshots; every CSS cause below is an unverified guess. Render the page with the rich-host fixture (see `App/tests/v2_mockup.py`), measure with a throwaway Playwright snippet in the scratchpad (not committed): `getBoundingClientRect()` of the named elements at the stated widths. Write the real cause (selector and computed value) in one line in the report. If a finding does not reproduce, skip its steps and say so. Measure at 1024: right edge of `.stays-head-actions` vs content right edge; height of the "Jak to funguje?" summary; `border-style` of each `.chip` (which are dashed and why: probably `.chip.ph-hide` or an inactive state rule).
2. Header at 1024: let `.stays-head-actions` wrap (`flex-wrap:wrap; justify-content:flex-end; min-width:0`) and the title block shrink (`min-width:0`), so no button passes the content edge. Commit `0772 step 2`.
3. "Jak to funguje?" summary: `white-space:nowrap`. Commit.
4. Chips: one border style (`1px solid var(--line-strong)`) for every chip state; the `on` state differs by background only. Commit.
5. **Cache key.** In `App/app/templates/base.html` bump the `app2.css?v=` value (now `20261102-0743`) to `20261102-0770` style: today's date plus this brief number. If you changed `dashboard-calendar.css` or `cleaning.css`, bump the key of that file in the template that links it (`grep -rn "dashboard-calendar.css\|cleaning.css" App/app/templates | head`). Commit.


## 5. Do not touch

Anything outside §3. No new dependency, no new colour, no dark mode, no JS unless §4 says so. Use existing `ui-*` classes and tokens (`var(--space-*)`, `--control-h`), never new magic numbers where a token exists. No dead CSS: delete a rule you replace.

## 6. Commands

From `App/`, each ending `2>&1 | tail -30`:

1. `.venv/bin/python -m pytest tests/test_reservations*.py tests/test_stays*.py -q --tb=short -x 2>&1 | tail -30` (the stays row of docs/context/test-map.md; use its exact files)
2. `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py -q -rs --tb=short -x 2>&1 | tail -30` (0 skipped; `App/tests/v2_mockup.py` holds the geometry helpers and the fixture).
3. Screenshots (8 total unless §4 says otherwise): Pobyty (`/reservations`) at 1024, 1280, 1440 and tablet 768, 820, plus 390 px. Put them in `docs/tasks/screenshots-NNNN/` and name each in the report with the measured value from §7. Look at each once.

Fixture caveat: the yellow demo banner and "UKÁZKA" sidebar chip appear only because the fixture account has demo data. Do not "fix" them; a real host never sees them.

## 7. Acceptance

- [ ] At 1024 the right edge of the last header button is <= the content right edge (difference <= 0 px).
- [ ] "Jak to funguje?" summary height equals one line (<= 44 px) at 1024.
- [ ] Every `.chip` computed `border-top-style` is `solid`.
- [ ] 390 px stays list unchanged (compare the screenshot with main).
- [ ] mockup browser test: 0 failed, 0 skipped. Screenshots attached.

## 8. Stop and ask

Stop and write the report as `blocked` if: an anchor is not found; Step 1 shows the finding does NOT reproduce (report the measured numbers, change nothing); a test fails twice; you reach 25 tool calls; a file outside §3 needs a change; a step is unclear.

## 9. Report

`docs/tasks/NNNN-report.md`, 600 tokens at most: `git diff --stat`, each command with its last 5 lines, §7 ticked with the measured numbers, Deviations, Questions, owner steps left. Set `Status: review`, open one PR. Never push to main.

## Risk list (for the reviewer)

The CSS diff in `App/app/static/app2.css` and any template named in §3.

## Owner steps

1. Review the PR, then merge with `scripts/merge-pr-on-green.sh`. Deploy is yours, manual.
