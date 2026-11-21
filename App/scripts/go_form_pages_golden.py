"""Write go/internal/web/guest/testdata/form_pages_golden.json from the real Python.

Brief 1723. Run from App/ (throwaway SQLite; no production data):

    .venv/bin/python scripts/go_form_pages_golden.py
    .venv/bin/python scripts/go_form_pages_golden.py --check

Seeds made-up rows, walks claim + the five GET/POST routes in scope, and stores
status, Location, and guest-page visible lines (g-wrap) per case. The Go test
replays the same seed on PostgreSQL. Keep visible_lines() in step with
formPagesVisibleLines in go/internal/web/guest/form_pages_test.go.
"""

from __future__ import annotations

import base64
import html
import json
import os
import re
import sys
import tempfile
import time
from datetime import date, timedelta
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
OUT = APP.parent / "go" / "internal" / "web" / "guest" / "testdata" / "form_pages_golden.json"

TOKEN = "formpagesgolden"
PIN_TOKEN = "formpagespin"
STAMP = "2026-06-01T12:00:00+00:00"
TODAY = date(2026, 6, 10)

DROP = [re.compile(p, re.S | re.I) for p in (
    r"<!--.*?-->", r"<script\b.*?</script>", r"<style\b.*?</style>", r"<svg\b.*?</svg>")]
TOKEN_RE = re.compile(r"<[^>]*>|[^<]+")
TAG = re.compile(r"^<[ \t\n\r\f\v]*(/?)([A-Za-z][A-Za-z0-9]*)")
ATTR = re.compile(
    r"""([^ \t\n\r\f\v=/>"']+)(?:[ \t\n\r\f\v]*=[ \t\n\r\f\v]*(?:"([^"]*)"|'([^']*)'|([^ \t\n\r\f\v>"']+)))?""")
SPACE = re.compile(r"[ \t\n\r\f\v]+")
KEPT = {"id", "href", "action", "method", "name", "value", "type", "selected", "checked", "required", "for",
        "aria-current", "class", "aria-label", "aria-controls", "formaction", "formnovalidate", "lang", "hreflang"}


def visible_lines(page: str) -> list[str]:
    idx = page.find('class="g-wrap'); start = page.rfind('<div', 0, idx) if idx >= 0 else -1
    if start < 0:
        return []
    page = page[start:]
    end = page.find('<div class="g-page-skeleton"')
    if end >= 0:
        page = page[:end]
    for pattern in DROP:
        page = pattern.sub("", page)
    out = []
    for tok in TOKEN_RE.findall(page):
        if not tok.startswith("<"):
            text = SPACE.sub(" ", html.unescape(tok)).strip(" ")
            if text:
                out.append(text)
            continue
        m = TAG.match(tok)
        if not m or m.group(1) == "/":
            continue
        name = m.group(2).lower()
        attrs = {}
        for a in ATTR.finditer(tok[m.end():]):
            key = a.group(1).lower()
            has_value = "=" in a.group(0)
            value = html.unescape((a.group(2) or "") + (a.group(3) or "") + (a.group(4) or ""))
            if key == "class":
                value = " ".join(value.split())
            attrs[key] = (has_value, value)
        if attrs.get("name", (False, ""))[1] == "_csrf":
            attrs["value"] = (True, "*")
        if attrs.get("content", (False, ""))[1] and name == "meta" and attrs.get("name", (False, ""))[1] == "csrf-token":
            attrs["content"] = (True, "*")
        parts = [k + ("=" + v if has else "") for k, (has, v) in sorted(attrs.items()) if k in KEPT]
        if parts:
            out.append("<" + name + " " + " ".join(parts) + ">")
    return out


def _png_data_url() -> str:
    return (
        "data:image/png;base64,"
        + base64.b64encode(
            bytes.fromhex(
                "89504e470d0a1a0a0000000d49484452000000140000001408060000008b89"
                "a8060000000a4944415478da6300010000050001ff03ac820000000049454e"
                "44ae426082"
            )
        ).decode("ascii")
    )


