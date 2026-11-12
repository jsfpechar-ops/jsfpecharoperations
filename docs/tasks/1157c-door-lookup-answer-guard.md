# 1157c: a lock answer without a list is unknown, and a full page always reads on

Status: todo
Depends on: 1157b (merged) | Base commit: HEAD of branch claude/zealous-maxwell-a7ub54 | Branch: task/1157c-door-lookup-answer-guard
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

`ttlock.code_is_listed` (1157) calls a door code gone after one call when the lock answers 200 without a `list` array, and trusts `pages` even when the page is full. Both can mark a live PIN `revoked` (1155b) or orphan it (1155). Fix: no `list` array means unknown (`None`); a full page of 20 always reads on; only a short or empty page ends the list.

## 2. Context

Rules: no dependency, no migration, no new outbound endpoint (same `POST /v3/lock/listKeyboardPwd`, still 1 to 5 calls; a list that ends exactly on a full page now costs one more call, page N+1 comes back empty). Nothing in `door_codes.py` changes: `_lock_code_state` already maps `None` to `PIN_UNKNOWN`, and `_already_gone` only accepts `PIN_GONE`.

Today, in `App/app/ttlock.py` `code_is_listed` (verbatim):
```python
        items = answer.get("list") or []
        if any(str(raw.get("keyboardPwdId")) == str(code_id) for raw in items):
            return True
        try:
            last_page = int(answer["pages"])
        except (KeyError, TypeError, ValueError):
            last_page = None
        if last_page is not None and page >= last_page:
            return False
        if last_page is None and len(items) < LIST_PAGE_SIZE:
            return False
    return None
```
Faults: (1) `{}`, `{"pages": 1}` and `{"list": None, "pages": 0}` give `[]` and then `False` after one call; a non-list `list` (`"oops"`, `{"a": 1}`) gives `AttributeError` or wrong matches. (2) `pages` is trusted even when 20 codes came back, so `pages: 1` with a full page 1 returns `False` while the code sits on page 2.

New rule: `list` not an array -> `None`. Id found -> `True`. Page shorter than `LIST_PAGE_SIZE` (an empty array included) -> `False`. Otherwise read the next page; after `LIST_MAX_PAGES` -> `None`. `pages` is no longer read. A valid empty array with a junk `pages` (`{"list": [], "pages": "x"}`) is a real end of list, so it stays `False` (the test pins that).

The match key stays the id (1157 decision): the new test adds a code with the row's name but another `keyboardPwdId` and expects gone, so a match on name would fail it.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/ttlock.py | edit | `code_is_listed`: list guard, full page reads on, docstring |
| App/tests/test_door_code_lookup_pages.py | edit | append 4 tests (8 cases with the parametrized one) |
| docs/tasks/1157c-report.md | create | report (§9) |

No other file may change.

## 4. Steps

**Step 1. Branch.** Run `git branch --show-current | tail -30`; expected `claude/zealous-maxwell-a7ub54`. Confirm 1157b is in: `grep -c "def code_is_listed" App/app/ttlock.py | tail -30` -> `1` and `grep -c "last_page" App/app/ttlock.py | tail -30` -> `4` (else STOP). Then `git switch -c task/1157c-door-lookup-answer-guard | tail -30`; expected `Switched to a new branch`.

