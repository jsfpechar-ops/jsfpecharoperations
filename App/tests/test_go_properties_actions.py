"""Parity of the Go property actions with admin.py (brief 1300).

go/internal/web/properties/testdata/actions_cases.json holds a seed and the
cases. This test replays them on the Python routes and compares what it sees
(status, Location, row changes, audit rows) with actions_golden.json; the Go
test replays the same cases on Postgres against the same file. To rewrite the
golden after a deliberate change to the Python routes:

    UBYHOST_WRITE_GOLDEN=1 .venv/bin/python -m pytest tests/test_go_properties_actions.py -q
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import auth, db, guest_slug
from app.main import app
from app.routes import admin

REPO = Path(__file__).resolve().parents[2]
DATA = REPO / "go" / "internal" / "web" / "properties" / "testdata"
CASES = json.loads((DATA / "actions_cases.json").read_text(encoding="utf-8"))
GOLDEN = DATA / "actions_golden.json"
LOW, HIGH = 130000, 130999

STAMP = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\+00:00$")
TOKEN = re.compile(r"^[abcdefghijkmnopqrstuvwxyz23456789]{20}$")
PIN = re.compile(r"^[0-9]{6}$")
SLUG = re.compile(r"^(.+)-[abcdefghijkmnopqrstuvwxyz23456789]{6}$")

# table -> (key columns for the row key, columns compared)
SNAPSHOT = {
    "legal_entity": (["id"], ["id", "archived_at"], "id BETWEEN %d AND %d" % (LOW, HIGH)),
    "apartment": (
        ["id"],
        ["id", "archived_at", "active", "permalink_token", "permalink_pin"],
        "id BETWEEN %d AND %d" % (LOW, HIGH),
    ),
    "ical_feed": (["id"], ["id", "apartment_id"], "id BETWEEN %d AND %d" % (LOW, HIGH)),
    "apartment_slug": (
        ["apartment_id", "slug"],
        ["apartment_id", "slug", "is_current", "created_at"],
        "apartment_id BETWEEN %d AND %d" % (LOW, HIGH),
    ),
}
AUDIT_COLUMNS = ["actor", "action", "detail", "owner_user_id", "actor_user_id", "impersonator_user_id", "at"]


def normal(column, value):
    """Random and clock-dependent values reduced to their shape."""
    if not isinstance(value, str):
        return value
    if STAMP.match(value):
        return "<ts>"
    if column == "permalink_token" and TOKEN.match(value):
        return "<token>"
    if column == "permalink_pin" and PIN.match(value):
        return "<pin>"
    if column == "slug":
        match = SLUG.match(value)
        if match:
            return match.group(1) + "-<code>"
    return value


def snapshot():
    state = {}
    for table, (keys, columns, where) in SNAPSHOT.items():
        rows = db.query(f"SELECT {', '.join(columns)} FROM {table} WHERE {where} ORDER BY {', '.join(keys)}")
        for row in rows:
            values = {c: normal(c, row[c]) for c in columns}
            state[table + "|" + "|".join(str(values[k]) for k in keys)] = values
    audit = db.query(
        f"SELECT {', '.join(AUDIT_COLUMNS)} FROM audit WHERE owner_user_id BETWEEN ? AND ? ORDER BY id",
        (LOW, HIGH),
    )
    for n, row in enumerate(audit):
        state[f"audit|{n:03d}"] = {c: normal(c, row[c]) for c in AUDIT_COLUMNS}
    return state


def changes(before, after):
    out = {"added": {}, "removed": [], "changed": {}}
    for key, row in after.items():
        if key not in before:
            out["added"][key] = row
        elif before[key] != row:
            out["changed"][key] = {c: [before[key][c], row[c]] for c in row if before[key][c] != row[c]}
    out["removed"] = sorted(k for k in before if k not in after)
    return out


def insert(table, row):
    cols = list(row)
    db.execute(
        f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})",
        [row[c] for c in cols],
    )


def wipe():
    db.execute("DELETE FROM audit WHERE owner_user_id BETWEEN ? AND ?", (LOW, HIGH))
    db.execute("DELETE FROM apartment_slug WHERE apartment_id BETWEEN ? AND ?", (LOW, HIGH))
    db.execute("DELETE FROM ical_feed WHERE id BETWEEN ? AND ?", (LOW, HIGH))
    db.execute("DELETE FROM apartment WHERE id BETWEEN ? AND ?", (LOW, HIGH))
    db.execute("DELETE FROM invoice WHERE id BETWEEN ? AND ?", (LOW, HIGH))
    db.execute("DELETE FROM legal_entity WHERE id BETWEEN ? AND ?", (LOW, HIGH))
    db.execute("DELETE FROM user_account WHERE id BETWEEN ? AND ?", (LOW, HIGH))


@pytest.fixture
def world():
    db.init_db()
    wipe()
    for table in ("user_account", "legal_entity", "invoice", "apartment", "ical_feed", "apartment_slug"):
        for row in CASES["seed"][table]:
            insert(table, row)
    yield
    wipe()


def replay():
    clients = {}
    before = snapshot()
    results = []
    for case in CASES["cases"]:
        uid, workspace = case["user"], case.get("as")
        if (uid, workspace) not in clients:
            client = TestClient(app, follow_redirects=False)
            if uid:
                # "as": an admin inside that host's workspace, started now.
                client.cookies.set(auth.SESSION_COOKIE, auth.issue_session(uid, 1, workspace_user_id=workspace))
            clients[(uid, workspace)] = client
        client = clients[(uid, workspace)]
        client.cookies.set("ubyhost_lang", case["lang"])
        response = client.post(case["path"], data=case.get("form") or {})
        after = snapshot()
        results.append(
            {
                "name": case["name"],
                "status": response.status_code,
                "location": response.headers.get("location", ""),
                "changes": changes(before, after),
            }
        )
        before = after
    return results


def return_to_cases():
    out = []
    for case in CASES["return_to"]:
        form = {"return_to": case["value"]}
        want = admin._form_return_to(form, case["default"], keep_fragment=case["keep_fragment"])
        out.append({**case, "want": want})
    return out


def readable_cases():
    return [{"name": name, "want": guest_slug._generated_readable(name)} for name in CASES["readable"]]


def test_go_actions_match_python(world):
    observed = {
        "cases": replay(),
        "return_to": return_to_cases(),
        "readable": readable_cases(),
    }
    text = "{\n" + ",\n".join(
        ' "%s": [\n%s\n ]' % (key, ",\n".join("  " + json.dumps(x, ensure_ascii=False, sort_keys=True) for x in rows))
        for key, rows in observed.items()
    ) + "\n}\n"
    if os.environ.get("UBYHOST_WRITE_GOLDEN") == "1":
        GOLDEN.write_text(text, encoding="utf-8")
    assert GOLDEN.exists(), "run once with UBYHOST_WRITE_GOLDEN=1"
    assert json.loads(GOLDEN.read_text(encoding="utf-8")) == json.loads(text)


def test_go_catalog_matches_host_i18n():
    sys.path.insert(0, str(REPO / "App" / "scripts"))
    import go_host_i18n

    folder = DATA.parent
    keys = go_host_i18n.read_keys(folder / "i18n_keys.txt")
    assert (folder / "i18n.json").read_text(encoding="utf-8") == go_host_i18n.render(keys)
