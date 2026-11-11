"""Brief 1109: pin every write of ``reservation_claim.state``.

The claim state decides which guest may see and edit a stay's guest data, so
it is access control. This test reads every writer source (Python, Go and the
SQL migrations) as text, finds each statement that writes the column, and
compares them with the pinned lists below. It fails when a write is added,
removed or changed, and when a pinned move is missing from
``claim.TRANSITIONS``. It changes no runtime behaviour.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

from app import claim

APP_DIR = Path(__file__).resolve().parent.parent  # App/
REPO = APP_DIR.parent
PY_ROOT = APP_DIR / "app"
GO_ROOT = REPO / "go"
SQL_ROOTS = (APP_DIR / "app" / "migrations", APP_DIR / "migrations_pg")

ANY = ("claimed", "provisional", "unclaimed")
INSERT = ("(insert)",)
STATE_NAMES = {"UNCLAIMED": "unclaimed", "PROVISIONAL": "provisional", "CLAIMED": "claimed"}

# One entry per statement that writes reservation_claim.state:
# (file, enclosing function, states its WHERE clause allows, states it writes).
# INSERT: the statement creates the row. ANY: the WHERE clause has no state
# condition (brief 1109, "Open questions").
PINNED_WRITES = [
    ("App/app/claim.py", "ensure_row", INSERT, ("unclaimed",)),
    ("App/app/claim.py", "expire_holds", ("provisional",), ("unclaimed",)),
    ("App/app/claim.py", "start_claim", ANY, ("claimed", "provisional")),
    ("App/app/claim.py", "confirm", ("claimed", "provisional"), ("claimed",)),
    ("App/app/claim.py", "release", ANY, ("unclaimed",)),
]

# The moves those writes make: (file, function, from-states, to-state).
# None as a from-state means "no row yet". start_claim has no state condition
# in its WHERE clause: its from-states are the ones its Python checks let
# through before the write.
PINNED_MOVES = [
    ("App/app/claim.py", "ensure_row", (None,), "unclaimed"),
    ("App/app/claim.py", "expire_holds", ("provisional",), "unclaimed"),
    ("App/app/claim.py", "start_claim", ("unclaimed", "provisional"), "provisional"),
    ("App/app/claim.py", "start_claim", ("claimed",), "claimed"),
    ("App/app/claim.py", "confirm", ("provisional", "claimed"), "claimed"),
    ("App/app/claim.py", "release", ("unclaimed", "provisional", "claimed"), "unclaimed"),
]

_WRITE_SQL = re.compile(
    r"\b(?:UPDATE\s+reservation_claim\s+SET|INSERT\s+INTO\s+reservation_claim)\b", re.I
)
_STATE_SET = re.compile(r"(?<![\w.])state\s*=", re.I)
_STATE_WHERE = re.compile(r"(?<![\w.])state\s*(?:=\s*\?|IN\s*\([^)]*\))", re.I)
_WHERE = re.compile(r"\bWHERE\b", re.I)


def _text(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return "".join(
            v.value if isinstance(v, ast.Constant) else "{}" for v in node.values
        )
    return None


def _states(node) -> tuple:
    """The claim states an argument can carry: the constants named in it."""
    found = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Name) and sub.id in STATE_NAMES:
            found.add(STATE_NAMES[sub.id])
        elif isinstance(sub, ast.Attribute) and sub.attr in STATE_NAMES:
            found.add(STATE_NAMES[sub.attr])
        elif isinstance(sub, ast.Constant) and sub.value in ANY:
            found.add(sub.value)
    return tuple(sorted(found))


def _sets_state(sql: str) -> bool:
    if not _WRITE_SQL.search(sql):
        return False
    if re.search(r"\bINSERT\b", sql, re.I):
        return True
    return bool(_STATE_SET.search(_WHERE.split(sql, 1)[0]))


def _sql_write(call: ast.Call):
    """(guard, to-states) for ``execute(sql, params)`` writing the state, else None."""
    if not call.args:
        return None
    sql = _text(call.args[0])
    if sql is None or not _sets_state(sql):
        return None
    params = call.args[1] if len(call.args) > 1 else None
    elts = params.elts if isinstance(params, (ast.Tuple, ast.List)) else None
    if re.search(r"\bINSERT\b", sql, re.I):
        return INSERT, (_states(params) if params is not None else ("unclaimed",))
    set_part = _WHERE.split(sql, 1)[0]
    match = _STATE_SET.search(set_part)
    index = set_part[: match.start()].count("?")
    to = _states(elts[index]) if elts is not None and index < len(elts) else ("?",)
    where_at = len(set_part)
    guard = _STATE_WHERE.search(sql, where_at)
    if guard is None:
        return ANY, to
    first = sql[: guard.start()].count("?")
    count = guard.group(0).count("?")
    if elts is None:
        return ("?",), to
    allowed = set()
    for elt in elts[first:first + count]:
        allowed.update(_states(elt))
    return tuple(sorted(allowed)), to


def _helper_write(call: ast.Call):
    """(guard, to-states) for ``db.insert("reservation_claim", {...})`` and the
    other db.py dict helpers, else None."""
    if not any(_text(a) == "reservation_claim" for a in call.args[:2]):
        return None
    values = next((a for a in call.args if isinstance(a, ast.Dict)), None)
    state = None
    if values is not None:
        for key, value in zip(values.keys, values.values):
            if key is not None and _text(key) == "state":
                state = value
    func = call.func
    name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
    if name.startswith("insert"):
        return INSERT, (_states(state) if state is not None else ("unclaimed",))
    if state is None:
        return None
    return ("(helper)",), _states(state)


def _scan(node, func, rel, found, consumed):
    for child in ast.iter_child_nodes(node):
        inner = func
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
            inner = child.name
        if isinstance(child, ast.Call):
            write = _sql_write(child)
            if write is not None:
                consumed.append(id(child.args[0]))
            else:
                write = _helper_write(child)
            if write is not None:
                found.append((rel, func, write[0], write[1]))
        _scan(child, inner, rel, found, consumed)


def _python_writes():
    found, strays = [], []
    for path in sorted(PY_ROOT.rglob("*.py")):
        rel = path.relative_to(REPO).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=rel)
        consumed = []
        _scan(tree, "<module>", rel, found, consumed)
        for node in ast.walk(tree):
            sql = _text(node) if isinstance(node, (ast.Constant, ast.JoinedStr)) else None
            if sql and _sets_state(sql) and id(node) not in consumed:
                strays.append((rel, sql[:80]))
    return found, strays


def _python_claim_update_count() -> int:
    """How many UPDATE reservation_claim statements the Python sources hold."""
    n = 0
    for path in sorted(PY_ROOT.rglob("*.py")):
        n += len(re.findall(r"UPDATE reservation_claim SET", path.read_text(encoding="utf-8")))
    return n


_GO_FUNC = re.compile(r"^func\s+(?:\([^)]*\)\s*)?(\w+)", re.M)


def _go_writes():
    found, seen = [], 0
    for path in sorted(GO_ROOT.rglob("*.go")):
        if path.name.endswith("_test.go"):
            continue
        text = path.read_text(encoding="utf-8")
        rel = path.relative_to(REPO).as_posix()
        for match in _WRITE_SQL.finditer(text):
            seen += 1
            end = text.find("`", match.start())
            sql = text[match.start(): end if end != -1 else match.start() + 600]
            if not _sets_state(sql):
                continue
            funcs = [m.group(1) for m in _GO_FUNC.finditer(text, 0, match.start())]
            found.append((rel, funcs[-1] if funcs else "<file>", sql[:80]))
    return found, seen


def _norm_writes(rows):
    return sorted((f, fn, tuple(sorted(g)), tuple(sorted(t))) for f, fn, g, t in rows)


def test_python_writes_match_pin():
    found, _ = _python_writes()
    assert _norm_writes(found) == _norm_writes(PINNED_WRITES)


def test_no_state_sql_outside_a_readable_call():
    # SQL held in a variable, or built where the scanner cannot see its
    # parameters, would escape the pin above.
    _, strays = _python_writes()
    assert strays == []


def test_scanner_sees_claim_updates():
    # Guard against a scanner that silently finds nothing: claim.py alone has
    # UPDATE statements that set the state and others that do not.
    assert _python_claim_update_count() > len(PINNED_WRITES)


def test_go_writes_no_claim_state():
    found, seen = _go_writes()
    assert seen >= 1, "the Go scan found no reservation_claim write at all"
    assert found == []


def test_sql_migrations_write_no_claim_state():
    hits = []
    for root in SQL_ROOTS:
        for path in sorted(root.glob("*.sql")):
            for stmt in path.read_text(encoding="utf-8").split(";"):
                if _sets_state(stmt):
                    hits.append(path.name)
    assert hits == []


def test_moves_match_writes():
    writes = {}
    for f, fn, guard, to in PINNED_WRITES:
        writes[(f, fn)] = (guard, set(to))
    moves = {}
    for f, fn, frm, to in PINNED_MOVES:
        moves.setdefault((f, fn), []).append((frm, to))
    assert set(moves) == set(writes)
    for key, (guard, to) in writes.items():
        assert {t for _, t in moves[key]} == to, key
        allowed = {None} if guard == INSERT else set(guard)
        for frm, _ in moves[key]:
            assert set(frm) <= allowed, key


def test_pinned_moves_are_in_transitions():
    for f, fn, frm, to in PINNED_MOVES:
        for state in frm:
            assert to in claim.TRANSITIONS.get(state, set()), (fn, state, to)


def test_transitions_list_only_pinned_moves():
    pinned = {(state, to) for _, _, frm, to in PINNED_MOVES for state in frm}
    table = {(state, to) for state, tos in claim.TRANSITIONS.items() for to in tos}
    assert table == pinned


def test_states_match_constants():
    assert {claim.UNCLAIMED, claim.PROVISIONAL, claim.CLAIMED} == set(ANY)
    states = {s for s in claim.TRANSITIONS if s is not None}
    for tos in claim.TRANSITIONS.values():
        states |= set(tos)
    assert states == set(ANY)
    schema = (PY_ROOT / "db.py").read_text(encoding="utf-8")
    assert "CHECK (state IN ('unclaimed', 'provisional', 'claimed'))" in schema


def test_transitions_not_used_at_runtime():
    # Round 1 declares the table only; nothing may read it yet.
    own = (PY_ROOT / "claim.py").read_text(encoding="utf-8")
    assert own.count("TRANSITIONS") == 1
    for path in sorted(PY_ROOT.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        assert not re.search(r"claim\.TRANSITIONS|from \.claim import[^\n]*TRANSITIONS", text), path
