"""1861: Go serves GET /reservations/{id} with the same stay page as Python.

Run with UBYHOST_GO_PATHS=/__go_test__ and PostgreSQL: any entry turns the test
server's Go routing on, and each stay then lists its own exact path so the
second fetch of the same session goes to Go. The inner HTML of
<div class="host-stay-detail"> and the <title> must match once whitespace is
collapsed and the CSRF token masked.
"""
from __future__ import annotations

import os
import re
import secrets
from datetime import date, timedelta
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from app import auth, config, db, host_i18n, property_setup, reporting
from app.main import app
from tests.conftest import login_as, mark_security_prompt_seen
from tests.go_stack import (
    ensure_go_running,
    go_paths_enabled,
    path_routed_to_go,
    seed_go_host_gate,
)
from tests.test_0710_v2_mockup_match_browser import _open_app
from tests.test_host_quiet_dashboard_browser import (  # noqa: F401
    _launch,
    base,
    dashboard_host,
    sync_api,
)

pytestmark = pytest.mark.skipif(
    not go_paths_enabled(),
    reason="UBYHOST_GO_PATHS must be set (e.g. /__go_test__)",
)

USERNAME = f"stay-parity-{secrets.token_hex(4)}"
OFF = "/__go_test__"
WIDTHS = (390, 768, 1024, 1280)
GUESTS = {
    "a": (("MINH", "NGUYEN"), ("ANNA", "NOVAK")),
    "b": (("LUCA", "ROSSI"),),
    "c": (("SARA", "BERG"),),
    "d": (("OLGA", "IVANOVA"),),
    "e": (("JAN", "HORAK"),),
    "f": (("PETR", "KRAL"),),
}
NAMES = re.compile("|".join(name for pair in GUESTS.values() for guest in pair for name in guest), re.IGNORECASE)
# What the Python page must show for each stay, so a seed that stops reaching
# its branch fails here instead of comparing two empty pages.
BRANCH = {
    "a": ('class="placeholder"', 'data-link-window="from"', "data-copy-own-link"),
    "b": ("data-fix-rejection",),
    "c": ("ui-banner-attention",),
    "d": ('id="demo-stay"',),
    "e": ('id="filed-by-hand"', "/filed-by-hand/undo"),
    "f": ('id="door-code-line"', 'class="code"'),
}


def _apartment(owner_id: int, entity_id: int, name: str, **extra) -> int:
    row = {
        "legal_entity_id": entity_id,
        "owner_user_id": owner_id,
        "internal_name": name,
        "permalink_token": f"parity{secrets.token_hex(6)}",
        "automation_mode": "manual",
        "default_purpose": "10",
        "uby_mark": "DEMO1",
        "active": 1,
        "created_at": db.utcnow(),
    }
    row.update(extra)
    apartment_id = db.insert("apartment", row)
    property_setup.start(apartment_id)
    property_setup.finish(apartment_id)
    return apartment_id


def _stay(apartment_id: int, key: str, start: date, nights: int, **extra) -> int:
    now = db.utcnow()
    row = {
        "apartment_id": apartment_id,
        "source": "airbnb",
        "uid": f"parity-{key}-{secrets.token_hex(4)}",
        "date_from": start.isoformat(),
        "date_to": (start + timedelta(days=nights)).isoformat(),
        "status": "active",
        "expected_guests_override": 1,
        "created_at": now,
        "updated_at": now,
    }
    row.update(extra)
    return db.insert("reservation", row)


def _guest(reservation_id: int, first: str, surname: str, *, complete: bool = True, **extra) -> int:
    now = db.utcnow()
    row = {
        "reservation_id": reservation_id,
        "first_name": first,
        "surname": surname,
        "is_lead": 0,
        "entered_by": "guest",
        "submit_state": reporting.PENDING,
        "created_at": now,
        "updated_at": now,
    }
    if complete:
        row.update({
            "birth_date": "01011990",
            "nationality": "VNM",
            "doc_type": "pas",
            "doc_number": "P9988771",
            "res_street": "Le Loi 5",
            "res_city": "Hanoi",
            "res_country": "VNM",
            "purpose": "10",
            "signature_png": "imported",
            "signed_at": now,
            "passport_photo_at": now,
        })
    row.update(extra)
    return db.insert("guest", row)


