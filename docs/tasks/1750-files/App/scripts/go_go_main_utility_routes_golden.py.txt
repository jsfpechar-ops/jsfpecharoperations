"""Golden HTTP responses for main.py utility routes (brief 1750).

Run from App/:

    .venv/bin/python scripts/go_go_main_utility_routes_golden.py
    .venv/bin/python scripts/go_go_main_utility_routes_golden.py --check

Writes go/internal/web/public/testdata/utility_golden.json. The Go test replays
the same seed on PostgreSQL when UBYHOST_TEST_DATABASE_URL is set.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest import mock

APP = Path(__file__).resolve().parents[1]
OUT = APP.parent / "go" / "internal" / "web" / "public" / "testdata" / "utility_golden.json"

_TMP = Path(tempfile.mkdtemp(prefix="utility-golden-"))
os.environ.pop("UBYHOST_DATABASE_URL", None)
os.environ.update(
    {
        "UBYHOST_DATA_DIR": str(_TMP),
        "UBYHOST_DB": str(_TMP / "golden.db"),
        "UBYHOST_SECRET_KEY": "utility-golden-secret-not-real-0123456789",
        "UBYHOST_ENABLE_SCHEDULER": "0",
        "UBYHOST_BOOTSTRAP_ADMIN": "0",
        "UBYHOST_UBYPORT_ENV": "mock",
        "UBYHOST_MAIL_BACKEND": "console",
        "UBYHOST_PUBLIC_BASE_URL": "https://golden.example.test",
        "UBYHOST_DEPLOYMENT": "local",
    }
)
sys.path.insert(0, str(APP))

from fastapi.testclient import TestClient  # noqa: E402

from app import config, db, security  # noqa: E402
from app.main import app  # noqa: E402

STAMP = "2026-01-01T00:00:00+00:00"

SEED = [
    {
        "table": "user_account",
        "columns": ["id", "username", "password_hash", "role", "created_at"],
        "rows": [[1, "host@example.test", "x", "host", STAMP]],
    },
    {
        "table": "apartment",
        "columns": ["id", "owner_user_id", "internal_name", "active", "created_at"],
        "rows": [[101, 1, "Golden flat", 1, STAMP]],
    },
    {
        "table": "property_page",
        "columns": ["apartment_id", "published", "published_at", "hide_from_search", "created_at", "updated_at"],
        "rows": [[101, 1, "2026-01-15", 0, STAMP, STAMP]],
    },
    {
        "table": "property_slug",
        "columns": ["apartment_id", "slug", "published", "published_at", "created_at", "updated_at"],
        "rows": [[101, "garden-loft-abc123", 1, "2026-01-15", STAMP, STAMP]],
    },
]

# Headers we compare; omitted keys mean the golden expects an empty string.
HEADER_KEYS = (
    "content-type",
    "cache-control",
    "content-language",
    "x-robots-tag",
    "service-worker-allowed",
    "location",
)


def _headers(response) -> dict[str, str]:
    out = {}
    for key in HEADER_KEYS:
        val = response.headers.get(key, "")
        if val:
            out[key] = val
    return out


def _cookie_fields(header: str) -> dict:
    parts = [p.strip() for p in header.split(";")]
    name, _, value = parts[0].partition("=")
    out = {"name": name, "value": value, "path": "", "max_age": "", "samesite": "", "secure": False, "httponly": False}
    for attr in parts[1:]:
        key, _, val = attr.partition("=")
        key = key.strip().lower()
        if key == "path":
            out["path"] = val
        elif key == "max-age":
            out["max_age"] = val
        elif key == "samesite":
            out["samesite"] = val.lower()
        elif key == "secure":
            out["secure"] = True
        elif key == "httponly":
            out["httponly"] = True
    return out


def _apply_seed() -> None:
    db.init_db()
    for block in SEED:
        cols = ", ".join(block["columns"])
        placeholders = ", ".join("?" * len(block["columns"]))
        sql = f"INSERT INTO {block['table']} ({cols}) VALUES ({placeholders})"
        for row in block["rows"]:
            db.execute(sql, row)


def _client() -> TestClient:
    return TestClient(app, base_url="https://golden.example.test")


def _record(name: str, method: str, path: str, **kwargs) -> dict:
    client = _client()
    if method == "GET":
        response = client.get(path, **kwargs)
    else:
        response = client.post(path, **kwargs)
    cookies = [
        _cookie_fields(h)
        for h in response.headers.get_list("set-cookie")
        if h.lower().startswith("ubyhost_lang=")
    ]
    body = response.content
    if response.headers.get("content-type", "").startswith("application/json") and body:
        # Manifest JSON: compact like Python json.dumps without spaces after separators.
        pass
    entry = {
        "name": name,
        "method": method,
        "path": path,
        "status": response.status_code,
        "headers": _headers(response),
        "set_cookies": cookies,
        "body": body.decode("utf-8") if body else "",
    }
    if "follow_redirects" in kwargs and not kwargs["follow_redirects"]:
        entry["body"] = ""
    return entry


def _csrf_post(path: str, data: dict) -> dict:
    import re

    client = _client()
    warm = client.get("/login?lang=en")
    m = re.search(r'name="csrf-token" content="([^"]+)"', warm.text)
    token = m.group(1) if m else ""
    headers = {security.CSRF_HEADER: token} if token else {}
    data = {**data, "_csrf": token}
    response = client.post(path, data=data, headers=headers, follow_redirects=False)
    cookies = [
        _cookie_fields(h)
        for h in response.headers.get_list("set-cookie")
        if h.lower().startswith("ubyhost_lang=")
    ]
    return {
        "name": "post-language-cs",
        "method": "POST",
        "path": path,
        "status": response.status_code,
        "headers": _headers(response),
        "set_cookies": cookies,
        "body": "",
    }


def build() -> dict:
    _apply_seed()
    cases = [
        _record("robots", "GET", "/robots.txt"),
        _record("tdmrep", "GET", "/.well-known/tdmrep.json"),
        _record("manifest", "GET", "/manifest.webmanifest"),
        _record("sw", "GET", "/sw.js"),
        _record("sitemap", "GET", "/sitemap.xml"),
        _record("favicon", "GET", "/favicon.ico", follow_redirects=False),
    ]
    for lang in ("en", "cs", "vi"):
        cases.append(_record(f"offline-{lang}", "GET", f"/offline?lang={lang}"))
    cases.append(
        _csrf_post("/language", {"lang": "cs", "next": "/login?lang=en"}),
    )
    return {"public_base_url": "https://golden.example.test", "seed": SEED, "cases": cases}


def main(argv: list[str]) -> int:
    check = "--check" in argv
    payload = json.dumps(build(), ensure_ascii=False, indent=1) + "\n"
    if check:
        if not OUT.exists() or OUT.read_text(encoding="utf-8") != payload:
            print(f"stale: {OUT}")
            return 1
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(payload, encoding="utf-8")
    print(f"wrote {OUT.relative_to(APP.parent)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))