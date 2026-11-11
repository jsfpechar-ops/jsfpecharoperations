# 1106: Declare and pin the submission.state machine

Status: todo
Depends on: none | Base commit: 5e034303 | Branch: task/1106-sm-submission-state
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

**HIGH RISK: police filing.** The `submission` row is the record of every UbyPort filing attempt. This brief changes **no runtime behaviour**: it adds one dict that nothing reads, and one test file that only reads source files as text.

## 1. Objective

Add `SUBMISSION_TRANSITIONS` to `App/app/reporting.py`, listing exactly the moves of `submission.state` that the Python and Go code make today, and add `App/tests/test_sm_submission_state.py`, which fails when a write of `submission.state` is added, removed or changed anywhere in `App/app`, `App/scripts` or `go/`. Today nobody can read the legal moves of the filing record in one place, and a new write could add an illegal move without any test failing.

## 2. Context

Plan: [explicit state machines](../plans/explicit-state-machines.md), round 1. Its rules, pasted:

1. **Derive, never design.** The table lists exactly the moves the code makes today. If the code and a doc disagree, the brief does not pick: it lists the disagreement under "Open questions" and pins what the code does.
2. The table lives in the owning module, next to the state constants. (Brief 1105 adds a dict named `TRANSITIONS` for `guest.submit_state` near the top of `reporting.py`; this brief's dict is named `SUBMISSION_TRANSITIONS` and sits far below it, so they do not collide.)
3. One new test file per machine. It reads the source of every writer (Python and Go) as text, finds every statement that writes the column, and compares them with a pinned list. It fails when a write is added, removed or changed, and when a pinned move is not in the table.
4. **Writers are not edited.** Go files are read by the test, never changed.
5. No migration, no new dependency, no template or copy change.

Anchor for step 2, in `App/app/reporting.py` (one line, verbatim):

```python
TERMINAL_SUBMISSION_STATES = ("ok", "ok_duplicate", "partial", "error", "transport_error", "outcome_unknown")
```

The line right after it is empty, and the line after that is:

```python
# The envelope is the only thing in the row that carries guest data, and the
```

The writes the test pins (found by the orchestrator's brief writer; you do not need to open these files):

| File | Function | SQL guard on state | Writes | Code path holds |
|---|---|---|---|---|
| `App/app/reporting.py` | `submit_batch` | insert | `running` | (new row) |
| `App/app/reporting.py` | `submit_batch` | none | `outcome_unknown` | `running` |
| `App/app/reporting.py` | `submit_batch` | none | `transport_error` | `running` |
| `App/app/reporting.py` | `submit_batch` | none | `state` from `plan_outcome`: ok, ok_duplicate, partial, error | `running` |
| `App/app/reporting.py` | `recover_stale_submissions` | none | `outcome_unknown` | `running` |
| `go/internal/ubyport/store.go` | `InsertSubmission` | insert | `running` | (new row) |
| `go/internal/ubyport/store.go` | `RecordOutcomeUnknown` | none | `outcome_unknown` | `running` |
| `go/internal/ubyport/store.go` | `RecordTransportError` | none | `transport_error` | `running` |
| `go/internal/ubyport/store.go` | `RecordOutcome` | none | `$1` = `plan.State`: ok, ok_duplicate, partial, error | `running` |
| `go/internal/ubyport/recover.go` | `RecoverStaleSubmissions` | none | `outcome_unknown` | `running` |

Not state writes (the test must not report them): `UPDATE submission SET retried_at ...` (`reporting.py` near lines 2053 and 2171, `sweep.go` near lines 597 and 699) and the envelope purge `UPDATE submission SET request_xml = NULL ...` (`reporting.py` near line 2745).

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/reporting.py` | edit | add `SUBMISSION_TRANSITIONS` after the `TERMINAL_SUBMISSION_STATES` line (step 2) |
| `App/tests/test_sm_submission_state.py` | create | the full file in step 3 |
| `docs/tasks/1106-report.md` | create | the report (step 6) |
| `docs/tasks/1106-sm-submission-state.md` | edit | `Status:` line only (step 6) |

No other file may change.

## 4. Steps

### Step 1: branch

From the repo root:

```bash
git checkout -b task/1106-sm-submission-state 2>&1 | tail -30
```

Expected: `Switched to a new branch 'task/1106-sm-submission-state'`.

### Step 2: add the table to App/app/reporting.py

Check the anchor first, from the repo root:

```bash
grep -nF 'TERMINAL_SUBMISSION_STATES = ("ok", "ok_duplicate", "partial", "error", "transport_error", "outcome_unknown")' App/app/reporting.py | head -50
```

Expected: exactly one line (about line 2696). Not found, or more than one: STOP (§8).

Apply this diff. It only adds lines directly after the anchor line; the existing empty line and the `# The envelope ...` comment stay below the new block.

```diff
 TERMINAL_SUBMISSION_STATES = ("ok", "ok_duplicate", "partial", "error", "transport_error", "outcome_unknown")
+
+# Every move of submission.state the code makes today (brief 1106). Declared
+# only: nothing reads this at runtime, and tests/test_sm_submission_state.py
+# fails when a writer changes. None is the INSERT that creates the row. Every
+# later write matches the row by id alone, with no state check in SQL; the
+# source state is the one the writer's code path holds.
+SUBMISSION_TRANSITIONS = {
+    # submit_batch; go store.go InsertSubmission
+    None: ("running",),
+    "running": (
+        # submit_batch (state from plan_outcome); go store.go RecordOutcome (plan.State)
+        "ok",
+        "ok_duplicate",
+        "partial",
+        "error",
+        # submit_batch; go store.go RecordTransportError
+        "transport_error",
+        # submit_batch, recover_stale_submissions; go store.go RecordOutcomeUnknown,
+        # go recover.go RecoverStaleSubmissions
+        "outcome_unknown",
+    ),
+}
 
 # The envelope is the only thing in the row that carries guest data, and the
```

Command, from `App/`:

```bash
grep -c 'SUBMISSION_TRANSITIONS' app/reporting.py | tail -30 && .venv/bin/python -m py_compile app/reporting.py && echo compiled 2>&1 | tail -30
```

Expected: `1`, then `compiled`. Commit: `git commit -am "1106 step 2"`.

### Step 3: create App/tests/test_sm_submission_state.py

Create the file with exactly this content:

```python
"""submission.state: every write is pinned (brief 1106).

The submission row is the police-filing attempt record. This test only reads
source files as text. It fails when a write of submission.state is added,
removed or changed in Python (App/app, App/scripts) or Go (go/), and when
reporting.SUBMISSION_TRANSITIONS does not match those writes. To change a write
on purpose, update PINNED_WRITES below and SUBMISSION_TRANSITIONS in the same
PR, and give the reason in the PR.
"""
import ast
import re
from collections import Counter
from pathlib import Path

from app import reporting

APP_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = APP_DIR.parent

ANY = "*"  # the write matches the row by id only: no state check in its WHERE
INSERT = "insert"  # the write creates the row
OUTCOME_STATES = {"ok", "ok_duplicate", "partial", "error"}
# Targets that are a variable, resolved in test_outcome_targets_resolve.
OUTCOME_TARGETS = ("<state>", "<param>")

# (file, function, state guard in the SQL, state written, state the code path holds)
PINNED_WRITES = [
    ("App/app/reporting.py", "submit_batch", INSERT, "running", None),
    ("App/app/reporting.py", "submit_batch", ANY, "outcome_unknown", "running"),
    ("App/app/reporting.py", "submit_batch", ANY, "transport_error", "running"),
    ("App/app/reporting.py", "submit_batch", ANY, "<state>", "running"),
    ("App/app/reporting.py", "recover_stale_submissions", ANY, "outcome_unknown", "running"),
    ("go/internal/ubyport/store.go", "InsertSubmission", INSERT, "running", None),
    ("go/internal/ubyport/store.go", "RecordOutcomeUnknown", ANY, "outcome_unknown", "running"),
    ("go/internal/ubyport/store.go", "RecordTransportError", ANY, "transport_error", "running"),
    ("go/internal/ubyport/store.go", "RecordOutcome", ANY, "<param>", "running"),
    ("go/internal/ubyport/recover.go", "RecoverStaleSubmissions", ANY, "outcome_unknown", "running"),
]

# States that may have no move out without being in TERMINAL_SUBMISSION_STATES.
KNOWN_DEAD_END_EXCEPTIONS = ()

DB_HELPERS = {"insert", "insert_in", "update", "update_in", "update_if"}
STATE_SET = re.compile(r"(?<!\w)state\s*=\s*(?:'(\w+)'|\$\d+|\?)")
STATE_WHERE = re.compile(
    r"(?<!\w)state\s*(=|!=|<>|\bIN\b|\bNOT IN\b)\s*(\([^)]*\)|'\w+'|\$\d+|\?)", re.I
)
GO_FUNC = re.compile(r"^func\s+(?:\([^)]*\)\s*)?(\w+)", re.M)
GO_STRING = re.compile(r"`([^`]*)`|\"((?:[^\"\\\n]|\\.)*)\"")


def _sql_write(sql):
    """(guard, state written) when the SQL writes submission.state, else None."""
    s = " ".join(sql.split())
    m = re.search(r"\bINSERT INTO submission\s*\(([^)]*)\)\s*VALUES\s*\(([^)]*)\)", s, re.I)
    if m:
        cols = [c.strip() for c in m.group(1).split(",")]
        if "state" not in cols:
            return None
        value = [v.strip() for v in m.group(2).split(",")][cols.index("state")]
        return (INSERT, value.strip("'") if value.startswith("'") else "<param>")
    m = re.search(r"\bUPDATE submission\s+SET\s+(.*?)(?:\s+WHERE\s+(.*))?$", s, re.I)
    if not m:
        return None
    target = STATE_SET.search(m.group(1))
    if not target:
        return None
    to = target.group(1) or "<param>"
    where = m.group(2) or ""
    conds = STATE_WHERE.findall(where)
    if not conds:
        return (ANY, to)
    if all(op == "=" and val.startswith("'") for op, val in conds):
        return (tuple(sorted(val.strip("'") for _op, val in conds)), to)
    return ("<guard: " + where + ">", to)


def _walk(node, func):
    for child in ast.iter_child_nodes(node):
        name = child.name if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) else func
        yield child, name, node
        yield from _walk(child, name)


def _value_name(value):
    if isinstance(value, ast.Constant) and isinstance(value.value, str):
        return value.value
    if isinstance(value, ast.Name):
        return "<" + value.id + ">"
    return "<expr>"


def _dict_state(node):
    if isinstance(node, ast.Dict):
        for key, value in zip(node.keys, node.values):
            if isinstance(key, ast.Constant) and key.value == "state":
                return value
    return None


def _python_writes():
    out = []
    files = sorted((APP_DIR / "app").rglob("*.py")) + sorted((APP_DIR / "scripts").glob("*.py"))
    for path in files:
        text = path.read_text(encoding="utf-8")
        if "submission" not in text:
            continue
        rel = path.relative_to(REPO_DIR).as_posix()
        for node, func, parent in _walk(ast.parse(text), "<module>"):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in DB_HELPERS
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "db"
            ):
                args = list(node.args) + [k.value for k in node.keywords]
                if not any(isinstance(a, ast.Constant) and a.value == "submission" for a in args):
                    continue
                dicts = [a for a in args if isinstance(a, ast.Dict)]
                if not dicts or _dict_state(dicts[0]) is None:
                    continue
                to = _value_name(_dict_state(dicts[0]))
                if node.func.attr in ("insert", "insert_in"):
                    guard = INSERT
                elif node.func.attr == "update_if":
                    expected = _dict_state(dicts[1]) if len(dicts) > 1 else None
                    guard = ANY if expected is None else (_value_name(expected),)
                else:
                    guard = ANY
                out.append((rel, func, guard, to))
            sql = None
            if isinstance(node, ast.JoinedStr):
                sql = "".join(
                    v.value if isinstance(v, ast.Constant) else "{}" for v in node.values
                )
            elif (
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and not isinstance(parent, ast.JoinedStr)
            ):
                sql = node.value
            if sql and "submission" in sql:
                write = _sql_write(sql)
                if write:
                    out.append((rel, func) + write)
    return out


def _go_writes():
    out = []
    for path in sorted((REPO_DIR / "go").rglob("*.go")):
        if path.name.endswith("_test.go"):
            continue
        text = path.read_text(encoding="utf-8")
        if "submission" not in text:
            continue
        rel = path.relative_to(REPO_DIR).as_posix()
        funcs = [(m.start(), m.group(1)) for m in GO_FUNC.finditer(text)]
        for m in GO_STRING.finditer(text):
            sql = m.group(1) if m.group(1) is not None else m.group(2)
            write = _sql_write(sql)
            if write:
                before = [name for start, name in funcs if start < m.start()]
                out.append((rel, before[-1] if before else "<file>") + write)
    return out


def _targets(to):
    return OUTCOME_STATES if to in OUTCOME_TARGETS else {to}


def _sorted(items):
    return sorted(items, key=repr)


def test_parser_reads_guards_and_targets():
    assert _sql_write("UPDATE submission SET state = 'error' WHERE id = ? AND state = 'running'") == (
        ("running",), "error")
    assert _sql_write("UPDATE submission SET state = $1, x = $2 WHERE id = $3") == (ANY, "<param>")
    assert _sql_write("UPDATE submission SET retried_at = ? WHERE id = ? AND state = ?") is None
    assert _sql_write("UPDATE guest SET submit_state = 'sent' WHERE id = ?") is None
    assert _sql_write("INSERT INTO submission (apartment_id, state) VALUES ($1, 'running')") == (
        INSERT, "running")
    assert _sql_write("INSERT INTO submission_claim (guest_id) VALUES (?)") is None
    assert _sql_write(
        "UPDATE submission SET state = ? WHERE id = ? AND state IN ('running', 'error')"
    )[0].startswith("<guard")


def test_every_write_is_pinned():
    found = Counter(_python_writes() + _go_writes())
    pinned = Counter((f, fn, g, to) for f, fn, g, to, _src in PINNED_WRITES)
    assert found == pinned, (
        "submission.state writes changed. Not pinned: "
        f"{_sorted((found - pinned).elements())}. Pinned but gone: "
        f"{_sorted((pinned - found).elements())}. Update PINNED_WRITES and "
        "reporting.SUBMISSION_TRANSITIONS together (brief 1106)."
    )


def test_outcome_targets_resolve():
    tree = ast.parse((APP_DIR / "app" / "reporting.py").read_text(encoding="utf-8"))
    funcs = {n.name: n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    planned = set()
    for node in ast.walk(funcs["plan_outcome"]):
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == "state"
        ):
            value = node.value
            parts = [value.body, value.orelse] if isinstance(value, ast.IfExp) else [value]
            for part in parts:
                assert isinstance(part, ast.Constant), ast.dump(node)
                planned.add(part.value)
    assert planned == OUTCOME_STATES
    sources = []
    for node in ast.walk(funcs["submit_batch"]):
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == "state"
        ):
            sources.append(ast.unparse(node.value))
    assert sources == ["plan['state']"]

    go_dir = REPO_DIR / "go" / "internal" / "ubyport"
    go_text = "".join(
        p.read_text(encoding="utf-8")
        for p in sorted(go_dir.glob("*.go"))
        if not p.name.endswith("_test.go")
    )
    literals = re.findall(r"\bplan\.State\s*=\s*\"(\w+)\"", go_text)
    assert len(literals) == len(re.findall(r"\bplan\.State\s*=[^=]", go_text))
    assert set(literals) == OUTCOME_STATES
    store = (go_dir / "store.go").read_text(encoding="utf-8")
    assert "plan.State, now, res.HeaderErrors" in store


