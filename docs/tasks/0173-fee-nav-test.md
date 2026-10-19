# 0173: stale rail assertion after the six-item sidebar

Status: todo
Depends on: 0165 | Branch: claude/project-thread-5hw8cf
Executor: Haiku 5.5 | Fits one session

## 1. Objective

CI on PR #404 fails `tests/test_host_redesign.py::test_fee_navigation_uses_active_owned_properties`: it asserts `href="/stay-fees"` inside the sidebar (`rail(...)`), but since 0165 Stay fees is a tab on the Invoices page, not a sidebar link. The behaviour it protects (the fee page link appears once the host owns an active property) must stay covered.

## 2. Context

`App/app/templates/_shell_sidebar.html` has six links and no `/stay-fees`. The Invoices page (`/invoices`) shows the section tabs from `_template_page_tabs` in `App/app/templating.py`, which include `("stay_fees", "/stay-fees", "nav.stay_fees")`. Do not touch app code.

## 3. Files

`App/tests/test_host_redesign.py`, `docs/tasks/0173-*`.

## 4. Steps

1. In `test_fee_navigation_uses_active_owned_properties` (about line 68) replace the two `rail(...)` assertions with: `assert 'href="/stay-fees"' in client.get('/invoices').text` and `assert 'href="/stay-fees"' not in rail(client.get('/').text)` (the sidebar no longer lists it). If `rail` becomes unused elsewhere in the file keep the import.
2. From `App/`: `.venv/bin/python -m pytest tests/test_host_redesign.py -q --tb=short 2>&1 | tail -5`. Expected: all passed.
3. Look for other stale sidebar assertions of the same kind: `grep -rn "stay-fees\|smart-locks" tests/*.py | grep -i "rail\|sidebar\|nav" | cut -c1-170 | head -20`. For each hit run its file: `.venv/bin/python -m pytest <file> -q --tb=short -x 2>&1 | tail -4`. Fix only assertions that expect these two links in the sidebar (same pattern as step 1). Report any other failure verbatim; do not fix unrelated ones.
4. Commit: `git add App/tests docs/tasks/0173-* && git commit` with message "0173: fee link is an Invoices tab, not a sidebar link" and the two trailers given by the orchestrator.

## 5. Do not touch

App code, any other assertion; hard rules 1, 3, 8.

## 6. Commands

As in each step.

## 7. Acceptance

- [ ] test_host_redesign passes; no other test expects those links in the sidebar.

## 8. Stop and ask

An anchor is missing, or a test fails twice.

## 9. Report

`docs/tasks/0173-report.md`, short; `Status: review`.
