# 0184: CI fix, a test still expects the removed Property column header

Status: review
Depends on: 0183 | Branch: claude/project-thread-5hw8cf
Executor: Haiku 5.5 | Fits one session

## 1. Objective

CI job `test` on PR #405 fails in `App/tests/test_first_property_step.py` line 229: `assert re.search(r"<th\b[^>]*>\s*Property\s*</th>", page.text)`. Brief 0177 removed the Property column from the Stays list on purpose (the Stay cell shows the property). Update the test to match, and find any other test that still expects that column.

## 2. Context

`test_the_stays_list_renders_the_word_property` (line ~224) also asserts the filter label `<label for="apartment">Property</label>`, which still exists and must keep passing. Do not change app code or templates.

## 3. Files

`App/tests/test_first_property_step.py`, any other test file the search in step 2 finds, `docs/tasks/0184-*`.

## 4. Steps

1. In the test, replace the `<th>` Property assertion with `assert not re.search(r"<th\b[^>]*>\s*Property\s*</th>", page.text)` and add a one-line comment "0177: the property shows in the Stay cell".
2. From `App/`: `grep -rn "Property\\\\s\*<\|Property</th>" tests | cut -c1-160 | head` and fix any test that expects the removed header the same way.
3. From `App/`: `.venv/bin/python -m pytest tests/test_first_property_step.py tests/test_overhaul.py tests/test_host_redesign.py -q --tb=short 2>&1 | tail -15`. Expected: all pass. If other tests fail because of 0177 (Stays Property column or 15 rows per page), fix only those test expectations and list them in the report.
4. From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -3`. Expected: OK.
5. Commit "0184: stays list test no longer expects the Property column" with the trailers given by the orchestrator. Do not push.

## 5. Do not touch

App code, templates, CSS; hard rules 1, 3, 8.

## 6. Commands

As in each step.

## 7. Acceptance

- [ ] The three test files pass; lint OK.

## 8. Stop and ask

An anchor is missing, or a test fails twice for a reason outside the Stays list.

## 9. Report

`docs/tasks/0184-report.md`, short; `Status: review`.
