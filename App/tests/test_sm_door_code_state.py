"""1107: door_code.state is pinned to door_codes.TRANSITIONS.

Reads every writer of door_code.state as source text and compares each write
with PINNED. A write that is added, removed or changed fails this test, and
so does a pinned move that door_codes.TRANSITIONS does not list. Writers are
located by enclosing function name, never by line number.
"""
from __future__ import annotations

import ast
import re
from collections import Counter
from pathlib import Path

from app import door_codes

APP = Path(__file__).resolve().parents[1]
REPO = APP.parent
SOURCE = APP / "app" / "door_codes.py"

ANY = "any"  # the SQL has no state guard in its WHERE clause
NEW = "new"  # INSERT: the row is created

# (function, SQL guard states or ANY/NEW, states the row is in when the write
# runs, new states). For a guarded write the third field equals the guard.
# For an unguarded write it is the state the function holds through its own
# earlier claim or SELECT; see brief 1107 "Open questions".
PINNED = [
    ("_release_issue_claim", ANY, ("issuing",), ("pending",)),
    ("_release_issue_claim", ANY, ("issuing",), ("pending",)),
    ("ensure_row", NEW, (), ("pending",)),
    ("issue", ("pending", "retrying"), ("pending", "retrying"), ("issuing",)),
    ("issue", ANY, ("issuing",), ("expired",)),
    ("issue", ANY, ("issuing",), ("retrying",)),
    ("issue", ANY, ("issuing",), ("issued",)),
    ("issue", ANY, ("issuing",), ("failed", "retrying")),
    ("issue", ANY, ("issuing",), ("failed", "retrying")),
    ("issue", ANY, ("issuing",), ("failed", "retrying")),
    ("_keep_issued", ("revoke_failed", "revoke_pending"), ("revoke_failed", "revoke_pending"), ("issued",)),
    ("_revoke_one", ("revoke_pending",), ("revoke_pending",), ("revoke_failed",)),
    ("_revoke_one", ("revoke_pending",), ("revoke_pending",), ("revoked",)),
    ("_revoke_one", ("revoke_pending",), ("revoke_pending",), ("revoke_failed",)),
    ("_revoke_one", ("revoke_pending",), ("revoke_pending",), ("revoke_failed",)),
    ("_reissue_lost_pin", ("issued",), ("issued",), ("pending",)),
    ("_handle_cancellations", ("pending", "retrying"), ("pending", "retrying"), ("revoked",)),
    ("_handle_cancellations", ("issued",), ("issued",), ("revoke_pending",)),
    ("reconcile", ("issuing",), ("issuing",), ("retrying",)),
    ("reconcile", ("issued",), ("issued",), ("expired",)),
]

WRITE_RE = re.compile(r"\b(UPDATE\s+door_code\s+SET|INSERT\s+INTO\s+door_code\b)", re.I)
UPDATE_RE = re.compile(r"UPDATE\s+door_code\s+SET\s+(?P<set>.*?)(?:\s+WHERE\s+(?P<where>.*))?$", re.I | re.S)
SET_STATE_RE = re.compile(r"(?:^|,)\s*state\s*=\s*(?P<value>[^,]+)", re.I)
GUARD_RE = re.compile(r"\bstate\s*(?:=\s*(?P<one>\?|'[^']*')|IN\s*\((?P<many>[^)]*)\))", re.I)
INSERT_RE = re.compile(r"INSERT\s+INTO\s+door_code\s*\((?P<cols>[^)]*)\)", re.I)


def _state_names() -> dict:
    return {
        name: value
        for name, value in vars(door_codes).items()
        if name.isupper() and isinstance(value, str) and value in door_codes.STATES
    }


def _sql_text(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value, False
    if isinstance(node, ast.JoinedStr):
        parts = [v.value if isinstance(v, ast.Constant) else "{}" for v in node.values]
        return "".join(parts), True
    return None, False


def _resolver(func: ast.AST, names: dict):
    assigned: dict = {}
    for node in ast.walk(func):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Name):
            for target in node.targets:
                if isinstance(target, ast.Name) and node.value.id in names:
                    assigned.setdefault(target.id, set()).add(names[node.value.id])

    def resolve(node) -> set:
        if isinstance(node, ast.Name):
            if node.id in names:
                return {names[node.id]}
            if node.id in assigned:
                return set(assigned[node.id])
        return {"?"}

    return resolve