def test_every_pinned_move_is_in_the_table():
    table = reporting.SUBMISSION_TRANSITIONS
    missing = [
        (f, fn, src, t)
        for f, fn, _g, to, src in PINNED_WRITES
        for t in sorted(_targets(to))
        if t not in table.get(src, ())
    ]
    assert not missing, f"pinned moves missing from SUBMISSION_TRANSITIONS: {missing}"


def test_table_lists_only_moves_the_code_makes():
    table = reporting.SUBMISSION_TRANSITIONS
    made = {(src, t) for _f, _fn, _g, to, src in PINNED_WRITES for t in _targets(to)}
    listed = {(src, t) for src, tos in table.items() for t in tos}
    assert listed == made, f"listed only: {_sorted(listed - made)}; made only: {_sorted(made - listed)}"


def test_states_without_a_move_out_are_terminal():
    table = reporting.SUBMISSION_TRANSITIONS
    terminal = set(reporting.TERMINAL_SUBMISSION_STATES)
    states = {t for tos in table.values() for t in tos} | {s for s in table if s is not None}
    dead_ends = {s for s in states if not table.get(s)}
    assert dead_ends - terminal - set(KNOWN_DEAD_END_EXCEPTIONS) == set()
    assert [s for s in sorted(terminal) if table.get(s)] == []
    assert terminal <= states


