# 1014: Property editor spacing and typography on laptop (from 768 px)

Status: todo
Depends on: brief 1013 (PR 814) | Base: `origin/claude/wolt-desktop-only` | Branch: `claude/wolt-desktop-only` (work on it directly, no new branch) | No PR (push the branch only; the orchestrator updates PR 814)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Josef sent three laptop screenshots of the property editor (`/mnt/project-files/ux-shots/josef/*.png`; look at all three). Fix these defects at `min-width: 768px` only. Phones (below 768 px) must stay byte-identical.

1. Accordion headers (`details.prop-sec > summary`: Basic details, Foreign police, Calendars, Automatic messages, Smart lock, Stay fee) touch the card's left border with no padding; the body below is padded 16 px. Give the summary the same 16 px inline padding as the body and a 16 px title.
2. The Leon (AI) bar ("Leon (AI) answers guest questions / Off") is wider than the status cards and the form column, and its text sizes are mixed. Align it to the form column width and give it one text size.
3. Vertical spacing between fields is inconsistent and label-to-input gaps are unequal (large gap under labels inside two-column rows, `margin-bottom:12px` on labels plus on inputs from line ~1927).
4. Mixed typography: "Business & legal details" label is tiny next to larger labels; section headings differ in size.
5. The help "?" icons float at inconsistent distances from labels.
6. Grey pill buttons ("See an example police letter", "Save and test connection") look off next to the red Copy link.
7. Card widths differ between sections.

## 2. Context (approach decided by the orchestrator; do not re-audit)

CSS only. Root cause: brief 1008 (commit `7db98b8e`) removed the summary padding and summary title overrides so `test_0710_v2_mockup_match_browser.py` passed. The Wolt block in `App/app/static/app2.css` is now wrapped in `@media (min-width:768px){ ... }` (brief 1013), so desktop summary padding and typography can come back inside that wrap. The rules live near the `body.v2 .form.prop-form-single details.prop-sec` lines.

Risk: test_0710 pins box and style props against the mockup at widths `(320, 390, 768, 1024, 1280, 1440, 1920)`; box checks run at >= 1024 (`DESKTOP` in `App/tests/v2_mockup.py`), style checks also at phone widths and 768. If a restored rule breaks test_0710, do not edit the test: first try moving the inset onto the summary's children instead of the summary box (read the summary markup with `grep -n "<summary" App/app/templates/_property_editor.html | tail -30`), and if it still fails, STOP and report the failing selector and prop.

Rules: all new CSS goes inside the existing `@media (min-width:768px){` Wolt block (before its closing `}`) or in a new `@media (min-width:768px){...}` appended at the end of the file; scope every selector `body.v2 .form.prop-form-single` or `.property-detail`; no markup change unless unavoidable (then say why); reuse existing tokens (`--line`, `--ink3`, `--bg`, `--space-*`); light mode only; no new colours, no new dependency.

Target values (adjust only if the screenshot shows a better fit):
- Summary: `padding:14px 16px;gap:8px 12px;min-height:44px`; `summary b` (or `summary > div b`) `font-size:16px;font-weight:700;line-height:1.3`.
- One label style inside `details.prop-sec`: `font-size:14px;font-weight:600;line-height:1.3;margin:0 0 6px`; inputs/selects `margin:0`; `.field{margin:0 0 16px}` already exists, keep it. Row gap in two-column grids `16px`.
- Section headings (`.property-section-title`, the "Business & legal details" label, "Check-in time / Check-out time", "Door-code access times") all 16px/700.
- Help "?" icon: `margin-left:8px;vertical-align:middle` (inline next to the label, same distance everywhere).
- Leon bar: `max-width:inherit;width:100%;box-sizing:border-box;margin-inline:0`, text `font-size:14px`, same width as the form column (776 px at >= 1024; find the Leon bar selector with `grep -n "leon" App/app/templates/_property_editor.html App/app/templates/property_detail.html | tail -30`).
- Pill buttons inside `.prop-form-single`: `.ui-btn-secondary` get `background:#fff;border:1px solid var(--line);box-shadow:none;min-height:44px` (white outline like the Archive button); primary stays unchanged.
- Card width: every `details.prop-sec`, `#sec-archive`, the status cards row and the Leon bar share the form column width (`width:100%;box-sizing:border-box`).

