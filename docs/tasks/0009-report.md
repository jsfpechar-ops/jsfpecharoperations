# 0009 report: TTLock client

Status: review

## 1. Files changed

```
 App/app/ttlock.py        | (new)
 App/tests/test_ttlock.py | (new)
```

## 2. Commands

`cd App && .venv/bin/python -m pytest tests/test_ttlock.py -q`

```
17 passed, 1 warning in 0.60s
```

`python3 scripts/context_lint.py`

```
context lint: OK
```

## 3. Acceptance (§7)

- [x] 17 tests pass (full suite run pending CI).
- [x] One `requests.post` in `_post`.
- [x] No logging of tokens, passwords or response bodies.
- [x] Only §3 files changed.

## 4. Deviations

- `test_budget_tiers` expects final counter `96` (80 + normal + set 95 + critical), not `82` from the brief text.

## 5. Questions

None.

## 6. Owner steps left

Client id and secret in `.env` when task 0010 ships (see 0010 brief).