**Step 2. Apply the diff.** From the repo root write the diff below to a file and apply it (it fails, changing nothing, if an anchor is missing; then STOP, §8):
```bash
cat > /tmp/1157c.diff <<'EOF'
diff --git a/App/app/ttlock.py b/App/app/ttlock.py
index 03d115f4..71a69e14 100644
--- a/App/app/ttlock.py
+++ b/App/app/ttlock.py
@@ -573,9 +573,11 @@ def code_is_listed(account_id: int, lock_id: str, name: str, code_id: str) -> Op
     """Is the lock code with this id on the lock? True, False, or None when it cannot be told.
 
     ``searchStr`` is a fuzzy match (UH-7 also lists UH-70 and UH-700), so the answer is read
-    page by page, at most LIST_MAX_PAGES calls. False only when the last page was read and
-    the id was not on any page. None when the page limit ran out first. The id decides,
-    not the name or the window. TTLock errors are raised as they are.
+    page by page, at most LIST_MAX_PAGES calls. A full page (LIST_PAGE_SIZE codes) is always
+    read on past, whatever ``pages`` says. False only when a short or empty page ended the
+    list and the id was on no page. None when an answer has no ``list`` array, or when the
+    page limit ran out first. The id decides, not the name or the window. TTLock errors are
+    raised as they are.
     """
     for page in range(1, LIST_MAX_PAGES + 1):
         answer = _call(
@@ -590,16 +592,12 @@ def code_is_listed(account_id: int, lock_id: str, name: str, code_id: str) -> Op
             },
             NORMAL,
         )
-        items = answer.get("list") or []
+        items = answer.get("list")
+        if not isinstance(items, list):
+            return None
         if any(str(raw.get("keyboardPwdId")) == str(code_id) for raw in items):
             return True
-        try:
-            last_page = int(answer["pages"])
-        except (KeyError, TypeError, ValueError):
-            last_page = None
-        if last_page is not None and page >= last_page:
-            return False
-        if last_page is None and len(items) < LIST_PAGE_SIZE:
+        if len(items) < LIST_PAGE_SIZE:
             return False
     return None
 
diff --git a/App/tests/test_door_code_lookup_pages.py b/App/tests/test_door_code_lookup_pages.py
index ce92a76c..bcca5e3d 100644
--- a/App/tests/test_door_code_lookup_pages.py
+++ b/App/tests/test_door_code_lookup_pages.py
@@ -233,3 +233,55 @@ def test_a_stale_error_on_an_issued_row_does_not_hide_a_lost_pin(world):
     after = _row(row)
     assert after["state"] == door_codes.ISSUED and after["provider_code_id"] != CODE
     assert lock.made == 1
+
+
+def test_a_code_with_the_same_name_but_another_id_is_gone(world):
+    lock, stay, row, sent = world
+    lock.add("7777", f"UH-{row}")  # same name as the row's code, not its id
+    assert _fresh_row(row) == door_codes.PIN_GONE
+    lock.add(CODE, f"UH-{row}")
+    assert _fresh_row(row) == door_codes.PIN_PRESENT
+
+
+NO_LIST = [{}, {"list": None, "pages": 0}, {"pages": 1}, {"list": "oops", "pages": 1}, {"list": {"a": 1}}]
+
+
+@pytest.mark.parametrize("answer", NO_LIST)
+def test_an_answer_without_a_list_is_unknown_and_never_revokes(world, monkeypatch, answer):
+    lock, stay, row, sent = world
+    real_call = lock.call
+
+    def broken(account_id, path, data, priority):
+        if path == "/v3/lock/listKeyboardPwd":
+            lock.list_calls += 1
+            return dict(answer)
+        if path == "/v3/keyboardPwd/delete":
+            raise ttlock.TTLockError("odd", code=UNMAPPED, kind="transient")
+        return real_call(account_id, path, data, priority)
+
+    monkeypatch.setattr(ttlock, "_call", broken)
+    assert ttlock.code_is_listed(1, "1", f"UH-{row}", CODE) is None
+    assert _fresh_row(row) == door_codes.PIN_UNKNOWN
+    door_codes._revoke_one(row)
+    assert _state(row) == door_codes.REVOKE_PENDING and _audits("door_code_revoked") == 0
+
+
+def test_an_empty_list_is_the_end_even_when_pages_is_not_a_number(world, monkeypatch):
+    lock, stay, row, sent = world
+    monkeypatch.setattr(ttlock, "_call", lambda *a, **k: {"list": [], "pages": "x"})
+    assert ttlock.code_is_listed(1, "1", f"UH-{row}", CODE) is False
+
+
+def test_a_full_page_is_read_past_even_when_pages_says_one(world, monkeypatch):
+    lock, stay, row, sent = world
+    _busy(lock, row)
+    real = lock.call
+
+    def pages_one(account_id, path, data, priority):
+        answer = real(account_id, path, data, priority)
+        answer["pages"] = 1
+        return answer
+
+    monkeypatch.setattr(ttlock, "_call", pages_one)
+    assert _fresh_row(row) == door_codes.PIN_PRESENT
+    assert lock.list_calls == 2
EOF
git apply --check /tmp/1157c.diff && git apply /tmp/1157c.diff && git diff --stat | tail -30
```
Expected: `2 files changed, 61 insertions(+), 11 deletions(-)`.

**Step 3. Tests.** From `App/`: `.venv/bin/python -m pytest tests/test_door_code_lookup_pages.py tests/test_door_code_ambiguous_delete.py tests/test_door_code_recancel.py tests/test_door_code_lost_pin.py tests/test_door_code_cancel_guard.py -q --tb=short 2>&1 | tail -30` -> `49 passed`.

