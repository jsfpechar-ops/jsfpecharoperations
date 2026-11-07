# 0993: query-shape and index follow-ups from 0991

Status: todo
Depends on: 0991 | Base commit: 915081a3 | Branch: claude/admiring-rubin-56jqe6 (stay on it, no new branch)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Split `alerts.open_alerts` into two query shapes so the `? IS NULL` parameter no longer blocks index use. Confirm in the report that the reservation and guest filters in reporting.py and stay_fee.py are already indexed (no migration), and that the `submit_state != 'sent'` query stays unchanged.

## 2. Context

Rules: all SQL through `db.query`, parameterised, Postgres-portable ([rules: database](../context/rules.md#database)). Goose files must be additive; none is needed here.

Existing indexes (read-only facts, do not re-verify beyond one grep):
- `idx_alert_owner ON alert (owner_user_id, resolved_at)` (baseline 00001:3087; SQLite db.py:339).
- `idx_alert_open_kind ON alert (kind) WHERE resolved_at IS NULL` (00008).
- `idx_res_apartment_dates ON reservation (apartment_id, date_from)` (00001:3360; db.py:331).
- `idx_guest_reservation ON guest (reservation_id)` (00001:3199; db.py:332).
- `idx_guest_submit_state_open ON guest (submit_state) WHERE archived_at IS NULL` (00008).

Excerpt, `App/app/alerts.py` (about lines 553-562); if not found verbatim, STOP:

```python
def open_alerts(owner_user_id: Optional[int] = None) -> List:
    marks = ", ".join("?" for _ in SYSTEM_ALERT_KINDS)
    rows = db.query(
        f"SELECT * FROM alert WHERE resolved_at IS NULL AND ("
        f"? IS NULL OR owner_user_id = ? OR kind IN ({marks})) "
        "ORDER BY created_at DESC",
        (owner_user_id, owner_user_id, *SYSTEM_ALERT_KINDS),
    )
    return sorted(rows, key=lambda r: LEVEL_ORDER.get(r["level"], 9))
```

Decisions already made (do not revisit):
- Item 1: owner None runs a plain `resolved_at IS NULL` query (served by `idx_alert_open_kind` / the open partial indexes; no owner predicate). Owner given keeps `owner_user_id = ? OR kind IN (...)` in ONE query: `idx_alert_owner` serves the owner branch and `idx_alert_open_kind` the kind branch, so Postgres can combine them with a BitmapOr. No UNION, no Python merge (a UNION could change duplicates/ordering for no gain). Python sort stays, so results and ordering are identical.
- Item 2: reporting.py ~1410 (`WHERE r.apartment_id = ?` with join `g.reservation_id = r.id`) and stay_fee.py ~307 `_GUESTS_SQL` (same shape) are served by `idx_res_apartment_dates` (leading column apartment_id) plus `idx_guest_reservation`. No new goose file, no SQLite twin.
- Item 3: reporting.py ~1566 `apartment_in_doubt` is selected by `r.apartment_id = ?` (same two indexes). `g.submit_state != 'sent'` is a residual filter; a btree cannot range-scan `!=` and `idx_guest_submit_state_open` is not the access path. Leave the query UNCHANGED.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/alerts.py | edit | `open_alerts` only (lines ~553-562) |
| docs/tasks/0993-report.md | create | report |
| docs/context/known-issues.md | no change | |

No other file may change.

## 4. Steps

1. `grep -n 'def open_alerts' App/app/alerts.py`, then read 15 lines from there. Confirm the excerpt.
2. Replace the whole function with:

```python
def open_alerts(owner_user_id: Optional[int] = None) -> List:
    # Two query shapes (0993): a `? IS NULL OR ...` test hides owner_user_id from the planner.
    if owner_user_id is None:
        rows = db.query(
            "SELECT * FROM alert WHERE resolved_at IS NULL ORDER BY created_at DESC"
        )
    else:
        marks = ", ".join("?" for _ in SYSTEM_ALERT_KINDS)
        rows = db.query(
            "SELECT * FROM alert WHERE resolved_at IS NULL AND ("
            f"owner_user_id = ? OR kind IN ({marks})) ORDER BY created_at DESC",
            (owner_user_id, *SYSTEM_ALERT_KINDS),
        )
    return sorted(rows, key=lambda r: LEVEL_ORDER.get(r["level"], 9))
```

3. `grep -n 'def query' App/app/db.py` and check `db.query` accepts a call without params; if it requires one, pass `()`.
4. Run one grep to confirm the four index names exist in `App/migrations_pg/00001_baseline.sql` and `00008_full_scan_indexes.sql`. Read (do not edit) the three queries named in §2 Item 2 and 3 to confirm the shapes.
5. Run the §6 commands, write the report.

## 5. Do not touch

App/app/reporting.py, App/app/stay_fee.py, App/migrations_pg/*, App/app/migrations/*, db.py, tests. No push, no PR, no new dependency. Never set PYTHONPATH.

## 6. Commands

From `App/` (each ends `2>&1 | tail -30`; all must pass):
- `.venv/bin/python -m pytest tests/test_alert_stack.py tests/test_alert_language.py tests/test_claim_checkin_alerts.py tests/test_deadlines.py tests/test_icalsync.py tests/test_p1_review.py -q --tb=short -x 2>&1 | tail -30`
- `.venv/bin/python -m pytest tests/test_stay_fee.py tests/test_stay_fee_list.py tests/test_stay_fee_auto.py -q --tb=short -x 2>&1 | tail -30`
- `.venv/bin/python -m pytest tests/test_report_detail_next_step.py tests/test_report_detail_polish.py tests/test_reporting_help_0097.py tests/test_deadline_after_reporting.py -q --tb=short -x 2>&1 | tail -30`
- `.venv/bin/python -m pytest tests/test_goose_migrations.py tests/test_migrations.py -q --tb=short -x 2>&1 | tail -30`

From repo root: `python3 scripts/context_lint.py 2>&1 | tail -30` (expect OK).

Commit on the current branch, message `0993: split open_alerts query shapes; confirm index coverage`, ending with:
Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_014N5J8NqnP3qxbXa5PkL49K

## 7. Acceptance

- [ ] `git diff --stat` shows only alerts.py (plus the report).
- [ ] All §6 test commands pass; context_lint OK.
- [ ] Report names, per item, the index and the query it serves.

## 8. Stop and ask

Stop, write the report as `blocked`, if: an excerpt is not found; a test fails twice; 25 tool calls or about 50k tokens; a file outside §3 needs a change; reading the queries shows a shape different from §2 (then report the real shape, change nothing); you need push, merge or deploy.

## 9. Report

Write `docs/tasks/0993-report.md` (600 tokens at most), set `Status: review`:
1. `git diff --stat`.
2. Each command, last 5 lines.
3. §7 ticked.
4. Item table: item, query (file:line), index that serves it, change or "unchanged" and why.
5. Deviations, questions. Do NOT push and do NOT open a PR.

## Risk list (for the reviewer)

- App/app/alerts.py `open_alerts`: owner None and owner given must return the same rows and order as before; system kinds still visible to every owner.

## Owner steps

None. The orchestrator pushes, opens the PR, and checks CI `test-postgres-full`. Deploy stays manual (owner).
