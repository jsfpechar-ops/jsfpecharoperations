# 0544: property pages on v2: rewrite the flow tests that used the removed tabs
Status: todo
Depends on: 0542 (this branch) | Branch: claude/project-thread-819gyo
Executor: Haiku 5.5, in its own worktree | Fits one session: 30 tool calls, 60k tokens

## 1. Objective
Several browser tests walk through the old property page: tabs (`.property-tabs a[data-property-tab]`), views (`[data-property-view]`), the old save bar (`.host-property-save`), and overview cards (`a.host-property-card`, `.host-property-grid`). The page is now one scroll page of `details.prop-sec#sec-<key>`, an `aside.preview` with `.pv .r` rows, and a `.savebar` (`button[type=submit]` Save, `a.btn.ghost` Cancel, `[data-unsaved-reset]` reset). Rewrite those flows so each one checks the same behaviour on the new page.

## 2. Context
- Open a section by clicking its summary (`#sec-<key> > summary`), or load `?view=settings&section=<group>`. The server then opens: property→basics, reporting→police and fee, guests→messages, lock→lock, automation→police. `?view=bookings` opens calendars.
- Below 1024 px, basics is closed on load when the URL has no section, view or hash (0541). The save bar shows only while a section is open.
- Files, worst first:
  - `tests/test_host_unsaved_changes_browser.py` (11): save, discard and stay flows, the rail and back links, the reset button, the keyboard-only flow, and without JS. In-page `#sec-*` links must not ask. The unsaved dialog must still appear for links that leave the page.
  - `tests/test_property_navigation_browser.py` (10).
  - `tests/test_onboarding_wizard_browser.py`: the `test_wizard_polish_and_overview_cards` overview part only (14). The overview cards became aside rows. The "Connected calendars" text is now the aside Kalendáře row.
  - `tests/test_onboarding_followup_browser.py` (16): triage with `-x` first. Property name is `main h1`, overview links are aside `.pv .r`.
  - `tests/test_0252_touch_sweep_browser.py`, `tests/test_a11y_guard_browser.py` (2), `tests/test_host_property_controls_browser.py` (2).
- For each failure: if it is about the property list or page markup, rewrite the selector or the flow step. If it is a real bug on the new page (a control unreachable, a dialog missing, a save not saving), stop and report the numbers. If it is about another page, list it as not ours.

## 3. Files
The seven test files only. Report: section "0544" at the end of `docs/tasks/0536-report.md`.

## 4. Steps
1. test_host_unsaved_changes_browser.py. Commit.
2. test_property_navigation_browser.py. Commit.
3. Onboarding wizard and follow-up. Commit.
4. The three small files. Commit.
5. Re-run all seven and ruff on tests. Commit the report.

## 5. Do not touch
App code, templates, CSS, JS. Do not touch the test files of brief 0543 (0284, wp28, 0282, host_controls, 0251, host_help). No new dependency.

## 6. Commands (from `App/` in your worktree)
`export UBYHOST_REQUIRE_BROWSER=1 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers`, then `.venv/bin/python -m pytest <file> -q --tb=line -rfs -p no:cacheprovider -k "not webkit" 2>&1 | tail -10`. Webkit is not installed here; say so. `.venv/bin/ruff check tests --select E9,F63,F7,F82,F401,F841 | tail -3`.

## 7. Acceptance
The seven files pass on chromium with 0 skipped, apart from not-ours failures listed with their failure line.

## 8. Stop and ask
Tests may get new selectors and flow steps that check the same behaviour (list each). A test may be deleted only if it checks nothing but removed markup (list it). Stop if a save/POST does not save, or the unsaved dialog no longer guards a link that leaves the page.

## 9. Report
Section "0544" in `docs/tasks/0536-report.md`. Stage by name, never `git add -A`; never commit `App/.venv`. Do not push. Hand back with SubagentHandback; never post to the user.
