# 0809 brief: no descriptions or fine print on the 0800-0804 pages

Status: todo
Executor: Haiku 5.5, alone, in /home/claude/jsfpecharoperations on branch claude/project-thread-a41o7b (checked out; App/.venv exists). Do not commit, push, checkout, reset, stash or restore: the orchestrator commits.

## 1. Objective
Owner rule (Josef, 2026-11-02): like Wolt, pages show no descriptions or fine print. Each page keeps its title, the data, the controls and their labels. Explanatory text moves under the existing help "?" (`.help-tip`) of the nearest label or heading, or is dropped when the control already says it. Pages: new property (/apartments/new), onboarding (/onboarding), setup wizard (all steps), host guest guide, Havel (/havel), cleaning new/shares/properties. Not Průvodce (/guide): it is the help itself.

## 2. Context
"Fine print" here means: page subtitles under the h1 (e.g. "Support assistant"), `.muted`/`.small`/`.hint`/`.lede`/`.setup-wizard-instruction`/"Have ready: …" paragraphs, card descriptions under a card title (onboarding step cards), and footnotes ("Available only in mock/demo environments…"). Wizard legal content (police reporting, GDPR, controller wording) must stay reachable: fold it into a help "?" next to the step question, never delete it. Help-tip markup: copy an existing `.help-tip` from `App/app/templates/setup_wizard/` (button with `aria-controls`, hidden panel).

## 3. Files
Templates of the pages above, `App/app/static/app2.css` (only blocks 0800-0804 and 0808, for help-tip placement), tests that assert the moved text is visible (change them to assert it is inside the help panel; never delete a legal-text assertion).

## 4. Steps
Env for test runs (from App/): `export PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_REQUIRE_BROWSER=1`.
a. Per page, list every descriptive paragraph (grep the template for `muted`, `small`, `hint`, `lede`, `instruction`, `<p`). Decide: help "?" (keeps meaning, e.g. "Copy each listing's private iCal export URL") or drop (repeats the label or button).
b. Move or drop. Keep the translation keys and texts unchanged (no new copy); a moved text uses the same `t('…')` call inside the help panel.
c. Run the test files below; where a test asserts a moved text is visible, assert it inside the help panel instead (open the "?" first if the test uses JS).
d. Regenerate screenshots: `UBYHOST_SHOTS_0800=1 .venv/bin/python -m pytest tests/test_0800_v2_remaining_pages_browser.py -q 2>&1 | tail -5`.

## 5. Do not touch
Copy text and translation files, behaviour, Průvodce, other pages, cache key, other app2.css blocks.

## 6. Commands
From App/, env above:
- `.venv/bin/python -m pytest tests/test_0800_v2_remaining_pages_browser.py tests/test_onboarding_wizard_browser.py tests/test_onboarding.py tests/test_design_setup_wizard_browser.py -q --tb=line -p no:cacheprovider 2>&1 | tail -8` → 0 failed
- `.venv/bin/python -m pytest tests -q -k "wizard or onboarding or havel or guest_guide or cleaning or apartment_form" --tb=line -p no:cacheprovider 2>&1 | tail -8` → 0 failed
- repo root: `python3 scripts/design_lint.py 2>&1 | tail -3`, `python3 scripts/context_lint.py 2>&1 | tail -3`

## 7. Acceptance
Section 6 green; screenshots show no paragraph text outside titles, labels, data and help panels.

## 8. Stop and ask
Stop at 30 tool calls, or if a legal text would have to go.

## 9. Report
`docs/tasks/0809-report.md`: per page what moved to help and what was dropped, changed assertions, final tails.
