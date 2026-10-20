# 0182: Cleaning drops the From / Until filter form

Status: todo
Depends on: 0181 (run after it) | Branch: claude/project-thread-5hw8cf
Executor: Haiku 5.5 | Fits one session

## 1. Objective

Owner: Cleaning shows a From / Until (exclusive) date form with "Show dates" and "Next 30 days", unlike other pages, and the calendar already has month, week and year controls. Remove the form from the host Cleaning page. The `from` and `to` query parameters keep working (links, calendar navigation, shared schedule); only the visible form goes.

## 2. Context

`App/app/templates/_cleaning_screen.html` lines 4-9: `<form class="cleaning-period" ...>` inside `{% if not read_only %}`. Routes in `App/app/routes/cleaning.py` (lines 60, 115, 334-354) read the params; do not change them. Check where else `cleaning-period` is used: `grep -rn "cleaning-period\|cleaning-from\|cleaning-to" App/app App/tests | cut -c1-160`.

## 3. Files

`_cleaning_screen.html`, CSS that styles `.cleaning-period` only if it becomes dead (host2.css gets a new key ending `-0182` only if you touch it; same rule for `app.css`, with the `-0182` key bumped in every template that references it), tests that assert the form (update them to assert it is absent), `docs/tasks/0182-*`.

## 4. Steps

1. Delete the `<form class="cleaning-period">` block (and its `{% if not read_only %}` wrapper if it becomes empty). Remove dead `.cleaning-period` CSS only if nothing else uses the class, then bump keys and run `.venv/bin/python tests/test_static_versions.py --write` from `App/`.
2. `python3 scripts/design_lint.py 2>&1 | tail -2` from the repo root. Expected: OK.
3. Update or add a test in `App/tests/test_cleaning*.py`: `/cleaning` no longer contains `id="cleaning-from"`, but `/cleaning?from=2026-10-17&to=2026-10-20` still returns 200 and its list covers that range.
4. Screenshots: `/mnt/project-files/design-reset/tools/shots.py --new-app $PWD --out docs/tasks/0182-screenshots --pages "/cleaning" --widths 390,1280`. Look: the legend and calendar sit directly under the page header, no gap.
5. From `App/`: `.venv/bin/python -m pytest tests/test_cleaning*.py -q 2>&1 | tail -5`; then foreground, timeout 600000, `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium`: `.venv/bin/python -m pytest tests/test_design_guardrails_browser.py tests/test_a11y_guard_browser.py -q -rs 2>&1 | tail -6`. Then `git checkout -- docs/tasks/0102-evidence && git clean -fdq docs/tasks/0102-evidence` (skip if refused). Expected: 0 skipped; known failure `test_list_pages_share_order_edges_and_rhythm` may appear, name it.
6. Commit "0182: Cleaning drops the From / Until form" with the trailers given by the orchestrator. Do not push.

## 5. Do not touch

Routes, the shared (read-only) schedule page behaviour, copy outside the removed form; hard rules 1, 3, 8.
