"""Brief 0705: the v2 shell is opt-in per page; pages without v2 keep the old stylesheets and sidebar.

TODO (brief 0706): once the Overview renders on the v2 shell, add a route-level test that a v2 page
loads app2.css, not host2.css, and has one aside.side with aria-current on the active nav link.
"""

import os
import re
import secrets
from pathlib import Path

import pytest

from app import auth, db
from tests.conftest import mark_security_prompt_seen
from tests.browser_support import chromium_launch_kwargs
from tests.test_host_geometry import _browser_session_cookie, base  # noqa: F401
from tests.test_signed_in_chrome import host_with_property, old_shell_path  # noqa: F401

ROOT = Path(__file__).resolve().parents[1]
GAP_PX = 12  # brief 0826 and 0775: at least 12 px between neighbouring blocks
# Top and bottom blocks of the v2 sidebar, measured as direct children of aside.side (only visible ones count).
SHELL_BLOCKS_JS = """(() => {
  const visible = el => { const r = el.getBoundingClientRect(), s = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'; };
  const els = [...document.querySelectorAll('.side > *')].filter(visible).map(el => {
    const r = el.getBoundingClientRect();
    return {name: el.tagName.toLowerCase() + '.' + String(el.className).split(' ').filter(Boolean).join('.'),
            l: r.left, r: r.right, t: r.top, b: r.bottom};
  });
  const pairs = [];
  for (let i = 0; i < els.length; i++) for (let j = i + 1; j < els.length; j++) {
    let a = els[i], b = els[j];
    if (a.t > b.t) [a, b] = [b, a];
    const xo = Math.min(a.r, b.r) - Math.max(a.l, b.l);
    const yo = Math.min(a.b, b.b) - Math.max(a.t, b.t);
    if (xo > 0 && yo > 0) pairs.push({a: a.name, b: b.name, kind: 'overlap', gap: 0});
    else if (xo > 0) pairs.push({a: a.name, b: b.name, kind: 'stacked', gap: b.t - a.b});
    else if (yo > 0) { const left = a.r <= b.l ? a : b, right = left === a ? b : a;
      pairs.push({a: a.name, b: b.name, kind: 'side by side', gap: right.l - left.r}); }
  }
  return {names: els.map(e => e.name), pairs};
})()"""


def _sync_playwright():
    if os.environ.get("UBYHOST_REQUIRE_BROWSER") == "1":
        import playwright.sync_api as sync_api
    else:
        sync_api = pytest.importorskip("playwright.sync_api")
    return sync_api


def _account_0826():
    username = f"shell{secrets.token_hex(3)}"
    owner = mark_security_prompt_seen(auth.create_account(f"{username}@example.test", "Shell", role="host", username=username))
    entity = db.insert("legal_entity", {"name": "Shell s.r.o.", "owner_user_id": owner, "created_at": db.utcnow()})
    db.insert("apartment", {"internal_name": "Shell flat", "owner_user_id": owner, "legal_entity_id": entity,
                            "permalink_token": f"sh{secrets.token_hex(4)}", "active": 1, "created_at": db.utcnow()})
    return username


@pytest.mark.parametrize("width", [320, 390, 768, 1024, 1280, 1440])
def test_shell_top_blocks_keep_12px_gaps(base, width):
    sync_api = _sync_playwright()
    cookie = _browser_session_cookie(_account_0826())
    with sync_api.sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(**chromium_launch_kwargs())
        except Exception as exc:
            if os.environ.get("UBYHOST_REQUIRE_BROWSER") == "1":
                raise
            pytest.skip(f"Chromium is not available: {exc}")
        context = browser.new_context(viewport={"width": width, "height": 900})
        context.add_cookies([{"name": auth.SESSION_COOKIE, "value": cookie, "url": base + "/"}])
        page = context.new_page()
        for path in ("/", "/stay-fees"):
            page.goto(base + path + "?lang=en")
            page.wait_for_selector(".side", state="attached", timeout=30000)
            result = page.evaluate(SHELL_BLOCKS_JS)
            if width >= 1024:  # the sidebar is the shell here: brand, account, search and nav must show
                for name in ("div.ui-brand", "button.search", "nav.side-nav"):
                    assert any(n.startswith(name) for n in result["names"]), (path, width, result["names"])
            for pair in result["pairs"]:
                assert pair["kind"] != "overlap", (path, width, pair)
                assert pair["gap"] >= GAP_PX - 0.01, (path, width, pair)
        browser.close()


def test_non_v2_dashboard_still_loads_the_old_stylesheets_and_sidebar(host_with_property):
    # Old shell: / is v2 since 0720 and /settings since 0780, so the non-v2 check uses the booking-site page (old shell, see old_shell_path).
    page = host_with_property.get(old_shell_path()).text
    assert "/static/host2.css" in page
    assert "/static/skeleton.css" in page
    assert "app2.css" not in page
    assert 'class="ui-sidebar" id="app-sidebar"' in page
    assert 'class="side" id="app-sidebar"' not in page


def test_v2_branch_is_wired_in_base_html_and_the_v2_shell_exists():
    base = (ROOT / "app/templates/base.html").read_text(encoding="utf-8")
    assert re.search(r"/static/app2\.css\?v=[\w-]+", base)
    assert '{% include "_shell_v2.html" %}' in base
    assert '{% include "_shell_sidebar.html" %}' in base
    shell = (ROOT / "app/templates/_shell_v2.html").read_text(encoding="utf-8")
    assert 'class="side" id="app-sidebar"' in shell
    assert "data-command-open" in shell and 'action="/logout"' in shell


def test_app2_css_has_the_phone_top_bar_rule_and_no_font_picker():
    css = (ROOT / "app/static/app2.css").read_text(encoding="utf-8")
    assert "@media (max-width: 767px)" in css
    assert "fontpick" not in css and "body.f-" not in css
    assert "--acc:#d0452d" in css  # v2 accent token as copied into app2.css (no --coral-600 there)
