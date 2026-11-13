"""Content parity of the Go property GET pages with admin.py (brief 1301).

go/internal/web/properties/testdata/pages_cases.json holds a seed and the
cases (path, host, language, the env the case runs with). This test renders
each case on the Python routes and records status, Location, <title> and the
items of the page content (the div.ui-page element: every tag with its
attributes and every text run) into pages_golden.json; the Go test renders
the same cases and compares. The shell (nav, banners, alerts) is the layout's
test, not this one. To rewrite the golden after a deliberate template change:

    UBYHOST_WRITE_GOLDEN=1 .venv/bin/python -m pytest tests/test_go_properties_pages.py -q

The extraction below is mirrored by extractItems in pages_test.go; keep both
the same.
"""
from __future__ import annotations

import html
import json
import os
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import auth, config, db
from app.main import app

REPO = Path(__file__).resolve().parents[2]
DATA = REPO / "go" / "internal" / "web" / "properties" / "testdata"
CASES = json.loads((DATA / "pages_cases.json").read_text(encoding="utf-8"))
GOLDEN = DATA / "pages_golden.json"
LOW, HIGH = 131000, 131999

TOKEN = re.compile(r"<!--.*?-->|<[^>]*>|[^<]+", re.S)
ATTR = re.compile(r"""([^\s=/>"']+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>"']+)))?""")
SPACE = re.compile(r"[ \t\n\r\f]+")
TITLE = re.compile(r"<title>(.*?)</title>", re.S)
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}


def squash(text: str) -> str:
    return SPACE.sub(" ", html.unescape(text)).strip(" ")


def extract_items(body: str) -> list:
    """The div.ui-page element as a list of items: '<tag a=v ...>' with the
    attributes sorted, '</tag>' and the text runs, all whitespace-squashed."""
    start = body.find('<div class="ui-page"')
    if start < 0:
        return []
    items, depth = [], 0
    for m in TOKEN.finditer(body, start):
        tok = m.group(0)
        if tok.startswith("<!--"):
            continue
        if not tok.startswith("<"):
            text = squash(tok)
            if text:
                items.append(text)
            continue
        if tok.startswith("</"):
            name = tok[2:-1].strip().lower()
            items.append("</" + name + ">")
            if name == "div":
                depth -= 1
                if depth == 0:
                    break
            continue
        inner = tok[1:-1].rstrip("/").strip()
        name, _, rest = inner.partition(" ")
        name = name.lower()
        attrs = {}
        for a in ATTR.finditer(rest):
            key = a.group(1).lower()
            value = next((g for g in a.groups()[1:] if g is not None), None)
            attrs[key] = None if value is None else squash(value)
        if name == "input" and attrs.get("name") == "_csrf":
            attrs["value"] = "<csrf>"
        parts = [k if v is None else f"{k}={v}" for k, v in sorted(attrs.items())]
        items.append("<" + " ".join([name] + parts) + ">")
        if name == "div":
            depth += 1
    return items


# env names of the cases -> the config attributes the Python code reads.
def apply_env(monkeypatch, env: dict) -> None:
    def names(value):
        return frozenset(p.strip().lower() for p in value.split(",") if p.strip())

    monkeypatch.setattr(config, "AI_FEATURES", names(env.get("UBYHOST_AI_FEATURES", "")))
    monkeypatch.setattr(config, "AI_TEST_EMAILS", names(env.get("UBYHOST_AI_TEST_EMAILS", "")))
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", env.get("UBYHOST_ANTHROPIC_API_KEY", ""))
    monkeypatch.setattr(config, "AI_PROVIDER", "anthropic")
    monkeypatch.setattr(config, "UBYPORT_ENV", env.get("UBYHOST_UBYPORT_ENV", "mock").lower())


def insert(table, row):
    cols = list(row)
    db.execute(
        f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})",
        [row[c] for c in cols],
    )


def wipe():
    db.execute("DELETE FROM apartment WHERE id BETWEEN ? AND ?", (LOW, HIGH))
    db.execute("DELETE FROM user_account WHERE id BETWEEN ? AND ?", (LOW, HIGH))


@pytest.fixture
def world():
    db.init_db()
    wipe()
    for table in ("user_account", "apartment"):
        for row in CASES["seed"][table]:
            insert(table, row)
    yield
    wipe()


def render_case(case, monkeypatch):
    apply_env(monkeypatch, case["env"])
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


def test_go_pages_match_python(world, monkeypatch):
    observed = []
    for case in CASES["cases"]:
        with monkeypatch.context() as m:
            observed.append(render_case(case, m))
    text = "[\n" + ",\n".join(json.dumps(x, ensure_ascii=False, sort_keys=True) for x in observed) + "\n]\n"
    if os.environ.get("UBYHOST_WRITE_GOLDEN") == "1":
        GOLDEN.write_text(text, encoding="utf-8")
    assert GOLDEN.exists(), "run once with UBYHOST_WRITE_GOLDEN=1"
    assert json.loads(GOLDEN.read_text(encoding="utf-8")) == json.loads(text)


def test_extract_items_scope():
    page = '<p>out</p><div class="ui-page" data-x><div>a &amp; b</div><input name="_csrf" value="t" hidden></div><p>after</p>'
    assert extract_items(page) == [
        "<div class=ui-page data-x>", "<div>", "a & b", "</div>", "<input hidden name=_csrf value=<csrf>>", "</div>",
    ]