def _param(params, index: int, resolve) -> set:
    if params is None or index >= len(params):
        return {"?"}
    return resolve(params[index])


def _parse_update(sql: str, params, resolve):
    match = UPDATE_RE.search(sql)
    if not match:
        return None
    set_clause = match.group("set")
    state_set = SET_STATE_RE.search(set_clause)
    if not state_set:
        return None
    value = state_set.group("value").strip()
    if value == "?":
        index = sql[: match.start("set") + state_set.end("value")].count("?") - 1
        to = _param(params, index, resolve)
    else:
        to = {"literal:" + value}
    where = match.group("where")
    guard = GUARD_RE.search(where) if where else None
    if not guard:
        return ANY, to
    index = sql[: match.start("where") + guard.start()].count("?")
    raw = guard.group("one") or guard.group("many")
    states: set = set()
    for item in raw.split(","):
        item = item.strip()
        if item == "?":
            states |= _param(params, index, resolve)
            index += 1
        else:
            states.add(item.strip("'"))
    return tuple(sorted(states)), to


def _parse_insert(sql: str, params, resolve, names: dict):
    match = INSERT_RE.search(sql)
    if not match:
        return None
    if "DO UPDATE" in sql.upper():
        return NEW, {"?"}
    cols = [c.strip() for c in match.group("cols").split(",")]
    if "state" not in cols:
        return NEW, {"default"}
    found = set()
    for node in params or ():
        if isinstance(node, ast.Name) and node.id in names:
            found.add(names[node.id])
    return NEW, found or {"?"}


def _writes_in(path: Path) -> list:
    """Every statement in ``path`` that writes door_code.state."""
    names = _state_names()
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out = []
    for top in tree.body:
        func_name = top.name if isinstance(top, (ast.FunctionDef, ast.AsyncFunctionDef)) else "<module>"
        resolve = _resolver(top, names)
        for node in ast.walk(top):
            if not isinstance(node, ast.Call) or not node.args:
                continue
            sql, is_fstring = _sql_text(node.args[0])
            if sql is None or not WRITE_RE.search(sql):
                continue
            params = None
            if len(node.args) > 1 and isinstance(node.args[1], (ast.Tuple, ast.List)):
                params = node.args[1].elts
            parsed = _parse_update(sql, params, resolve) or _parse_insert(sql, params, resolve, names)
            if parsed is None:
                continue
            guard, to = parsed
            if is_fstring:
                to = {"f-string"}
            out.append((func_name, guard, tuple(sorted(to))))
    return out


def _pinned_writes() -> Counter:
    return Counter(
        (func, guard if isinstance(guard, str) else tuple(sorted(guard)), tuple(sorted(to)))
        for func, guard, _held, to in PINNED
    )


def test_every_state_write_in_door_codes_is_pinned():
    found = Counter(_writes_in(SOURCE))
    expected = _pinned_writes()
    assert found - expected == Counter(), f"unpinned writes: {sorted((found - expected).elements())}"
    assert expected - found == Counter(), f"pinned writes not found: {sorted((expected - found).elements())}"


def test_no_update_statement_is_missed():
    text = SOURCE.read_text(encoding="utf-8")
    in_text = len(re.findall(r"UPDATE\s+door_code\s+SET", text))
    tree = ast.parse(text)
    in_ast = sum(
        1
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and node.args
        and isinstance(node.args[0], ast.Constant)
        and isinstance(node.args[0].value, str)
        and re.search(r"UPDATE\s+door_code\s+SET", node.args[0].value)
    )
    assert in_text == in_ast


def test_no_other_python_file_writes_door_code_state():
    others = []
    for path in sorted((APP / "app").rglob("*.py")):
        if path == SOURCE:
            continue
        for write in _writes_in(path):
            others.append((str(path.relative_to(REPO)), write))
    assert others == []


# The demo seeder (mock-only, removed by "Clear demo") is the one file outside
# door_codes.py that writes door_code, through the db helpers. It INSERTs one row
# directly in the initial state; it never UPDATEs one, so no transition is used.
# (file, function, helper, state the new row is in)
PINNED_DEMO_HELPER_WRITES = [
    ("App/app/demo.py", "_enrich_extras", "insert", "pending"),
]


