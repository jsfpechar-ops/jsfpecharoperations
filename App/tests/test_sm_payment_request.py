"""Pins every writer of payment_request.status, Python and Go, against
payment_request._TRANSITIONS (plan: docs/plans/explicit-state-machines.md,
brief 1104).

The test reads the writer sources as text. It fails when a statement that
writes payment_request.status is added, removed or changed, and when a pinned
move is not allowed by the table. Go has no table: its moves are pinned from
the arguments its callers pass (derivation: docs/tasks/1104-sm-payment-request-pin.md).
"""
import re
from collections import defaultdict
from pathlib import Path

import pytest

from app import payment_request

APP_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = APP_DIR.parent

TABLE = payment_request._TRANSITIONS

LATE_PAID_FROM = ("sent", "awaiting_payment", "expired", "cancelled")
OVERDUE_FROM = ("sent", "awaiting_payment")

# (file, anchor that must appear verbatim in that file, from-states, to-state)
MOVES = [
    # Python: card or QR send, draft -> sent
    ("App/app/routes/payments.py",
     'payment_request.set_status(request_id, "sent", today=date.today())',
     ("draft",), "sent"),
    ("App/app/routes/payments.py",
     'payment_request.set_status(request_id, "sent", today=__import__("datetime").date.today())',
     ("draft",), "sent"),
    # Python: Stripe webhook (payment_links.on_paid)
    ("App/app/payment_links.py",
     'model.set_status(int(row["id"]), "sent", today=date.today())',
     ("draft",), "sent"),
    ("App/app/payment_links.py",
     'model.mark_paid(int(row["id"]), today=date.today(), via="stripe_webhook")',
     LATE_PAID_FROM, "paid"),
    # Python: inside payment_request.py
    ("App/app/payment_request.py",
     'ok = set_status(request_id, "paid", today=today, paid_at=db.utcnow())',
     LATE_PAID_FROM, "paid"),
    ("App/app/payment_request.py",
     'set_status(int(row["id"]), "expired", today=today)',
     OVERDUE_FROM, "expired"),
    # Go: expireSQL; the from-state is o.current, read by selectOverdueSQL
    ("go/internal/payments/sweep.go",
     "tx.Exec(ctx, expireSQL, now, o.id, o.current)",
     OVERDUE_FROM, "expired"),
    # Go: requestSentSQL has the from-state in its own WHERE
    ("go/internal/payments/requests.go",
     "pool.Exec(ctx, requestSentSQL, stamp, id)",
     ("draft",), "sent"),
    ("go/internal/payments/paylink_routes.go",
     "pool.Exec(ctx, requestSentSQL, stamp, id)",
     ("draft",), "sent"),
    # Go: transitionSQL, only reached through setStatus in onPaid
    ("go/internal/payments/webhook.go",
     'setStatus(ctx, q, id, owner, "draft", "sent", false, stamp)',
     ("draft",), "sent"),
    ("go/internal/payments/webhook.go",
     'setStatus(ctx, q, id, owner, status, "paid", true, stamp)',
     LATE_PAID_FROM, "paid"),
]

# Anchors that justify the from-states above. Moves cannot be derived without them.
ANCHORS = [
    ("App/app/payment_request.py",
     "\" WHERE status IN ('sent', 'awaiting_payment') AND expires_at < ?\","),
    ("go/internal/payments/sweep.go",
     "WHERE status IN ('sent', 'awaiting_payment') AND expires_at < $1 ORDER BY id"),
    ("go/internal/payments/requests.go",
     "SET status = 'sent', updated_at = $1 WHERE id = $2 AND status = 'draft'"),
    ("go/internal/payments/webhook.go",
     'case "draft", "sent", "awaiting_payment", "expired", "cancelled":'),
    ("go/internal/payments/webhook.go",
     "WHERE id = $4 AND status = $5"),
]