def _seed(db) -> tuple[int, int, int, int]:
    entity_id = db.insert("legal_entity", {"name": "Form Pages Golden", "created_at": STAMP})
    apt_id = db.insert(
        "apartment",
        {
            "legal_entity_id": entity_id,
            "internal_name": "Golden flat",
            "uby_name": "Golden Stay",
            "permalink_token": TOKEN,
            "permalink_window_days": 30,
            "default_purpose": "10",
            "passport_photo_policy": "off",
            "automation_mode": "manual",
            "active": 1,
            "created_at": STAMP,
        },
    )
    apt_pin_id = db.insert(
        "apartment",
        {
            "legal_entity_id": entity_id,
            "internal_name": "PIN flat",
            "uby_name": "PIN Stay",
            "permalink_token": PIN_TOKEN,
            "permalink_pin": "2468",
            "permalink_window_days": 30,
            "default_purpose": "10",
            "passport_photo_policy": "required_foreign",
            "automation_mode": "manual",
            "active": 1,
            "created_at": STAMP,
        },
    )
    stay_id = db.insert(
        "reservation",
        {
            "apartment_id": apt_id,
            "uid": "golden-stay-1",
            "date_from": TODAY.isoformat(),
            "date_to": (TODAY + timedelta(days=2)).isoformat(),
            "declared_guests": 2,
            "status": "active",
            "source": "manual",
            "created_at": STAMP,
            "updated_at": STAMP,
        },
    )
    stay_pin_id = db.insert(
        "reservation",
        {
            "apartment_id": apt_pin_id,
            "uid": "golden-stay-pin",
            "date_from": TODAY.isoformat(),
            "date_to": (TODAY + timedelta(days=2)).isoformat(),
            "declared_guests": 1,
            "status": "active",
            "source": "manual",
            "created_at": STAMP,
            "updated_at": STAMP,
        },
    )
    adult_id = db.insert(
        "guest",
        {
            "reservation_id": stay_id,
            "first_name": "Jan",
            "surname": "Novak",
            "birth_date": "01011990",
            "nationality": "DEU",
            "doc_number": "C01X00T47",
            "res_street": "Hauptstr. 1",
            "res_city": "Berlin",
            "res_country": "DEU",
            "purpose": "10",
            "submit_state": "pending",
            "entered_by": "guest",
            "created_at": STAMP,
            "updated_at": STAMP,
        },
    )
    minor_id = db.insert(
        "guest",
        {
            "reservation_id": stay_id,
            "first_name": "Ana",
            "surname": "Novak",
            "birth_date": "01012015",
            "nationality": "DEU",
            "doc_number": "INPASS",
            "purpose": "10",
            "submit_state": "pending",
            "entered_by": "guest",
            "created_at": STAMP,
            "updated_at": STAMP,
        },
    )
    foreign_id = db.insert(
        "guest",
        {
            "reservation_id": stay_pin_id,
            "first_name": "John",
            "surname": "Smith",
            "birth_date": "15061980",
            "nationality": "GBR",
            "doc_number": "P1234567",
            "visa_number": "V 123",
            "res_street": "Baker Street 221B",
            "res_city": "London",
            "res_country": "GBR",
            "purpose": "10",
            "submit_state": "pending",
            "entered_by": "guest",
            "created_at": STAMP,
            "updated_at": STAMP,
        },
    )
    return stay_id, stay_pin_id, adult_id, minor_id, foreign_id


def _prime_client(client, owned_ids: list[int] | None = None) -> None:
    """Guest form routes need CSRF meta from guest/base.html and optional owned ids."""
    from app.routes import guest as guest_routes
    from tests.conftest import csrf_token_for

    csrf_token_for(client)
    if owned_ids:
        client.cookies.set(
            guest_routes.OWNED_COOKIE,
            guest_routes._serializer().dumps(sorted({int(i) for i in owned_ids})),
        )



def _form_csrf(page: str) -> str:
    m = re.search(r'name="_csrf"[^>]*value="([^"]*)"', page)
    if not m:
        m = re.search(r'value="([^"]*)"[^>]*name="_csrf"', page)
    return m.group(1) if m else ""


def _case(name: str, method: str, path: str, *, client, lang: str = "en") -> dict:
    client.cookies.set("ubyhost_lang", lang)
    response = client.request(method, path, follow_redirects=False)
    body = response.text if response.status_code == 200 else ""
    return {
        "name": name,
        "method": method,
        "path": path,
        "lang": lang,
        "status": response.status_code,
        "location": response.headers.get("location") or "",
        "lines": visible_lines(body),
    }


