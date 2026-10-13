"""0101: no internal link points at a removed or missing route.

The owner removed every old adapter (2026-10-13: "get rid of all the old
links"). This renders the main host pages for one fixture host and checks
that every same-origin ``href`` answers below 400 and every form ``action`` /
``formaction`` names a route that exists for its method. It also checks that
the removed paths appear nowhere in ``App/app`` and that the one kept
redirect (``/guest-links``, linked from lifecycle e-mails already sent) works.
"""
from __future__ import annotations

import re
import secrets
from datetime import timedelta
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from fastapi.testclient import TestClient
from starlette.routing import Match

from app import auth, claim, config, db, mail_notify
from app.main import app
from tests.conftest import login_as
from tests.invoice_stay_helper import stay_form

APP_DIR = Path(__file__).resolve().parents[1] / "app"

# Removed in 0101. Each pattern must match nowhere under App/app.
REMOVED_PATTERNS = {
    "/invoices/settings": re.compile(r"/invoices/settings"),
    "/stay-fees/{id}/setup": re.compile(r"/stay-fees/[^\"'\s]*/setup"),
    "/apartments/{id}/ws-request.txt": re.compile(r"ws-request"),
    "/automation": re.compile(r"[\"'](?:\{\{ *[a-z_]+ *\}\})?/automation[\"'?#]"),
    "/setup, /setup/<step>": re.compile(r"[\"']\/setup[\"']"),
    "setup_wizard module": re.compile(r"routes/setup_wizard"),
    "app.js old-hash table": re.compile(r"var HASHES\s*="),
}


