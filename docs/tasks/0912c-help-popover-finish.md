# 0912c: help popover finish (three failures of the stricter test)

Status: review
Depends on: 0912b (3 Haiku sessions used; its work is on disk, uncommitted) | Base commit: current HEAD of `vibe/stay-fee-guest-payment-plan-73df64` plus the uncommitted 0912b work | Branch: this branch (checked out). No commit, no push, no branch: the orchestrator commits.
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

`test_opened_help_stays_inside_the_viewport` (App/tests/test_layout_lint_browser.py, added by 0912b) fails on three things. Fix all three in the shared components, keep the test exactly as strict, and make it pass with 0 skipped. Orchestrator decisions are final; do not relax the test.

## 2. Context

Rules: design-system Help row ("max 360 px, fits the 390 px screen, 16 px gutter"); AGENTS.md rules 6, 7. Run every command in the foreground (no `run_in_background`, no `&`).

The three failures (from `docs/tasks/0912b-report.md`, 0912c run):

1. **stays-how box, right gutter 12 px at 320 and 390.** The box is anchored with `left:0` to the title row, which starts at x = 20 px (main padding). Box spans 20 to 308 at 320. Needs 16 px both sides, so its left must be 16 px.
2. **`details.page-help` dialog is 320 px wide at 390** (needs >= 356). App/app/static/app2.css line 2040 caps it at `min(320px, ...)`. Affects /stays, properties, fee-setup, stay-detail, stays-archive, property-detail(-configured).
3. **Tooltips near the page bottom at 320** (setup-property, setup-police, setup-guest-link, trigger 9): the last link sits at about 782 px in an 800 px viewport, under the fixed phone tab bar. Root cause: `place()` in App/app/static/app.js (about line 1972 to 2012) limits the tooltip to `vh - margin`, ignoring the fixed bottom bar (`.ui-tabbar`, host2.css 331: `position:fixed; height:calc(var(--tabbar-h) + safe-area)`, phone only).

Anchors (each must be found verbatim; if not, STOP, section 8).

app2.css, the 0912b block (about lines 1214 to 1220):
```
@media (max-width:1023px){
body.v2 .head-title-row:has(>details.stays-how){position:relative}
body.v2 .head-title-row>details.stays-how{position:static}
body.v2 .head-title-row>details.stays-how[open] .ui-how-body{left:0;right:auto;width:min(360px,calc(100vw - 32px));max-width:none;max-height:none}
}
```
app2.css line 2040 contains the exact substring `transform:translate(-50%,-50%);width:min(320px,calc(100vw - 32px));max-height:calc(100vh - 32px)`.

app.js, inside `place()`:
```
      var top = r.bottom + 6;
      if (top + h > vh - margin && r.top - 6 - h >= margin) top = r.top - 6 - h;
      top = Math.max(margin, Math.min(top, vh - h - margin));
```

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/static/app2.css | edit | Fix 1 (left offset) and Fix 2 (dialog width) |
| App/app/static/app.js | edit | Fix 3 (tab-bar-aware bottom in `place()`) |
| App/app/templates/base.html | edit | bump the two `?v=` for app2.css and app.js |
| App/tests/static_versions.json | regenerate | via the repo's static-versions tool (step 5) |
| docs/tasks/screenshots-0912c/*.png | add | screenshots (step 7) |
| docs/tasks/0912c-report.md | add | report |
| docs/tasks/0912c-help-popover-finish.md | edit | Status line only |

No other file may change. Do NOT edit App/tests/test_layout_lint_browser.py (the test stays as strict as it is).

## 4. Steps

**Step 1: set Status.** Change line 3 of this brief to `Status: in-progress`.

**Step 2: Fix 1, stays-how box gutter (app2.css).** First measure: in a throwaway Playwright script in the scratchpad (not in the repo), reuse the `wide_host` / `wide_base` setup of the 0912b screenshot run (or a temporary test file in App/tests that you delete afterwards), open `/stay-fees` at 320, 390 and 768 px, and print `document.querySelector('.head-title-row').getBoundingClientRect().left`. Call it `L` (expected 20 at 320 and 390; check 768). Then in the 0912b block replace `left:0;right:auto;width:min(360px,calc(100vw - 32px))` with `left:calc(16px - L px)` where the value is `16 - L` (expected `-4px`), keeping the width. Expected diff if L = 20 at every width below 1024:
```
-body.v2 .head-title-row>details.stays-how[open] .ui-how-body{left:0;right:auto;width:min(360px,calc(100vw - 32px));max-width:none;max-height:none}
+body.v2 .head-title-row>details.stays-how[open] .ui-how-body{left:-4px;right:auto;width:min(360px,calc(100vw - 32px));max-width:none;max-height:none}
```
If L differs at 768 (a tablet gutter), add a second `@media (min-width:768px)` line in the same block with its own `16 - L` value. Result to verify: at 320 the box spans 16 to 304 (gutter 16 on both sides), at 390 it is 358 px wide and spans 16 to 374, at 768 it spans 16 to 376. Write the three `left`/`right` pairs into the report.

**Step 3: Fix 2, page-help dialog width (app2.css line 2040).** Exact diff (only this substring changes):
```
-transform:translate(-50%,-50%);width:min(320px,calc(100vw - 32px));max-height:calc(100vh - 32px)
+transform:translate(-50%,-50%);width:min(360px,calc(100vw - 32px));max-height:calc(100vh - 32px)
```
Command: `grep -c 'width:min(360px,calc(100vw - 32px));max-height:calc(100vh - 32px)' App/app/static/app2.css | tail -30` (expect 1).

**Step 4: Fix 3, tooltip clears the fixed tab bar (app.js `place()`).** Replace the three anchor lines with:
```
      /* 0912c: on phones the fixed tab bar covers the bottom of the screen; the visible bottom is above it. */
      var bar = document.querySelector(".ui-tabbar");
      var barH = 0;
      if (bar && window.getComputedStyle(bar).position === "fixed") barH = bar.getBoundingClientRect().height;
      var floorY = vh - barH - margin;
      var top = r.bottom + 6;
      if (top + h > floorY && r.top - 6 - h >= margin) top = r.top - 6 - h;
      top = Math.max(margin, Math.min(top, floorY - h));
