# 0859: Domovní kniha v2 renders no alert stack

Status: todo
Depends on: 0793 | Branch: claude/project-thread-v4nqi5 (main checkout, do NOT commit; the orchestrator commits)
Executor: Haiku 5.5 | Fits one session: 15 tool calls, 30k tokens

## 1. Objective

CI (PR #707, shard 3) fails `tests/test_host_wide_geometry_browser.py:523`: `('housebook', 'en', 1024, {...})` has a `.notification-stack`, but v2 pages render no alert stack (0538 rule; submissions and invoices already follow it). `App/app/templates/housebook.html` line ~17 still has `{% include "_host_alerts.html" %}`. Remove that include so housebook matches submissions and invoices. Red alerts stay reachable from the dashboard's "What needs you" card.

## 2. Context

Compare `submissions.html` and `invoices.html` (no include). Check no housebook test asserts the alert stack (grep `notification-stack` and `housebook` in `App/tests`); if one does for the old shell, update it with the comment "v2, 0793".

## 3. Files

`App/app/templates/housebook.html`; a test only per §2.

## 4. Steps

Reproduce, remove the include, rerun.

## 5. Do not touch

Anything outside §3.

## 6. Commands (from `App/`, `2>&1 | tail -30`)

`UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_host_wide_geometry_browser.py tests/test_0710_v2_mockup_match_browser.py -k "wide_lanes or housebook" -q -rs --tb=short`

## 7. Acceptance

- [ ] The command: 0 failed, 0 skipped.

## 8. Stop and ask

Blocked if a fix fails twice or a file outside §3 needs a change.

## 9. Report

`docs/tasks/0859-report.md`, 100 tokens at most. Do not commit or push.
