# 0931: layout lint checks for the design system (rules 4, 5, 6)

Status: todo

Executor: Haiku 5.5. Read AGENTS.md, docs/context/executor.md, this brief, and only `docs/design/design-system.md` section 1 (rules 4, 5, 6) plus the files named below.

## 1. Objective

Add three checks to `App/tests/layout_lint.js` so the build fails on the owner's recurring complaints. Do not touch templates or CSS. If a real host page fails a new check, do not fix the page: list the findings in the report (the lint must stay green on main, so see step 4).

## 2. Context
Read only `docs/design/design-system.md` section 1 (rules 4, 5, 6). Lint file: `App/tests/layout_lint.js`; test: `App/tests/test_layout_lint_browser.py`.

## 3. Files
`App/tests/layout_lint.js`, `App/tests/test_layout_lint_browser.py`, `docs/context/decisions.md`.

## 4. Steps

1. In `App/tests/layout_lint.js`, before the final `return out;`, add rule `header-actions-misaligned`. For each visible `h1` inside `main` (or `.page-head`/`header` that contains it), find the nearest ancestor that also contains visible `button, a.ui-btn, .btn, .ui-btn` elements (not inside `[role=menu]`, not `position:fixed`). At widths 768 and up, flag when those buttons sit beside the h1 but differ in height by more than 2 px, or their vertical centres differ by more than 4 px, or any button label wraps to two lines (`textLines` > 1). Also flag one lone button that sits beside the h1 with no sibling button and is not the only action in a `.page-head`. Keep it conservative: when unsure, do not flag.
2. Add rule `multiple-save-in-form`: in one `form`, more than one visible `button[type=submit], input[type=submit]` whose text matches /save|uložit|ulozit/i (Czech and English). Also flag a visible `position:fixed` bar that contains a submit button while the same page has another visible save submit outside it.
3. Add rule `duplicate-heading`: two visible `h1, h2, h3` on one page with the same normalised text (lower case, trimmed, whitespace collapsed), ignoring headings inside `[role=dialog]`, `dialog`, `nav`, and ignoring text shorter than 3 characters.
4. In `App/tests/test_layout_lint_browser.py`: add a bad-markup sample for each new rule to `BAD_PAGE` and add the three rule names to the `expected` set in `test_the_lint_catches_the_known_regressions`. Run `test_layout_lint_browser.py` once. If real host pages fail a new rule, add that rule name to a `KNOWN_FINDINGS` allow-list dict in the test file with the page and element names, each with a comment `# owner debt, fix in UX threads`, so CI stays green and the debt is listed. Do not silence a rule globally.
5. Append a `[workflow]` line to `docs/context/decisions.md`: `2026-11-04 [workflow] design-system.md is the front door for host UX rules; layout lint gained header-actions-misaligned, multiple-save-in-form, duplicate-heading (brief 0931).`

## 5. Do not touch
Templates, CSS, anything under `App/app/`, guest and public pages.

## 6. Commands

From `App/`: `UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_layout_lint_browser.py -q --tb=short -rs -x 2>&1 | tail -30`. 0 skipped. From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`.

## 7. Acceptance
Three new rules fire on the bad sample, `test_layout_lint_browser.py` passes with 0 skipped, context lint is green.

## 8. Stop and ask
A real host page fails a new rule in a way the allow-list cannot express: stop and report.

## 9. Report

`docs/tasks/0931-report.md` as in executor.md, including the list of real findings per rule. Commit each step as `0931 step k`. No push.
