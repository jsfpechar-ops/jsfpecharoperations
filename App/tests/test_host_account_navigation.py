"""0083: Settings is six visible groups; specialized actions stay distinct."""
from __future__ import annotations

import html as htmllib
import os
import re
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

from app import auth, db
from app.host_i18n import STRINGS
from app.main import app
from tests.browser_support import chromium_launch_kwargs
from tests.conftest import login_as

EVIDENCE = Path(__file__).resolve().parents[2] / "docs" / "tasks" / "0083-evidence"
GROUPS = ("account", "security", "data", "privacy", "technical", "help")
FORM_ACTIONS = (
    "/account/email",
    "/settings/purge-expired",
    "/account/passkeys/",
)


def _account(role: str):
    db.init_db()
    username = f"acct-nav-{role}-{secrets.token_hex(3)}"
    uid = auth.create_account(f"{username}@example.test", "Account Nav", role=role, username=username)
    db.execute("UPDATE user_account SET must_change_password = 0 WHERE id = ?", (uid,))
    client = TestClient(app)
    response = login_as(client, username, url="/login?lang=en", follow_redirects=False)
    assert response.status_code == 303, response.text
    return uid, client


def _drop(uid):
    for table in ("audit", "apartment", "legal_entity"):
        db.execute(f"DELETE FROM {table} WHERE owner_user_id = ?", (uid,))
    db.execute("DELETE FROM user_account WHERE id = ?", (uid,))


@pytest.fixture()
def host():
    uid, client = _account("host")
    yield client
    _drop(uid)


@pytest.fixture()
def admin():
    uid, client = _account("admin")
    yield client
    _drop(uid)


def _group_positions(html: str):
    return [html.index(f'id="settings-group-{key}"') for key in GROUPS]


def test_six_groups_in_order_and_index_links_each(host):
    html = host.get("/settings?lang=en").text
    positions = _group_positions(html)
    assert positions == sorted(positions)
    nav = html[html.index('class="host-property-grid"'):]
    nav = nav[: nav.index("</nav>")]
    for key in GROUPS[:4] + GROUPS[5:]:
        assert f'href="#settings-group-{key}"' in nav
    assert 'href="#settings-technical"' in nav
    for key in GROUPS:
        title = STRINGS["en"][f"settings.group.{key}"]
        assert f'id="settings-group-{key}-title">{htmllib.escape(title)}</h2>' in html


def test_ordinary_user_sees_no_admin_controls(host):
    html = host.get("/settings?lang=en").text
    assert "/admin/" not in html
    assert STRINGS["en"]["settings.account.users"] not in html


def test_admin_sees_team_and_incidents_in_account_group(admin):
    html = admin.get("/settings?lang=en").text
    account = html[html.index('id="settings-group-account"'): html.index('id="settings-group-security"')]
    assert 'href="/admin/users"' in account
    assert 'href="/admin/incidents"' in account


def test_email_change_is_a_visible_form_not_a_disclosure(host):
    html = host.get("/settings?lang=en").text
    start = html.index('id="settings-login-email"')
    form = html[html.index('<form method="post" action="/account/email"', start):]
    form = form[: form.index("</form>")]
    assert 'name="email"' in form and 'type="email"' in form
    assert 'aria-describedby="account-new-email-help"' in form
    assert 'id="account-new-email-help"' in html
    before = html[start - 200: html.index('<form method="post" action="/account/email"')]
    assert "<details" not in before.split("settings-group-account")[-1]
    # No broad "save everything" form: language stays in the account menu.
    assert 'action="/language"' in html
    assert html.count('action="/account/email"') == 1


def test_specialized_actions_stay_distinct(host):
    html = host.get("/settings?lang=en").text
    assert 'action="/settings/purge-expired"' in html
    assert "data-confirm" in html[html.index('action="/settings/purge-expired"'):][:200]
    for href in ("/settings/archived", "/privacy-requests", "/guide", "/legal", "/terms", "/privacy", "/dpa"):
        assert f'href="{href}"' in html, href
    assert 'href="/account/2fa/setup"' in html
    assert "data-passkey-add" in html or "passkeys" in html


