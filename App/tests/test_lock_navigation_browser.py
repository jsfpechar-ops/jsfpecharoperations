"""0090: lock setup feedback lands on its own section, never the page top.

Every TTLock call is mocked; no PIN is issued, changed or deleted.
"""
from __future__ import annotations

import json
import os
import secrets
import socket
import threading
import time
from pathlib import Path

import pytest
import uvicorn
from fastapi.testclient import TestClient

REQUIRE_BROWSER = os.environ.get("UBYHOST_REQUIRE_BROWSER") == "1"
if REQUIRE_BROWSER:
    import playwright.sync_api as sync_api
else:
    sync_api = pytest.importorskip("playwright.sync_api")

from app import auth, config, db, ttlock
from app.main import app
from tests.browser_support import chromium_launch_kwargs
from tests.conftest import login_as

EVIDENCE = Path(__file__).resolve().parents[2] / "docs" / "tasks" / "0090-evidence"
LONG_TITLE = "Apartmán Vinohrady s výhledem na Žižkovskou věž a zahradou u parku"
LOCK_A = {"lock_id": "7001", "alias": "Front door (synthetic)", "battery": 88, "tz_offset_ms": 3600000}
LOCK_B = {"lock_id": "7002", "alias": "Garden gate (synthetic)", "battery": 70, "tz_offset_ms": 3600000}


def _shot(page, name):
    if os.environ.get("UBYHOST_CAPTURE_0090") == "1":
        EVIDENCE.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(EVIDENCE / f"{name}.png"), full_page=False)


class FakeTTLock:
    """Stands in for the provider: what the next "check" finds."""

    def __init__(self):
        self.next_locks = []
        self.calls = []
        self.fail_kind = None

    def create_account(self, owner_id):
        self.calls.append("create")
        if ttlock.account_for(owner_id):
            return int(ttlock.account_for(owner_id)["id"])
        now = db.utcnow()
        return db.insert("lock_account", {
            "owner_user_id": owner_id, "provider": "ttlock", "username": "uhsynthetic0001",
            "status": "ok", "locks_json": "[]", "created_at": now, "updated_at": now,
        })

    def check_locks(self, account_id):
        self.calls.append("check")
        if self.fail_kind:
            raise ttlock.TTLockError("synthetic failure", kind=self.fail_kind)
        db.execute(
            "UPDATE lock_account SET locks_json = ?, locks_fetched_at = ? WHERE id = ?",
            (json.dumps(self.next_locks), db.utcnow(), account_id),
        )
        return list(self.next_locks), 0

    def forbidden(self, *args, **kwargs):  # any PIN or network call fails the test
        raise AssertionError("a TTLock PIN/network call was made")


