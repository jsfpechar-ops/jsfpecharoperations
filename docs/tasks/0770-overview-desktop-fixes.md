# 0770: Overview: calendar clip, orphan links, stats spacing, bottom-nav overlap

Status: todo
Depends on: none | Base commit: <current main sha> | Branch: task/0770-overview-desktop
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Fix four desktop/tablet defects on the Overview (`/`): 14-day calendar clipped at 1024 (audit finding 1, P1), security prompt overlapping the bottom nav at 768 (finding 4, P1), orphan "+ Úklid" and "Smazat ukázková data" links and "Zobrazit další" touching the stats line (finding 14). They are the first things a host sees.

## 2. Context

Rules: v2 pages only, light mode, geometry tests with 0 skipped (AGENTS rule 7). Known anchors (verify with grep first):
- `App/app/templates/dashboard.html` line ~74 `<a href="/cleaning/new" class="ov-link">+ {{ t('nav.cleaning') }}</a>`; line ~75 the demo reset form `class="inline ov-inline ph-hide"` with `ui_button(t('demo.clear'), 'quiet', ...)`; line ~100 `<details class="needs-you-more ov-section ...">` ("Zobrazit další"); line ~123 `ov-cal-block`.
- `App/app/static/app2.css` lines 149-155 (`.ov-links`, `.ov-link`, `.ov-inline`), line 422 (`.ov-cal-block` hidden on v2), 231+ (tab bar shell below 1024).
- Calendar markup: `App/app/templates/_dashboard_calendar.html`, styles `App/app/static/dashboard-calendar.css`.
- Security prompt text "Přidat druhý způsob přihlášení": `grep -rn "second_factor\|druhý způsob" App/app/templates App/app/host_i18n.py | head`.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/static/app2.css` | edit | overflow, link style, spacing, z-index/padding |
| `App/app/static/dashboard-calendar.css` | edit only if the clip originates here | calendar min-width/overflow |
| `App/app/templates/dashboard.html` | edit | replace the two orphan links with `ui_button`/`ui-btn-quiet` (as already used for the demo clear button) |
| `App/app/templates/base.html` | edit | cache key |
| the template holding the security prompt | edit only if needed | z-index/placement |

No other file may change.

## 4. Steps

1. **Verify the finding still reproduces first.** The audit (`/mnt/project-files/ux-desktop-audit/audit-report.md`, 2026-11-02, main 1bd2148) was made by reviewers looking at screenshots; every CSS cause below is an unverified guess. Render the page with the rich-host fixture (see `App/tests/v2_mockup.py`), measure with a throwaway Playwright snippet in the scratchpad (not committed): `getBoundingClientRect()` of the named elements at the stated widths. Write the real cause (selector and computed value) in one line in the report. If a finding does not reproduce, skip its steps and say so. Targets: calendar right edge vs content right edge at 1024 (no clipping: `scrollWidth <= clientWidth` of the calendar container, last day label fully visible); security prompt bottom vs tab bar top at 768/820.
2. Calendar: give the 14-day grid either `min-width:0` on its flex/grid parent chain or a horizontal scroll container (`overflow-x:auto`) only if it cannot fit at 1024 with the 64 px rail; prefer shrinking columns over scrolling. Commit `0770 step 2`.
3. Links: render "+ Úklid" and "Smazat ukázková data" with the same quiet button style as the other header actions, inside one flex row (`.ov-links`, gap `var(--space-3)`), with a 36 px min height at 1024+ and 44 px below. Delete `.ov-link` rules that become unused. Commit.
4. "Zobrazit další": add `margin-top:var(--space-3)` between the stats line and the `.needs-you-more` summary card on desktop. Commit.
5. Security prompt at 768/820: it must sit in normal flow above the content, never fixed under the tab bar; add `padding-bottom: calc(var(--tabbar-h) + var(--tabbar-safe) + var(--space-4))` to the page wrapper if content is hidden behind the bar. Commit.
6. **Cache key.** In `App/app/templates/base.html` bump the `app2.css?v=` value (now `20261102-0743`) to `20261102-0770` style: today's date plus this brief number. If you changed `dashboard-calendar.css` or `cleaning.css`, bump the key of that file in the template that links it (`grep -rn "dashboard-calendar.css\|cleaning.css" App/app/templates | head`). Commit.


## 5. Do not touch

Anything outside §3. No new dependency, no new colour, no dark mode, no JS unless §4 says so. Use existing `ui-*` classes and tokens (`var(--space-*)`, `--control-h`), never new magic numbers where a token exists. No dead CSS: delete a rule you replace.

## 6. Commands

From `App/`, each ending `2>&1 | tail -30`:

1. `.venv/bin/python -m pytest tests/test_dashboard*.py -q --tb=short -x 2>&1 | tail -30` (the dashboard rows of docs/context/test-map.md; use the exact files the row lists)
2. `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py -q -rs --tb=short -x 2>&1 | tail -30` (0 skipped; `App/tests/v2_mockup.py` holds the geometry helpers and the fixture).
3. Screenshots (8 total unless §4 says otherwise): Overview (`/`) at 1024, 1280, 1440 and tablet 768, 820, plus 390 px. Put them in `docs/tasks/screenshots-NNNN/` and name each in the report with the measured value from §7. Look at each once.

Fixture caveat: the yellow demo banner and "UKÁZKA" sidebar chip appear only because the fixture account has demo data. Do not "fix" them; a real host never sees them.

## 7. Acceptance

- [ ] At 1024 the 14-day calendar's right edge is <= the content column's right edge (difference <= 0 px) and the last day label is not clipped.
- [ ] At 768 and 820 the security prompt's bottom is >= 8 px above the tab bar's top; no overlap.
- [ ] "+ Úklid" and "Smazat ukázková data" have the same height and font size as the other quiet header buttons (36 px at >= 1024).
- [ ] Gap between stats line and "Zobrazit další" card >= 12 px at 1280.
- [ ] mockup browser test: 0 failed, 0 skipped. Screenshots attached.

## 8. Stop and ask

Stop and write the report as `blocked` if: an anchor is not found; Step 1 shows the finding does NOT reproduce (report the measured numbers, change nothing); a test fails twice; you reach 25 tool calls; a file outside §3 needs a change; a step is unclear.

## 9. Report

`docs/tasks/NNNN-report.md`, 600 tokens at most: `git diff --stat`, each command with its last 5 lines, §7 ticked with the measured numbers, Deviations, Questions, owner steps left. Set `Status: review`, open one PR. Never push to main.

## Risk list (for the reviewer)

The CSS diff in `App/app/static/app2.css` and any template named in §3.

## Owner steps

1. Review the PR, then merge with `scripts/merge-pr-on-green.sh`. Deploy is yours, manual.
