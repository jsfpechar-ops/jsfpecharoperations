"""Pins every writer of billing_account.status against billing.TRANSITIONS
(plan: docs/plans/explicit-state-machines.md, brief 1134).

The test reads the writer sources as text. It fails when a statement that writes
billing_account.status is added, removed or moved to another file, and when a
pinned move is not allowed by the table. Go has no writer of this column.
"""
import re
from pathlib import Path

import pytest

from app import billing

APP_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = APP_DIR.parent

TABLE = billing.TRANSITIONS

# (file, anchor that must appear verbatim, from-states, to-state)
MOVES = [
    ("App/app/billing_trial.py",
     "UPDATE billing_account SET status = 'trialing', trial_started_at = ?, ",
     ("trial_pending",), "trialing"),
]

# The one move outside TRANSITIONS: operator plan assignment (owner decision 2026-11-12).
OPERATOR_MOVES = [
    ("App/app/billing.py",
     "UPDATE billing_account SET status = 'paused', updated_at = ? ",
     ("trial_pending", "trialing"), "paused"),
    ("App/app/billing_order.py",
     "billing.operator_pause(owner_user_id, actor=actor)",
     ("trial_pending", "trialing"), "paused"),
]

# Rows are born in these states: ensure_account and signup verification.
INITIAL = [
    ("App/app/billing.py", "VALUES (?, 'trial_pending', ?) ON CONFLICT(owner_user_id) DO NOTHING", "trial_pending"),
    ("App/app/signup.py", "VALUES (?, 'trialing', ?, ?, ?) ON CONFLICT(owner_user_id) DO NOTHING", "trialing"),
]

# Every file that writes the status column, and how many times.
PINNED_WRITERS = {
    "App/app/billing.py": {"status_updates": 2, "inserts": 1},
    "App/app/billing_trial.py": {"status_updates": 1},
    "App/app/signup.py": {"inserts": 1},
}

UPDATE_RE = re.compile(r"UPDATE\s+billing_account\s+SET\b(.*?)\bWHERE\b", re.S | re.I)
STATUS_RE = re.compile(r"(?<![\w])status\s*=")
INSERT_RE = re.compile(r"INSERT\s+INTO\s+billing_account\b", re.I)


def _read(rel: str) -> str:
    return (REPO_DIR / rel).read_text(encoding="utf-8")


def _rel(path: Path) -> str:
    return path.relative_to(REPO_DIR).as_posix()


def _files():
    go = (p for p in (REPO_DIR / "go").rglob("*.go") if not p.name.endswith("_test.go"))
    return sorted(list((APP_DIR / "app").rglob("*.py")) + list(go))


def test_table_is_well_formed():
    assert set(TABLE) == set(billing.STATUSES)
    for source, targets in TABLE.items():
        assert targets <= set(billing.STATUSES), source


@pytest.mark.parametrize("rel,anchor", [(f, a) for f, a, _, _ in MOVES] + [(f, a) for f, a, _ in INITIAL])
def test_anchor_is_in_file(rel, anchor):
    assert anchor in _read(rel), f"{rel} no longer contains: {anchor}"


@pytest.mark.parametrize(
    "rel,anchor,source,target",
    [(f, a, s, t) for f, a, froms, t in MOVES for s in froms],
)
def test_pinned_move_is_allowed_by_table(rel, anchor, source, target):
    assert target in TABLE[source], f"{rel}: {source} -> {target} is not in billing.TRANSITIONS"


@pytest.mark.parametrize("rel,anchor,state", INITIAL)
def test_birth_states_exist(rel, anchor, state):
    assert state in TABLE


def test_status_writing_statements_match_the_pins():
    found = {}
    for path in _files():
        text = path.read_text(encoding="utf-8")
        counts = {
            "status_updates": sum(1 for m in UPDATE_RE.finditer(text) if STATUS_RE.search(m.group(1))),
            "inserts": len(INSERT_RE.findall(text)),
        }
        counts = {k: v for k, v in counts.items() if v}
        if counts:
            found[_rel(path)] = counts
    assert found == PINNED_WRITERS


@pytest.mark.parametrize("rel,anchor", [(f, a) for f, a, _, _ in OPERATOR_MOVES])
def test_operator_move_anchor_is_in_file(rel, anchor):
    assert anchor in _read(rel), f"{rel} no longer contains: {anchor}"


def test_operator_move_is_not_in_transitions():
    # set_status and the operator status form must keep refusing it; the Go table has no such move.
    assert "paused" not in TABLE["trial_pending"]
    assert {s for _, _, froms, _ in OPERATOR_MOVES for s in froms} == {"trial_pending", "trialing"}
