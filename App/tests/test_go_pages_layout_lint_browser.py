"""Layout lint for Go-served host pages (brief 1668)."""
from __future__ import annotations

import os
from pathlib import Path

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
    LINT,
    SHOT_WIDTHS,
    assert_no_layout_findings,
    lint_go_paths,
    register_static_routes,
    settle_motion,
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


def test_go_guide_external_link_states_pass_the_lint(go_web, go_cookie):
    apt = go_web["apartment_id"]
    base = go_web["base_url"]
    guide = f"/apartments/{apt}/guide"
    guide_hash = guide + "#external"
    findings: list[dict] = []
    out = Path(os.environ.get("UBYHOST_SHOTS_DIR", "/tmp/shots1664")) / "layout-lint"
    out.mkdir(parents=True, exist_ok=True)

    def run_lint(page, label: str) -> None:
        page.wait_for_load_state("networkidle")
        settle_motion(page)
        page.evaluate("window.scrollTo(0, 0)")
        for item in page.evaluate(LINT):
            findings.append({"route": label, "width": page.viewport_size["width"], "finding": item})
        width = page.viewport_size["width"]
        page.screenshot(path=str(out / f"guide-external-{label}-{width}.png"), full_page=True)

    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        for width in SHOT_WIDTHS:
            context = browser.new_context(viewport={"width": width, "height": 1200})
            register_static_routes(context)
            context.add_cookies(
                [
                    {"name": "ubyhost_session", "value": go_cookie, "url": base + "/"},
                    {"name": "ubyhost_lang", "value": "en", "url": base + "/"},
                ]
            )
            page = context.new_page()
            with psycopg.connect(go_web["database_url"]) as conn, conn.cursor() as cur:
                cur.execute(
                    "UPDATE apartment SET guide_external_url = NULL WHERE id = %s", (apt,)
                )
                conn.commit()
            response = page.goto(f"{base}{guide_hash}")
            assert response and response.status < 400
            run_lint(page, "empty")

            page.goto(f"{base}{guide}")
            page.fill('input[name="guide_external_url"]', "https://www.notion.so/page")
            page.locator("#external form button.ui-btn-secondary").click()
            page.wait_for_load_state("networkidle")
            response = page.goto(f"{base}{guide_hash}")
            assert response and response.status < 400
            run_lint(page, "saved")

            page.goto(f"{base}{guide_hash}")
            page.fill('input[name="guide_external_url"]', "https://h.cz:8443")
            page.locator("#external form button.ui-btn-secondary").click()
            page.wait_for_load_state("networkidle")
            run_lint(page, "error")
            context.close()
        browser.close()
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


def _access_enc(plain: str) -> str:
    os.environ["UBYHOST_SECRET_KEY"] = "harness-fixture-secret-012345678901234567"
    from app import db

    return db.encrypt_field(plain)


def _access_clear(cur, apt: int) -> None:
    cur.execute("DELETE FROM apartment_entry_code WHERE apartment_id = %s", (apt,))
    cur.execute("UPDATE apartment SET lock_id = NULL, guide_external_url = NULL WHERE id = %s", (apt,))


def _access_seed(cur, apt: int, rows: list[tuple]) -> None:
    for pos, code_type, label, plain, until in rows:
        cur.execute(
            """INSERT INTO apartment_entry_code
               (apartment_id, position, code_type, custom_label, code_enc, valid_until, created_at, updated_at)
               VALUES (%s, %s, %s, %s, %s, %s, '2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00')""",
            (apt, pos, code_type, label, _access_enc(plain), until),
        )


def test_go_access_page_states_pass_the_layout_lint(go_web, go_cookie):
    apt = go_web["apartment_id"]
    base_path = f"/apartments/{apt}/access"
    long_label = "A" * 30 + " " + "B" * 29
    setups: dict[str, tuple[str, list[tuple]]] = {
        "access-empty": ("", []),
        "access-one": ("", [(1, "gate", None, "1234", None)]),
        "access-three": (
            "",
            [
                (1, "gate", None, "1001", None),
                (2, "building_entrance", None, "2002", None),
                (3, "garage", None, "3003", None),
            ],
        ),
        "access-other": ("?edit=1", [(1, "other", long_label, "9999", None)]),
        "access-expired": ("", [(1, "gate", None, "1234", "2020-01-01")]),
        "access-error": ("?add=1", []),
        "access-replaced": ("?edit=1", [(1, "gate", None, "1234", None)]),
        "access-preview-lock": ("", [(1, "gate", None, "4321", None)]),
        "access-preview-nolock": ("", [(1, "bike_room", None, "5555", None)]),
    }
    def _access_replace(page) -> None:
        page.locator('form#access-form input[name="code"]').fill("5678")
        page.locator('form#access-form button[type="submit"]').click()

    after = {"access-replaced": _access_replace}
    all_findings: list[dict] = []
    with psycopg.connect(go_web["database_url"]) as conn, conn.cursor() as cur:
        for name, (suffix, rows) in setups.items():
            _access_clear(cur, apt)
            if name == "access-preview-lock":
                cur.execute("UPDATE apartment SET lock_id = 'lint-lock' WHERE id = %s", (apt,))
            if name == "access-other":
                cur.execute(
                    "UPDATE apartment SET guide_external_url = %s WHERE id = %s",
                    ("https://www.notion.so/page", apt),
                )
            if rows:
                _access_seed(cur, apt, rows)
            conn.commit()
            paths = {name: base_path + suffix}
            all_findings.extend(
                lint_go_paths(go_web, paths, go_cookie, shot_labels={name: name}, after=after)
            )
    assert_no_layout_findings(all_findings)

    base = go_web["base_url"]
    with psycopg.connect(go_web["database_url"]) as conn, conn.cursor() as cur:
        _access_clear(cur, apt)
        conn.commit()
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        context = browser.new_context(java_script_enabled=False, viewport={"width": 390, "height": 900})
        register_static_routes(context)
        context.add_cookies(
            [
                {"name": "ubyhost_session", "value": go_cookie, "url": base + "/"},
                {"name": "ubyhost_lang", "value": "en", "url": base + "/"},
            ]
        )
        page = context.new_page()
        page.goto(f"{base}{base_path}?add=1")
        page.wait_for_selector("form#access-form, form[action$='/access']")
        page.select_option("select[name=code_type]", "other")
        page.fill('input[name="code"]', "n1")
        page.locator("form#access-form button[type=submit], form[action$='/access'] button[type=submit]").first.click()
        page.wait_for_load_state("networkidle")
        assert "Add a name for Other" in page.inner_text("body") or "other_label" in page.url
        assert page.locator('input[name="custom_label"]').count() == 1
        browser.close()


from tests.comfy_host_ux_checks import (  # noqa: E402, F401
    comfy_world,
    test_comfy_ux_all_pages_pass_layout_lint_and_capture_shots,
    test_comfy_ux_rigorous_geometry_and_design_invariants,
)

