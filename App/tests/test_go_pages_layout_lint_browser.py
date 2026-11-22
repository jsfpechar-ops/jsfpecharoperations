"""Layout lint for Go-served host pages (brief 1668)."""
from __future__ import annotations

import os

os.environ.setdefault("UBYHOST_APIFY_TOKEN", "harness-apify-token")

import psycopg
import pytest

pytest_plugins = ("tests.go_web_harness",)

REQUIRE_BROWSER = os.environ.get("UBYHOST_REQUIRE_BROWSER") == "1"
if REQUIRE_BROWSER:
    import playwright.sync_api as sync_api
else:
    sync_api = pytest.importorskip("playwright.sync_api")

from tests.browser_support import chromium_launch_kwargs
from tests.go_web_harness import (
    assert_no_layout_findings,
    lint_go_paths,
    register_static_routes,
)

GO_PATHS = {
    "guide": "/apartments/{apt}/guide",
    "leon": "/apartments/{apt}/leon",
    "guide-qr": "/apartments/{apt}/guide/qr",
    "guide-quick": "/apartments/{apt}/guide/quick",
    "guide-card-wifi": "/apartments/{apt}/guide/{item}",
}


def _resolved_paths(go_web: dict, item_id: int | None = None) -> dict[str, str]:
    apt = go_web["apartment_id"]
    paths: dict[str, str] = {}
    for name, template in GO_PATHS.items():
        if name == "guide-card-wifi":
            if item_id is None:
                continue
            paths[name] = template.format(apt=apt, item=item_id)
        else:
            paths[name] = template.format(apt=apt)
    return paths


def _wifi_item_id(go_web: dict, cookie: str) -> int:
    base = go_web["base_url"]
    apt = go_web["apartment_id"]
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        context = browser.new_context()
        register_static_routes(context)
        context.add_cookies(
            [
                {"name": "ubyhost_session", "value": cookie, "url": base + "/"},
                {"name": "ubyhost_lang", "value": "en", "url": base + "/"},
            ]
        )
        page = context.new_page()
        page.goto(f"{base}/apartments/{apt}/guide")
        page.wait_for_load_state("networkidle")
        browser.close()
    with psycopg.connect(go_web["database_url"]) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM guide_item WHERE apartment_id = %s AND kind = 'wifi'",
            (apt,),
        )
        row = cur.fetchone()
        assert row, "wifi guide_item missing after first /guide visit"
        return row[0]


def test_go_host_pages_pass_the_layout_lint(go_web, go_cookie):
    item_id = _wifi_item_id(go_web, go_cookie)
    paths = _resolved_paths(go_web, item_id)
    order = ("guide", "leon", "guide-qr", "guide-quick", "guide-card-wifi")
    findings = lint_go_paths(go_web, {k: paths[k] for k in order}, go_cookie)
    assert_no_layout_findings(findings)


def test_go_harness_signs_in_and_loads_css(go_web, go_cookie):
    apt = go_web["apartment_id"]
    base = go_web["base_url"]
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        context = browser.new_context(viewport={"width": 390, "height": 900})
        register_static_routes(context)
        context.add_cookies(
            [
                {"name": "ubyhost_session", "value": go_cookie, "url": base + "/"},
                {"name": "ubyhost_lang", "value": "en", "url": base + "/"},
            ]
        )
        page = context.new_page()
        response = page.goto(f"{base}/apartments/{apt}/guide")
        assert response and response.status == 200
        assert "Layout lint flat" in page.inner_text("body")
        serif = page.evaluate(
            "() => window.getComputedStyle(document.body).fontFamily.toLowerCase()"
        )
        assert "times" not in serif and serif != "serif"
        browser.close()


def _hide_security_prompt(go_web: dict) -> None:
    with psycopg.connect(go_web["database_url"]) as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE user_account SET two_factor_prompted_at = '2026-01-01T00:00:00+00:00' WHERE id = %s",
            (go_web["host_id"],),
        )
        conn.commit()


def _seed_url_notice(go_web: dict, count: int) -> None:
    apt = go_web["apartment_id"]
    with psycopg.connect(go_web["database_url"]) as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM guide_import WHERE apartment_id = %s", (apt,))
        cur.execute(
            """INSERT INTO guide_import (apartment_id, source, url, status, codes_left_out, used_at, created_at)
               VALUES (%s, 'url', 'https://www.notion.so/test/page', 'used', %s, '2026-01-02', '2026-01-01')""",
            (apt, count),
        )
        conn.commit()


def test_go_guide_import_public_url_states_pass_the_lint(go_web, go_cookie):
    _hide_security_prompt(go_web)
    apt = go_web["apartment_id"]
    path = f"/apartments/{apt}/guide"
    cases = [
        ("empty", path, None),
        ("notice", path, 3),
        ("notice-one", path, 1),
        ("error", path + "?err=flash.error.guide_import_public_url#import", None),
        ("queued", path + "?msg=flash.guest_guide.import_queued#import", None),
    ]
    findings: list = []
    for label, url, notice in cases:
        if notice is not None:
            _seed_url_notice(go_web, notice)
        elif label == "empty":
            with psycopg.connect(go_web["database_url"]) as conn, conn.cursor() as cur:
                cur.execute("DELETE FROM guide_import WHERE apartment_id = %s", (apt,))
                conn.commit()
        findings.extend(
            lint_go_paths(
                go_web,
                {label: url},
                go_cookie,
                shot_labels={label: f"guide-import-url-{label}"},
            )
        )
    assert_no_layout_findings(findings)


def test_go_harness_rejects_a_signed_out_request(go_web):
    apt = go_web["apartment_id"]
    base = go_web["base_url"]
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        context = browser.new_context()
        page = context.new_page()
        response = page.goto(f"{base}/apartments/{apt}/guide", wait_until="commit")
        final_url = page.url
        status = response.status if response else 0
        browser.close()
    if "/login" in final_url:
        assert status in (200, 302, 303, 307, 308)
        return
    assert status in (401, 403), f"expected auth failure, got {status} url={final_url}"