**Step 4. Commit.** `git add App/app/ttlock.py App/tests/test_door_code_lookup_pages.py && git commit -m "1157c: a lock answer without a list is unknown; a full page always reads on" | tail -30`.

**Step 5. Revert-bite, four runs.** Each run, from the repo root: apply the `sed`, run `T`, expect the named result, then `git checkout App/app | tail -30`. `T` is `cd App && .venv/bin/python -m pytest tests/test_door_code_lookup_pages.py tests/test_door_code_ambiguous_delete.py -q --tb=no -rf 2>&1 | tail -30`. After each `sed`, `git diff --stat | tail -30` must show `1 file changed` (the bite is 1 to 10 lines of ttlock.py, never more).
- (a) Guard off, a missing list is read as a list: `sed -i 's/not isinstance(items, list)/False/' App/app/ttlock.py` then `T`: `5 failed, 19 passed` (the five `answer_without_a_list_is_unknown_and_never_revokes` cases).
- (b) Missing list counts as gone: `sed -i '/isinstance(items, list)/{n;s/return None/return False/}' App/app/ttlock.py` then `T`: `5 failed, 19 passed` (the same five).
- (c) `pages` trusted again: `sed -i 's/^        if len(items) < LIST_PAGE_SIZE:$/        if len(items) < LIST_PAGE_SIZE or page >= int(answer.get("pages") or 1):/' App/app/ttlock.py` then `T`: `2 failed, 22 passed` (`full_page_is_read_past_even_when_pages_says_one`, `answer_without_a_pages_field_reads_on_while_the_page_is_full`).
- (d) Match on name, not id: `sed -i 's/str(raw.get("keyboardPwdId")) == str(code_id)/raw.get("keyboardPwdName") == name/' App/app/ttlock.py` then `T`: `1 failed, 23 passed` (`code_with_the_same_name_but_another_id_is_gone`).
If a run does not fail as stated, STOP (§8). Finally `git status --short | tail -30` -> empty.

**Step 6. Door-codes row (test-map) and lint.** From `App/`: `.venv/bin/python -m pytest tests/test_door_code*.py tests/test_ttlock*.py tests/test_smart_locks_page.py tests/test_sm_door_code_state.py tests/test_sm_go_parity.py -q --tb=short -rs 2>&1 | tail -30` -> no failures; only the `playwright` skips. Then `.venv/bin/ruff check app tests tools --select E9,F63,F7,F82,F401,F841 2>&1 | tail -30` -> `All checks passed!`.

**Step 7. Postgres.** From `App/`: `UBYHOST_DATABASE_URL=postgresql://uby:uby@localhost:5432/ubytest .venv/bin/python -m pytest tests/test_door_code_lookup_pages.py tests/test_door_code_ambiguous_delete.py tests/test_door_code_recancel.py -q --tb=short 2>&1 | tail -30` -> all pass (or report `not run: no Postgres`).

**Step 8. Report.** Write `docs/tasks/1157c-report.md` (§9), set this file's line 3 to `Status: review`, then `python3 scripts/context_lint.py | tail -3` from the repo root.

## 5. Do not touch

`door_codes.py`, `ttlock.find_code_by_name`, `cleaning_codes.py`, `ttlock.ERROR_KINDS`, `docs/context/*`, migrations, `go/`. Hard rules: 3, 4, 5.

## 6. Commands

All Python from `App/`, each ending `2>&1 | tail -30`: Steps 3 to 7 give the exact command and result. Never the full suite.

## 7. Acceptance

- [ ] Step 3 shows `49 passed` (the 1157 file now has 17 tests).
- [ ] The four revert-bite runs fail as stated and `git status --short` is empty afterwards.
- [ ] The door-codes row passes with only the `playwright` skips; ruff passes; Postgres run passes or is reported as not run.
- [ ] The report says the outbound-request reason is unchanged except that an exact-multiple-of-20 list costs one extra call.

## 8. Stop and ask

Stop, and write the report, if:

- an anchor is not found (`git apply --check` fails or Step 1 counts differ);
- a test fails twice;
- a revert-bite run does not fail as stated;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency, a migration or a new state transition seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1157c-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

`App/app/ttlock.py` `code_is_listed` (False only after a short or empty page of a real array; None otherwise), the four new tests.

## Owner steps

1. Open the pull request for `task/1157c-door-lookup-answer-guard` as a draft.
2. When CI is green and the review is done, run `scripts/merge-pr-on-green.sh <PR number>` (rule 8).
