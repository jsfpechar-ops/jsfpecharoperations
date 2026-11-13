# 1173d: last nits of the review of 1173c (two tests that guard nothing, a hard-coded placeholder list, a delete before the row can be recreated)

Status: todo
Depends on: 1173c | Base commit: claude/zealous-maxwell-a7ub54 HEAD (8d7ba6cd, PR #950, contains 1173, 1173b, 1173c) | Branch: task/1173d-queue-final-nits
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens (about 16 calls planned; if you reach 25, stop and write the report as `blocked`)

## 1. Objective

Close four small findings of the review of 1173c. T1 and T2: two guards in the 1173b/1173c code are not pinned by any test (the per-stay correlation of the delayed-card sweep; the eligibility clause of the revive), so add tests that fail when the guard is dropped. C1: the `IN (?, ?, ?)` list in `_issue_due` must follow `RELEASE_REASONS`. C2: `_revive_unissued_expired` deletes an expired row even when `ensure_row` would then refuse to make a new one, which leaves the stay with no row; skip the delete in that case.

## 2. Context

Rules: AGENTS.md hard rules 1, 4 (no new dependency), 5 (SQL only through `db.py` helpers, Postgres-portable; no schema change). No UI, no template, no copy. No state-machine change, so `go/` does not change.

Executor rules (strict): never `git rebase`, `git commit --amend`, `git stash` or `git commit -a`. Commit with `git add <files>` then `git commit`. Restore bites with `git checkout HEAD -- <files>` and check `git diff HEAD --stat | tail -3` is empty before every commit. Helper scripts go to `/tmp/claude-0/-home-user-jsfpecharoperations/39c8a7b8-8460-5b3b-80f9-3bc7a1fab9d7/scratchpad/` (not `/tmp`, not the repo). Anchors: each `sub(old, new)` below asserts `old` occurs exactly once; if not, STOP (section 8).

### Decisions in this brief (the orchestrator made them; do not reopen)

**T1.** The test `test_the_delayed_card_closes_when_the_stay_ends_without_a_code` calls `door_codes.reconcile()`. There `_alert_delayed` raises the other stay's card again in the same call, so a sweep without `dc.reservation_id = alert.reservation_id` (App/app/door_codes.py, second `UPDATE alert` of `_resolve_unverified_cards`) still passes. The test now calls `_expire_ended_stays` and `_resolve_unverified_cards()` directly and checks that the other stay's card is the same row (same `id`, `resolved_at` still NULL).

**T2.** Three new test cases pin `AND {clause}` in `_revive_unissued_expired`: an expired never-coded row whose window is ahead, of a cancelled stay, and of a stay with `registration_completed_at` NULL: `_revive_unissued_expired() == 0` and the row stays `expired`.

**C1.** `_issue_due` builds the list as `', '.join('?' * len(RELEASE_REASONS))`. One new test patches `door_codes.RELEASE_REASONS` to four reasons: with the old text the bindings do not match and the query raises.

**C2.** New helper `_owner_can_hold_code(owner_user_id)` holding exactly the two checks `ensure_row` makes today (`ttlock.allowed_for`, then `ttlock.account_for` with status `ok`). `ensure_row` calls it (same behaviour), and `_revive_unissued_expired` calls it before the delete and `continue`s when it is false (the select also returns `a.owner_user_id`). No other logic changes. Tests: owner not allowed (patch `ttlock.allowed_for`) or lock account status `error`: row stays expired, returns 0, no `door_code_reset` audit; owner fine: returns 1, row deleted, audit written.

### Current text (verbatim anchors)

`App/app/door_codes.py`, in `ensure_row`:
```python
    if not ttlock.allowed_for(row["owner_user_id"]):
        return None
    account = ttlock.account_for(row["owner_user_id"])
    if not account or account["status"] != "ok":
        return None
    now = db.utcnow()
    db.execute(
        "INSERT INTO door_code (reservation_id,
```
(the last line is cut on purpose; the anchor used below is the first six lines plus `db.execute(` and `"INSERT INTO door_code (reservation_id,`).

In `_issue_due`:
```python
        "ORDER BY CASE WHEN last_error IN (?, ?, ?) THEN 2 WHEN attempts > 0 THEN 1 ELSE 0 END, "
        "(next_attempt_at IS NOT NULL), next_attempt_at, id LIMIT ?",
```
In `_revive_unissued_expired`:
```python
        f"SELECT dc.id, r.date_from, r.date_to, a.checkin_hour, a.checkout_hour "
```
and
```python
        if end_ms < now_ms:
            continue
        # Guarded: only a row that is still expired is deleted.
```
`App/tests/test_door_code_unverified_card.py`, end of `test_the_delayed_card_closes_when_the_stay_ends_without_a_code`:
```python
    door_codes.reconcile()
    assert _row(row_id)["state"] == door_codes.EXPIRED
    assert alerts.open_alert(f"door_code_delayed:{stay}") is None
    assert alerts.open_alert(f"door_code_delayed:{other}") is not None  # still waiting: the card stays
```
`App/tests/test_issue_queue_starvation.py` already has `_stuck`, `_healthy`, `_row`, `OLD`, `_expired_unissued(offset_days)`, the `lock` fixture and imports `datetime`, `timedelta`, `pytest`, `db`, `deadlines`, `door_codes`, `ttlock`, `_stay`.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/door_codes.py | edit | `_owner_can_hold_code`, `ensure_row` uses it, `_issue_due` placeholder list, owner check in `_revive_unissued_expired` |
| App/tests/test_door_code_unverified_card.py | edit | T1: the delayed-card test calls the sweep directly |
| App/tests/test_issue_queue_starvation.py | edit | append 6 test cases (4 functions, two parametrized twice) |
| docs/tasks/1173d-queue-final-nits.md | edit | `Status: todo` to `review` |
| docs/tasks/1173d-report.md | create | the report |

No other file may change.

## 4. Steps

1. Branch and baseline. From the repo root:
```bash
git checkout -b task/1173d-queue-final-nits 2>&1 | tail -3
(cd App && env -u UBYHOST_DATABASE_URL .venv/bin/python -m pytest tests/test_issue_queue_starvation.py tests/test_door_code_unverified_card.py tests/test_null_order_portability.py -q --tb=short -x 2>&1 | tail -30)
```
Expect: `22 passed`. (If the branch exists already, use `git checkout task/1173d-queue-final-nits` and say so in the report.)

2. Code (C1, C2). Write the script `/tmp/claude-0/-home-user-jsfpecharoperations/39c8a7b8-8460-5b3b-80f9-3bc7a1fab9d7/scratchpad/step2.py`, then run it from the repo root with `python3 <that path> 2>&1 | tail -30`. Expect no output (a failed anchor raises `AssertionError`: STOP).
```python
def sub(path, old, new):
    s = open(path).read()
    assert s.count(old) == 1, (path, old[:60], s.count(old))
    open(path, "w").write(s.replace(old, new))

P = "App/app/door_codes.py"
sub(P, """        "ORDER BY CASE WHEN last_error IN (?, ?, ?) THEN 2 WHEN attempts > 0 THEN 1 ELSE 0 END, "
        "(next_attempt_at IS NOT NULL), next_attempt_at, id LIMIT ?",""",
"""        f"ORDER BY CASE WHEN last_error IN ({', '.join('?' * len(RELEASE_REASONS))}) THEN 2 "
        "WHEN attempts > 0 THEN 1 ELSE 0 END, "
        "(next_attempt_at IS NOT NULL), next_attempt_at, id LIMIT ?",""")
sub(P, """    if not ttlock.allowed_for(row["owner_user_id"]):
        return None
    account = ttlock.account_for(row["owner_user_id"])
    if not account or account["status"] != "ok":
        return None
    now = db.utcnow()
    db.execute(
        "INSERT INTO door_code (reservation_id,""", """    if not _owner_can_hold_code(row["owner_user_id"]):
        return None
    now = db.utcnow()
    db.execute(
        "INSERT INTO door_code (reservation_id,""")
sub(P, """def ensure_row(reservation_id: int) -> Optional[int]:""", """def _owner_can_hold_code(owner_user_id) -> bool:
    \"\"\"The plan allows TTLock and the lock account works: the test ensure_row makes before it inserts a row.\"\"\"
    if not ttlock.allowed_for(owner_user_id):
        return False
    account = ttlock.account_for(owner_user_id)
    return bool(account and account["status"] == "ok")


def ensure_row(reservation_id: int) -> Optional[int]:""")
sub(P, """        f"SELECT dc.id, r.date_from, r.date_to, a.checkin_hour, a.checkout_hour "
""", """        f"SELECT dc.id, r.date_from, r.date_to, a.checkin_hour, a.checkout_hour, a.owner_user_id "
""")
sub(P, """        if end_ms < now_ms:
            continue
        # Guarded""", """        if end_ms < now_ms:
            continue
        if not _owner_can_hold_code(row["owner_user_id"]):
            continue  # ensure_row would not make a new row: keep the expired one (1173d)
        # Guarded""")
```
Then:
```bash
git diff --stat | tail -3
(cd App && env -u UBYHOST_DATABASE_URL .venv/bin/python -m pytest tests/test_issue_queue_starvation.py tests/test_door_code_unverified_card.py tests/test_null_order_portability.py -q --tb=short -x 2>&1 | tail -30)
```
Expect: one file changed (about 14 insertions, 6 deletions) and `22 passed` (behaviour unchanged). Commit: `git add App/app/door_codes.py && git commit -m "1173d step 2: placeholder list from RELEASE_REASONS, no revive delete when ensure_row would refuse"`.

3. Tests T1 (edit the delayed-card test). Script `.../scratchpad/step3.py`, run as `python3 <path> 2>&1 | tail -30`; expect no output.
```python
def sub(path, old, new):
    s = open(path).read()
    assert s.count(old) == 1, (path, old[:60], s.count(old))
    open(path, "w").write(s.replace(old, new))

sub("App/tests/test_door_code_unverified_card.py", """    door_codes.reconcile()
    assert _row(row_id)["state"] == door_codes.EXPIRED
    assert alerts.open_alert(f"door_code_delayed:{stay}") is None
    assert alerts.open_alert(f"door_code_delayed:{other}") is not None  # still waiting: the card stays
""", """    # Not reconcile(): its _alert_delayed would raise the other stay's card again and hide a sweep that
    # ignores which stay a card belongs to (1173d).
    door_codes._expire_ended_stays(db.utcnow())
    assert _row(row_id)["state"] == door_codes.EXPIRED
    other_card = alerts.open_alert(f"door_code_delayed:{other}")
    door_codes._resolve_unverified_cards()
    assert alerts.open_alert(f"door_code_delayed:{stay}") is None
    still = alerts.open_alert(f"door_code_delayed:{other}")  # still waiting: the same card stays open
    assert still is not None and still["id"] == other_card["id"] and still["resolved_at"] is None
""")
```

4. Tests T2, C1, C2: append this block to the END of `App/tests/test_issue_queue_starvation.py` (two blank lines before it; use `cat >> ... <<'EOF'` or an editor, do not change anything above it):
```python

# --- 1173d ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "change",
    [
        "UPDATE reservation SET status = 'cancelled' WHERE id = ?",
        "UPDATE reservation SET registration_completed_at = NULL WHERE id = ?",
    ],
)
def test_an_expired_row_of_a_stay_that_is_not_eligible_is_not_revived(lock, change):
    """The window is ahead, but the stay is cancelled or not registered: the eligibility clause keeps the row."""
    stay, row_id = _expired_unissued(2)
    db.execute(change, (stay,))
    assert door_codes._revive_unissued_expired() == 0
    assert _row(row_id)["state"] == door_codes.EXPIRED


def _reset_audited(row_id: int):
    return db.query_one(
        "SELECT 1 AS n FROM audit WHERE action = 'door_code_reset' AND detail = ?", (f"door_code={row_id}",)
    )


@pytest.mark.parametrize("how", ["plan", "account"])
def test_an_expired_row_is_kept_when_no_new_row_could_be_made(monkeypatch, lock, how):
    """ensure_row would refuse this owner: deleting the row would leave the stay with none (1173d)."""
    stay, row_id = _expired_unissued(2)
    if how == "plan":
        monkeypatch.setattr(ttlock, "allowed_for", lambda owner: False)
    else:
        db.execute(
            "UPDATE lock_account SET status = 'error' WHERE owner_user_id = "
            "(SELECT a.owner_user_id FROM apartment a JOIN reservation r ON r.apartment_id = a.id WHERE r.id = ?)",
            (stay,),
        )
    assert door_codes._revive_unissued_expired() == 0
    assert _row(row_id)["state"] == door_codes.EXPIRED
    assert _reset_audited(row_id) is None


def test_an_expired_row_is_revived_when_the_owner_can_hold_a_code(lock):
    _, row_id = _expired_unissued(2)
    assert door_codes._revive_unissued_expired() == 1
    assert _row(row_id) is None
    assert _reset_audited(row_id)


def test_the_due_query_follows_the_number_of_release_reasons(monkeypatch):
    """The IN list is built from RELEASE_REASONS: a fourth reason must not break the bindings (1173d)."""
    monkeypatch.setattr(door_codes, "RELEASE_REASONS", (*door_codes.RELEASE_REASONS, "other_release"))
    retry_id = _healthy()
    db.execute(
        "UPDATE door_code SET state = ?, attempts = 1, last_error = 'network', next_attempt_at = ? WHERE id = ?",
        (door_codes.RETRYING, OLD, retry_id),
    )
    released_id = _stuck("not_eligible")
    db.execute("UPDATE door_code SET last_error = 'other_release' WHERE id = ?", (released_id,))
    seen = []
    monkeypatch.setattr(door_codes, "issue", lambda rid, allow_gateway=False: seen.append(rid) or True)
    door_codes._issue_due(db.utcnow())
    assert seen.index(retry_id) < seen.index(released_id)  # the fourth reason ranks last too
```
Then:
```bash
(cd App && env -u UBYHOST_DATABASE_URL .venv/bin/python -m pytest tests/test_issue_queue_starvation.py tests/test_door_code_unverified_card.py tests/test_null_order_portability.py -q --tb=short -x 2>&1 | tail -30)
(cd App && .venv/bin/ruff check --select E9,F63,F7,F82,F401,F841 app tests 2>&1 | tail -30)
```
Expect: `28 passed` and `All checks passed!`. Commit: `git add App/tests/test_door_code_unverified_card.py App/tests/test_issue_queue_starvation.py && git commit -m "1173d step 3-4: tests for the sweep correlation, the revive guards and the placeholder list"`.

5. Wider SQLite run (door-code and TTLock rows of the test-map, admin ops, state machine incl. the Go parity test, ruff):
```bash
(cd App && env -u UBYHOST_DATABASE_URL .venv/bin/python -m pytest tests/test_door_code*.py tests/test_ttlock*.py tests/test_smart_locks_page.py tests/test_admin_operations.py tests/test_issue_queue_starvation.py tests/test_sm_*.py tests/test_null_order_portability.py -q --tb=short -x 2>&1 | tail -30)
```
Expect: `542 passed, 2 skipped` (2 Playwright skips are fine).

6. PostgreSQL. Start it if needed, apply the schema, run both sets:
```bash
pg_isready -h localhost || sudo pg_ctlcluster 16 main start
(cd App && UBYHOST_DATABASE_URL=postgresql://uby:uby@localhost:5432/ubytest .venv/bin/python scripts/pg_schema.py apply --expect-database ubytest 2>&1 | tail -3)
(cd App && UBYHOST_DATABASE_URL=postgresql://uby:uby@localhost:5432/ubytest .venv/bin/python -m pytest tests/test_issue_queue_starvation.py tests/test_door_code_unverified_card.py tests/test_null_order_portability.py -q --tb=short -x 2>&1 | tail -30)
(cd App && UBYHOST_DATABASE_URL=postgresql://uby:uby@localhost:5432/ubytest .venv/bin/python -m pytest tests/test_door_code*.py tests/test_ttlock*.py tests/test_smart_locks_page.py tests/test_admin_operations.py tests/test_issue_queue_starvation.py tests/test_sm_*.py tests/test_null_order_portability.py -q --tb=short -x 2>&1 | tail -30)
```
Expect: `PostgreSQL schema apply OK: database=ubytest, ...`, `28 passed`, then `541 passed, 3 skipped` (2 Playwright, 1 `sqlite_only`). Known flake: when this run directly follows bite runs on PostgreSQL, the first run once failed in `test_ttlock_lock_setup.py::test_a_lock_setup_answer_on_a_move_retries_in_an_hour...` (leftover rows); it passes alone and on a re-run. If that exact test fails, re-run the same command once; it is not a defect of this brief. Any other failure, or a second failure: STOP.

7. Bites (revert-bite). Four mutants, each must make the 1173d tests fail. Write this script to `/tmp/claude-0/-home-user-jsfpecharoperations/39c8a7b8-8460-5b3b-80f9-3bc7a1fab9d7/scratchpad/bite1173d.py` (it restores with `git checkout HEAD --`; the tree must be committed first, see step 4):
```python
"""Run from the repo root: python3 <this file>. Applies each bite to App/app/door_codes.py, expects the tests to fail, restores."""
import subprocess, sys, os
P = "App/app/door_codes.py"
BITES = {
 "A correlation": ('WHERE dc.reservation_id = alert.reservation_id AND dc.state IN (?, ?))",', 'WHERE dc.state IN (?, ?))",'),
 "B eligibility": ('f"WHERE dc.state = ? AND dc.provider_code_id IS NULL AND {clause}",', 'f"WHERE dc.state = ? AND dc.provider_code_id IS NULL AND {clause} OR 1=1",'),
 "C placeholders": ("f\"ORDER BY CASE WHEN last_error IN ({', '.join('?' * len(RELEASE_REASONS))}) THEN 2 \"", '"ORDER BY CASE WHEN last_error IN (?, ?, ?) THEN 2 "'),
 "D owner check": ('        if not _owner_can_hold_code(row["owner_user_id"]):\n            continue  # ensure_row', '        if False:\n            continue  # ensure_row'),
}
env = {k: v for k, v in os.environ.items() if k != "UBYHOST_DATABASE_URL"}
if os.environ.get("PGURL"): env["UBYHOST_DATABASE_URL"] = os.environ["PGURL"]
bad = 0
for name, (old, new) in BITES.items():
    s = open(P).read()
    assert s.count(old) == 1, name
    open(P, "w").write(s.replace(old, new))
    r = subprocess.run(["bash", "-c", "cd App && .venv/bin/python -m pytest tests/test_issue_queue_starvation.py tests/test_door_code_unverified_card.py -q --tb=no 2>&1 | tail -3"], env=env, capture_output=True, text=True)
    subprocess.run(["git", "checkout", "HEAD", "--", P])
    failed = " failed" in r.stdout
    print(("BITE FAILS AS EXPECTED " if failed else "BITE SURVIVED ") + name)
    bad += 0 if failed else 1
print("ALL BITES CAUGHT" if not bad else "SOME BITES SURVIVED")
```
Run from the repo root, once per database:
```bash
git diff HEAD --stat | tail -3
python3 /tmp/claude-0/-home-user-jsfpecharoperations/39c8a7b8-8460-5b3b-80f9-3bc7a1fab9d7/scratchpad/bite1173d.py 2>&1 | tail -8
PGURL=postgresql://uby:uby@localhost:5432/ubytest python3 /tmp/claude-0/-home-user-jsfpecharoperations/39c8a7b8-8460-5b3b-80f9-3bc7a1fab9d7/scratchpad/bite1173d.py 2>&1 | tail -8
git diff HEAD --stat | tail -3
```
Expect: first `git diff HEAD --stat` empty; each run prints four `BITE FAILS AS EXPECTED ...` lines and `ALL BITES CAUGHT`; last `git diff HEAD --stat` empty. A `BITE SURVIVED` line: STOP. (Bite A drops the correlation, B makes the eligibility clause moot, C hard-codes three placeholders, D drops the owner check.)

8. Docs and lint. Set `Status: todo` to `Status: review` in this brief, write `docs/tasks/1173d-report.md` (section 9), then:
```bash
git add docs/tasks/1173d-queue-final-nits.md docs/tasks/1173d-report.md && git commit -m "1173d: report" 2>&1 | tail -3
python3 scripts/context_lint.py | tail -3
git diff 8d7ba6cd --stat | tail -8
```
Expect: `context lint: OK` (a WARN that status.md is behind is not this brief's work) and a stat listing the three App files and the two docs.

## 5. Do not touch

`go/`, `App/app/migrations/`, `docs/context/*` (the orchestrator records decisions and known issues), every file not in section 3. Hard rule 8: never push to `main`; leave the push and the PR to the owner.

## 6. Commands

The steps carry them: SQLite 1, 4, 5; PostgreSQL 6; bites 7; lint 8. No Go change, so no Go commands. Never the full suite.

## 7. Acceptance

- [ ] `git diff 8d7ba6cd --stat` lists `door_codes.py`, `test_door_code_unverified_card.py`, `test_issue_queue_starvation.py`, this brief and the report.
- [ ] SQLite: `28 passed` (small set), `542 passed, 2 skipped` (step 5), ruff `All checks passed!`.
- [ ] PostgreSQL: `28 passed`, `541 passed, 3 skipped`.
- [ ] `ALL BITES CAUGHT` on both databases; `git diff HEAD --stat` empty afterwards.
- [ ] `context lint: OK`.

## 8. Stop and ask

Stop, and write the report, if:

- an anchor is not found verbatim;
- a test fails twice (the one flake named in step 6 may be re-run once);
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside section 3 needs a change;
- section 5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1173d-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff 8d7ba6cd --stat`).
2. Each command, with the last 5 lines of its output.
3. Section 7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

- `App/app/door_codes.py`: the `ensure_row` refactor (must behave exactly as before), the f-string in `_issue_due` (only `?` characters are interpolated, never data), the new `continue` in `_revive_unissued_expired`.
- The T1 test: it must not call `reconcile()`.

## Owner steps

1. Open the PR from `task/1173d-queue-final-nits` when the checks are green, including test-postgres and test-postgres-full.
2. Merge with `scripts/merge-pr-on-green.sh`.
