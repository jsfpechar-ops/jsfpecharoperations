# 1173e: the revive keeps an expired row when the lock account is broken, so nobody tells the host

Status: review
Depends on: 1173d | Base commit: claude/zealous-maxwell-a7ub54 HEAD (e8c30e72, PR #950, contains 1173d) | Branch: task/1173e-revive-broken-account
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens (about 10 calls planned; at 25, stop and write the report as `blocked`)

## 1. Objective

`_revive_unissued_expired` (1173d) skips the delete when `_owner_can_hold_code(owner)` is false. When the plan allows TTLock but the lock account status is not ok, an extended (live-again) stay keeps its expired unissued row: `_alert_delayed` only looks at stays with no row or a pending/issuing/retrying row, and the delayed-card sweep closes cards of expired rows, so the host is told nothing while the guest has no code. Fix: the revive skips only when `not ttlock.allowed_for(owner)`. The row is then deleted, `_alert_delayed` raises the existing `door_code_delayed` card with reason `not_set_up`, and once the account is ok again the code is issued.

## 2. Context

Rules: AGENTS.md hard rules 1, 4 (no new dependency), 5 (SQL only through `db.py` helpers; no schema change). No UI, no copy, no state-machine change (`go/` unchanged). Keep `_owner_can_hold_code` as it is: `ensure_row` still uses it.

Executor rules (strict): never `git rebase`, `git commit --amend`, `git stash` or `git commit -a`. Commit with `git add <files>` then `git commit`. Restore bites with `git checkout HEAD -- <files>` and check `git diff HEAD --stat | tail -3` is empty before every commit. Helper scripts go to `/tmp/claude-0/-home-user-jsfpecharoperations/39c8a7b8-8460-5b3b-80f9-3bc7a1fab9d7/scratchpad/` (not `/tmp`, not the repo).

Anchor (verbatim), `App/app/door_codes.py`, in `_revive_unissued_expired`:
```python
        if not _owner_can_hold_code(row["owner_user_id"]):
            continue  # ensure_row would not make a new row: keep the expired one (1173d)
```
Anchor, `App/tests/test_issue_queue_starvation.py`: the block from `@pytest.mark.parametrize("how", ["plan", "account"])` up to (not including) `def test_an_expired_row_is_revived_when_the_owner_can_hold_a_code`, and the import line `from app import db, deadlines, door_codes, ttlock`. If an anchor is not found, STOP (§8).

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/door_codes.py | edit | the revive checks only `ttlock.allowed_for` |
| App/tests/test_issue_queue_starvation.py | edit | split the parametrized test: plan stays kept; broken account now deletes and raises the card |
| docs/tasks/1173e-revive-broken-account.md | edit | `Status: todo` to `review` |
| docs/tasks/1173e-report.md | create | the report |

No other file may change.

## 4. Steps

1. Branch and baseline. From the repo root:
```bash
git checkout -b task/1173e-revive-broken-account 2>&1 | tail -3
(cd App && env -u UBYHOST_DATABASE_URL .venv/bin/python -m pytest tests/test_issue_queue_starvation.py -q --tb=short -x 2>&1 | tail -30)
```
Expect: `19 passed`.

2. Apply this diff exactly (the two files only; make each replacement by an editor or a script that asserts the old text occurs once). Verified by the orchestrator on SQLite and PostgreSQL.
```diff
diff --git a/App/app/door_codes.py b/App/app/door_codes.py
index a78a2eb3..00813f77 100644
--- a/App/app/door_codes.py
+++ b/App/app/door_codes.py
@@ -1573,8 +1573,10 @@ def _revive_unissued_expired() -> int:
             continue
         if end_ms < now_ms:
             continue
-        if not _owner_can_hold_code(row["owner_user_id"]):
-            continue  # ensure_row would not make a new row: keep the expired one (1173d)
+        if not ttlock.allowed_for(row["owner_user_id"]):
+            # Plan without TTLock: ensure_row would never make a new row, keep the expired one (1173d).
+            # A lock account that is not ok does not count: _alert_delayed then tells the host (1173e).
+            continue
         # Guarded: only a row that is still expired is deleted.
         removed = db.execute("DELETE FROM door_code WHERE id = ? AND state = ?", (row["id"], EXPIRED))
         if removed:
diff --git a/App/tests/test_issue_queue_starvation.py b/App/tests/test_issue_queue_starvation.py
index 7f6eff6e..481bebaf 100644
--- a/App/tests/test_issue_queue_starvation.py
+++ b/App/tests/test_issue_queue_starvation.py
@@ -9,7 +9,7 @@ from datetime import datetime, timedelta, timezone
 
 import pytest
 
-from app import db, deadlines, door_codes, ttlock
+from app import alerts, db, deadlines, door_codes, ttlock
 from tests.test_door_codes_safeguards import _env, _stay  # noqa: F401
 
 OLD = "2000-01-01T00:00:00+00:00"
@@ -242,23 +242,31 @@ def _reset_audited(row_id: int):
     )
 
 
-@pytest.mark.parametrize("how", ["plan", "account"])
-def test_an_expired_row_is_kept_when_no_new_row_could_be_made(monkeypatch, lock, how):
-    """ensure_row would refuse this owner: deleting the row would leave the stay with none (1173d)."""
-    stay, row_id = _expired_unissued(2)
-    if how == "plan":
-        monkeypatch.setattr(ttlock, "allowed_for", lambda owner: False)
-    else:
-        db.execute(
-            "UPDATE lock_account SET status = 'error' WHERE owner_user_id = "
-            "(SELECT a.owner_user_id FROM apartment a JOIN reservation r ON r.apartment_id = a.id WHERE r.id = ?)",
-            (stay,),
-        )
+def test_an_expired_row_is_kept_when_the_plan_does_not_allow_ttlock(monkeypatch, lock):
+    """ensure_row would never make a new row for this owner: deleting would leave the stay with none (1173d)."""
+    _, row_id = _expired_unissued(2)
+    monkeypatch.setattr(ttlock, "allowed_for", lambda owner: False)
     assert door_codes._revive_unissued_expired() == 0
     assert _row(row_id)["state"] == door_codes.EXPIRED
     assert _reset_audited(row_id) is None
 
 
+def test_a_broken_lock_account_deletes_the_expired_row_and_the_host_is_told(lock):
+    """Plan allows TTLock, account not ok: the row goes so _alert_delayed raises the card (1173e)."""
+    stay, row_id = _expired_unissued(2)
+    db.execute(
+        "UPDATE lock_account SET status = 'error' WHERE owner_user_id = "
+        "(SELECT a.owner_user_id FROM apartment a JOIN reservation r ON r.apartment_id = a.id WHERE r.id = ?)",
+        (stay,),
+    )
+    assert door_codes._revive_unissued_expired() == 1
+    assert _row(row_id) is None
+    assert _reset_audited(row_id)
+    door_codes.reconcile()
+    card = alerts.open_alert(f"door_code_delayed:{stay}")
+    assert card is not None and "reason=not_set_up" in card["detail"]
+
+
 def test_an_expired_row_is_revived_when_the_owner_can_hold_a_code(lock):
     _, row_id = _expired_unissued(2)
     assert door_codes._revive_unissued_expired() == 1
```
Then:
```bash
git diff --stat | tail -3
(cd App && env -u UBYHOST_DATABASE_URL .venv/bin/python -m pytest tests/test_issue_queue_starvation.py -q --tb=short -x 2>&1 | tail -30)
```
Expect: 2 files changed (25 insertions, 15 deletions) and `19 passed` (the old parametrized test of 2 cases became 2 functions plus 1 new case: 19 in total). Commit: `git add App/app/door_codes.py App/tests/test_issue_queue_starvation.py && git commit -m "1173e: revive deletes the expired row when only the lock account is broken, so the delayed card is raised"`.

3. Revert-bite. Restore the old check, the new test must fail, then restore:
```bash
cp App/app/door_codes.py /tmp/claude-0/-home-user-jsfpecharoperations/39c8a7b8-8460-5b3b-80f9-3bc7a1fab9d7/scratchpad/dc.fixed
git checkout HEAD~1 -- App/app/door_codes.py
(cd App && env -u UBYHOST_DATABASE_URL .venv/bin/python -m pytest tests/test_issue_queue_starvation.py -q --tb=line 2>&1 | tail -5)
git checkout HEAD -- App/app/door_codes.py
git diff HEAD --stat | tail -3
```
Expect: `FAILED ...test_a_broken_lock_account_deletes_the_expired_row_and_the_host_is_told` (`assert 0 == 1`), `1 failed, 18 passed`, then an empty `git diff HEAD --stat`. Repeat the pytest line with `UBYHOST_DATABASE_URL=postgresql://uby:uby@localhost:5432/ubytest` (instead of `env -u`) between the two checkouts: same result.

4. Both databases, the five test-map files for the revive and the cards:
```bash
(cd App && env -u UBYHOST_DATABASE_URL .venv/bin/python -m pytest tests/test_issue_queue_starvation.py tests/test_door_code_unverified_card.py tests/test_door_codes_safeguards.py tests/test_door_code_handover.py tests/test_sm_go_parity.py -q --tb=short -x 2>&1 | tail -30)
pg_isready -h localhost || sudo pg_ctlcluster 16 main start
(cd App && UBYHOST_DATABASE_URL=postgresql://uby:uby@localhost:5432/ubytest .venv/bin/python scripts/pg_schema.py apply --expect-database ubytest 2>&1 | tail -3)
(cd App && UBYHOST_DATABASE_URL=postgresql://uby:uby@localhost:5432/ubytest .venv/bin/python -m pytest tests/test_issue_queue_starvation.py tests/test_door_code_unverified_card.py tests/test_door_codes_safeguards.py tests/test_door_code_handover.py tests/test_sm_go_parity.py -q --tb=short -x 2>&1 | tail -30)
(cd App && .venv/bin/ruff check --select E9,F63,F7,F82,F401,F841 app tests 2>&1 | tail -30)
```
Expect: `88 passed` on SQLite, `PostgreSQL schema apply OK`, `88 passed` on PostgreSQL, `All checks passed!`.

5. Docs and lint. Set `Status: review`, write `docs/tasks/1173e-report.md` (§9), then:
```bash
git add docs/tasks/1173e-revive-broken-account.md docs/tasks/1173e-report.md && git commit -m "1173e: report" 2>&1 | tail -3
python3 scripts/context_lint.py | tail -3
git diff e8c30e72 --stat | tail -6
```
Expect: `context lint: OK` and a stat listing the two App files and the two docs.

## 5. Do not touch

`go/`, `App/app/migrations/`, `docs/context/*` (the orchestrator records decisions and known issues), `_owner_can_hold_code` and `ensure_row`, every file not in §3. Hard rule 8: never push to `main`; leave the push and the PR to the owner.

## 6. Commands

The steps carry them: SQLite 1, 2, 4; PostgreSQL 3, 4; bite 3; lint 5. Never the full suite.

## 7. Acceptance

- [ ] `git diff e8c30e72 --stat` lists `door_codes.py`, `test_issue_queue_starvation.py`, this brief and the report.
- [ ] `19 passed` (one file) and `88 passed` (five files) on SQLite and on PostgreSQL; ruff `All checks passed!`.
- [ ] Bite: old check restored gives `1 failed, 18 passed` on both databases; `git diff HEAD --stat` empty afterwards.
- [ ] `context lint: OK`.

## 8. Stop and ask

Stop, and write the report, if:

- an anchor is not found verbatim;
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1173e-report.md` (600 tokens at most) and set `Status: review`. The report has: 1. files changed (`git diff e8c30e72 --stat`); 2. each command with the last 5 lines of output; 3. §7 ticked; 4. deviations; 5. questions; 6. owner steps left.

## Risk list (for the reviewer)

- `App/app/door_codes.py`: the revive now deletes the row for an owner whose lock account is not ok; the same tick `ensure_row` returns None for that owner, so the stay has no row until the account works. `_alert_delayed` covers exactly that state (no row, plan allowed, registered more than 5 minutes ago) with reason `not_set_up`.
- Not-allowed plan: row kept, no audit, no card (`_alert_delayed` skips such owners on purpose).

## Owner steps

1. Open the PR from `task/1173e-revive-broken-account` when the checks are green, including test-postgres and test-postgres-full.
2. Merge with `scripts/merge-pr-on-green.sh`.
