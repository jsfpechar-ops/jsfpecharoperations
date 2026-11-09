# 1065 report: baseline funnel stage times and per-route query counts

Status: blocked (code done; context lint over cap on `docs/context/test-map.md`)

## 1. Files changed (`git diff --stat 0d851ca4 HEAD`, without the brief)

```
 App/app/admin_funnel.py        | 64 ++++
 App/app/main.py                |  1 +
 App/app/metrics.py             | 37 ++-
 App/tests/test_admin_funnel.py | 61 ++++
 App/tests/test_metrics_0427.py | 31 ++
 docs/context/test-map.md       |  1 +
```

## 2. Commands (last lines)

- Step 1: `('retained', 'retained_at')` / `True`
- Step 2: `600 {'accounts': 0, 'median_seconds': None, 'p75_seconds': None}`
- Step 3: `['ubyhost_request_db_queries_total{method="GET",route="/x/{id}"} 3', 'ubyhost_request_db_seconds_total{method="GET",route="/x/{id}"} 0.02']`
- Step 4: `360:            db_queries=stats.queries, db_seconds=stats.db_seconds,`
- Step 5: `6 passed in 1.32s`
- Step 6: `12 passed in 1.60s`
- Step 7: `28:| Funnel stage times, `/metrics` | ... |`
- §6.1 `pytest tests/test_admin_funnel.py tests/test_metrics_0427.py`: `18 passed in 1.58s`
- §6.2 `pytest tests/test_posthog_*.py tests/test_privacy_first.py`: `12 passed, 1 skipped in 9.27s` (the skip was already there; it is not a browser test)
- `python3 scripts/context_lint.py`:
  ```
  ERROR docs/context/status.md: ~712 tokens > cap 700.
  ERROR docs/context/test-map.md: ~1216 tokens > cap 1200.
  context lint: FAIL
  ```

## 3. Acceptance

- [x] `stages()` and `csv_columns()` unchanged (`test_first_run_times_do_not_change_stages_or_csv` passes).
- [x] `first_run_times()` returns four stages with `accounts`, `median_seconds`, `p75_seconds` from existing columns; no migration and no `db.py` change.
- [x] `/metrics` has `ubyhost_request_db_queries_total` and `ubyhost_request_db_seconds_total` with only `method` and `route` labels; `/l/not-a-real-token` shows `route="/l/{token}"` and never the raw token.
- [x] No new template, script, cookie or outbound request; `retention.py` unchanged.
- [ ] Context lint passes: fails on test-map.md (see 4). Both test commands pass.
- [x] "Guest seconds per registration" not built: no pair of existing timestamps measures one registration. `reservation_claim.claimed_at` is when a stay link was claimed, `guest` has no start timestamp, and `registration_completed_at` is per stay. Building it needs a new column, which is out of scope.

## 4. Deviations

- Every step matched its anchor and its expected output. No code deviation.
- `docs/context/test-map.md` was 4767 chars (about 1191 tokens) at the base. The step 7 row (99 chars) takes it to about 1216 tokens, over the 1200 cap. Getting under needs about 63 chars cut from other rows, which is outside this brief, so the row stays as written. The `status.md` cap error is expected (fixed elsewhere).
- Setup: created `App/.venv` per `App/run.sh` (`python3 -m venv .venv`, upgraded pip, then `pip install -r requirements.txt -r requirements-dev.txt`). It is gitignored.

## 5. Questions

- Orchestrator: compact `test-map.md` (or raise its cap) so the 1065 row fits, then set this brief to review.

## 6. Owner steps left

After merge and deploy, follow "Owner steps" in the brief: run `docker compose exec ubyhost python -m app.admin_funnel 2>&1 | tail -30` for the stage times, then chart the Grafana query-per-route ratio for one week. Leave `ACCESS_LOG` off.
