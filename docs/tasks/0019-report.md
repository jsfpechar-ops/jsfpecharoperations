# 0019 report: Stay invoice rules (backend only)

Status: review

## 1. git diff --stat

```
 App/app/invoices.py                  | 236 +++++++++++++++++++++++++++++++++-
 App/tests/test_invoice_stay_rules.py | 217 +++++++++++++++++++++++++++++++
 2 files changed, 447 insertions(+), 6 deletions(-)
```

(Plus this report and brief status flip.)

## 2. Commands (§6)

**`.venv/bin/python -m pytest tests/test_invoice_stay_rules.py -q`**
```
............                                                             [100%]
=============================== warnings summary ===============================
...
12 passed, 1 warning in 0.84s
```

**`.venv/bin/python -m pytest tests -q`**
```
...
2865 passed, 2 skipped, 7 warnings in 313.97s (0:05:13)
```
(summary line: no `failed`)

**`python3 scripts/context_lint.py`**
```
next free: task 0021 | migration 0008
context lint: OK
```

## 3. Acceptance (§7)

- [x] `git diff --stat` shows only the two files in §3 (implementation).
- [x] The 12 new tests pass.
- [x] The full suite passes (all old invoice tests green).
- [x] `grep -n "stay is None\|stay is not None" App/app/invoices.py` → two `stay is not None` branches in `build_draft` (lines ~357, ~412).

## 4. Deviations

- Step 6 uses `draft.get("kind")` instead of `draft["kind"]`. Four old invoice tests call `validate_for_issue` with minimal drafts that omit `kind`; the exact brief line raised `KeyError`. Semantics unchanged for real drafts (always have `kind`); stay checks still only run when `kind == "invoice"` and `reservation_id` is set.
- No date-format adjustment needed; `validation.fmt_date_range` matches the test expectations (`01.10.2026`).

## 5. Questions

None.

## 6. Owner steps left

1. Merge the PR with `scripts/merge-pr-on-green.sh` when CI is green. Nothing to deploy yet: no page changes until 0020.
