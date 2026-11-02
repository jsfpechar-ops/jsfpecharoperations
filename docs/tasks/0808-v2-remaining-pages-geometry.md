# 0808 brief: owner geometry fixes on the 0800-0804 pages

Status: todo
Executor: Haiku 5.5, alone, in /home/claude/jsfpecharoperations on branch claude/project-thread-a41o7b (checked out; App/.venv exists). Do not commit, push, checkout, reset, stash or restore: the orchestrator commits.

## 1. Objective
Josef reviewed the screenshots of the pages moved to v2 in briefs 0800-0804 and asked for four fixes. Apply each wherever it occurs on these pages: new property (/apartments/new), onboarding (/onboarding), setup wizard, host guest guide, Průvodce (/guide), Havel (/havel), cleaning new/shares/properties. Add a geometry test for each rule so it cannot come back.

## 2. Context
The pages' look lives in the `/* 0800 … */` to `/* 0804 … */` blocks of `App/app/static/app2.css`. Shared browser test: `App/tests/test_0800_v2_remaining_pages_browser.py` (6 widths 320/390/768/1024/1280/1440, `UBYHOST_SHOTS_0800=1` writes docs/tasks/screenshots-0800/). Look at the current PNGs there before you change anything.

## 3. Files
`App/app/static/app2.css` (only inside the 0800-0804 blocks), templates of the pages above (class/markup order only, no text, no behaviour), `App/tests/test_0800_v2_remaining_pages_browser.py`; for step 0 also `App/app/templates/base.html` (skeleton only).

## 4. Steps
Env for test runs (from App/): `export PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_REQUIRE_BROWSER=1`.
0. First finish the 10 wizard failures left by 0807 (read `docs/tasks/0807-report.md`); orchestrator decisions, no owner question needed:
   - Guest-link cards at >=1024 px: the link and PIN cards sit side by side (`.setup-wizard-cards{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}` with the message card spanning both columns), stacked below 1024. This is the old layout; restore it in the 0801 block.
   - Exit button in the wizard head: `min-height:36px` (the v2 `.ui-btn` size), keep it beside the h1.
   - Skeleton (`window.ubyhostSkeleton.start()` then `[data-page-skeleton]` never visible): find why on v2 pages (likely skeleton.css not loaded in the v2 branch of base.html, or an app2.css rule hiding it); fix it for all v2 pages in base.html or app2.css (new block `/* 0808 skeleton (v2) */` at the end), not by touching the test.
   - Then `tests/test_onboarding_wizard_browser.py` must be 0 failed.
   Answers after the first run (the first two items are already in the 0801 block, uncommitted; keep them):
   - Copy cards still stacked at 1280: the 0801 block never sets `display:grid` on `.setup-wizard-cards`, and `.setup-wizard-card` is not a flex column, so `margin-top:auto` on the copy button does nothing. Add `body.v2 .wiz-page .setup-wizard-cards{display:grid;grid-template-columns:minmax(0,1fr);gap:16px}` and `body.v2 .wiz-page .setup-wizard-card{display:flex;flex-direction:column;min-width:0}` (old host.css 1358). The test expectation (same row at 1280) stays.
   - Skeleton cause: v2 pages do not load host2.css, which holds all `.ui-skel*`, `.ui-bone*` and `@keyframes ui-pulse` rules (host2.css lines 198-219, plus the `.ui-w14/18/30/40/60` width helpers: grep them). Without them the bones are empty inline spans, so the skeleton has 0 height and is "not visible". Port those rules into a new block `/* 0808 skeleton (v2) */` at the end of app2.css, scoped `body.v2` instead of `.host-workspace`, replacing any variable not defined in tokens.css/app2.css with the v2 equivalent (check with grep; e.g. `--surface-2`→`var(--side2)`, `--surface`→`var(--s)`). Include the reduced-motion `animation:none` rule. No base.html change needed.
   - Verify the exit button: the `.setup-wizard-exit .ui-btn{min-height:36px}` rule must win at 1280 (check computed height; raise specificity if a `.ui-btn-sm` or similar rule beats it).
a. Help "?" next to its label. Every `.help-tip` / `.help-tip-btn` that belongs to a form label (e.g. "Street" on /apartments/new, wizard fields) sits on the same line as the label text, 6-8 px after it, vertically centred with it, never on its own line below. Typical fix: the label row is `display:flex;align-items:center;gap:6px` (inline-flex if the label wraps an input). Test: for each label with a help tip, the tip's vertical centre is within the label text's line box (|centre_tip - centre_label| <= 4 px) and tip.x >= label_text.right.
b. Grouped actions on the onboarding step cards (see owner screenshot: status "Done", the primary button and "Learn why" float apart and "Learn why" wraps onto two lines). Put status, button and "Learn why" into one right-hand group: `display:flex;align-items:center;gap:12px`, `white-space:nowrap` on "Learn why" and the status. Card text and the group keep at least 16 px between them; buttons inside any group on these pages keep at least 8 px between each other. At <768 px the group goes below the text, left-aligned, same 12 px gap. Test: "Learn why" control height equals a single line (no wrap); horizontal gap between neighbouring controls in a group is 8-16 px; gap between text column and group >= 16 px.
c. Text padding on Průvodce (/guide) and help pages: no text touches a card or panel edge. Every card/panel with text has at least 16 px inner padding (20-24 px at >=1024). Test: for each `.ui-card` (or the page's card class) on /guide and the guest guide, each direct text child's left/right edge is >= 16 px inside the card box.
d. Havel chat like a standard chatbot. On /havel (and the Havel panel if it uses the same markup), messages stack vertically, one per row, assistant left, user right, max-width ~80% of the thread. The topic buttons ("Add or change a stay", "Guest link and PIN", …) are a vertical list below the greeting, each full width of the message column (max ~420 px), left-aligned icon + text with 8 px gap, 8 px between items, rounded like `.ui-btn` (no square boxes). Test: topic buttons share the same x (±1 px) and each next one has a larger y; no two messages share a row.
e. Run the whole 0800 file at all widths, then regenerate screenshots: `UBYHOST_SHOTS_0800=1 .venv/bin/python -m pytest tests/test_0800_v2_remaining_pages_browser.py -q 2>&1 | tail -5`.

## 5. Do not touch
Other app2.css blocks (outside 0800-0804), copy text, behaviour, other pages, cache key (the orchestrator bumps it), screenshot folders other than screenshots-0800.

## 6. Commands
From App/, env above:
- `.venv/bin/python -m pytest tests/test_0800_v2_remaining_pages_browser.py -q --tb=line 2>&1 | tail -8` → 0 failed
- `.venv/bin/python -m pytest tests/test_onboarding_wizard_browser.py tests/test_onboarding.py tests/test_design_setup_wizard_browser.py tests/test_quick_answers_browser.py -q --tb=line -p no:cacheprovider 2>&1 | tail -8` → 0 failed
- `.venv/bin/python -m pytest tests -q -k "havel or guide" --tb=line 2>&1 | tail -8` → 0 failed
- repo root: `python3 scripts/design_lint.py 2>&1 | tail -3`

## 7. Acceptance
All commands in section 6 green; screenshots-0800 regenerated showing all four fixes.

## 8. Stop and ask
Stop at 30 tool calls, or if a fix needs a text change or a behaviour change.

## 9. Report
`docs/tasks/0808-report.md`: per step what changed (file, selector), the new tests, final tails.
