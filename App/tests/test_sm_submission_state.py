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
    ("App/app/reporting.py", "recover_stale_submissions", ("running",), "outcome_unknown", "running"),
    ("go/internal/ubyport/store.go", "InsertSubmission", INSERT, "running", None),
    ("go/internal/ubyport/store.go", "RecordOutcomeUnknown", ANY, "outcome_unknown", "running"),
    ("go/internal/ubyport/store.go", "RecordTransportError", ANY, "transport_error", "running"),
    ("go/internal/ubyport/store.go", "RecordOutcome", ANY, "<param>", "running"),
    ("go/internal/ubyport/recover.go", "RecoverStaleSubmissions", ("running",), "outcome_unknown", "running"),
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