def _cleanup(owner_id: int) -> None:
    stays = "SELECT r.id FROM reservation r JOIN apartment a ON a.id = r.apartment_id WHERE a.owner_user_id = ?"
    db.execute(f"DELETE FROM door_code WHERE reservation_id IN ({stays})", (owner_id,))
    db.execute(f"DELETE FROM guest WHERE reservation_id IN ({stays})", (owner_id,))
    db.execute(f"DELETE FROM reservation WHERE id IN ({stays})", (owner_id,))
    db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (owner_id,))
    db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (owner_id,))


@pytest.fixture(scope="module")
def stay_pages():
    db.init_db()
    owner_id = mark_security_prompt_seen(
        auth.create_account(f"{USERNAME}@example.test", "Stay Parity", username=USERNAME)
    )
    seed_go_host_gate(owner_id)
    entity_id = db.insert(
        "legal_entity", {"name": "Parity s.r.o.", "owner_user_id": owner_id, "created_at": db.utcnow()}
    )
    flat = _apartment(owner_id, entity_id, "Parity Flat")
    door = _apartment(owner_id, entity_id, "Parity Door", lock_provider="ttlock", checkin_hour=15, checkout_hour=11)
    today, now = date.today(), db.utcnow()
    stays: dict[str, int] = {}

    # (a) Three expected: one reported, one incomplete, one placeholder row.
    stays["a"] = _stay(flat, "a", today + timedelta(days=10), 3, expected_guests_override=3, summary="Reserved")
    (lead, other) = GUESTS["a"]
    _guest(stays["a"], *lead, is_lead=1, submit_state=reporting.SENT, submitted_at=now)
    _guest(stays["a"], *other, complete=False, entered_by="host", note="Late arrival")

    # (b) A refused guest: the fix CTA and Send again.
    stays["b"] = _stay(flat, "b", today, 3)
    _guest(stays["b"], *GUESTS["b"][0], is_lead=1, submit_state=reporting.ERROR,
           last_errors="Document number is not valid.")

    # (c) Cancelled and archived.
    stays["c"] = _stay(flat, "c", today - timedelta(days=20), 2, status="cancelled", archived_at=now)
    _guest(stays["c"], *GUESTS["c"][0], is_lead=1, submit_state=reporting.SENT, submitted_at=now)

    # (d) The demo stay.
    stays["d"] = _stay(flat, "d", today + timedelta(days=2), 2, source="demo", expected_guests_override=2)
    _guest(stays["d"], *GUESTS["d"][0], is_lead=1)

    # (e) Filed by hand a moment ago: inside the undo window.
    stays["e"] = _stay(flat, "e", today - timedelta(days=1), 3)
    _guest(stays["e"], *GUESTS["e"][0], is_lead=1)
    reporting.mark_filed_by_hand(stays["e"], reporting.parse_manual_filed_at(""), "PRAHA-1861")

    # (f) A door code issued on a TTLock property.
    start = today + timedelta(days=1)
    stays["f"] = _stay(door, "f", start, 2, source="manual")
    _guest(stays["f"], *GUESTS["f"][0], is_lead=1)
    db.insert("door_code", {
        "reservation_id": stays["f"],
        "apartment_id": door,
        "lock_id": "lock-1861",
        "code_kind": "random",
        "state": "issued",
        "pin_enc": db.encrypt_field("482193"),
        "valid_from": f"{start.isoformat()}T13:00:00+00:00",
        "valid_to": f"{(start + timedelta(days=2)).isoformat()}T09:00:00+00:00",
        "issued_at": now,
        "created_at": now,
        "updated_at": now,
    })

    client = TestClient(app)
    login_as(client, USERNAME, url="/login?lang=en", follow_redirects=False)
    cookie = client.cookies.get(auth.SESSION_COOKIE)
    assert cookie
    try:
        yield cookie, stays
    finally:
        _cleanup(owner_id)


def _fetch(url: str, cookie: str, lang: str) -> httpx.Response:
    # The first Go request builds and starts ubyhost-web.
    return httpx.get(
        url,
        cookies={auth.SESSION_COOKIE: cookie, host_i18n.LANG_COOKIE: lang},
        follow_redirects=False,
        timeout=300,
    )


_DIV = re.compile(r"<div\b|</div>")
_DETAIL = '<div class="host-stay-detail">'


