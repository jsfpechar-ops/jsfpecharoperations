# 0137 report

Status: review

## Commits (branch claude/project-thread-td6fpc, not pushed)

- 3e6dbcb 0137 step 1 (templates: dashboard, apartments, reservations, reservation_detail, _property_editor)
- 0e208e6 0137 step 2 (admin.py: manual_send flag, one query)
- a72fef6 0137 step 3 (host_i18n.py, host_design_i18n.py: unused keys removed)
- 0cabe48 0137 step 4 (tests updated; new App/tests/test_remove_legacy_actions.py)

## Commands and last lines

- Step 1 script: `ok`; template compile: `compiled`.
- Step 2 script: `ok`. `test_send_controls.py` + `test_stays_empty_workspace.py`: one expected failure at test_send_controls.py:741 (fixed in step 4).
- Step 3 script: `ok`; grep of removed keys outside admin.py: `0`; `imports`.
- Step 4 main list (14 files incl. new test): `139 passed, 1 warning`.
- Step 4 test_endtoend.py alone: `28 passed, 1 warning`. In the combined run it failed once (test_04_connection_test_reaches_the_service, order-dependent, known K-T01); not a new failure.
- Filing row: `214 passed, 4 warnings`.
- Browser (quiet dashboard, stay actions, stay detail layout, list layouts): `6 passed, 1 warning in 95.18s`, 0 skipped.
- Screenshot helper: the brief's single run with SHOT_OPEN_MENU=1 fails on `stays` because the helper opens `#now .row-menu-trigger` on every page whose name starts with "stay" (no such element on the list). Split into two runs instead: stays/properties/property-reporting without menu (6 SHOT lines, 1 passed), stay-failed with menu flag (2 SHOT lines, 1 passed). Scroll width matched viewport in all eight.
- Lint: `design lint: OK`; ruff: `All checks passed!`.

## Screenshots (390 px, /tmp/claude-0/-home-user-jsfpecharoperations/3c6f1ec6-a025-553c-863a-9c0748d5832e/scratchpad/shots/0137/)

- stays-390.png: no per-row Send button; rows show only the menu. Viewed.
- properties-390.png: Properties header shows only "Add a property"; no code-list refresh text in the reporting area. Viewed.
- property-reporting-390.png: "Save and test connection" kept; no "Refresh code lists". Viewed.
- stay-failed-390.png: one coral "Fix rejection" button plus secondary "Generate invoice"; no separate Send button. The More menu was NOT visibly open in this capture, so "Send again" in the menu is not confirmed by screenshot (covered by the test_send_controls assertion).
- Dashboard: the brief's `dashboard-en-390.png` was not produced; the shots folder holds `dashboard-single-en-390.png` from an earlier test. Not viewed in this session.
- 360 and 1280 not reviewed.

## Acceptance (section 7)

- [x] Dashboard/Properties sync copies removed (tests); property calendar section keeps one Update calendars.
- [x] Stays list: menu only; Send all ready gated on manual_send.
- [x] Stay detail: Send again moved into More menu; claim actions moved; slot button removed; demo buttons kept.
- [x] Filing tests pass.
- [~] Screenshots: taken; stay-failed menu-open state not visible in the image.

No route or filing logic changed; only the stays route gained the manual_send flag.

## Deviations

- Screenshot helper split into two runs (see above).
- Step 6 commit skipped: all changes were already committed in steps 1 to 4, so there was nothing new to add.

## Questions

- Should the screenshot helper skip the menu click on non-stay pages? It currently fails the "stays" page when SHOT_OPEN_MENU=1.

## Owner steps left

- Review and merge the PR via scripts/merge-pr-on-green.sh. Push not done by executor.