def render() -> str:
    from fastapi.testclient import TestClient

    from app import config, db
    from app.main import app

    config.GUEST_PIN_REQUIRED = False
    db.init_db()
    db.execute("DELETE FROM guest")
    db.execute("DELETE FROM reservation")
    db.execute("DELETE FROM apartment")
    db.execute("DELETE FROM legal_entity WHERE name = ?", ("Form Pages Golden",))
    stay_id, stay_pin_id, adult_id, minor_id, foreign_id = _seed(db)
    client = TestClient(app)
    _prime_client(client, [adult_id, minor_id, foreign_id])

    cases = [
        _case("new_en", "GET", f"/l/{TOKEN}/{stay_id}/new?lang=en", client=client),
        _case("new_cs", "GET", f"/l/{TOKEN}/{stay_id}/new?lang=cs", client=client, lang="cs"),
        _case("edit_adult", "GET", f"/l/{TOKEN}/{stay_id}/edit/{adult_id}?lang=en", client=client),
        _case("edit_minor", "GET", f"/l/{TOKEN}/{stay_id}/edit/{minor_id}?lang=en", client=client),
        _case("edit_foreigner", "GET", f"/l/{PIN_TOKEN}/{stay_pin_id}/edit/{foreign_id}?lang=en", client=client),
        _case("remove_confirm", "GET", f"/l/{TOKEN}/{stay_id}/remove/{adult_id}?lang=en", client=client),
    ]
    from app.routes import guest as guest_routes
    from tests.conftest import csrf_token_for

    owned_val = client.cookies.get(guest_routes.OWNED_COOKIE, "")
    remove_page = client.get(f"/l/{TOKEN}/{stay_id}/remove/{minor_id}?lang=en")
    csrf = _form_csrf(remove_page.text)
    remove = client.post(
        f"/l/{TOKEN}/{stay_id}/remove/{minor_id}?lang=en",
        data={},
        cookies={guest_routes.OWNED_COOKIE: owned_val, "ubyhost_lang": "en"},
        follow_redirects=False,
    )
    cases.append({
        "name": "remove_post",
        "method": "POST",
        "path": f"/l/{TOKEN}/{stay_id}/remove/{minor_id}",
        "lang": "en",
        "status": remove.status_code,
        "location": remove.headers.get("location") or "",
        "lines": [],
    })
    form_page = client.get(f"/l/{TOKEN}/{stay_id}/new?lang=cs")
    csrf = _form_csrf(form_page.text)
    relang = client.post(
        f"/l/{TOKEN}/{stay_id}/relang?lang=cs",
        data={
            "surname": "Novak",
            "first_name": "Jan",
            "birth_date": "1.1.1990",
            "nationality": "DEU",
            "doc_number": "C01X00T47",
            "res_street": "Hauptstr. 1",
            "res_city": "Berlin",
            "res_country": "DEU",
            "purpose": "10",
            "legal_ack": "1",
            "party_size": "1",
        },
        cookies={guest_routes.OWNED_COOKIE: owned_val, "ubyhost_lang": "cs"},
        follow_redirects=False,
    )
    cases.append({
        "name": "relang_cs",
        "method": "POST",
        "path": f"/l/{TOKEN}/{stay_id}/relang",
        "lang": "cs",
        "status": relang.status_code,
        "location": relang.headers.get("location") or "",
        "lines": visible_lines(relang.text) if relang.status_code == 200 else [],
    })

    golden = {
        "now": STAMP,
        "token": TOKEN,
        "pin_token": PIN_TOKEN,
        "stay_id": stay_id,
        "stay_pin_id": stay_pin_id,
        "adult_id": adult_id,
        "minor_id": minor_id,
        "foreign_id": foreign_id,
        "cases": cases,
    }
    return json.dumps(golden, ensure_ascii=False, indent=1, sort_keys=True) + "\n"


def main(argv: list[str]) -> int:
    text = render()
    if "--check" in argv:
        if OUT.exists() and OUT.read_text(encoding="utf-8") == text:
            return 0
        print(f"stale: {OUT}; run scripts/go_form_pages_golden.py", file=sys.stderr)
        return 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text, encoding="utf-8")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    tmp = Path(tempfile.mkdtemp(prefix="ubyhost-form-pages-golden-"))
    os.environ.setdefault("UBYHOST_DATA_DIR", str(tmp))
    os.environ.setdefault("UBYHOST_DB", str(tmp / "form_pages_golden.sqlite3"))
    os.environ.setdefault("UBYHOST_SECRET_KEY", "golden-secret-key-not-for-real-use")
    os.environ.setdefault("UBYHOST_ENABLE_SCHEDULER", "0")
    os.environ.setdefault("UBYHOST_BOOTSTRAP_ADMIN", "0")
    os.environ["UBYHOST_PUBLIC_BASE_URL"] = "https://golden.example.test"
    os.environ["UBYHOST_GUEST_PIN_REQUIRED"] = "0"
    os.environ["UBYHOST_MAIL_BACKEND"] = "off"
    sys.path.insert(0, str(APP))
    sys.exit(main(sys.argv[1:]))