def _detail(page: str) -> str:
    """The inner HTML of the stay page's host-stay-detail div."""
    start = page.index(_DETAIL) + len(_DETAIL)
    depth = 1
    for match in _DIV.finditer(page, start):
        depth += 1 if match.group() == "<div" else -1
        if depth == 0:
            return page[start:match.start()]
    raise AssertionError("host-stay-detail is not closed")


def _title(page: str) -> str:
    match = re.search(r"<title>(.*?)</title>", page, re.DOTALL)
    assert match, "page has no <title>"
    return match.group(1)


def _norm(html: str) -> str:
    """Whitespace may differ (brief step 1): runs collapse and a gap between two tags goes.

    Jinja macros and the Go layout helpers indent differently (row_menu_begin);
    text, attributes and markup still compare exactly, and the screenshots show
    any gap that renders.
    """
    html = re.sub(r'(name="_csrf" value=")[^"]*"', r'\1X"', html)
    html = re.sub(r"\s+", " ", html).strip()
    return re.sub(r"> <", "><", html)


def _first_diff(py: str, go: str) -> str:
    """The first 200 differing characters of each side, guest names masked (the repo is public)."""
    at = next((i for i, (a, b) in enumerate(zip(py, go)) if a != b), min(len(py), len(go)))
    lo = max(0, at - 40)
    return (
        f"first difference at {at}:\n"
        f"  py: {NAMES.sub('<name>', py[lo:lo + 200])}\n"
        f"  go: {NAMES.sub('<name>', go[lo:lo + 200])}"
    )


@pytest.mark.parametrize("lang", ["en", "cs"])
def test_go_stay_page_matches_python(base, stay_pages, monkeypatch, lang):
    cookie, stays = stay_pages
    # go_stack starts Go with the test server as its public base; the guest link must agree.
    monkeypatch.setattr(config, "PUBLIC_BASE_URL", base)
    failures = []
    for key, reservation_id in stays.items():
        path = f"/reservations/{reservation_id}"
        monkeypatch.setenv("UBYHOST_GO_PATHS", OFF)
        assert not path_routed_to_go(path)
        py = _fetch(base + path, cookie, lang)
        assert py.status_code == 200, (key, "python", py.status_code)
        for marker in BRANCH[key]:
            assert marker in py.text, f"stay ({key}): the seed no longer reaches {marker!r}"

        monkeypatch.setenv("UBYHOST_GO_PATHS", path)
        assert path_routed_to_go(path)
        go = _fetch(base + path, cookie, lang)
        assert go.status_code == 200, (key, "go", go.status_code)
        direct = _fetch(ensure_go_running(base) + path, cookie, lang)
        assert direct.status_code == 200 and direct.headers.get("x-ubyhost-not-ported") != "1", (
            key, "Go does not serve the path itself", direct.status_code,
        )

        if _norm(_title(py.text)) != _norm(_title(go.text)):
            failures.append(f"stay ({key}) {lang} <title>: " + _first_diff(_norm(_title(py.text)), _norm(_title(go.text))))
        py_detail, go_detail = _norm(_detail(py.text)), _norm(_detail(go.text))
        if py_detail != go_detail:
            failures.append(f"stay ({key}) {lang}: " + _first_diff(py_detail, go_detail))
    assert not failures, "\n".join(failures)


def test_python_and_go_screenshots(base, stay_pages, monkeypatch, tmp_path):
    """Stays (a) and (b) at every width, Python and Go, for the side-by-side look (rule 10)."""
    cookie, stays = stay_pages
    out = Path(os.environ.get("UBYHOST_SHOTS_DIR") or tmp_path) / "stay-detail"
    out.mkdir(parents=True, exist_ok=True)
    with sync_api.sync_playwright() as playwright:
        browser = _launch(playwright)
        try:
            for key in ("a", "b"):
                path = f"/reservations/{stays[key]}"
                for side, routed in (("py", OFF), ("go", path)):
                    monkeypatch.setenv("UBYHOST_GO_PATHS", routed)
                    for width in WIDTHS:
                        context, page = _open_app(browser, base, cookie, path, width)
                        assert page.locator(".host-stay-detail").count() == 1, (side, key, width)
                        page.screenshot(path=str(out / f"{side}-{key}-{width}.png"), full_page=True)
                        context.close()
        finally:
            browser.close()
