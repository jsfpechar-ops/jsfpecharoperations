# 0341 report: guest guide data layer

Status: review

## 1. Files changed

- `App/app/migrations/0013_guest_guide.sql` (new): `guide_item`, `guide_photo`, indexes.
- `App/app/guest_guide.py` (new): topics, kinds, defaults, save/skip/custom, progress, `for_guest`.
- `App/tests/test_guest_guide.py` (new): 9 tests.
- `docs/tasks/0291-report.md` (new) and `docs/tasks/0291-guest-guide-data.md` (Status line only).

No other file changed. `db.py`, existing migrations, templates, routes and i18n are untouched.

## 2. Commands (last 5 lines of output)

Step 1, migration number check: `ls App/app/migrations/ | tail -3`. Last file is `0012_web_push.sql`, so `0013` is free. No `guest_guide.py` or test file existed beforehand.

Step 3, import: `cd App && .venv/bin/python -c "import app.guest_guide"`. No output, so the import is clean.

Step 4 and section 6, tests: `cd App && .venv/bin/python -m pytest tests/test_guest_guide.py tests/test_migrations.py tests/test_db_*.py -q --tb=short -x -rs`

```
...........................                                              [100%]
=============================== warnings summary ===============================
.venv/lib/python3.13/site-packages/fastapi/testclient.py:1
  /home/claude/jsfpecharoperations/App/.venv/lib/python3.13/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
27 passed, 1 warning in 5.02s
```

`tests/test_guest_guide.py` alone: `9 passed, 1 warning in 0.86s`. No skips.

Lint: `python3 scripts/context_lint.py 2>&1 | tail -30`. Last lines: `next free: task 0350 | migration 0014` then `context lint: OK`. The WARN lines name existing open briefs (for example `App/app/routes/guest_guide.py`, shared with 0342 to 0349). These are warnings, not failures.

## 3. Section 7

- [x] The three files exist as briefed. The diff touches only them plus the report.
- [x] `tests/test_guest_guide.py`: 9 passed.
- [x] `tests/test_migrations.py` and `tests/test_db_*.py` pass.
- [x] Context lint OK.

## 4. Deviations

None. The file contents are the brief's text as given. No UI changed, so no screenshot is needed.

## 5. Questions

None.

## 6. Owner steps left

1. Review and merge the PR once CI is green. The tables are created on the next normal deploy. Nothing uses them until 0342.
