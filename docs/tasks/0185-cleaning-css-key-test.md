# 0185: CI fix, a test hard-codes the cleaning.css key

Status: todo
Depends on: 0184 | Branch: claude/project-thread-5hw8cf
Executor: Haiku 5.5 | Fits one session

## 1. Objective

CI fails: `App/tests/test_design_cleaning.py::test_shared_cleaner_page_template_keeps_its_own_stylesheet` (line 42) asserts the exact old key `cleaning.css?v=20261016-0123b-0106b`; 0182 correctly bumped it to `20261020-0182a-0182` in `cleaning_shared.html`. Make the test key-agnostic so the next bump does not break it. Look for the same hard-coded-key pattern in other tests: `grep -rn "static/[a-z0-9_-]*\.\(css\|js\)?v=" App/tests/*.py | cut -c1-170`.

## 2. Context

The static-versions test already guards keys; this test only needs to prove the shared cleaner page links `cleaning.css` with some `?v=`.

## 3. Files

`App/tests/test_design_cleaning.py`, any other test the grep in section 1 shows with a literal key, `docs/tasks/0185-*`.

## 4. Steps

1. Replace the literal assertion with `assert re.search(r'href="/static/cleaning\.css\?v=[^"]+"', text)` (add `import re` if missing). Fix other literal-key tests the same way, only if they would break on the next bump.
2. From `App/`: `.venv/bin/python -m pytest tests/test_design_cleaning.py tests/test_static_versions.py -q --tb=short 2>&1 | tail -8`. Expected: all pass.
3. From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -3`. Expected: OK.
4. Commit "0185: cleaning stylesheet test no longer hard-codes the key" with the trailers given by the orchestrator. Do not push.

## 5. Do not touch

App code, templates, CSS; hard rules 1, 3, 8.

## 6. Commands

As in each step.

## 7. Acceptance

- [ ] Both test files pass; lint OK.

## 8. Stop and ask

An anchor is missing, or a test fails twice.

## 9. Report

`docs/tasks/0185-report.md`, short; `Status: review`.