@pytest.fixture(scope="module")
def world():
    db.init_db()
    patch = pytest.MonkeyPatch()
    fake = FakeTTLock()
    patch.setattr(config, "DOOR_CODES_ENABLED", True)
    patch.setattr(config, "TTLOCK_CLIENT_ID", "cid")
    patch.setattr(config, "TTLOCK_CLIENT_SECRET", "csecret")
    patch.setattr(ttlock, "create_account", fake.create_account)
    patch.setattr(ttlock, "check_locks", fake.check_locks)
    patch.setattr(ttlock, "_call", fake.forbidden)
    patch.setattr(ttlock, "_post", fake.forbidden)
    username = f"locknav-{secrets.token_hex(4)}"
    owner_id = auth.create_account(f"{username}@example.test", "Lock Nav", role="host", username=username)
    entity_id = db.insert("legal_entity", {"name": "Lock Operator", "owner_user_id": owner_id, "created_at": db.utcnow()})
    apartment_id = db.insert("apartment", {
        "internal_name": LONG_TITLE, "owner_user_id": owner_id, "legal_entity_id": entity_id,
        "permalink_token": f"locknav{secrets.token_hex(4)}", "permalink_pin": "123456",
        "checkin_hour": 15, "checkout_hour": 10, "active": 1, "created_at": db.utcnow(),
    })
    other = auth.create_account(f"other-{username}@example.test", "Other", role="host", username=f"other-{username}")
    foreign_id = db.insert("apartment", {
        "internal_name": "Foreign flat", "owner_user_id": other,
        "permalink_token": f"locknavf{secrets.token_hex(4)}", "permalink_pin": "123456",
        "active": 1, "created_at": db.utcnow(),
    })
    client = TestClient(app)
    assert login_as(client, username, url="/login?lang=en", follow_redirects=False).status_code == 303
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 15
    while not server.started and time.time() < deadline:
        time.sleep(0.05)
    if not server.started:
        pytest.fail("the test server did not start")
    yield {
        "base": f"http://127.0.0.1:{port}", "cookie": client.cookies.get(auth.SESSION_COOKIE),
        "owner": owner_id, "apartment": apartment_id, "foreign": foreign_id, "fake": fake,
    }
    server.should_exit = True
    thread.join(timeout=5)
    patch.undo()
    for owner in (owner_id, other):
        db.execute("DELETE FROM audit WHERE owner_user_id = ?", (owner,))
        db.execute("DELETE FROM alert WHERE owner_user_id = ?", (owner,))
        db.execute("DELETE FROM lock_account WHERE owner_user_id = ?", (owner,))
        db.execute(
            "DELETE FROM apartment_slug WHERE apartment_id IN (SELECT id FROM apartment WHERE owner_user_id = ?)",
            (owner,),
        )
        db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (owner,))
        db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (owner,))
        db.execute("DELETE FROM rate_limit_event")
        db.execute("DELETE FROM user_account WHERE id = ?", (owner,))


def _reset(world):
    db.execute("DELETE FROM lock_account WHERE owner_user_id = ?", (world["owner"],))
    db.execute("DELETE FROM rate_limit_event")
    db.execute("UPDATE apartment SET lock_provider = NULL, lock_id = NULL WHERE id = ?", (world["apartment"],))
    world["fake"].next_locks = []


def _page(browser, world, width, js=True):
    context = browser.new_context(viewport={"width": width, "height": 800}, java_script_enabled=js)
    context.add_cookies([{"name": auth.SESSION_COOKIE, "value": world["cookie"], "url": world["base"] + "/"}])
    return context, context.new_page()


def _in_view(page, selector):
    """The target is on screen (not left at the page top) after landing."""
    box = page.evaluate(
        """(sel) => { const el = document.querySelector(sel); if (!el) return null;
           const r = el.getBoundingClientRect();
           return {top: r.top, bottom: r.bottom, vh: window.innerHeight, y: window.scrollY}; }""",
        selector,
    )
    assert box, selector
    assert -2 <= box["top"] < box["vh"] * 0.75, box
    return box


def _settle(page):
    page.wait_for_load_state()
    page.wait_for_timeout(150)


def test_lock_setup_flow_keeps_its_place(world):
    base, apartment = world["base"], world["apartment"]
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        for lang in ("en", "cs"):
            _reset(world)
            context, page = _page(browser, world, 1280)
            page.goto(f"{base}/apartments/{apartment}?lang={lang}#door-code")
            _settle(page)
            assert page.locator("details#door-code").evaluate("d => d.open")
            _in_view(page, "#door-code")
            page.locator("#door-code a.btn").click()
            _settle(page)
            assert page.url.endswith("#smart-locks-how")
            _in_view(page, "#smart-locks-how")
            _shot(page, f"how-1280-{lang}")

            page.check("#terms")
            page.locator("#smart-locks-setup button[type=submit]").click()
            _settle(page)
            assert page.url.endswith("#smart-locks-share")
            box = _in_view(page, "#smart-locks-share")
            assert box["y"] > 0  # a real scroll to the section, not the page top
            assert page.locator("#smart-locks-share .guide-steps li").count() == 3
            assert page.locator('#smart-locks-share a.help-link[href="/guide#door-codes-share"]').is_visible()
            _shot(page, f"share-1280-{lang}")

            # No lock shared yet: stays on the sharing section.
            page.locator("#smart-locks-share button[type=submit]").click()
            _settle(page)
            assert page.url.endswith("#smart-locks-share")
            _in_view(page, "#smart-locks-share")

            # One admin-shared lock found: back to the property's expanded lock section.
            world["fake"].next_locks = [LOCK_A]
            page.locator("#smart-locks-share button[type=submit]").click()
            _settle(page)
            assert f"/apartments/{apartment}" in page.url and page.url.endswith("#door-code")
            assert page.locator("details#door-code").evaluate("d => d.open")
            _in_view(page, "#door-code")
            row = db.query_one("SELECT lock_provider FROM apartment WHERE id = ?", (apartment,))
            assert row["lock_provider"] is None  # nothing assigned or switched on
            _shot(page, f"property-door-code-1280-{lang}")
            page.select_option("#lock_id", LOCK_A["lock_id"])
            page.locator(".host-property-save button[type=submit]").click()
            _settle(page)
            row = db.query_one("SELECT lock_provider, lock_id FROM apartment WHERE id = ?", (apartment,))
            assert row["lock_id"] == LOCK_A["lock_id"] and row["lock_provider"] is None

            # Back navigation returns to the lock page section history.
            page.go_back()
            _settle(page)
            assert "/apartments/" in page.url or "/smart-locks" in page.url
            context.close()
        assert "check" in world["fake"].calls
        browser.close()