## 3. Files

| Path | Action |
|---|---|
| App/app/static/app2.css | edit (steps 1-3) |
| App/app/templates/base.html | edit (step 4, cache key) |
| App/tests/static_versions.json | edit (step 4, via the script) |
| docs/tasks/1014-report.md | create (step 7) |
| docs/tasks/1014-ux-property-editor-spacing.md | Status line only |

## 4. Steps

Anchors: `grep -nF "<text>" <file> | tail -30`. Not found: STOP and report. Every command ends with `| tail -30`. Commit after each step with `1014 step k` (message ends with the two attribution lines from the system reminder).

0. **Branch and look.** From the repo root: `git fetch origin claude/wolt-desktop-only 2>&1 | tail -3 && git checkout claude/wolt-desktop-only 2>&1 | tail -3 && git reset --hard origin/claude/wolt-desktop-only 2>&1 | tail -3 && git log --oneline -1 | cat`. Check the wrap is there: `grep -c '^@media (min-width:768px){' App/app/static/app2.css | tail -3` (at least 1) and `grep -nF "1013: the whole Wolt-style restyle" App/app/static/app2.css | tail -3`. If missing, STOP. Open the three Josef screenshots with Read. Then: `grep -nF "details.prop-sec>summary" App/app/static/app2.css | tail -30` and `grep -n "Leon\|leon" App/app/templates/_property_editor.html | tail -30` to find selectors. Baseline the phone: `cp App/app/static/app2.css /tmp/app2.before.css`.
1. **Summary padding and title (defects 1, 4, 7).** Edit the line `body.v2 .form.prop-form-single details.prop-sec>summary{min-height:44px;box-sizing:border-box}` to the target summary values above and re-add the `summary b` rule after it. Commit `1014 step 1`. Run test_0710 right now (step 5 command 2) because it is the riskiest change; on failure apply the fallback from section 2 before going on.
2. **Field rhythm, labels, "?" icons, headings (defects 3, 4, 5).** Add the label, input margin, row gap, heading and help-icon rules from the target values, scoped `body.v2 .form.prop-form-single details.prop-sec`. They must beat the global `body.v2 .prop-sec label{margin-bottom:12px}` and the input `margin-bottom:12px` rules (specificity is higher with the extra classes; do not use `!important`). Commit `1014 step 2`.
3. **Leon bar, pill buttons, card widths (defects 2, 6, 7).** Add the Leon, `.ui-btn-secondary` and width rules from the target values. Commit `1014 step 3`.
4. **Cache key.** In `App/app/templates/base.html` replace the current `app2.css?v=...` value with `20261108-1014` (anchor `grep -nF "app2.css?v=" App/app/templates/base.html | tail -3`, one match). From `App/`: `.venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -10`. Brace balance: `python3 -c "s=open('App/app/static/app2.css').read(); print(s.count('{')-s.count('}'))" | tail -3` must print `0` (from repo root). Commit `1014 step 4`.
5. **Tests (from `App/`, one command each, 0 skipped).**
   ```
   UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots .venv/bin/python -m pytest tests/test_layout_lint_browser.py -q -x 2>&1 | tail -30
   UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py -q -x 2>&1 | tail -30
   UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_0833_property_editor_browser.py tests/test_host_property_controls_browser.py tests/test_property_navigation_browser.py -q --tb=short -x 2>&1 | tail -30
   .venv/bin/python -m pytest tests/test_static_versions.py -q --tb=short -x 2>&1 | tail -30
   ```
   Drop a file that does not exist and say so. Expected: all pass, `0 skipped`, zero layout-lint findings. Never edit a test, never silence a finding. A failure you cannot fix by CSS in scope: STOP and report test name, selector, prop.