def test_table_is_not_used_at_runtime():
    hits = []
    paths = sorted((APP_DIR / "app").rglob("*.py")) + sorted((REPO_DIR / "go").rglob("*.go"))
    for path in paths:
        count = path.read_text(encoding="utf-8").count("SUBMISSION_TRANSITIONS")
        if count:
            hits.append((path.relative_to(REPO_DIR).as_posix(), count))
    assert hits == [("App/app/reporting.py", 1)]
```

Command, from `App/`:

```bash
.venv/bin/python -m pytest tests/test_sm_submission_state.py -q --tb=short -x 2>&1 | tail -30
```

Expected: `7 passed`. If a test fails: read the last 30 lines, check the file against the code above once (a copy mistake), rerun. Fails again: STOP (§8) and paste the assertion message in the report. **Do not** change `PINNED_WRITES`, the table or any writer to make it pass. Commit: `git add tests/test_sm_submission_state.py && git commit -m "1106 step 3"`.

### Step 4: run the filing test-map row

From `App/`:

```bash
.venv/bin/python -m pytest tests/test_ubyport_*.py tests/test_soap.py tests/test_worker.py tests/test_submission_*.py tests/test_stale_submission.py tests/test_filed_by_hand.py tests/test_filing_watchdog.py tests/test_police_*.py tests/test_deadline*.py tests/test_claim_*.py tests/test_endtoend.py tests/test_sm_submission_state.py -q --tb=short -x 2>&1 | tail -30
```

Expected: a final line with `passed` and no `failed` or `error`. Nothing to commit.

### Step 5: context lint

From the repo root:

```bash
python3 scripts/context_lint.py 2>&1 | tail -30
```

Expected: no error. A warning that another open brief names `App/app/reporting.py` in §3 (brief 1105) is expected; note it in the report, do not act on it.

### Step 6: report

Write `docs/tasks/1106-report.md` (§9), then change the line `Status: todo` in this file to `Status: review`. Commit: `git add docs/tasks/1106-report.md docs/tasks/1106-sm-submission-state.md && git commit -m "1106 step 6"`. Open one draft PR (`gh pr create --draft --base main --title "1106: declare and pin submission.state" --body-file docs/tasks/1106-report.md`). If `gh` is read-only or push fails, give the owner the commands under "Owner steps".

## 5. Do not touch

- Every writer: `submit_batch`, `recover_stale_submissions`, `plan_outcome` and the rest of `App/app/reporting.py` outside the step 2 block; `App/app/db.py`; everything under `go/`.
- `docs/context/test-map.md` (the orchestrator adds the row at review), `docs/UBYPORT_CORE.md`, `docs/OPERATIONS.md`.
- No migration, no dependency, no template, no copy.
- AGENTS.md hard rules that apply: 1 (filing correctness beats every other feature: no runtime change), 3 (public repo), 4 (no new dependency), 5 (no schema change), 8 (never push to `main`, never merge).

## 6. Commands

| Step | Command (directory) | Expected |
|---|---|---|
| 2 | `grep -c 'SUBMISSION_TRANSITIONS' app/reporting.py \| tail -30 && .venv/bin/python -m py_compile app/reporting.py && echo compiled 2>&1 \| tail -30` (App/) | `1`, `compiled` |
| 3 | `.venv/bin/python -m pytest tests/test_sm_submission_state.py -q --tb=short -x 2>&1 \| tail -30` (App/) | `7 passed` |
| 4 | the filing row in step 4 (App/) | `passed`, no `failed` |
| 5 | `python3 scripts/context_lint.py 2>&1 \| tail -30` (root) | no error |
| final | `git diff --stat 5e034303 2>&1 \| tail -30` (root) | exactly the four files in §3 |

## 7. Acceptance

- [ ] `grep -rn SUBMISSION_TRANSITIONS App/app go | head -50` prints exactly one line, in `App/app/reporting.py`.
- [ ] `git diff 5e034303 -- App/app/reporting.py | grep -c '^-[^-]' | tail -30` prints `0` (only added lines).
- [ ] `git diff --stat 5e034303 -- go | tail -30` prints nothing.
- [ ] Step 3 command: `7 passed`.
- [ ] Step 4 command: `passed`, no `failed`, no `error`.
- [ ] Step 5 command: no error.

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt is not found, or the step 2 anchor appears more than once;
- `App/.venv/bin/python` does not exist;
- a test fails twice (never edit `PINNED_WRITES`, the table or a writer to make a test pass);
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1106-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Open questions (for the owner; this brief does not decide them)

1. **No UPDATE of `submission.state` has a state guard.** Each matches the row by id only, so the SQL itself allows a move from any state. Pinned as from-any (`ANY`): `App/app/reporting.py:1719` (outcome_unknown), `:1756` (transport_error), `:1820` (outcome from `plan_outcome`), `:1998` (recover, outcome_unknown); `go/internal/ubyport/store.go:113` (outcome_unknown), `:132` (transport_error), `:159` (`$1` = `plan.State`); `go/internal/ubyport/recover.go:122` (outcome_unknown). The table lists the source the code path holds (`running`: the row was inserted as `running` in the same call, or selected with `state = 'running'`).
2. **Recover reads and writes in separate transactions.** `recover_stale_submissions` selects `state = 'running'` (`App/app/reporting.py:1977`) and writes `outcome_unknown` in a later transaction without checking the state again (`:1998`); Go does the same (`recover.go:68`, then `:122`). If a live send whose claim has expired finishes in between, its outcome (`ok`, ...) can be overwritten with `outcome_unknown`; and a live send's final write, being unguarded, can overwrite an `outcome_unknown` set by recover. So `ok`/`partial`/... -> `outcome_unknown` and `outcome_unknown` -> `ok`/... are possible in SQL but are not in the table. Round 2 could add `AND state = 'running'` to these writes; that is a behaviour change and needs an owner decision.
3. **No doc describes this machine.** `docs/UBYPORT_CORE.md` has no mention of `outcome_unknown` or `transport_error` (grep finds nothing), so there is no doc to compare with. The comment above `TERMINAL_SUBMISSION_STATES` (`App/app/reporting.py:2693-2695`) says the envelope "is stored at the moment the row moves to one of these", but the `transport_error` writes (`reporting.py:1756`, `store.go:132`) store no envelope.
4. **`outcome_unknown` is terminal for the row but not for the filing.** A retry creates a new `submission` row and only sets `retried_at` on the old one (`reporting.py:2053`, `:2171`; `sweep.go:597`, `:699`). These are not state writes and are not pinned.

## Risk list (for the reviewer)

- `App/app/reporting.py`: the diff must be additions only, inside the block after `TERMINAL_SUBMISSION_STATES`.
- `App/tests/test_sm_submission_state.py`: `PINNED_WRITES` must match the table in §2 exactly.

## Owner steps

1. Open the draft PR for branch `task/1106-sm-submission-state` on GitHub. If there is none, run from the repo root: `git push -u origin task/1106-sm-submission-state`, then `gh pr create --draft --base main --title "1106: declare and pin submission.state" --body-file docs/tasks/1106-report.md`.
2. Read "Open questions" above and write one decision line in `docs/context/decisions.md` (or ask the orchestrator to) on whether round 2 adds state guards to the unguarded writes.
3. Leave the PR as a draft until the orchestrator has reviewed it; then merge only with `scripts/merge-pr-on-green.sh`.