# Rows are born in 'draft': Python insert dict, Go INSERT.
INITIAL = [
    ("App/app/payment_request.py", '"status": "draft",'),
    ("go/internal/payments/requests.go",
     "VALUES ($1, NULL, $2, $3, $4, 'CZK', $5, $6, $7, 'draft', $8, $9, $9) RETURNING id"),
]

# Every file that writes the status column or inserts a row, and how many times.
PINNED_WRITERS = {
    "App/app/payment_request.py": {"status_updates": 1, "inserts": 1},
    "go/internal/payments/requests.go": {"status_updates": 1, "inserts": 1},
    "go/internal/payments/sweep.go": {"status_updates": 1},
    "go/internal/payments/webhook.go": {"status_updates": 1},
    # demo seeder: two db.update("payment_request", ...) calls, see DEMO_ONLY_MOVES
    "App/app/demo.py": {"helper_updates": 2},
}

# The demo seeder (mock-only, removed by "Clear demo") creates two requests with
# payment_request.create (born draft) and then sets their status with a direct
# db.update, skipping set_status. Neither move is in _TRANSITIONS, so each is a
# named demo-only exception here; the production table is not widened.
# (file, function, from-state, to-state)
DEMO_ONLY_MOVES = [
    ("App/app/demo.py", "_enrich_extras", "draft", "paid"),
    ("App/app/demo.py", "_enrich_extras", "draft", "awaiting_payment"),
]

# Where the status-writing functions and SQL constants are used.
PINNED_PY_CALLERS = {
    "App/app/routes/payments.py": ["set_status", "set_status"],
    "App/app/payment_links.py": ["set_status", "mark_paid"],
    "App/app/scheduler.py": ["expire_sweep"],
}
PINNED_PY_INTERNAL = ["set_status", "set_status"]  # inside payment_request.py
PINNED_GO_EXEC = {
    "requestSentSQL": {"go/internal/payments/requests.go": 1, "go/internal/payments/paylink_routes.go": 1},
    "transitionSQL": {"go/internal/payments/webhook.go": 1},
    "expireSQL": {"go/internal/payments/sweep.go": 1},
}
PINNED_GO_SETSTATUS = {"go/internal/payments/webhook.go": 2}

UPDATE_RE = re.compile(r"UPDATE\s+payment_request\s+SET\b(.*?)\bWHERE\b", re.S | re.I)
STATUS_RE = re.compile(r"(?<![\w])status\s*=")
INSERT_SQL_RE = re.compile(r"INSERT\s+INTO\s+payment_request\s*\(", re.I)
INSERT_HELPER_RE = re.compile(r"\b(?:insert|insert_in)\(\s*(?:cur,\s*)?[\"']payment_request[\"']")
UPDATE_HELPER_RE = re.compile(r"\b(?:update|update_if|update_in)\(\s*(?:cur,\s*)?[\"']payment_request[\"']")
PY_CALL_RE = re.compile(r"\b(?:payment_request|model)\.(set_status|mark_paid|expire_sweep)\(")
PY_INTERNAL_RE = re.compile(r"(?<![.\w])(?<!def )(set_status)\(")


def _read(rel: str) -> str:
    return (REPO_DIR / rel).read_text(encoding="utf-8")


def _py_files():
    return sorted((APP_DIR / "app").rglob("*.py"))


def _go_files():
    return sorted(p for p in (REPO_DIR / "go").rglob("*.go") if not p.name.endswith("_test.go"))


def _rel(path: Path) -> str:
    return path.relative_to(REPO_DIR).as_posix()


def test_table_is_well_formed():
    assert set(TABLE) == set(payment_request.STATUSES)
    for source, targets in TABLE.items():
        assert targets <= set(payment_request.STATUSES), source


@pytest.mark.parametrize("rel,anchor", [(f, a) for f, a, _, _ in MOVES] + ANCHORS + INITIAL)
def test_anchor_is_in_file(rel, anchor):
    assert anchor in _read(rel), f"{rel} no longer contains: {anchor}"