def test_many_locks_list_and_add_more_sections(world):
    base = world["base"]
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        _reset(world)
        world["fake"].create_account(world["owner"])
        world["fake"].check_locks(ttlock.account_for(world["owner"])["id"])
        world["fake"].next_locks = [LOCK_A, LOCK_B]
        world["fake"].check_locks(ttlock.account_for(world["owner"])["id"])
        for width in (360, 390, 1280):
            for lang in ("en", "cs"):
                context, page = _page(browser, world, width)
                page.goto(f"{base}/smart-locks?lang={lang}")
                _settle(page)
                page.locator("#smart-locks-list button[type=submit]").first.click()
                _settle(page)
                assert page.url.endswith("#smart-locks-list")
                _in_view(page, "#smart-locks-list")
                assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")
                _shot(page, f"list-{width}-{lang}")
                page.goto(f"{base}/smart-locks?lang={lang}#smart-locks-add-more")
                _settle(page)
                assert page.locator("details#smart-locks-add-more").evaluate("d => d.open")
                world["fake"].fail_kind = "budget"
                page.locator("#smart-locks-add-more button[type=submit]").click()
                _settle(page)
                assert page.url.endswith("#smart-locks-add-more")
                assert page.locator("details#smart-locks-add-more").evaluate("d => d.open")
                _in_view(page, "#smart-locks-add-more")
                _shot(page, f"add-more-{width}-{lang}")
                world["fake"].fail_kind = None
                context.close()
        browser.close()


def test_share_section_without_javascript_and_foreign_returns(world):
    base = world["base"]
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        _reset(world)
        world["fake"].create_account(world["owner"])
        for width in (360, 390):
            for lang in ("en", "cs"):
                context, page = _page(browser, world, width, js=False)
                page.goto(f"{base}/smart-locks?return_to=/apartments/{world['apartment']}&lang={lang}#smart-locks-share")
                share = page.locator("#smart-locks-share")
                assert share.is_visible()
                assert share.locator("button[type=submit]").is_visible()
                assert share.locator('input[name="section"]').get_attribute("value") == "share"
                _shot(page, f"share-nojs-{width}-{lang}")
                context.close()
        context, page = _page(browser, world, 1280)
        for bad in ("https://evil.example/x", "//evil.example/x", f"/apartments/{world['foreign']}"):
            page.goto(f"{base}/smart-locks?return_to={bad}")
            value = page.locator('#smart-locks-share input[name="return_to"]').get_attribute("value")
            assert "evil" not in value
        world["fake"].next_locks = [LOCK_A]
        page.goto(f"{base}/smart-locks?return_to=/apartments/{world['foreign']}")
        page.locator("#smart-locks-share button[type=submit]").click()
        _settle(page)
        assert "/smart-locks" in page.url and page.url.endswith("#smart-locks-list")
        assert f"/apartments/{world['foreign']}#" not in page.url
        context.close()
        browser.close()
