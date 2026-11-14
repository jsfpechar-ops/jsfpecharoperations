"""Content parity of the Go property list pages with admin.py (brief 1302).

go/internal/web/properties/testdata/lists_cases.json holds a seed and the
cases for GET /entities and GET /apartments. This test renders each case on
the Python routes and records status, Location, <title> and the items of the
page content (div.ui-page) into lists_golden.json; the Go test renders the
same cases and compares. A case marked "go": 501 is a branch Go does not
serve yet: Python's page is still recorded, the Go test checks the 501. To
rewrite the golden after a deliberate template change:

    UBYHOST_WRITE_GOLDEN=1 .venv/bin/python -m pytest tests/test_go_properties_lists.py -q

The extraction is the one of test_go_properties_pages.py (extractItems in Go).
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import alerts, auth, db
from app.main import app
from tests.test_go_properties_pages import TITLE, extract_items, insert, squash

REPO = Path(__file__).resolve().parents[2]
DATA = REPO / "go" / "internal" / "web" / "properties" / "testdata"
CASES = json.loads((DATA / "lists_cases.json").read_text(encoding="utf-8"))
GOLDEN = DATA / "lists_golden.json"
LOW, HIGH = 132000, 132999
TABLES = ("user_account", "legal_entity", "apartment", "ical_feed", "settings", "alert")
HOLD = "1302-test-hold"


def wipe():
    db.execute("DELETE FROM alert WHERE id BETWEEN ? AND ?", (LOW, HIGH))
    db.execute("DELETE FROM settings WHERE key LIKE 'onboarding_dismissed_132%'")
    db.execute("DELETE FROM ical_feed WHERE id BETWEEN ? AND ?", (LOW, HIGH))
    db.execute("DELETE FROM apartment WHERE id BETWEEN ? AND ?", (LOW, HIGH))
    db.execute("DELETE FROM legal_entity WHERE id BETWEEN ? AND ?", (LOW, HIGH))
    db.execute("DELETE FROM user_account WHERE id BETWEEN ? AND ?", (LOW, HIGH))


@pytest.fixture
def world():
    db.init_db()
    wipe()
    # Open system alerts left by other tests show on every workspace; hold
    # them while the cases run so the golden does not depend on test order.
    marks = ", ".join("?" for _ in alerts.SYSTEM_ALERT_KINDS)
    db.execute(
        f"UPDATE alert SET resolved_at = ? WHERE resolved_at IS NULL AND kind IN ({marks})",
        (HOLD, *sorted(alerts.SYSTEM_ALERT_KINDS)),
    )
    for table in TABLES:
        for row in CASES["seed"][table]:
            insert(table, row)
    yield
    wipe()
    db.execute("UPDATE alert SET resolved_at = NULL WHERE resolved_at = ?", (HOLD,))


def render_case(case):
    client = TestClient(app, follow_redirects=False)
    if case["user"]:
        client.cookies.set(
            auth.SESSION_COOKIE, auth.issue_session(case["user"], 1, workspace_user_id=case.get("as"))
        )
    client.cookies.set("ubyhost_lang", case["lang"])
    response = client.get(case["path"])
    body = response.text if response.status_code == 200 else ""
    title = TITLE.search(body)
    return {
        "name": case["name"],
        "status": response.status_code,
        "location": response.headers.get("location", ""),
        "title": squash(title.group(1)) if title else "",
        "items": extract_items(body),
    }


def test_go_lists_match_python(world):
    observed = [render_case(case) for case in CASES["cases"]]
    text = "[\n" + ",\n".join(json.dumps(x, ensure_ascii=False, sort_keys=True) for x in observed) + "\n]\n"
    if os.environ.get("UBYHOST_WRITE_GOLDEN") == "1":
        GOLDEN.write_text(text, encoding="utf-8")
    assert GOLDEN.exists(), "run once with UBYHOST_WRITE_GOLDEN=1"
    assert json.loads(GOLDEN.read_text(encoding="utf-8")) == json.loads(text)


def test_cases_cover_the_brief():
    """Every page has an en, a cs and a vi case, an admin-inside case and a
    signed-out case; the not-ported cases are the three of the brief."""
    names = {c["name"]: c for c in CASES["cases"]}
    for page in ("/entities", "/apartments"):
        mine = [c for c in CASES["cases"] if c["path"].split("?")[0] == page]
        assert {c["lang"] for c in mine} == {"en", "cs", "vi"}
        assert any(c.get("as") for c in mine) and any(not c["user"] for c in mine)
    assert sorted(n for n, c in names.items() if c.get("go")) == [
        "apartments_rows_not_ported",
        "entities_alert_not_ported",
    ]
