# 0774: Nemovitost page: left edge, duplicate heading, margins, aside, save bar

Status: todo
Depends on: none | Base commit: <current main sha> | Branch: task/0774-property-desktop
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Audit findings 5, 11 and 15 on the property page (`/apartments/<id>`): content left edge indented vs other pages, "Základní údaje" shown twice, sub-headings with no top margin, fields 300 px in a 650 px card, aside not aligned with the form, and the floating Zrušit/Uložit bar hovering mid-page and colliding with the help button at 1440.

## 2. Context

- `App/app/templates/_property_editor.html`: `<details class="prop-sec" id="sec-basics">` with `<b>{{ t('property_page.sec.basics.title') }}</b>` (line ~52) and inside `<h2 class="property-section-title">{{ t('apartment.form.basics.title') }}</h2>` (~55): this pair is the duplicate. Other `property-section-title` at ~74, 89, 95.
- `App/app/static/app2.css`: `body.v2 .property-settings-form{display:contents}` (359), `.savebar` rules at 352, 820, 946-948, 995-1022, `.property-section-title` (938).
- The help button is the Havel/help FAB; on v2 desktop find it with `grep -n "havel-fab\|help-fab" App/app/static/*.css App/app/templates/*.html | head`.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/static/app2.css` | edit | edges, margins, grid, savebar |
| `App/app/templates/_property_editor.html` | edit | drop the duplicate heading |
| `App/app/templates/base.html` | edit | cache key |

No other file may change.

## 4. Steps

1. **Verify the finding still reproduces first.** The audit (`/mnt/project-files/ux-desktop-audit/audit-report.md`, 2026-11-02, main 1bd2148) was made by reviewers from screenshots; every CSS cause below is an unverified guess. Render the page with the rich-host fixture (`App/tests/v2_mockup.py`), measure with a throwaway Playwright snippet in the scratchpad (not committed) using `getBoundingClientRect()` at the stated widths. Write the real cause (selector, computed value) in one line in the report. A finding that does not reproduce: skip its steps and say so. Measure at 1440: left edge of the property content vs Pobyty (256 px expected), the two "Základní údaje" occurrences, margin-top of each `.property-section-title`, input width vs card width, aside top vs form top, savebar rect vs help-button rect.
2. Duplicate: keep the summary title (it is the section handle) and remove the inner `<h2 class="property-section-title">` for basics only (line ~55). Check that no test greps for that h2 (`grep -rn "apartment.form.basics.title" App/tests | head -3`); if one does, STOP. Commit `0774 step 2`.
3. Headings: `body.v2 .property-section-title{margin:var(--space-6) 0 var(--space-2)}` and `:first-child{margin-top:0}`. Commit.
4. Fields: inside the card, field grid uses two columns of `minmax(0,1fr)` from 1024, inputs `width:100%` (no 300 px fixed width); aside `align-self:start` and its top equals the form card top. Left edge matches other v2 pages. Commit.
5. Save bar (desktop >= 1024): `position:sticky; bottom:var(--space-4)` inside the form column instead of fixed to the viewport, and keep `right` clear of the help button (already `calc(var(--control-h) + ...)` at line 946; verify the rects no longer overlap at 1440). Delete the superseded fixed-position rule. Commit.
6. **Cache key.** In `App/app/templates/base.html` bump `app2.css?v=` (now `20261102-0743`) to today's date plus this brief number. If you changed another stylesheet, bump its key too (`grep -rn "<name>.css" App/app/templates | head`). Commit.


## 5. Do not touch

Anything outside §3. No new dependency, no new colour, no dark mode, no JS unless §4 says so. Use existing `ui-*` classes and tokens (`var(--space-*)`, `--control-h`), no new magic numbers where a token exists. No dead CSS: delete a rule you replace.

## 6. Commands

From `App/`, each ending `2>&1 | tail -30`:

1. `.venv/bin/python -m pytest tests/test_property_page*.py tests/test_apartment*.py -q --tb=short -x 2>&1 | tail -30` (the property rows of docs/context/test-map.md; use its exact files)
2. `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py -q -rs --tb=short -x 2>&1 | tail -30` (0 skipped; `App/tests/v2_mockup.py` holds the geometry helpers and the fixture).
3. Screenshots: Nemovitost (`/apartments/<id>`) at 1024, 1280, 1440 and tablet 768, 820, plus 390 px. Put them in `docs/tasks/screenshots-NNNN/` and name each in the report with the measured value from §7. Look at each once.

Fixture caveat: the yellow demo banner and "UKÁZKA" sidebar chip appear only because the fixture account has demo data. Do not "fix" them.

## 7. Acceptance

- [ ] At 1280 and 1440 the page content left edge equals the Pobyty page's (difference 0 px).
- [ ] The text "Základní údaje" appears once in the basics section (count 1).
- [ ] Every `.property-section-title` except the first in a section has margin-top >= 24 px.
- [ ] Inputs fill their grid cell (input width / cell width >= 0.95); aside top equals form card top (difference <= 2 px).
- [ ] At 1440 the save bar rect and the help button rect do not intersect.
- [ ] 390 px property page unchanged (the phone savebar rules stay).
- [ ] mockup browser test: 0 failed, 0 skipped. Screenshots attached.

## 8. Stop and ask

Stop and write the report as `blocked` if: an anchor is not found; Step 1 shows the finding does NOT reproduce (report the numbers, change nothing); a test fails twice; you reach 25 tool calls; a file outside §3 needs a change; a step is unclear.

## 9. Report

`docs/tasks/NNNN-report.md`, 600 tokens at most: `git diff --stat`, each command with its last 5 lines, §7 ticked with measured numbers, Deviations, Questions, owner steps left. Set `Status: review`, open one PR. Never push to main.

## Risk list (for the reviewer)

The CSS diff in `App/app/static/app2.css` and any template named in §3.

## Owner steps

1. Review the PR, then merge with `scripts/merge-pr-on-green.sh`. Deploy is yours, manual.