6. **Phone unchanged check and screenshots (UX gate, rule 10).**
   a. Phone: `git diff origin/claude/wolt-desktop-only -- App/app/static/app2.css | grep '^[+-]' | grep -v '^+++\|^---' | tail -60`. Every added line must sit inside an `@media (min-width:768px)` block and every removed line must be one you meant to replace (the summary line). Say so in the report. Then compare a 390 screenshot of the property editor before and after: the before is `/mnt/project-files/ux-shots/revert/property-editor-390.png` (from 1013); open the new `-configured+open` 390 PNG from `/tmp/shots/layout-lint` (`ls /tmp/shots/layout-lint | grep -i property-detail | tail -30`) and confirm no visible difference at the summary, labels, Leon bar and buttons.
   b. Open the 390, 768 and 1280 PNGs of `property-detail` (configured account, sections open) with Read (tall images: crop the top 1600 px with PIL into `/tmp/crop_<name>.png`, and a second crop of the Foreign police section). Check per defect: summary text has 16 px inset from the border; Leon bar same width as cards and form; equal label-to-input gap; "Business & legal details" same size as other labels' headings; "?" icons a constant 8 px from the label; pill buttons white outline; all cards same width.
   c. Save: `mkdir -p /mnt/project-files/ux-shots/spacing && cp <each> /mnt/project-files/ux-shots/spacing/property-editor-<size>.png && ls -l /mnt/project-files/ux-shots/spacing | tail -30` (sizes 390, 768, 1280).
   d. Tests may rewrite tracked PNGs. Restore with path-limited checkout, never commit PNGs and never run `git checkout -- docs/tasks`: `git status --short | grep -i '\.png' | tail -30`, then `git checkout -- <each png path>`. Final `git status --short | tail -30` shows no PNG.
7. **Report.** Write `docs/tasks/1014-report.md` (500 tokens at most): `git diff --stat origin/claude/wolt-desktop-only | tail -10`, last line of each step 5 command, the phone-unchanged result, per page "390: ...; 768: ...; 1280: ..." (what you saw for property editor, naming each of the 7 defects fixed or not), the three screenshot paths, deviations. Set this brief `Status: review`. Commit: `git add docs/tasks/1014-report.md docs/tasks/1014-ux-property-editor-spacing.md && git commit -m "1014 report"`.
8. **Push, no PR.** `git push origin claude/wolt-desktop-only 2>&1 | tail -5`. Never push to `main`. If refused, put the exact command in the report. Do not open a PR.

## 5. Do not touch

`App/` templates, routes, i18n, any test, the phone (below 768 px) rules, any file outside section 3.

## 6. Commands

See steps 0-8 (test-map rows: layout lint browser, `test_0710_v2_mockup_match_browser.py`, property editor browser tests, `test_static_versions.py`).

## 7. Acceptance

- [ ] Every added CSS line is inside `@media (min-width:768px)`; CSS brace balance is 0; phone 390 screenshot unchanged.
- [ ] Layout lint and `test_0710_v2_mockup_match_browser.py`: green, 0 skipped. The three property editor browser tests and `test_static_versions.py` green.
- [ ] Cache key is `20261108-1014` and `static_versions.json` matches.
- [ ] Three screenshots exist in `/mnt/project-files/ux-shots/spacing/`; no PNG in `git status`.
- [ ] Branch `claude/wolt-desktop-only` pushed; nothing on `main`; no PR opened.

## 8. Stop and ask

An anchor is missing; test_0710 still fails after the child-inset fallback; a layout-lint finding that only a phone change would clear; a markup change looks unavoidable; more than 30 tool calls. Stop, write what you found in the report, hand over.

## 9. Report

Step 7 writes `docs/tasks/1014-report.md`; reply with its path and one line per defect (fixed or not).
