"""FE-4: one inventory backs the public cookie table, and nothing is set without it.

The test greps the app for `set_cookie(` and `localStorage.setItem(` and fails
when a cookie or storage key is set that has no row in `cookie_inventory`. It
also pins the lifetimes to the constants in code, so the published table cannot
drift from what is set.
"""
from __future__ import annotations

import re
from pathlib import Path

from starlette.testclient import TestClient

from app import auth, cookie_inventory, db, host_i18n, security
from app.main import app

APP = Path(__file__).resolve().parents[1] / "app"

_ASSIGN = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*[\"']([^\"']+)[\"']", re.M)
_SET_COOKIE = re.compile(r"set_cookie\(\s*([A-Za-z_][A-Za-z0-9_]*)")
_JS_ASSIGN = re.compile(r"(?:var|const|let)\s+([A-Za-z_$][\w$]*)\s*=\s*[\"']([^\"']+)[\"']")
_JS_SET = re.compile(r"localStorage\.setItem\(\s*([A-Za-z_$][\w$]*)")


def _python_constants() -> dict:
    values = {}
    for path in APP.rglob("*.py"):
        for name, value in _ASSIGN.findall(path.read_text(encoding="utf-8")):
            values.setdefault(name, value)
    return values


def test_every_set_cookie_names_a_declared_inventory_row():
    declared = set(cookie_inventory.names())
    constants = _python_constants()
    seen = set()
    for path in APP.rglob("*.py"):
        for identifier in _SET_COOKIE.findall(path.read_text(encoding="utf-8")):
            name = constants.get(identifier, identifier)
            seen.add(name)
            assert name in declared, f"{path.name} sets undeclared cookie {name}"
    assert seen, "the set_cookie scan found nothing"


def test_every_local_storage_key_is_declared():
    declared = set(cookie_inventory.names())
    for path in (APP / "static").glob("*.js"):
        source = path.read_text(encoding="utf-8")
        keys = dict(_JS_ASSIGN.findall(source))
        for identifier in _JS_SET.findall(source):
            name = keys.get(identifier, identifier)
            assert name in declared, f"{path.name} writes undeclared storage {name}"


def test_the_published_lifetimes_match_the_code_constants():
    rows = {row["name"]: row for row in cookie_inventory.COOKIE_INVENTORY}
    assert "180" in rows["ubyhost_lang"]["lifetime"]["en"]
    assert host_i18n.LANG_COOKIE_MAX_AGE == 60 * 60 * 24 * 180
    assert "7 days" in rows["ubyhost_pin"]["lifetime"]["en"]
    assert auth._PIN_MAX_AGE == 60 * 60 * 24 * 7
    assert "30 days" in rows["ubyhost_session"]["lifetime"]["en"]
    assert auth.SESSION_REMEMBER_MAX_AGE == 60 * 60 * 24 * 30
    assert "30 days" in rows["ubyhost_csrf"]["lifetime"]["en"]
    assert security.CSRF_MAX_AGE == auth.SESSION_REMEMBER_MAX_AGE
    for name in ("ubyhost_owned", "ubyhost_claim", "ubyhost_guest_lang"):
        assert "60 days" in rows[name]["lifetime"]["en"]


def test_the_inventory_is_fully_translated():
    for row in cookie_inventory.COOKIE_INVENTORY:
        for field in ("purpose", "lifetime"):
            assert row[field]["en"] and row[field]["cs"], (row["name"], field)
            assert row[field]["en"] != row[field]["cs"], (row["name"], field)


def test_the_public_privacy_page_lists_every_inventory_name():
    """The published table is the full inventory, not a surface subset."""
    db.init_db()
    html = TestClient(app).get("/privacy?lang=en").text
    for name in cookie_inventory.names():
        assert name in html, f"{name} is missing from the public cookie table"
    assert "ubyhost_session" in html
