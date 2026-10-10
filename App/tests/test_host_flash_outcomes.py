"""Host toast severity follows the translated flash key and known outcome."""
from __future__ import annotations

from types import SimpleNamespace
from urllib.parse import parse_qs, quote, urlparse
import os
import socket
import threading

import pytest
import uvicorn
from fastapi.testclient import TestClient

from app import auth, db, host_i18n
from app.main import app
from app.routes.admin_helpers import FlashMessage, back, flash, flash_plural
from tests.browser_support import chromium_launch_kwargs
from tests.conftest import login_as

REQUIRE_BROWSER = os.environ.get("UBYHOST_REQUIRE_BROWSER") == "1"
if REQUIRE_BROWSER:
    import playwright.sync_api as sync_api
else:
    sync_api = pytest.importorskip("playwright.sync_api")

USERNAME = "flash-outcomes-host"


def _cleanup():
    ids = [row["id"] for row in db.query(
        "SELECT id FROM user_account WHERE username = ?", (USERNAME,)
    )]
    for user_id in ids:
        apartments = "(SELECT id FROM apartment WHERE owner_user_id = ?)"
        stays = f"(SELECT id FROM reservation WHERE apartment_id IN {apartments})"
        db.execute(f"DELETE FROM guest WHERE reservation_id IN {stays}", (user_id,))
        db.execute(f"DELETE FROM reservation WHERE apartment_id IN {apartments}", (user_id,))
        db.execute("DELETE FROM alert WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM audit WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM user_account WHERE id = ?", (user_id,))


@pytest.fixture
def host():
    db.init_db()
    _cleanup()
    auth.create_account(f"{USERNAME}@example.test", "Flash Host", username=USERNAME)
    client = TestClient(app)
    assert login_as(client, USERNAME, follow_redirects=False).status_code == 303
    client.cookies.set(host_i18n.LANG_COOKIE, "en")
    try:
        yield client
    finally:
        _cleanup()


@pytest.fixture(scope="module")
def browser_base():
    db.init_db()
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = __import__("time").time() + 15
    while not server.started and __import__("time").time() < deadline:
        __import__("time").sleep(0.05)
    if not server.started:
        pytest.fail("the test server did not start")
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=5)


def _request(lang: str = "en"):
    return SimpleNamespace(state=SimpleNamespace(lang=lang))


def _attrs(location: str) -> dict[str, list[str]]:
    return parse_qs(urlparse(location).query)


@pytest.mark.parametrize(
    "key,kind,sticky",
    [
        ("flash.entities.added_first", "success", False),
        ("flash.entities.saved", "success", False),
        ("flash.apartments.created", "success", False),
        ("flash.apartments.saved_ready", "success", False),
        ("flash.apartments.saved", "warning", True),
        ("flash.apartments.pin_rotated", "warning", True),
        ("flash.apartments.guest_link", "warning", True),
        ("flash.reservations.accepted", "info", False),
        ("flash.reservations.reported", "info", False),
        ("flash.reservations.sent", "info", False),
        ("flash.guests.resent", "info", False),
        ("flash.entities.archived", "info", False),
        ("unreviewed.key", "info", False),
    ],
)
def test_exact_key_controls_flash_severity(key, kind, sticky):
    message = flash(_request(), key)
    assert isinstance(message, str)
    assert message.toast_kind == kind
    assert message.toast_sticky is sticky


def test_positive_partial_acceptance_is_persistent_amber():
    message = flash_plural(_request(), "flash.reservations.accepted", 2)
    assert message.toast_kind == "partial"
    assert message.toast_sticky is True
    assert "2" in message


def test_zero_partial_acceptance_stays_neutral_information():
    message = flash_plural(_request(), "flash.reservations.accepted", 0)
    assert message.toast_kind == "info"
    assert message.toast_sticky is False


@pytest.mark.parametrize("lang", ["en", "cs"])
def test_flash_text_is_exactly_the_existing_translation(lang):
    result = flash(_request(lang), "flash.apartments.saved_ready")
    assert result == host_i18n.translate(lang, "flash.apartments.saved_ready")
    assert str(result) == host_i18n.translate(lang, "flash.apartments.saved_ready")


