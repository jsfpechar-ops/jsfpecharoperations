# 0008 report: Door codes schema and settings

Status: review

## 1. Files changed

```
 App/app/config.py                      |  10 ++
 App/app/migrations/0007_door_codes.sql |  65 ++++++++++++
 App/app/retention.py                   |  22 ++++
 App/tests/test_door_codes_schema.py    | 184 +++++++++++++++++++++++++++++++++
 docs/ENVIRONMENT.md                    |  10 ++
 docs/privacy/RETENTION.md              |   2 +
 6 files changed, 293 insertions(+)
```

(Plus this report file.)

## 2. Commands

`cd App && .venv/bin/python -m pytest tests/test_door_codes_schema.py tests/test_migrations.py -q`

```
.venv/lib/python3.12/site-packages/fastapi/testclient.py:1
  /workspace/App/.venv/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
17 passed, 1 warning in 3.63s
```

`cd App && .venv/bin/python -m pytest tests -q`

```
    grey_pixels = sum(1 for px in crop.getdata() if px < 235)

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
2826 passed, 2 skipped, 7 warnings in 317.43s (0:05:17)
```

`python3 scripts/context_lint.py`

```
next free: task 0017 | migration 0008
context lint: OK
```

`grep -rn "TTLOCK_CLIENT_SECRET" App/app --include='*.py'`

```
App/app/config.py:169:TTLOCK_CLIENT_SECRET = os.environ.get("UBYHOST_TTLOCK_CLIENT_SECRET", "").strip()
```

## 3. Acceptance (§7)

- [x] The 4 tests in step 4 pass. The full suite passes.
- [x] `tests/test_migrations.py` passes unchanged.
- [x] `git diff --stat` shows only the files in §3 (implementation commit).
- [x] `grep -rn "TTLOCK_CLIENT_SECRET" App/app` shows only the line in `config.py`.

## 4. Deviations

- Added `door_code_pins` to `_cutoffs()` in `retention.py` so `test_every_step_of_the_run_writes_class_count_and_cutoff` gets a cutoff string for the new step (same file as step 3; not named in the brief).

## 5. Questions

None.

## 6. Owner steps left

None (feature stays off until `UBYHOST_DOOR_CODES` is set).