```
(`barH` is 0 on desktop where the tab bar is `display:none`, so desktop is unchanged: `floorY = vh - margin`.) Do not add page-level padding or margin hacks anywhere.

**Step 5: version bumps and regenerate.** In App/app/templates/base.html change `app2.css?v=20261104-0912c` to `app2.css?v=20261104-0912d` and `app.js?v=20261104-0912b` to `app.js?v=20261104-0912d`. Then find how static_versions.json is regenerated (`grep -n 'static_versions' App/tests/test_static_versions.py scripts/*.py | head -10 | tail -30`; 0912b used a regenerate command, normally something like `python3 scripts/static_versions.py --write` or the test's own helper) and run it so the sha256 and `v` of app.js and app2.css are updated. Verify: `git diff --stat App/tests/static_versions.json | tail -30` shows only app.js and app2.css entries changed (app.js `v` `20261104-0912d`, app2.css `v` `20261104-0912d`).

**Step 6: tests (foreground).** From `App/`:
`UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_layout_lint_browser.py tests/test_host_geometry.py tests/test_static_versions.py tests/test_stay_fee*.py -q --tb=short -rs 2>&1 | tail -30`
Expected: all pass, 0 failed, 0 skipped (215 passed before; the stricter test is among them). If it still fails, read the failing line; you may adjust only the CSS/JS values in step 2 to 4 (e.g. the measured `left`). A second identical failure: STOP (section 8).
Then from repo root: `python3 scripts/design_lint.py 2>&1 | tail -30` and `python3 scripts/context_lint.py 2>&1 | grep -v WARN | tail -30` (both OK).

**Step 7: screenshots** into `docs/tasks/screenshots-0912c/` (viewport shots, 800 px high, throwaway script, delete the script afterwards). Open each PNG with Read and describe it in the report:
- `stay-fees-help-320.png`, `stay-fees-help-390.png`, `stay-fees-help-768.png`: /stay-fees with the title-row "?" open (box fully visible, 16 px gutters, "More in the guide" visible).
- `stays-page-help-390.png`: /stays with the `details.page-help` dialog open at 390 (dialog 356 to 360 px wide, centred).
- `setup-tip-bottom-320.png`: the setup-property page at 320, scroll the last `?` tooltip trigger (trigger 9) into view near the bottom, open it: the tooltip and its last link are fully above the tab bar.

**Step 8: report.** Write `docs/tasks/0912c-report.md` (600 tokens at most, Status: review) per section 9; set this brief's Status to `review`.

## 5. Do not touch

App/tests/test_layout_lint_browser.py (no loosening), any template other than base.html's two `?v=`, host2.css, any other CSS rule, desktop (>= 1024 px) tooltip or popover behaviour, secrets, git history. AGENTS.md rules: light mode only; no new dependency; no commit or push.

## 6. Commands

As in steps 3, 5, 6. Never the full suite. End every command with `| tail -30`.

## 7. Acceptance

- [ ] `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_layout_lint_browser.py tests/test_host_geometry.py tests/test_static_versions.py tests/test_stay_fee*.py -q --tb=short -rs` passes, 0 failed, 0 skipped.
- [ ] `git diff App/tests/test_layout_lint_browser.py` shows no change since 0912b (test not relaxed).
- [ ] stays-how box at 320, 390, 768: left 16 px, right edge at most viewport - 16 px, width at most 360 px (numbers in the report).
- [ ] app2.css line 2040 dialog width is `min(360px,calc(100vw - 32px))`.
- [ ] `place()` uses a tab-bar-aware `floorY`; no page-level padding added; desktop unchanged.
- [ ] `?v=` bumped in base.html, static_versions.json regenerated, `test_static_versions.py` green.
- [ ] 5 screenshots in `docs/tasks/screenshots-0912c/`, each opened and described.
- [ ] design_lint and context_lint OK.

## 8. Stop and ask

Stop and write the report as `blocked` if: an anchor is not found; a test fails twice with the same message; you reach 25 tool calls or about 50k tokens; a file outside section 3 needs a change; the test would have to be relaxed to pass; you need push, merge, secrets or deploy.

## 9. Report

`docs/tasks/0912c-report.md`, 600 tokens at most, `Status: review`: 1. `git diff --stat`. 2. Each command with the last 5 lines. 3. Section 7 ticked. 4. Measured `L` and the three gutter pairs. 5. Screenshot descriptions. 6. Deviations and questions.

## Risk list (for the reviewer)

app.js `place()` diff (shared by every tooltip), app2.css lines 1214 to 1220 and 2040.

## Owner steps

None. The orchestrator commits and opens the PR.
