"""1075-cont-1: the next-number hint wraps inside the open "More invoice options" fold."""
from __future__ import annotations

import os
import secrets
import socket
import threading
import time

import pytest
import uvicorn
from fastapi.testclient import TestClient

REQUIRE_BROWSER = os.environ.get("UBYHOST_REQUIRE_BROWSER") == "1"
if REQUIRE_BROWSER:
    import playwright.sync_api as sync_api
else:
    sync_api = pytest.importorskip("playwright.sync_api")

from app import auth, db
from app.main import app
from tests.browser_support import chromium_launch_kwargs
from tests.conftest import login_as, mark_security_prompt_seen

TIP = "#invoice-next-number-help"

# Inside details on .entities-page the ? button is hidden (0543) and the hint is plain text,
# so the test reads the always-visible text; it never clicks.
MEASURE = """() => {
  const tip = document.querySelector('#invoice-next-number-help');
  const fold = tip.closest('details.invoice-more');
  const label = tip.closest('label');
  const r = tip.getBoundingClientRect();
  const f = fold.getBoundingClientRect();
  const cs = getComputedStyle(fold);
  const contentRight = f.right - parseFloat(cs.borderRightWidth) - parseFloat(cs.paddingRight);
  const chain = [];
  for (let el = tip; el && el !== document.body; el = el.parentElement) {
    const s = getComputedStyle(el);
    chain.push([el.tagName + '.' + el.className, el.scrollWidth, el.clientWidth, s.display, s.flex,
                s.whiteSpace, s.minWidth, Math.round(el.getBoundingClientRect().width)]);
  }
  return {open: fold.open, top: r.top, bottom: r.bottom, right: r.right, contentRight,
          tipScroll: tip.scrollWidth, tipClient: tip.clientWidth,
          labelScroll: label.scrollWidth, labelClient: label.clientWidth,
          docScroll: document.documentElement.scrollWidth, inner: window.innerWidth, chain};
}"""


@pytest.fixture(scope="module")
def host():
    db.init_db()
    username = f"fold-tip-{secrets.token_hex(4)}"
    owner_id = mark_security_prompt_seen(auth.create_account(
        f"{username}@example.test", "Fold Tip", role="host", username=username
    ))
    entity_id = db.insert("legal_entity", {
        "name": "Fold Tip 1075 s.r.o.", "seat": "Praha", "ico": "12345678", "contact_email": "biz@example.test",
        "vat_status": "non_payer", "invoice_due_days": 14, "invoice_prefix": "UB",
        "owner_user_id": owner_id, "created_at": db.utcnow(),
    })
    client = TestClient(app)
    response = login_as(client, username, url="/login?lang=en", follow_redirects=False)
    assert response.status_code == 303, response.text
    yield {"client": client, "owner": owner_id, "entity": entity_id}
    db.execute("DELETE FROM audit WHERE owner_user_id = ?", (owner_id,))
    db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (owner_id,))
    db.execute("DELETE FROM user_account WHERE id = ?", (owner_id,))


@pytest.fixture(scope="module")
def base(host):
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
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=5)


@pytest.mark.parametrize("width", [390, 768, 1280])
def test_next_number_hint_wraps_inside_the_fold(host, base, width):
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        context = browser.new_context(viewport={"width": width, "height": 800})
        cookie = host["client"].cookies.get(auth.SESSION_COOKIE)
        context.add_cookies([{"name": auth.SESSION_COOKIE, "value": cookie, "url": base + "/"}])
        page = context.new_page()
        page.goto(f"{base}/entities?edit={host['entity']}&lang=en")
        page.locator(TIP).scroll_into_view_if_needed()
        m = page.evaluate(MEASURE)
        browser.close()
    assert m["open"], "the fold must render open when a prefix is set"
    assert m["bottom"] > m["top"], m
    assert m["right"] <= m["contentRight"] - 16 + 0.5, m
    assert m["tipScroll"] <= m["tipClient"], m
    assert m["labelScroll"] <= m["labelClient"], m
    assert m["docScroll"] <= m["inner"], m
