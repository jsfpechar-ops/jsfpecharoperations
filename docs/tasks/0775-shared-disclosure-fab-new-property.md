# 0775: Shared: 'Jak to funguje?' disclosure, help button clearance, Nové ubytování on the v2 shell

Status: todo
Depends on: 0770, 0772 (they must not restyle the disclosure) | Base commit: <current main sha> | Branch: task/0775-shared-v2-polish
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Audit findings 6, 9 and 10: one consistent full-width, left-aligned "Jak to funguje?" disclosure on every v2 page (today a tiny floating card, double chevron, different width per page, centred on Ubytování); the help button must not cover content; `/apartments/new` must use the v2 shell like the other host pages.

## 2. Context

- Shared markup: `App/app/templates/host_page.html` lines ~28-39: `<details class="ui-how" data-how=...>` with `<summary class="ui-how-toggle">{{ icon('circle-help', 16) }}<span>...</span>{{ icon('chevron-down', 16, 'ui-how-chevron') }}</summary>`.
- Page-specific copies to merge into one rule (all in `App/app/static/app2.css`): `.ov-head details.ui-how` (227-229), `body.v2 details.stays-how` (463-464), `body.v2 .ov-how` (685); old shell `host2.css` 712-722 (`max-width:40rem` body, pill toggle). Overview also has its own markup in `dashboard.html` (~70) and stays in `reservations.html` (~27, class `stays-how`).
- Double chevron: the CSS `::before`/marker plus the `chevron-down` icon; find the second one by measuring.
- Help FAB: `body.v2:has(.havel-fab) .wrap.with-sidebar{padding-bottom:...}` at `app2.css` 756; `.havel-fab` is hidden at line 130 under some condition. Verify which element is the "help button" at 1024/1440 before changing.
- `App/app/templates/apartment_form.html` line 3: `{% set v2 = editing %}`; non-editing (`/apartments/new`) therefore gets the old shell. `_property_create.html` holds the form body.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/static/app2.css` | edit | one `body.v2 .ui-how*` rule set; delete the 3 page-specific copies; FAB padding |
| `App/app/templates/host_page.html` | edit only if the chevron/label markup must change | |
| `App/app/templates/dashboard.html`, `reservations.html` | edit | drop the page-specific classes (`ov-how`, `stays-how`) only if the shared rule replaces them |
| `App/app/templates/apartment_form.html` | edit | `{% set v2 = true %}` |
| `App/app/templates/base.html` | edit | cache key |

No other file may change.

## 4. Steps

1. **Verify the finding still reproduces first.** The audit (`/mnt/project-files/ux-desktop-audit/audit-report.md`, 2026-11-02, main 1bd2148) was made by reviewers from screenshots; every CSS cause below is an unverified guess. Render the page with the rich-host fixture (`App/tests/v2_mockup.py`), measure with a throwaway Playwright snippet in the scratchpad (not committed) using `getBoundingClientRect()` at the stated widths. Write the real cause (selector, computed value) in one line in the report. A finding that does not reproduce: skip its steps and say so. Measure on Overview, Pobyty, Pobyt, Ubytování, Nemovitost at 1280: disclosure width vs content width, text-align of the label, number of chevrons rendered, and the help button rect vs the last content element at 1024 and 1440.
2. Disclosure: one rule set under `body.v2 .ui-how`: `display:block; width:100%; box-sizing:border-box`; toggle `width:100%; justify-content:flex-start; text-align:left`, chevron pushed right with `margin-left:auto`, exactly one chevron; body `max-width:none`. `white-space:nowrap` on the label. Delete `.ov-head details.ui-how`, `.stays-how`, `.ov-how` variants that this replaces (keep their `:not([open]) .ui-how-body{display:none}` only if still needed). Commit `0775 step 2`.
3. Help FAB clearance: for v2 desktop add bottom padding to the content wrapper equal to `calc(var(--control-h) + var(--space-6))` whenever a FAB is rendered (extend the rule at line 756 to the exact selector verified in Step 1). Commit.
4. Nové ubytování: set `{% set v2 = true %}` in `apartment_form.html`; load `/apartments/new` and compare with Pobyty: sidebar, logo, icon order, left edge. If the form body breaks (it is unstyled in v2), fix only with existing `ui-field`/card classes from 0773, in this file's CSS section. Commit.
5. **Shared button and section spacing (owner feedback 2026-11-02: buttons are too close to each other).** Put one rule in `body.v2` on the shared ui-* classes so every v2 page behaves the same: adjacent buttons/links in a row use `gap:var(--space-3)` (12 px), a button or help row that ends a block is followed by >= `var(--space-6)` (24 px) before the next heading, and an empty-state line sits `var(--space-4)` (16 px) below the row above it. Remove page-local margins this makes redundant. Check Overview, Úklid, Pobyty, Pobyt and Nemovitost headers and empty states.

5. **Cache key.** In `App/app/templates/base.html` bump `app2.css?v=` (now `20261102-0743`) to today's date plus this brief number. If you changed another stylesheet, bump its key too (`grep -rn "<name>.css" App/app/templates | head`). Commit.


## 5. Do not touch

Anything outside §3. No new dependency, no new colour, no dark mode, no JS unless §4 says so. Use existing `ui-*` classes and tokens (`var(--space-*)`, `--control-h`), no new magic numbers where a token exists. No dead CSS: delete a rule you replace.

## 6. Commands

From `App/`, each ending `2>&1 | tail -30`:

1. `.venv/bin/python -m pytest tests/test_host_page*.py tests/test_apartment*.py tests/test_dashboard*.py -q --tb=short -x 2>&1 | tail -30` (rows for host_page, apartments, dashboard in docs/context/test-map.md; use their exact files)
2. `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py -q -rs --tb=short -x 2>&1 | tail -30` (0 skipped; `App/tests/v2_mockup.py` holds the geometry helpers and the fixture).
3. Screenshots: Overview, Pobyty, Pobyt, Ubytování, Nemovitost (disclosure) and `/apartments/new` at 1024, 1280, 1440 and tablet 768, 820, plus 390 px. Put them in `docs/tasks/screenshots-NNNN/` and name each in the report with the measured value from §7. Look at each once.

Fixture caveat: the yellow demo banner and "UKÁZKA" sidebar chip appear only because the fixture account has demo data. Do not "fix" them.

## 7. Acceptance

- [ ] On all five v2 pages at 1280, the closed disclosure's width equals the content column width (difference 0 px), its label is left-aligned (label left edge - toggle left edge <= 24 px), and exactly 1 chevron is visible.
- [ ] At 1024 and 1440 no content element's bottom edge lies under the help button (rects do not intersect at scroll bottom).
- [ ] `/apartments/new` has the same sidebar markup class and left edge as `/reservations` (difference 0 px) and `body.v2` is present.
- [ ] `grep -n "stays-how\|ov-how" App/app/static/app2.css` returns only rules still referenced by a template.
- [ ] On the five v2 pages at 1024/1280/1440 (incl. the empty-account Overview): gap between adjacent buttons in a row >= 12 px; gap from a block-ending button to the next heading >= 24 px; empty-state line >= 16 px below the row above (getBoundingClientRect).
- [ ] mockup browser test: 0 failed, 0 skipped. Screenshots attached.

## 8. Stop and ask

Stop and write the report as `blocked` if: an anchor is not found; Step 1 shows the finding does NOT reproduce (report the numbers, change nothing); a test fails twice; you reach 25 tool calls; a file outside §3 needs a change; a step is unclear.

## 9. Report

`docs/tasks/NNNN-report.md`, 600 tokens at most: `git diff --stat`, each command with its last 5 lines, §7 ticked with measured numbers, Deviations, Questions, owner steps left. Set `Status: review`, open one PR. Never push to main.

## Risk list (for the reviewer)

The CSS diff in `App/app/static/app2.css` and any template named in §3.

## Owner steps

1. Review the PR, then merge with `scripts/merge-pr-on-green.sh`. Deploy is yours, manual.