@pytest.mark.parametrize(
    "rel,anchor,source,target",
    [(f, a, s, t) for f, a, froms, t in MOVES for s in froms],
)
def test_pinned_move_is_allowed_by_table(rel, anchor, source, target):
    assert target in TABLE[source], f"{rel}: {source} -> {target} is not in payment_request._TRANSITIONS"


def test_rows_are_born_draft_and_nothing_moves_back_to_draft():
    assert "draft" in TABLE
    assert all("draft" not in targets for targets in TABLE.values())


def test_status_writing_statements_match_the_pins():
    found = {}
    for path in _py_files() + _go_files():
        text = path.read_text(encoding="utf-8")
        counts = {
            "status_updates": sum(1 for m in UPDATE_RE.finditer(text) if STATUS_RE.search(m.group(1))),
            "inserts": len(INSERT_SQL_RE.findall(text)) + len(INSERT_HELPER_RE.findall(text)),
            "helper_updates": len(UPDATE_HELPER_RE.findall(text)),
        }
        counts = {k: v for k, v in counts.items() if v}
        if counts:
            found[_rel(path)] = counts
    assert found == PINNED_WRITERS


def test_python_callers_match_the_pins():
    found = {}
    for path in _py_files():
        if _rel(path) == "App/app/payment_request.py":
            continue
        names = PY_CALL_RE.findall(path.read_text(encoding="utf-8"))
        if names:
            found[_rel(path)] = names
    assert found == PINNED_PY_CALLERS
    internal = PY_INTERNAL_RE.findall(_read("App/app/payment_request.py"))
    assert internal == PINNED_PY_INTERNAL


def test_go_callers_match_the_pins():
    for name, expected in PINNED_GO_EXEC.items():
        pattern = re.compile(r"\bExec\(ctx,\s*" + name + r"\b")
        found = defaultdict(int)
        for path in _go_files():
            n = len(pattern.findall(path.read_text(encoding="utf-8")))
            if n:
                found[_rel(path)] = n
        assert dict(found) == expected, name
    found = {}
    for path in _go_files():
        n = len(re.findall(r"\bsetStatus\(ctx, ", path.read_text(encoding="utf-8")))
        if n:
            found[_rel(path)] = n
    assert found == PINNED_GO_SETSTATUS


def _demo_status_updates():
    """(file, function, status literal) for each db.update("payment_request", ...) in demo.py."""
    import ast

    path = APP_DIR / "app" / "demo.py"
    out = []
    for func in ast.parse(path.read_text(encoding="utf-8")).body:
        if not isinstance(func, ast.FunctionDef):
            continue
        for node in ast.walk(func):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in {"update", "update_if", "update_in", "insert", "insert_in"}
                and any(isinstance(a, ast.Constant) and a.value == "payment_request" for a in node.args[:2])
            ):
                continue
            status = None
            for arg in node.args:
                if isinstance(arg, ast.Dict):
                    for key, value in zip(arg.keys, arg.values):
                        if isinstance(key, ast.Constant) and key.value == "status" and isinstance(value, ast.Constant):
                            status = value.value
            out.append((_rel(path), func.name, node.func.attr, status))
    return out


def test_demo_seeder_writes_match_the_pinned_demo_only_moves():
    found = _demo_status_updates()
    assert all(helper == "update" for _f, _fn, helper, _s in found), found
    assert sorted((f, fn, s) for f, fn, _h, s in found) == sorted((f, fn, to) for f, fn, _frm, to in DEMO_ONLY_MOVES)
    # rows are born draft (payment_request.create), so draft is the from-state
    assert all(frm == "draft" for _f, _fn, frm, _to in DEMO_ONLY_MOVES)


def test_demo_only_moves_are_exactly_the_ones_the_table_lacks():
    for _f, _fn, frm, to in DEMO_ONLY_MOVES:
        assert to not in TABLE[frm], f"{frm} -> {to} is now in the table: drop it from DEMO_ONLY_MOVES"
