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
GROUP_PAGE = {"privacy": "data"}
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


def _plain(html: str) -> str:
    return " ".join(re.sub(r"<[^>]+>", " ", html).split())


def _group_page(key: str) -> str:
    return f"/settings/{GROUP_PAGE.get(key, key)}"


def test_six_groups_in_order_and_index_links_each(admin, host):
    index = admin.get("/settings?lang=en").text
    index = index[index.index('class="airbnb-index"'):]
    index = index[: index.index("</nav>")]
    positions = [index.index(f'href="/settings/{key}"') for key in ("account", "security", "data", "technical", "help")]
    assert positions == sorted(positions)
    for key in GROUPS:
        page = admin.get(f"{_group_page(key)}?lang=en").text
        assert f'id="settings-group-{key}"' in page
        title = STRINGS["en"][f"settings.group.{key}"]
        assert f'id="settings-group-{key}-title">{htmllib.escape(title)}</h2>' in page


def test_ordinary_user_sees_no_admin_controls(host):
    html = host.get("/settings?lang=en").text
    # The speculation-rules JSON excludes "/admin/*" for everyone; that is not a control.
    assert 'href="/admin' not in html
    assert STRINGS["en"]["settings.account.users"] not in html


def test_admin_sees_team_and_incidents_in_account_group(admin):
    html = admin.get("/settings/account?lang=en").text
    account = html[html.index('id="settings-group-account"'):]
    assert 'href="/admin/customers"' in account
    assert 'href="/admin/incidents"' in account


@pytest.mark.parametrize("role", ("host", "admin"))
@pytest.mark.parametrize("lang", ("en", "cs", "vi"))
def test_account_menu_in_the_sidebar_corner_lists_settings_and_admin_links(role, lang, request):
    """0896: Settings, Funnel and Admin live in the profile bubble's menu, not in the main sidebar list."""
    client = request.getfixturevalue(role)
    html = client.get(f"/settings?lang={lang}").text
    menu = re.search(r'<details class="me-menu host-account" data-host-account>.*?</details>', html, re.S)
    assert menu is not None
    menu = menu.group(0)
    assert 'href="/settings"' in menu and 'href="/guide"' in menu
    assert ('href="/admin"' in menu) == (role == "admin")
    assert ('href="/admin/fakturace#funnel"' in menu) == (role == "admin")
    main_nav = re.search(r'<nav class="side-nav" aria-label="[^"]+">.*?</nav>', html, re.S).group(0)
    assert 'href="/settings"' not in main_nav


def test_email_change_is_a_visible_form_not_a_disclosure(host):
    html = host.get("/settings/account?lang=en").text
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
    data = host.get("/settings/data?lang=en").text
    # 0910: with nothing to delete there is no purge button
    assert 'action="/settings/purge-expired"' not in data
    index = host.get("/settings?lang=en").text + host.get("/settings/help?lang=en").text
    for href in ("/settings/archived", "/privacy-requests", "/guide", "/legal", "/terms", "/privacy", "/dpa"):
        assert f'href="{href}"' in index, href
    security = host.get("/settings/security?lang=en").text
    assert 'href="/account/2fa/setup"' in security
    assert "data-passkey-add" in security or "passkeys" in security


def test_business_details_link_lives_in_one_place(host):
    html = host.get("/settings/account?lang=en").text
    assert html.count('id="settings-business"') == 1
    row = html[html.index('id="settings-business"'):]
    row = row[: row.index("</a>") + 4]
    assert 'href="/entities' in row
    assert htmllib.escape(STRINGS["en"]["settings.business.title"]) in _plain(row)


def test_routine_helper_text_is_behind_the_question_mark(host):
    expected = {
        "/settings/security": ("settings-passkeys-help",),
        "/settings/data": ("settings-retention-help",),
        "/settings/archived": ("archive-retention-help",),
    }
    for path, keys in expected.items():
        html = host.get(f"{path}?lang=en").text
        for key in keys:
            assert f'id="{key}"' in html and f'aria-controls="{key}"' in html, (path, key)
        # Ids stay unique so aria-controls is unambiguous.
        ids = re.findall(r'\sid="([^"]+)"', html)
        assert len(ids) == len(set(ids)), (path, sorted({i for i in ids if ids.count(i) > 1}))


def test_czech_groups(host, admin):
    for key in GROUPS:
        html = admin.get(f"{_group_page(key)}?lang=cs").text
        assert STRINGS["cs"][f"settings.group.{key}"] in html
    assert STRINGS["cs"]["settings.business.title"] in _plain(host.get("/settings/account?lang=cs").text)


def test_search_reaches_settings_groups_and_help(host, admin):
    items = host.get("/api/command-palette").json()["items"]
    urls = {item.get("url") for item in items}
    assert {"/settings", "/guide", "/settings/security", "/settings/data"} <= urls
    assert "/admin/users" not in urls
    admin_urls = {item.get("url") for item in admin.get("/api/command-palette").json()["items"]}
    assert {"/admin/customers", "/admin/incidents"} <= admin_urls


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
                for key in [g for g in GROUPS if g != "technical"]:
                    page.goto(f"{base}{_group_page(key)}?lang={lang}")
                    overflow = page.evaluate(
                        "document.documentElement.scrollWidth - document.documentElement.clientWidth"
                    )
                    assert overflow <= 0, (lang, width, key, overflow)
                    assert page.locator("h1.airbnb-title").is_visible(), (lang, width, key)
                    if key == "account":
                        # the e-mail form is visible without opening anything
                        assert page.locator("#account-new-email").is_visible()
                    if key == "security":
                        # keyboard focus opens a ? tip and it stays inside the viewport
                        button = page.locator("[aria-controls='settings-passkeys-help']")
                        button.focus()
                        tip = page.locator("#settings-passkeys-help")
                        assert tip.is_visible()
                        box = tip.bounding_box()
                        assert box["x"] >= 0 and box["x"] + box["width"] <= width + 0.5
                        page.keyboard.press("Escape")
                    if capture:
                        EVIDENCE.mkdir(parents=True, exist_ok=True)
                        page.screenshot(path=str(EVIDENCE / f"settings-{key}-{width}-{lang}.png"), full_page=True)
                context.close()
        browser.close()


def test_technical_page_is_admin_only(host, admin):
    assert host.get("/settings/technical?lang=en").status_code == 404
    assert 'href="/settings/technical"' not in host.get("/settings?lang=en").text
    assert admin.get("/settings/technical?lang=en").status_code == 200
    assert 'href="/settings/technical"' in admin.get("/settings?lang=en").text
