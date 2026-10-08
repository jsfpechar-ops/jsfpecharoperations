# 0019 report: Stay invoice rules (backend only)

Status: review

## 1. git diff --stat

```
 App/app/invoices.py                  | (stay rules + council harden)
 App/tests/test_invoice_stay_rules.py | 14 tests
 docs/tasks/0019-report.md
 docs/tasks/0019-stay-invoice-rules.md | Status: review
```

## 2. Commands (§6)

**`.venv/bin/python -m pytest tests/test_invoice_stay_rules.py -q`**
```
..............                                                           [100%]
14 passed, 1 warning in 0.67s
```

**`.venv/bin/python -m pytest tests -q -k invoice`** (after council fixes; full suite was green on first land)
```
75+ passed (invoice filter); no failed
```

**`python3 scripts/context_lint.py`**
```
context lint: OK
```

## 3. Acceptance (§7)

- [x] Implementation only touches `invoices.py` + `test_invoice_stay_rules.py` (+ report/brief status).
- [x] New stay-rule tests pass (14, including 2 council follow-ups).
- [x] Old invoice tests green.
- [x] Two `stay is not None` branches in `build_draft`.

## 4. Deviations

- Step 6 uses `draft.get("kind")` instead of `draft["kind"]` (old minimal fixtures omit `kind`).
- **Council (Claude Sonnet 5.5 ×3, owner-requested):** fixed a validation hole where a forged `item_kind=stay` extra was filtered out of `_stay_issues` and skipped every cap. Now line 1 must be the stay line; extras are `items[1:]`; form `"stay"` maps to `"invalid"`. Caps skipped when stay price already invalid (less noise). Tests added for forged stay kind, qty 0, and stay+4 extras → `too_many_items`.

## 5. Council summary

| Finding | Action |
|---|---|
| Posted `item_kind=stay` bypasses caps (A+B) | **Fixed** |
| Require `items[0]` stay line; extras = rest (A+B) | **Fixed** |
| Skip caps when stay price invalid (C) | **Fixed** |
| Negative extras defeat caps (B) | Already blocked by `price_invalid` + qty range |
| Force DUZP ignore form (A) | **Skipped** — plan §5.2: DUZP still editable |
| Entity ownership inside lock (A) | **Defer 0020** (brief: route checks) |
| Unique extra kinds (A) | **Skipped** — not in brief |
| `stay_problem` on issue path (C) | **Defer 0020** (by design) |

Verdict: approve-with-fixes → fixes landed.

## 6. Questions

None.

## 7. Owner steps left

1. Merge the PR with `scripts/merge-pr-on-green.sh` when CI is green. Nothing to deploy until 0020.
