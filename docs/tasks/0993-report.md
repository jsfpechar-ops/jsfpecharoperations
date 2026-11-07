# 0993 report: query-shape and index follow-ups

Status: blocked

## 1. Diff

```
 App/app/alerts.py | 19 ++++++++++++-------
 1 file changed, 12 insertions(+), 7 deletions(-)
```

## 2. Test commands (last 5 lines each, from App/)

Group 1, alert/deadline (6 files):
```
........................................................................ [ 51%]
...................................................................      [100%]
139 passed in 9.91s
```

Group 2, stay fee (3 files):
```
..................................................................       [100%]
66 passed in 2.07s
```

Group 3, reporting (4 files):
```
...................................                                      [100%]
=========================== short test summary info ============================
SKIPPED [1] tests/test_host_ux_acceptance.py:41: could not import 'playwright.sync_api': No module named 'playwright'
35 passed, 1 skipped in 2.61s
```

Group 4, migrations (2 files):
```
..ssss..............                                                     [100%]
=========================== short test summary info ============================
SKIPPED [1] tests/test_goose_migrations.py:58: PostgreSQL integration tests need UBYHOST_DATABASE_URL ...
16 passed, 4 skipped in 1.74s
```

`python3 scripts/context_lint.py 2>&1 | tail -5`: `context lint: OK` (warnings about open briefs and status.md only).

## 3. Acceptance (§7)

- [x] `git diff --stat` shows only alerts.py (plus this report).
- [ ] All §6 test commands pass with 0 skipped: all 4 commands exit green, but see skips below. Not ticked.
- [x] Report names, per item, the index and the query it serves (below).

## 4. Item table

| Item | Query (file:line) | Index that serves it | Change |
|---|---|---|---|
| 1 | `alerts.open_alerts` (alerts.py:555) | owner None: `resolved_at IS NULL` via `idx_alert_open_kind` (partial, 00008). Owner given: `owner_user_id = ?` via `idx_alert_owner` (baseline 00001:3087), `kind IN (...)` via `idx_alert_open_kind`; planner can BitmapOr. | Split into two query shapes. The `? IS NULL OR` test is gone. Python sort kept, so rows and order are unchanged. |
| 2 | reporting.py:1412 and stay_fee.py:305 (`_GUESTS_SQL`) | `idx_res_apartment_dates (apartment_id, date_from)` (00001:3360) and `idx_guest_reservation (reservation_id)` (00001:3199) | unchanged; already indexed, no migration. |
| 3 | reporting.py:1567 `apartment_in_doubt` | same two indexes as item 2 | unchanged. `g.submit_state != 'sent'` is a residual filter; a btree cannot range-scan `!=`, so `idx_guest_submit_state_open` is not the access path. |

## 5. Deviations

- Commits: `d6f7536a 0993 step 2` (alerts.py only). The report and the final commit follow.
- The brief assumes `App/.venv` has all deps installed. It did not: `requests` was missing, and `requirements-dev.txt` does not include `requirements.txt`. I ran `pip install -r requirements-dev.txt` and then `pip install -r requirements.txt` inside `App/.venv`. These are already-declared repo dependencies, not new ones.

## 6. Questions and blockers

1. **Playwright is not installed.** `tests/test_host_ux_acceptance.py` (pulled in by the reporting group) skips with `No module named 'playwright'`. The brief requires 0 skipped for browser tests. Playwright is not declared in any requirements file or in `docs/context/decisions.md`, so I did not add it. Owner decision needed: add a `decisions.md` line for Playwright as a dev dependency, or confirm that CI covers this test. Then rerun the group.
2. **Postgres tests skipped** (4 in `test_goose_migrations.py`): they need `UBYHOST_DATABASE_URL` pointing at a disposable DB with `test` in its name. CI job `test-postgres-full` covers them.
3. **Attribution.** The brief and your message asked for a Sonnet 5.5 and an Opus 5.5 trailer. I am Haiku 5.5, and the session attribution says Haiku 5.5, so the final commit uses the Haiku trailer.

## 7. Owner steps left

None to merge the code. Decide item 1 above (Playwright). Do not push or open a PR from this report: the orchestrator does that.
