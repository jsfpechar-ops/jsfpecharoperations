# 1122: PR #920 pins account for the demo seeder's writes

Status: todo
Depends on: none | Base commit: 86c807fd (head of branch task/sm-round1-combined, PR #920, main already merged in) | Branch: task/sm-round1-combined (the existing PR branch, no new branch)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 0. Open questions (read first)

1. Two demo.py writes are real UPDATE moves that `payment_request._TRANSITIONS` does not allow. `App/app/demo.py:605` (`db.update("payment_request", paid_id, {"status": "paid", ...})`) moves draft -> paid, and `App/app/demo.py:621` moves draft -> awaiting_payment. The table allows draft only to sent and cancelled. Per the owner's rule these are pinned in the test as named demo-only exceptions (`DEMO_ONLY_MOVES`); the production table is NOT widened. Whether the seeder should instead go through `set_status` is a separate decision for the owner.
2. The `door_code` and `site_booking` writes are direct INSERTs of a new row (door code in `pending`, the initial state; booking in `paid`, a non-initial state). They are not transitions, so no table entry is needed or added.
3. The `context` CI job on PR #920 also fails, for a separate reason: `docs/context/decisions.md` is over its token cap and has merge-conflict markers on main. This brief does not fix it.

## 1. Objective

PR #920 pin tests list every writer of three state columns. `App/app/demo.py` (the mock-only demo data seeder, merged in from main) writes `door_code`, `payment_request` and `site_booking` through the db helpers, so three pin tests fail (6594 passed, 3 failed in CI, jobs `test` and `test-postgres-full`). This brief pins demo.py as an explicit, counted writer in those three tests, without loosening any test.

## 2. Context

When demo.py runs: `demo.seed(owner_id)` runs when a host clicks "Load demo" (`App/app/routes/onboarding.py:28`); `_enrich_extras` is called from `seed`. It is mock-only (`config.UBYPORT_ENV == "mock"`) and `demo.clear` ("Clear demo") deletes the rows by apartment_id. It is not run by the scheduler.

What demo.py does (file `App/app/demo.py`, function `_enrich_extras`):

| Table | Write | Kind | State |
|---|---|---|---|
| payment_request | `payment_request.create(...)` x2 | new row via the model (counted in payment_request.py) | draft |
| payment_request | `db.update("payment_request", paid_id, {"status": "paid", ...})` | UPDATE | draft -> paid (not in table) |
| payment_request | `db.update("payment_request", open_id, {"status": "awaiting_payment", ...})` | UPDATE | draft -> awaiting_payment (not in table) |
| door_code | `db.insert("door_code", {... "state": "pending" ...})` | INSERT | NEW -> pending (initial) |
| site_booking | `db.insert("site_booking", {... "status": "paid" ...})` | INSERT | NEW -> paid |
| site_booking | `db.update("site_booking", booking_id, {"reservation_id": ..., "updated_at": ...})` | UPDATE, no status | none |

demo.py also writes `guest.submit_state` (already pinned in `test_sm_guest_submit_state.py`, `("App/app/demo.py", "kwarg", ...)`). It writes none of cleaning_code, reservation_claim, email_outbox, push_outbox, ad_click, guide_import or submission state. The other five pin files (guest submit_state, submission, cleaning_code, reservation_claim, queues) pass today with no change; checked by running all eight files.

Measured before: from `App/`, `python -m pytest tests/test_sm_*.py -q --tb=short` gave 3 failed, 97 passed (the three tests named in step 4).

## 3. Files

| Path | Action | What |
|---|---|---|
| App/tests/test_sm_door_code_state.py | edit | pin demo.py's one door_code insert |
| App/tests/test_sm_payment_request.py | edit | pin demo.py's two status updates as demo-only moves |
| App/tests/test_sm_site_booking.py | edit | pin demo.py's one insert and one non-status update |
| docs/tasks/1122-report.md | create | the report (section 9) |
| docs/tasks/1122-sm-pin-demo-writers.md | edit | set Status to review |

No other file may change. In particular no file under `App/app/`.

## 4. Steps

Run everything from the repo root unless a command says `cd App`.

1. Check out the existing PR branch (this is the one case where the executor pushes to an existing PR branch; no new PR):
   `git fetch origin task/sm-round1-combined && git checkout task/sm-round1-combined 2>&1 | tail -5`
   Then `git log -1 --oneline | tail -3`. Expected: starts with `86c807fd`. If the head is newer, run `git apply --check` in step 3 anyway; if it fails, STOP (section 8).
2. Confirm the fault: `cd App && .venv/bin/python -m pytest tests/test_sm_door_code_state.py tests/test_sm_payment_request.py tests/test_sm_site_booking.py -q --tb=line 2>&1 | tail -30`
   Expected: 3 failed (`test_no_dict_helper_writes_door_code`, `test_status_writing_statements_match_the_pins`, `test_no_other_code_touches_the_table_by_helper`).
3. Save the diff below as `/tmp/1122.diff` (copy the whole block between the lines `BEGIN DIFF` and `END DIFF`, without those two lines), then run from the repo root:
   `git apply --check /tmp/1122.diff && git apply /tmp/1122.diff && git diff --stat | tail -10`
   Expected: 3 files changed (test_sm_door_code_state.py, test_sm_payment_request.py, test_sm_site_booking.py), about 150 insertions, 4 deletions.
4. Run the pin tests: `cd App && .venv/bin/python -m pytest tests/test_sm_*.py -q --tb=short 2>&1 | tail -30`
   Expected: `104 passed`, 0 failed, 0 skipped. (If `tests/test_sm_go_parity.py` exists it is included by the glob.)
5. Context lint from the repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`. Expected: no new error from this change. A failure on `docs/context/decisions.md` (token cap, conflict markers) is the known separate fault: record it in the report, do not fix it.
6. Write `docs/tasks/1122-report.md` (section 9), set `Status: review` at the top of this file.
7. Commit and push to the same branch (no new PR, no new branch):
   `git add App/tests/test_sm_door_code_state.py App/tests/test_sm_payment_request.py App/tests/test_sm_site_booking.py docs/tasks/1122-report.md docs/tasks/1122-sm-pin-demo-writers.md && git commit -m "Pin demo seeder writes in the state-machine pin tests (1122)" && git push origin task/sm-round1-combined 2>&1 | tail -5`
   Add the attribution lines from the session reminder to the commit message. Never push to `main`.

What the diff pins, in words:
- door_code: `PINNED_DEMO_HELPER_WRITES = [("App/app/demo.py", "_enrich_extras", "insert", "pending")]`. The no-helper test now requires the hit list to be exactly demo.py and the AST-found demo writes to equal that list (any added or changed call fails). It also asserts the demo state is `door_codes.PENDING`.
- payment_request: `PINNED_WRITERS` gains `"App/app/demo.py": {"helper_updates": 2}`; `DEMO_ONLY_MOVES` names draft -> paid and draft -> awaiting_payment; two new tests check the AST-found demo updates equal those moves and that each move is really absent from `_TRANSITIONS` (so the list cannot go stale).
- site_booking: `PINNED_DEMO_HELPER_WRITES` pins insert `paid` and a status-less update in `_enrich_extras`; the "no other code" test expects `booking_site.py` plus `demo.py`; a new test pins demo.py by function, helper and state, counts its table-name mentions (2 writes + 1 clear-list entry), and rejects raw SQL in it.

BEGIN DIFF
diff --git a/App/tests/test_sm_door_code_state.py b/App/tests/test_sm_door_code_state.py
index b1c4769..d9ee639 100644
--- a/App/tests/test_sm_door_code_state.py
+++ b/App/tests/test_sm_door_code_state.py
@@ -210,6 +210,40 @@ def test_no_other_python_file_writes_door_code_state():
     assert others == []
 
 
+# The demo seeder (mock-only, removed by "Clear demo") is the one file outside
+# door_codes.py that writes door_code, through the db helpers. It INSERTs one row
+# directly in the initial state; it never UPDATEs one, so no transition is used.
+# (file, function, helper, state the new row is in)
+PINNED_DEMO_HELPER_WRITES = [
+    ("App/app/demo.py", "_enrich_extras", "insert", "pending"),
+]
+
+
+def _demo_helper_writes(path: Path, table: str) -> list:
+    """(file, function, helper, state literal or None) for db.insert/update calls on ``table``."""
+    tree = ast.parse(path.read_text(encoding="utf-8"))
+    out = []
+    for func in tree.body:
+        if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
+            continue
+        for node in ast.walk(func):
+            if not (
+                isinstance(node, ast.Call)
+                and isinstance(node.func, ast.Attribute)
+                and node.func.attr in {"update", "update_if", "update_in", "insert", "insert_in"}
+                and any(isinstance(a, ast.Constant) and a.value == table for a in node.args[:2])
+            ):
+                continue
+            state = None
+            for arg in node.args:
+                if isinstance(arg, ast.Dict):
+                    for key, value in zip(arg.keys, arg.values):
+                        if isinstance(key, ast.Constant) and key.value == "state" and isinstance(value, ast.Constant):
+                            state = value.value
+            out.append((str(path.relative_to(REPO)), func.name, node.func.attr, state))
+    return out
+
+
 def test_no_dict_helper_writes_door_code():
     helper = re.compile(
         r"\b(?:update|update_if|update_in|insert|insert_in)\(\s*(?:cur\s*,\s*)?['\"]door_code['\"]"
@@ -219,7 +253,13 @@ def test_no_dict_helper_writes_door_code():
         for path in sorted((APP / "app").rglob("*.py"))
         if helper.search(path.read_text(encoding="utf-8"))
     ]
-    assert hits == []
+    assert hits == sorted({f for f, *_ in PINNED_DEMO_HELPER_WRITES})
+    assert sorted(_demo_helper_writes(APP / "app" / "demo.py", "door_code")) == sorted(PINNED_DEMO_HELPER_WRITES)
+
+
+def test_demo_door_code_state_is_the_initial_state():
+    for _file, _func, helper, state in PINNED_DEMO_HELPER_WRITES:
+        assert helper == "insert" and state == door_codes.PENDING
 
 
 def test_no_go_file_writes_door_code():
diff --git a/App/tests/test_sm_payment_request.py b/App/tests/test_sm_payment_request.py
index 9949bb7..e585f53 100644
--- a/App/tests/test_sm_payment_request.py
+++ b/App/tests/test_sm_payment_request.py
@@ -93,8 +93,20 @@ PINNED_WRITERS = {
     "go/internal/payments/requests.go": {"status_updates": 1, "inserts": 1},
     "go/internal/payments/sweep.go": {"status_updates": 1},
     "go/internal/payments/webhook.go": {"status_updates": 1},
+    # demo seeder: two db.update("payment_request", ...) calls, see DEMO_ONLY_MOVES
+    "App/app/demo.py": {"helper_updates": 2},
 }
 
+# The demo seeder (mock-only, removed by "Clear demo") creates two requests with
+# payment_request.create (born draft) and then sets their status with a direct
+# db.update, skipping set_status. Neither move is in _TRANSITIONS, so each is a
+# named demo-only exception here; the production table is not widened.
+# (file, function, from-state, to-state)
+DEMO_ONLY_MOVES = [
+    ("App/app/demo.py", "_enrich_extras", "draft", "paid"),
+    ("App/app/demo.py", "_enrich_extras", "draft", "awaiting_payment"),
+]
+
 # Where the status-writing functions and SQL constants are used.
 PINNED_PY_CALLERS = {
     "App/app/routes/payments.py": ["set_status", "set_status"],
@@ -201,3 +213,43 @@ def test_go_callers_match_the_pins():
         if n:
             found[_rel(path)] = n
     assert found == PINNED_GO_SETSTATUS
+
+
+def _demo_status_updates():
+    """(file, function, status literal) for each db.update("payment_request", ...) in demo.py."""
+    import ast
+
+    path = APP_DIR / "app" / "demo.py"
+    out = []
+    for func in ast.parse(path.read_text(encoding="utf-8")).body:
+        if not isinstance(func, ast.FunctionDef):
+            continue
+        for node in ast.walk(func):
+            if not (
+                isinstance(node, ast.Call)
+                and isinstance(node.func, ast.Attribute)
+                and node.func.attr in {"update", "update_if", "update_in", "insert", "insert_in"}
+                and any(isinstance(a, ast.Constant) and a.value == "payment_request" for a in node.args[:2])
+            ):
+                continue
+            status = None
+            for arg in node.args:
+                if isinstance(arg, ast.Dict):
+                    for key, value in zip(arg.keys, arg.values):
+                        if isinstance(key, ast.Constant) and key.value == "status" and isinstance(value, ast.Constant):
+                            status = value.value
+            out.append((_rel(path), func.name, node.func.attr, status))
+    return out
+
+
+def test_demo_seeder_writes_match_the_pinned_demo_only_moves():
+    found = _demo_status_updates()
+    assert all(helper == "update" for _f, _fn, helper, _s in found), found
+    assert sorted((f, fn, s) for f, fn, _h, s in found) == sorted((f, fn, to) for f, fn, _frm, to in DEMO_ONLY_MOVES)
+    # rows are born draft (payment_request.create), so draft is the from-state
+    assert all(frm == "draft" for _f, _fn, frm, _to in DEMO_ONLY_MOVES)
+
+
+def test_demo_only_moves_are_exactly_the_ones_the_table_lacks():
+    for _f, _fn, frm, to in DEMO_ONLY_MOVES:
+        assert to not in TABLE[frm], f"{frm} -> {to} is now in the table: drop it from DEMO_ONLY_MOVES"
diff --git a/App/tests/test_sm_site_booking.py b/App/tests/test_sm_site_booking.py
index d18edce..b702c9f 100644
--- a/App/tests/test_sm_site_booking.py
+++ b/App/tests/test_sm_site_booking.py
@@ -6,6 +6,7 @@ edited by this test; the table lists only what the code does today.
 """
 from __future__ import annotations
 
+import ast
 import re
 from pathlib import Path
 
@@ -47,6 +48,16 @@ UNUSED_TABLE_MOVES = {("paid", "refunded"), ("paid", "clash_refunded")}
 PINNED_INSERT_FILES = ["booking_site.py"]
 PINNED_INSERT_STATES = {"pending", "requested"}
 
+# 5. The demo seeder (mock-only, removed by "Clear demo") inserts one booking
+#    directly as 'paid' (a new row, not a move) and later sets reservation_id
+#    on it with no status change. Pinned by function, helper and state.
+#    (file, function, helper, status written or None)
+PINNED_DEMO_HELPER_WRITES = [
+    ("demo.py", "_enrich_extras", "insert", "paid"),
+    ("demo.py", "_enrich_extras", "update", None),
+]
+PINNED_DEMO_NAME_MENTIONS = 1  # the "Clear demo" table list, a DELETE by apartment_id
+
 
 def _py_files():
     return sorted(p for p in APP_PKG.rglob("*.py"))
@@ -129,6 +140,32 @@ def test_set_status_callers_are_pinned():
     )
 
 
+def _demo_helper_writes(table: str = "site_booking"):
+    """(file, function, helper, status literal or None) for db.insert/update calls on the table in demo.py."""
+    path = APP_PKG / "demo.py"
+    tree = ast.parse(path.read_text(encoding="utf-8"))
+    out = []
+    for func in tree.body:
+        if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
+            continue
+        for node in ast.walk(func):
+            if not (
+                isinstance(node, ast.Call)
+                and isinstance(node.func, ast.Attribute)
+                and node.func.attr in {"update", "update_if", "update_in", "insert", "insert_in"}
+                and any(isinstance(a, ast.Constant) and a.value == table for a in node.args[:2])
+            ):
+                continue
+            status = None
+            for arg in node.args:
+                if isinstance(arg, ast.Dict):
+                    for key, value in zip(arg.keys, arg.values):
+                        if isinstance(key, ast.Constant) and key.value == "status" and isinstance(value, ast.Constant):
+                            status = value.value
+            out.append((path.name, func.name, node.func.attr, status))
+    return out
+
+
 def test_no_other_code_touches_the_table_by_helper():
     """db.insert/update/update_in helpers take the table name as a string."""
     found = []
@@ -136,7 +173,7 @@ def test_no_other_code_touches_the_table_by_helper():
         text = path.read_text(encoding="utf-8")
         if re.search(r"""["']site_booking["']""", text):
             found.append(path.name)
-    assert sorted(found) == sorted(PINNED_INSERT_FILES), found
+    assert sorted(found) == sorted(PINNED_INSERT_FILES + ["demo.py"]), found
     source = (APP_PKG / "booking_site.py").read_text(encoding="utf-8")
     assert len(re.findall(r"""db\.\w+\(\s*["']site_booking["']""", source)) == 1
     assert 'db.insert("site_booking"' in source
@@ -144,6 +181,19 @@ def test_no_other_code_touches_the_table_by_helper():
     assert PINNED_INSERT_STATES == {"pending", "requested"}
 
 
+def test_demo_seeder_site_booking_writes_are_pinned():
+    """demo.py is allowed exactly the pinned writes, by function, helper and state."""
+    assert sorted(_demo_helper_writes()) == sorted(PINNED_DEMO_HELPER_WRITES)
+    text = (APP_PKG / "demo.py").read_text(encoding="utf-8")
+    mentions = len(re.findall(r"""["']site_booking["']""", text))
+    assert mentions == len(PINNED_DEMO_HELPER_WRITES) + PINNED_DEMO_NAME_MENTIONS
+    # a seeded status is a created row, so it must still be a real status
+    for _f, _fn, helper, status in PINNED_DEMO_HELPER_WRITES:
+        if helper == "insert":
+            assert status in booking_site.STATUSES
+    assert not re.search(r"UPDATE\s+site_booking|INSERT\s+INTO\s+site_booking", text, re.I)
+
+
 def test_go_and_migrations_do_not_write_site_booking_status():
     go_dir = REPO / "go"
     for path in sorted(go_dir.rglob("*.go")):
END DIFF

## 5. Do not touch

`App/app/` (production code and transition tables), `.github/`, `go/`, docs/context/decisions.md. Hard rules 3 and 8: no secrets; never push to `main`. No test is weakened, skipped, or made to ignore unknown files: demo.py is allowed only as pinned by function, helper and count.

## 6. Commands

- Fault: step 2, expected 3 failed.
- After: `cd App && .venv/bin/python -m pytest tests/test_sm_*.py -q --tb=short 2>&1 | tail -30`, expected `104 passed`.
- Lint: `python3 scripts/context_lint.py 2>&1 | tail -30`.

## 7. Acceptance

- [ ] All `tests/test_sm_*.py` pass (104 passed, 0 skipped).
- [ ] Only the three test files plus the two docs/tasks files changed (`git diff --stat HEAD~1 | tail -10`).
- [ ] No file under App/app changed.
- [ ] Pushed to task/sm-round1-combined; no new PR.

## 8. Stop and ask

Stop and write the report as `blocked` if: `git apply --check` fails; the step 4 count differs or any test fails twice; a file outside section 3 needs a change; you reach 25 tool calls; you need to widen a production transition table (never do this; list it in the report instead).

## 9. Report

Write `docs/tasks/1122-report.md` (600 tokens at most): files changed, each command with its last 5 lines, section 7 ticked, deviations, and the open questions from section 0 (the two draft moves in demo.py, the separate `context` job failure).