class _Links(HTMLParser):
    """Links (GET) and form targets (method, path) of one rendered page."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links: list[str] = []
        self.targets: list[tuple[str, str]] = []
        self._form_method: list[str] = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ("a", "link") and a.get("href"):
            self.links.append(a["href"])
        if tag == "form":
            method = (a.get("method") or "get").upper()
            self._form_method.append(method)
            if a.get("action"):
                self.targets.append((method, a["action"]))
        if tag in ("button", "input") and a.get("formaction"):
            method = (a.get("formmethod") or (self._form_method[-1] if self._form_method else "GET")).upper()
            self.targets.append((method, a["formaction"]))

    def handle_endtag(self, tag):
        if tag == "form" and self._form_method:
            self._form_method.pop()


def _local_path(url: str) -> str | None:
    """The path of a same-origin URL, or None for fragments, other origins and schemes."""
    url = url.strip()
    base = config.PUBLIC_BASE_URL.rstrip("/")
    if base and url.startswith(base + "/"):
        url = url[len(base):]
    if not url.startswith("/") or url.startswith("//"):
        return None
    return url


def _route_exists(path: str, method: str) -> bool:
    scope = {"type": "http", "path": path, "method": method, "root_path": "",
             "query_string": b"", "headers": []}
    return any(route.matches(scope)[0] == Match.FULL for route in app.routes)


def _purge(owner_id: int) -> None:
    db.execute("INSERT INTO settings (key, value) VALUES ('invoice_purge_unlock', '1') "
               "ON CONFLICT(key) DO UPDATE SET value = '1'")
    db.execute("DELETE FROM invoice_item WHERE invoice_id IN (SELECT id FROM invoice WHERE owner_user_id = ?)",
               (owner_id,))
    db.execute("DELETE FROM invoice WHERE owner_user_id = ?", (owner_id,))
    db.execute("INSERT INTO settings (key, value) VALUES ('invoice_purge_unlock', '') "
               "ON CONFLICT(key) DO UPDATE SET value = ''")
    db.execute("DELETE FROM guest WHERE reservation_id IN (SELECT r.id FROM reservation r "
               "JOIN apartment a ON a.id = r.apartment_id WHERE a.owner_user_id = ?)", (owner_id,))
    db.execute("DELETE FROM reservation WHERE apartment_id IN (SELECT id FROM apartment WHERE owner_user_id = ?)",
               (owner_id,))
    db.execute("DELETE FROM apartment_slug WHERE apartment_id IN (SELECT id FROM apartment WHERE owner_user_id = ?)",
               (owner_id,))
    db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (owner_id,))
    db.execute("DELETE FROM invoice_sequence WHERE legal_entity_id IN "
               "(SELECT id FROM legal_entity WHERE owner_user_id = ?)", (owner_id,))
    db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (owner_id,))
    for table in ("audit", "alert", "email_outbox"):
        db.execute(f"DELETE FROM {table} WHERE owner_user_id = ?", (owner_id,))
    db.execute("DELETE FROM user_account WHERE id = ?", (owner_id,))


@pytest.fixture(scope="module")
def world():
    db.init_db()
    username = f"deadlinks-{secrets.token_hex(3)}"
    owner_id = auth.create_account(f"{username}@example.test", "Dead Links Host", role="host", username=username)
    now = db.utcnow()
    entity_id = db.insert("legal_entity", {
        "name": "Odkazy s.r.o.", "seat": "Praha 1", "ico": "04656679",
        "contact_email": "odkazy@example.test", "bank_account": "19-2000781379/0800",
        "iban": "CZ6508000000192000781379", "registry_entry": "Fyzická osoba zapsaná v živnostenském rejstříku",
        "vat_status": "non_payer", "invoice_due_days": 14, "owner_user_id": owner_id, "created_at": now,
    })
    apartment_id = db.insert("apartment", {
        "internal_name": "Byt Odkazy", "owner_user_id": owner_id, "legal_entity_id": entity_id,
        "addr_obec": "Praha", "addr_street": "Synthetic", "addr_house_no": "1", "addr_zip": "11000",
        "permalink_token": f"dl{secrets.token_hex(5)}", "permalink_pin": "123456",
        "automation_mode": "manual", "default_purpose": "10", "active": 1,
        "stay_fee_rate_czk": 50, "stay_fee_cadence": "monthly", "stay_fee_vs": "123456",
        "stay_fee_authority_name": "Městský úřad", "created_at": now,
    })
    today = claim.prague_today()
    reservation_id = db.insert("reservation", {
        "apartment_id": apartment_id, "source": "manual", "uid": f"deadlinks-{secrets.token_hex(4)}",
        "date_from": (today - timedelta(days=4)).isoformat(),
        "date_to": (today - timedelta(days=1)).isoformat(),
        "status": "active", "created_at": now, "updated_at": now,
    })
    guest_id = db.insert("guest", {
        "reservation_id": reservation_id, "first_name": "Synthetic", "surname": "Guest",
        "birth_date": "01011990", "nationality": "DEU", "created_at": now, "updated_at": now,
    })
    client = TestClient(app)
    assert login_as(client, username, url="/login?lang=en", follow_redirects=False).status_code == 303
    issued = client.post("/invoices", data={"buyer_name": "Buyer", "lang": "cs", "already_paid": "1",
                                            **stay_form(reservation_id)}, follow_redirects=False)
    assert issued.status_code == 303, issued.text
    invoice_id = int(issued.headers["location"].split("?")[0].rsplit("/", 1)[1])
    month = (today.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
    try:
        yield {
            "client": client, "owner": owner_id, "entity": entity_id, "apartment": apartment_id,
            "reservation": reservation_id, "guest": guest_id, "invoice": invoice_id, "month": month,
        }
    finally:
        _purge(owner_id)


def _pages(w) -> list[str]:
    p = f"/apartments/{w['apartment']}"
    return [
        "/", "/reservations", f"/reservations/{w['reservation']}", f"/guests/{w['guest']}",
        "/apartments", p, f"{p}?view=overview", f"{p}?view=bookings",
        *(f"{p}?view=settings&section={s}" for s in ("property", "guests", "reporting", "lock", "automation")),
        "/entities", f"/entities?edit={w['entity']}", "/invoices", "/invoices/new",
        f"/invoices/new?reservation_id={w['reservation']}&entity={w['entity']}", f"/invoices/{w['invoice']}",
        "/stay-fees", f"/stay-fees/{w['apartment']}?month={w['month']}",
        "/submissions", "/housebook", "/settings", "/settings/archived", "/guide", "/onboarding",
    ]


def test_every_internal_link_and_form_target_resolves(world):
    client = world["client"]
    links: dict[str, str] = {}
    bad_targets: list[tuple[str, str, str, str]] = []
    for page_path in _pages(world):
        response = client.get(page_path)
        assert response.status_code == 200, page_path
        parser = _Links()
        parser.feed(response.text)
        for href in parser.links:
            path = _local_path(href)
            if path:
                links.setdefault(path, page_path)
        for method, action in parser.targets:
            path = _local_path(action)
            if path and not _route_exists(urlsplit(path).path, method):
                bad_targets.append((page_path, method, action, "no route"))
    # Search (command palette) destinations are links too.
    for item in client.get("/api/command-palette").json()["items"]:
        url = item.get("url")
        if url and item.get("method", "get").lower() == "get":
            links.setdefault(_local_path(url) or url, "/api/command-palette")
        elif url and not _route_exists(urlsplit(url).path, item["method"].upper()):
            bad_targets.append(("/api/command-palette", item["method"], url, "no route"))
    assert len(links) > 40, sorted(links)
    dead = []
    for path, source in sorted(links.items()):
        response = client.get(path.split("#", 1)[0], follow_redirects=False)
        if response.status_code >= 400:
            dead.append((source, path, response.status_code))
    assert not dead, dead
    assert not bad_targets, bad_targets


def test_js_literal_paths_name_existing_routes():
    """Whole paths written in the host scripts exist (fragments built with + are skipped)."""
    missing = []
    for script in sorted((APP_DIR / "static").glob("*.js")):
        for number, line in enumerate(script.read_text().splitlines(), 1):
            code = line.split("//", 1)[0] if "://" not in line else line
            if "+" in code or "endsWith(" in code or "*=" in code:
                continue
            for literal in re.findall(r"[\"'](/[a-z][\w./-]*)(?:[?#][^\"']*)?[\"']", code):
                if not any(_route_exists(literal, m) for m in ("GET", "POST")):
                    missing.append((script.name, number, literal))
    assert not missing, missing


def test_removed_paths_appear_nowhere_in_the_app():
    hits = []
    for file in sorted(APP_DIR.rglob("*")):
        if file.suffix not in (".py", ".html", ".js", ".css", ".txt") or "__pycache__" in file.parts:
            continue
        text = file.read_text(errors="ignore")
        for name, pattern in REMOVED_PATTERNS.items():
            for match in pattern.finditer(text):
                line = text.count("\n", 0, match.start()) + 1
                hits.append((name, str(file.relative_to(APP_DIR)), line))
    assert not hits, hits


@pytest.mark.parametrize("path", [
    "/invoices/settings", "/automation", "/setup", "/setup/name", "/setup/address", "/setup/bookings",
])
def test_removed_routes_answer_404(world, path):
    assert world["client"].get(path, follow_redirects=False).status_code == 404


def test_removed_property_routes_answer_404(world):
    client, apartment_id = world["client"], world["apartment"]
    assert client.get(f"/stay-fees/{apartment_id}/setup", follow_redirects=False).status_code == 404
    assert client.get(f"/apartments/{apartment_id}/ws-request.txt", follow_redirects=False).status_code == 404


def test_the_e_mail_link_is_canonical_and_the_old_one_still_redirects(world):
    """Lifecycle tips now link the canonical page; tips already sent link /guest-links."""
    content = mail_notify.build_lifecycle("lifecycle_no_guest", unsubscribe_url="https://example.test/u", lang="en")
    assert "/apartments#property-summaries" in content["text"]
    assert "/guest-links" not in content["text"] and "/guest-links" not in content["html"]
    kept = world["client"].get("/guest-links", follow_redirects=False)
    assert kept.status_code == 303
    assert kept.headers["location"] == (
        f"/apartments/{world['apartment']}?view=settings&section=guests#communication"
    )
