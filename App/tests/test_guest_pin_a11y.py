"""UX-119 (audit A-32): the PIN error must be tied to the PIN input."""
import html
import re
from datetime import timedelta
from pathlib import Path

from fastapi.testclient import TestClient
from starlette.requests import Request

from app import claim, db, i18n
from app.main import app
from app.routes import guest as guest_routes

TEMPLATES = Path(__file__).resolve().parents[1] / "app" / "templates"
TOKEN = "pina11y"
PIN = "551234"
ENTITY = "PIN a11y test"


def _read(name: str) -> str:
    return (TEMPLATES / name).read_text(encoding="utf-8")


def _cleanup():
    apartment = db.query_one("SELECT * FROM apartment WHERE permalink_token = ?", (TOKEN,))
    if not apartment:
        return
    db.execute("DELETE FROM reservation WHERE apartment_id = ?", (apartment["id"],))
    db.execute("DELETE FROM apartment WHERE id = ?", (apartment["id"],))
    db.execute("DELETE FROM legal_entity WHERE id = ?", (apartment["legal_entity_id"],))


def _seed() -> int:
    db.init_db()
    _cleanup()
    now = db.utcnow()
    today = claim.prague_today()
    entity_id = db.insert("legal_entity", {"name": ENTITY, "created_at": now})
    apartment_id = db.insert(
        "apartment",
        {
            "legal_entity_id": entity_id,
            "internal_name": "PIN a11y flat",
            "permalink_token": TOKEN,
            "permalink_pin": PIN,
            "permalink_window_days": 14,
            "automation_mode": "manual",
            "active": 1,
            "created_at": now,
        },
    )
    return db.insert(
        "reservation",
        {
            "apartment_id": apartment_id,
            "source": "manual",
            "uid": "pin-a11y-stay",
            "date_from": today.isoformat(),
            "date_to": (today + timedelta(days=3)).isoformat(),
            "status": "active",
            "created_at": now,
            "updated_at": now,
        }
    )


def _request() -> Request:
    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "server": ("testserver", 80),
            "root_path": "",
            "path": f"/l/{TOKEN}/pin",
            "query_string": b"",
            "headers": [],
        }
    )


def _pin_input(page: str) -> str:
    match = re.search(r"<input[^>]*id=\"pin\"[^>]*>", page)
    assert match, "the PIN input disappeared from the page"
    return html.unescape(match.group(0))


def _page(error: str = "") -> str:
    response = guest_routes._pin_page(_request(), TOKEN, "en", error)
    return html.unescape(response.body.decode("utf-8"))


def test_the_template_names_the_error_and_points_the_input_at_it():
    template = _read("guest/pin.html")
    assert 'class="g-err" id="pin-error"' in template
    assert 'aria-invalid="true" aria-describedby="pin-error"' in template
    # still gated, so a clean PIN page carries neither attribute
    assert template.count("{% if error %}") == 2


def test_a_failed_pin_is_announced_on_the_input():
    _seed()
    try:
        page = _page(i18n.STRINGS["en"]["pin_wrong"])
        assert i18n.STRINGS["en"]["pin_wrong"] in page
        assert 'id="pin-error"' in page
        field = _pin_input(page)
        assert 'aria-invalid="true"' in field
        assert 'aria-describedby="pin-error"' in field
    finally:
        _cleanup()


def test_a_clean_pin_page_is_not_marked_invalid():
    _seed()
    try:
        page = _page()
        assert 'id="pin-error"' not in page
        field = _pin_input(page)
        assert "aria-invalid" not in field
        assert "aria-describedby" not in field
        # the fix must not cost the guest the field's own affordances
        assert 'autocomplete="one-time-code"' in field
        assert 'inputmode="numeric"' in field
        assert "autofocus" in field
    finally:
        _cleanup()


def test_the_live_pin_gate_renders_clean_and_then_marks_the_field(monkeypatch):
    stay_id = _seed()
    monkeypatch.setenv("UBYHOST_GUEST_PIN", "1")
    monkeypatch.setattr("app.config.GUEST_PIN_REQUIRED", True)
    try:
        client = TestClient(app)
        gated = client.get(f"/l/{TOKEN}/{stay_id}?lang=en")
        assert gated.status_code == 200
        assert "aria-invalid" not in _pin_input(gated.text)

        wrong = client.post(
            f"/l/{TOKEN}/pin",
            data={"pin": "000000", "return_to": f"/l/{TOKEN}/{stay_id}"},
            follow_redirects=False,
        )
        assert wrong.status_code == 200
        field = _pin_input(wrong.text)
        assert 'aria-invalid="true"' in field
        assert 'aria-describedby="pin-error"' in field
    finally:
        _cleanup()