def test_business_details_link_lives_in_one_place(host):
    html = host.get("/settings?lang=en").text
    assert html.count('id="settings-business"') == 1
    row = html[html.index('id="settings-business"'):]
    row = row[: row.index("</div>\n        </div>") + 20]
    assert 'href="/entities"' in row
    assert htmllib.escape(STRINGS["en"]["settings.business.title"]) in row


def test_routine_helper_text_is_behind_the_question_mark(host):
    html = host.get("/settings?lang=en").text
    for key in ("settings-security-help", "settings-retention-help", "settings-archive-help", "settings-access-help"):
        assert f'id="{key}"' in html and f'aria-controls="{key}"' in html
    # Ids stay unique so aria-controls is unambiguous.
    ids = re.findall(r'\sid="([^"]+)"', html)
    assert len(ids) == len(set(ids)), sorted({i for i in ids if ids.count(i) > 1})


def test_czech_groups(host):
    html = host.get("/settings?lang=cs").text
    for key in GROUPS:
        assert STRINGS["cs"][f"settings.group.{key}"] in html
    assert STRINGS["cs"]["settings.business.title"] in html


def test_search_reaches_settings_groups_and_help(host, admin):
    items = host.get("/api/command-palette").json()["items"]
    urls = {item.get("url") for item in items}
    assert {"/settings", "/guide", "/settings#settings-group-security", "/settings#settings-group-data"} <= urls
    assert "/admin/users" not in urls
    admin_urls = {item.get("url") for item in admin.get("/api/command-palette").json()["items"]}
    assert {"/admin/users", "/admin/incidents"} <= admin_urls


def test_group_strings_in_step():
    new = {k for k in STRINGS["en"] if k.startswith(("settings.group.", "settings.business.", "settings.help."))}
    assert new <= set(STRINGS["cs"])


# --- browser: geometry, focus and screenshots ------------------------------


@pytest.fixture(scope="module")
def live():
    uid, client = _account("host")
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
    yield f"http://127.0.0.1:{port}", client
    server.should_exit = True
    thread.join(timeout=5)
    _drop(uid)


def test_settings_geometry_and_help_at_widths(live):
    base, client = live
    capture = os.environ.get("UBYHOST_CAPTURE_0083") == "1"
    cookie = client.cookies.get(auth.SESSION_COOKIE)
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        for lang in ("en", "cs"):
            for width in (360, 390, 1280):
                context = browser.new_context(viewport={"width": width, "height": 900})
                context.add_cookies([{"name": auth.SESSION_COOKIE, "value": cookie, "url": base + "/"}])
                page = context.new_page()
                page.goto(f"{base}/settings?lang={lang}")
                overflow = page.evaluate(
                    "document.documentElement.scrollWidth - document.documentElement.clientWidth"
                )
                assert overflow <= 0, (lang, width, overflow)
                for key in GROUPS:
                    assert page.locator(f"#settings-group-{key}-title").is_visible(), (lang, width, key)
                # the e-mail form is visible without opening anything
                assert page.locator("#account-new-email").is_visible()
                # keyboard focus opens a ? tip and it stays inside the viewport
                button = page.locator("[aria-controls='settings-security-help']")
                button.focus()
                tip = page.locator("#settings-security-help")
                assert tip.is_visible()
                box = tip.bounding_box()
                assert box["x"] >= 0 and box["x"] + box["width"] <= width + 0.5
                page.keyboard.press("Escape")
                if capture:
                    EVIDENCE.mkdir(parents=True, exist_ok=True)
                    page.screenshot(path=str(EVIDENCE / f"settings-{width}-{lang}.png"), full_page=True)
                context.close()
        browser.close()