def _demo_helper_writes(path: Path, table: str) -> list:
    """(file, function, helper, state literal or None) for db.insert/update calls on ``table``."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out = []
    for func in tree.body:
        if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for node in ast.walk(func):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in {"update", "update_if", "update_in", "insert", "insert_in"}
                and any(isinstance(a, ast.Constant) and a.value == table for a in node.args[:2])
            ):
                continue
            state = None
            for arg in node.args:
                if isinstance(arg, ast.Dict):
                    for key, value in zip(arg.keys, arg.values):
                        if isinstance(key, ast.Constant) and key.value == "state" and isinstance(value, ast.Constant):
                            state = value.value
            out.append((str(path.relative_to(REPO)), func.name, node.func.attr, state))
    return out


def test_no_dict_helper_writes_door_code():
    helper = re.compile(
        r"\b(?:update|update_if|update_in|insert|insert_in)\(\s*(?:cur\s*,\s*)?['\"]door_code['\"]"
    )
    hits = [
        str(path.relative_to(REPO))
        for path in sorted((APP / "app").rglob("*.py"))
        if helper.search(path.read_text(encoding="utf-8"))
    ]
    assert hits == sorted({f for f, *_ in PINNED_DEMO_HELPER_WRITES})
    assert sorted(_demo_helper_writes(APP / "app" / "demo.py", "door_code")) == sorted(PINNED_DEMO_HELPER_WRITES)


def test_demo_door_code_state_is_the_initial_state():
    for _file, _func, helper, state in PINNED_DEMO_HELPER_WRITES:
        assert helper == "insert" and state == door_codes.PENDING


def test_no_go_file_writes_door_code():
    pattern = re.compile(r"\b(UPDATE\s+door_code\s+SET|INSERT\s+INTO\s+door_code\b)", re.I)
    hits = [
        str(path.relative_to(REPO))
        for path in sorted((REPO / "go").rglob("*.go"))
        if pattern.search(path.read_text(encoding="utf-8"))
    ]
    assert hits == []


def test_every_pinned_move_is_in_transitions():
    for func, _guard, held, to in PINNED:
        for old in held:
            for new in to:
                assert new in door_codes.TRANSITIONS.get(old, set()), f"{func}: {old} -> {new}"


def test_transitions_list_exactly_the_pinned_moves():
    pinned = {(old, new) for _f, _g, held, to in PINNED for old in held for new in to}
    table = {(old, new) for old, targets in door_codes.TRANSITIONS.items() for new in targets}
    assert table == pinned


def test_states_match_the_constants_and_the_table():
    assert door_codes.STATES == (
        door_codes.PENDING,
        door_codes.ISSUING,
        door_codes.RETRYING,
        door_codes.ISSUED,
        door_codes.FAILED,
        door_codes.EXPIRED,
        door_codes.REVOKE_PENDING,
        door_codes.REVOKED,
        door_codes.REVOKE_FAILED,
    )
    assert set(door_codes.TRANSITIONS) == set(door_codes.STATES)
    for targets in door_codes.TRANSITIONS.values():
        assert set(targets) <= set(door_codes.STATES)
    for _f, _g, held, to in PINNED:
        assert set(held) <= set(door_codes.STATES)
        assert set(to) <= set(door_codes.STATES)


def test_every_state_is_reachable_from_pending():
    seen = {door_codes.PENDING}
    todo = [door_codes.PENDING]
    while todo:
        for new in door_codes.TRANSITIONS[todo.pop()]:
            if new not in seen:
                seen.add(new)
                todo.append(new)
    assert seen == set(door_codes.STATES)


def test_table_is_not_used_at_runtime():
    text = SOURCE.read_text(encoding="utf-8")
    assert len(re.findall(r"\bTRANSITIONS\b", text)) == 1
    assert len(re.findall(r"\bSTATES\b", text)) == 1
    users = [
        str(path.relative_to(REPO))
        for path in sorted((APP / "app").rglob("*.py"))
        if re.search(r"door_codes\.(?:TRANSITIONS|STATES)\b", path.read_text(encoding="utf-8"))
    ]
    assert users == []