def test_back_preserves_redirect_shape_and_adds_only_typed_metadata():
    message = flash(_request(), "flash.apartments.pin_rotated")
    response = back("/apartments?range=all#edit", msg=message)
    assert response.status_code == 303
    parsed = urlparse(response.headers["location"])
    values = parse_qs(parsed.query)
    assert parsed.path == "/apartments"
    assert parsed.fragment == "edit"
    assert values["range"] == ["all"]
    assert values["msg"] == [host_i18n.translate("en", "flash.apartments.pin_rotated")]
    assert values["toast_kind"] == ["warning"]
    assert values["toast_sticky"] == ["1"]


def test_plain_unknown_message_has_no_severity_metadata():
    response = back("/apartments?range=all", msg="Saved successfully")
    assert response.status_code == 303
    assert response.headers["location"] == "/apartments?range=all&msg=Saved%20successfully"


def test_explicit_sticky_information_metadata_is_preserved():
    message = FlashMessage("Still working", "host.explicit_status", "info", True)
    response = back("/reservations", msg=message)
    values = _attrs(response.headers["location"])
    assert values["toast_kind"] == ["info"]
    assert values["toast_sticky"] == ["1"]


def test_typed_neutral_flash_preserves_legacy_redirect_and_renders_info(host):
    message = flash(_request(), "flash.entities.archived", name="Flat")
    response = back("/apartments?range=all", msg=message)
    expected = f"/apartments?range=all&msg={quote(str(message))}"
    assert response.status_code == 303
    assert response.headers["location"] == expected

    page = host.get(response.headers["location"])
    assert page.status_code == 200
    assert 'data-toast-kind="info"' in page.text


def test_real_property_creation_renders_green_and_plain_query_stays_info(host):
    response = host.post(
        "/apartments", data={"internal_name": "Flash property"}, follow_redirects=False
    )
    assert response.status_code == 303
    values = _attrs(response.headers["location"])
    assert values["toast_kind"] == ["success"]
    assert values["msg"] == [host_i18n.translate("en", "flash.apartments.created")]

    page = host.get(response.headers["location"])
    assert page.status_code == 200
    assert 'data-toast-kind="success"' in page.text
    assert "data-toast-sticky" not in page.text

    plain = host.get("/apartments?msg=Saved%20successfully")
    assert plain.status_code == 200
    assert 'data-toast-kind="info"' in plain.text


def test_browser_renders_saved_warning_as_sticky_amber(host, browser_base):
    created = host.post(
        "/apartments", data={"internal_name": "Warning property"}, follow_redirects=False
    )
    apartment_path = urlparse(created.headers["location"]).path
    saved = host.post(
        apartment_path, data={"internal_name": "Warning property"}, follow_redirects=False
    )
    assert saved.status_code == 303
    assert _attrs(saved.headers["location"])["toast_kind"] == ["warning"]
    assert _attrs(saved.headers["location"])["toast_sticky"] == ["1"]

    with sync_api.sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(**chromium_launch_kwargs())
        except Exception:
            if REQUIRE_BROWSER:
                raise
            pytest.skip("Chromium is required for host flash outcome browser coverage")
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        context.add_cookies([{
            "name": auth.SESSION_COOKIE,
            "value": host.cookies.get(auth.SESSION_COOKIE),
            "url": browser_base + "/",
        }])
        page = context.new_page()
        page.goto(browser_base + saved.headers["location"])
        warning = page.locator('.toast[data-toast-kind="warning"][data-toast-sticky]')
        warning.wait_for(state="visible")
        assert "Still missing for police reporting" in warning.inner_text()
        context.close()
        browser.close()


def test_existing_err_flash_is_not_reclassified():
    message = flash(_request(), "flash.error.name_required")
    response = back("/apartments/new", err=message)
    assert response.status_code == 303
    assert "toast_kind" not in response.headers["location"]
