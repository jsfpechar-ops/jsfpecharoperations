# 0167: buttons and fields in one row line up; the guard compares them

Status: todo
Depends on: 0166 | Branch: claude/project-thread-5hw8cf
Executor: Haiku 5.5 | Fits one session

## 1. Objective

On `/cleaning` the "Show dates" button sits about 16 to 26 px lower than the two date fields next to it, and the "Next 30 days" link floats on its own line. The owner's screenshot shows it. The layout guard missed it because it only compares buttons with buttons. Fix the cleaning row, then make the guard compare buttons with fields (input, select, textarea) that share a row.

## 2. Context

`App/app/templates/_cleaning_screen.html` line 4 to 8: a `form.cleaning-period` holds two `<div class="ui-field">`, a submit button and a link. `App/app/static/cleaning.css` lines 17 and 18 style `.cleaning-period .field`, but the markup uses `.ui-field`, so the margin and flex rules never apply and the fields' bottom margin lifts them above the button (the form uses `align-items: flex-end`). `host2.css` loads after `cleaning.css` and wins at equal specificity. S2 lint: no bare px in margin, padding, gap or font-size.

## 3. Files

`App/app/static/host2.css` (append), `App/app/templates/base.html` (host2.css key), `App/tests/static_versions.json`, `App/tests/design_guard.js`, `docs/design/MASTER.md` (one bullet), `docs/tasks/0167-*`.

## 4. Steps

1. Append to `App/app/static/host2.css`:

```
/* 0167: the cleaning period row aligns fields and button on one bottom line */
.host-workspace .cleaning-period { align-items: flex-end; gap: var(--space-3); }
.host-workspace .cleaning-period .ui-field { margin: 0; flex: 0 1 12rem; min-width: 0; }
.host-workspace .cleaning-period > .ui-btn { align-self: flex-end; }
.host-workspace .cleaning-period > a { align-self: flex-end; display: inline-flex; align-items: center; min-height: var(--control-h); }
```

   Lint from the repo root: `python3 scripts/design_lint.py 2>&1 | tail -2` (OK). Change the host2.css key in `App/app/templates/base.html` (grep `host2.css?v=`) to `20261019-0167`, then from `App/`: `.venv/bin/python tests/test_static_versions.py --write && .venv/bin/python -m pytest tests/test_static_versions.py -q 2>&1 | tail -3` (passed).
2. In `App/tests/design_guard.js`, directly after the closing `}` of the loop that reports `button-heights-differ` and `buttons-misaligned` (find it with `grep -n "buttons-misaligned" App/tests/design_guard.js`; the block ends with `  }` just before `  // 5. phone tap targets`), insert:

```
  // 4b. a button and a field that share a row sit on one bottom line (a label above the field must not push it up)
  const fieldSel = 'input:not([type=hidden]):not([type=checkbox]):not([type=radio]):not(.sr-only),select,textarea';
  const rowCtl = [...ws.querySelectorAll(btnSel + ',' + fieldSel)].filter((e) => vis(e) && !e.closest('[role=menu],dialog:not([open])') && !inScroller(e));
  for (let i = 0; i < rowCtl.length; i++) for (let j = i + 1; j < rowCtl.length; j++) {
    const a = rowCtl[i], b = rowCtl[j];
    if (a.matches(fieldSel) === b.matches(fieldSel)) continue;
    if (a.tagName === 'TEXTAREA' || b.tagName === 'TEXTAREA') continue;
    const ra = a.getBoundingClientRect(), rb = b.getBoundingClientRect();
    const overlap = Math.min(ra.bottom, rb.bottom) - Math.max(ra.top, rb.top);
    if (overlap < Math.min(ra.height, rb.height) / 2) continue;
    if (ra.right > rb.left && rb.right > ra.left) continue;
    if (Math.abs(ra.bottom - rb.bottom) > 2 && Math.abs((ra.top + ra.bottom) / 2 - (rb.top + rb.bottom) / 2) > 2) out.push(['field-button-misaligned', name(a), name(b), Math.round(ra.bottom - rb.bottom)]);
  }
```

3. In `docs/design/MASTER.md` section 11.0, add to the item-1 list: `- a button and a field in one row that do not share a bottom or centre line (field-button-misaligned);`.
4. From `App/`: `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium .venv/bin/python -m pytest tests/test_design_guardrails_browser.py tests/test_cleaning_browser.py tests/test_dashboard_calendar_browser.py -q -rs -p no:cacheprovider 2>&1 | tail -25` (foreground, timeout 900000). Expected: passed, 0 skipped. If the guard reports `field-button-misaligned` on the cleaning page, the CSS in step 1 is not enough: stop and report the lines. If it reports the same finding on OTHER pages, do not fix them and do not loosen the check: copy `/tmp/ubyhost-layout-guard.json` to `/mnt/project-files/design-reset/a11y/layout-0167-findings.json`, list every distinct page, width and pair in `docs/tasks/0167-report.md`, still commit, and say the guard test fails because of them.
5. From the repo root: `git checkout -- docs/tasks/0102-evidence; git clean -fdq docs/tasks/0102-evidence`. Commit: `git add App/app/static/host2.css App/app/templates/base.html App/tests/static_versions.json App/tests/design_guard.js docs/design/MASTER.md docs/tasks/0167-* && git commit` with message `0167: cleaning period row aligned, guard compares buttons with fields` and the two trailers from your prompt.

## 5. Do not touch

Any template other than none; any other CSS; hard rules 1, 3, 8. Never add an allowlist or skip to the guard.

## 6. Commands

As in each step.

## 7. Acceptance

- [ ] Cleaning row aligned, guard extended, cleaning pages pass, other pages' findings listed if any.

## 8. Stop and ask

An anchor is missing, or the cleaning page still fails after step 1.

## 9. Report

`docs/tasks/0167-report.md`; `Status: review`.
