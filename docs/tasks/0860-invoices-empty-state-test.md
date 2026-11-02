# 0860: Invoices v2 empty state: test follows the single-line look

Status: todo
Depends on: 0854 | Branch: claude/project-thread-v4nqi5 (main checkout, do NOT commit; the orchestrator commits)
Executor: Haiku 5.5 | Fits one session: 15 tool calls, 30k tokens

## 1. Objective

CI (PR #707, shard 1) fails `tests/test_host_list_page_layout_browser.py:197` `test_empty_states_use_the_shared_component`: for `/invoices` the empty block (`data-empty-state`, "No invoices yet") has no action link. 0854 made it one line on purpose, because the page head already has the action (Josef: no sentence or button the head already says). Update the test for `/invoices` only: the empty block has 0 action links, and the page head (`.stays-head-actions` or the head the v2 invoices template renders) has exactly one primary action for the `none` user. Comment "v2, 0854: the head carries the action". Keep the other three paths unchanged.

First check what `/invoices` renders in the head for the `none` user (no businesses). If the head has no action for that user, stop and report instead of changing the test.

## 2. Context

`App/app/templates/invoices.html` (head and empty state), test lines ~189-199.

## 3. Files

`App/tests/test_host_list_page_layout_browser.py` only.

## 4. Steps

Check the head, update the test, rerun.

## 5. Do not touch

Anything outside §3.

## 6. Commands (from `App/`, `2>&1 | tail -30`)

`UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_host_list_page_layout_browser.py -q -rs --tb=short`

## 7. Acceptance

- [ ] The command: 0 failed, 0 skipped.

## 8. Stop and ask

Per §1, or if a fix fails twice.

## 9. Report

`docs/tasks/0860-report.md`, 100 tokens at most. Do not commit or push.
