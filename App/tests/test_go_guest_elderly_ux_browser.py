"""Playwright Chromium UX and accessibility regression test for the Go guest
registration flow (elderly-friendly readability, contrast, tap targets, calm
inline validation, A/A+ large-text mode without cookies, and full E2E submit).
"""
from __future__ import annotations

import os
import secrets
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import psycopg
import pytest
from playwright.sync_api import sync_playwright

from tests.browser_support import chromium_launch_kwargs, settle_motion
from tests.go_web_harness import (
    APP_DIR,
    FIXTURE_SECRET,
    GO_DIR,
    MIGRATIONS_DIR,
    _pick_port,
    register_static_routes,
)

LINT_JS = (APP_DIR / "tests" / "layout_lint.js").read_text(encoding="utf-8")

AUDIT_JS = """() => {
  const overflow = Math.round(document.documentElement.scrollWidth - window.innerWidth);
  const bodyFont = parseFloat(getComputedStyle(document.body).fontSize);
  const badTargets = [];
  for (const el of document.querySelectorAll('a, button, summary, input:not([type=hidden]):not(.g-vh), select:not(.g-vh)')) {
    const r = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    if (r.width === 0 || r.height === 0 || cs.visibility === 'hidden' || cs.display === 'none') continue;
    if (el.classList.contains('skip-link') || el.classList.contains('g-sr-only')) continue;
    if (el.type === 'checkbox' || el.type === 'radio') continue;
    if (el.closest('.g-step-error-summary')) continue;
    const closedDetails = el.closest('details:not([open])');
    if (closedDetails && el.tagName !== 'SUMMARY') continue;
    if (r.height < 43.5) {
      badTargets.push({
        tag: el.tagName,
        cls: el.className,
        text: (el.innerText || el.getAttribute('aria-label') || '').trim().slice(0, 40),
        h: Math.round(r.height),
      });
    }
  }
  return { overflow, bodyFont, badTargets };
}"""


def _seed_guest_property(test_db: str, token: str) -> int:
    now_iso = "2026-11-27T12:00:00+00:00"
    with psycopg.connect(test_db) as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO user_account (username, password_hash, role, active, session_version, created_at, email)
               VALUES ('host_elderly_ux', 'x', 'host', 1, 1, %s, 'host@example.test') RETURNING id""",
            (now_iso,),
        )
        uid = cur.fetchone()[0]
        cur.execute(
            """INSERT INTO legal_entity (owner_user_id, name, seat, ico, contact_email, created_at)
               VALUES (%s, 'Karlin Stays s.r.o.', 'Sokolovska 10, Praha', '12345678', 'host@example.test', %s)
               RETURNING id""",
            (uid, now_iso),
        )
        eid = cur.fetchone()[0]
        cur.execute(
            """INSERT INTO apartment (
                   owner_user_id, legal_entity_id, internal_name, permalink_token, permalink_pin,
                   city_en, addr_street, addr_house_no, addr_zip, addr_obec, guest_message,
                   automation_mode, submit_after_hours, checkin_hour, checkout_hour, active, created_at
               ) VALUES (
                   %s, %s, 'Vinohrady Sunny Flat', %s, '123456',
                   'Prague', 'Korunni', '42', '12000', 'Praha 2',
                   'Welcome! Keys are in the lockbox next to the main entrance. Call us anytime if you need help.',
                   'scheduled', 24, 15, 10, 1, %s
               ) RETURNING id""",
            (uid, eid, token, now_iso),
        )
        apt_id = cur.fetchone()[0]
        cur.execute(
            """INSERT INTO reservation (apartment_id, source, uid, date_from, date_to, status, created_at, updated_at)
               VALUES (%s, 'manual', 'r-elderly-1', '2026-11-27', '2026-11-30', 'active', %s, %s)
               RETURNING id""",
            (apt_id, now_iso, now_iso),
        )
        res_id = cur.fetchone()[0]
        conn.commit()
    return int(res_id)


def test_go_guest_elderly_ux_flow_geometry_and_a11y():
    base_db = os.environ.get(
        "UBYHOST_TEST_DATABASE_URL",
        "postgres://postgres:postgres@localhost:5432/ubyhost_test?sslmode=disable",
    )
    db_name = f"ubyhost_gelderly_{secrets.token_hex(4)}"
    parsed = urlparse(base_db)
    test_db = urlunparse(parsed._replace(path=f"/{db_name}"))
    token = f"elderly{secrets.token_hex(6)}"

    admin = psycopg.connect(base_db, autocommit=True)
    admin.execute(f'CREATE DATABASE "{db_name}"')
    admin.close()

    work = Path(tempfile.mkdtemp(prefix="guest-elderly-test-"))
    binary = work / "ubyhost-web"
    data_dir = work / "data"
    data_dir.mkdir()
    proc = None
    try:
        subprocess.run(
            ["go", "build", "-buildvcs=false", "-o", str(binary), "./cmd/ubyhost-web"],
            cwd=GO_DIR,
            check=True,
        )
        subprocess.run(
            [sys.executable, "scripts/pg_schema.py", "apply", "--expect-database", db_name],
            cwd=APP_DIR,
            env={**os.environ, "UBYHOST_DATABASE_URL": test_db},
            check=True,
        )
        res_id = _seed_guest_property(test_db, token)
        port = _pick_port()
        base_http = f"http://127.0.0.1:{port}"
        proc = subprocess.Popen(
            [str(binary)],
            env={
                **os.environ,
                "UBYHOST_DATABASE_URL": test_db,
                "UBYHOST_GO_ADDR": f"127.0.0.1:{port}",
                "UBYHOST_MIGRATIONS_DIR": str(MIGRATIONS_DIR.resolve()),
                "UBYHOST_SECRET_KEY": FIXTURE_SECRET,
                "UBYHOST_PUBLIC_BASE_URL": base_http,
                "UBYHOST_DATA_DIR": str(data_dir),
                "UBYHOST_DEPLOYMENT": "dev",
                "UBYHOST_GUEST_PIN": "1",
                "UBYHOST_MAIL_ENABLED": "0",
                "UBYHOST_MAIL_BACKEND": "",
            },
            stdout=subprocess.DEVNULL,
            stderr=subprocess.STDOUT,
        )
        for _ in range(80):
            try:
                if urllib.request.urlopen(f"{base_http}/healthz", timeout=1).status == 200:
                    break
            except Exception:
                time.sleep(0.2)
        else:
            pytest.fail("Go ubyhost-web did not become ready on /healthz")

        def assert_screen(page, name: str, min_body_font: float = 17.0):
            settle_motion(page)
            audit = page.evaluate(AUDIT_JS)
            lint = page.evaluate(LINT_JS)
            assert audit["overflow"] <= 0, (name, audit)
            assert audit["bodyFont"] >= min_body_font, (name, audit)
            assert audit["badTargets"] == [], (name, audit["badTargets"])
            assert lint == [], (name, lint)

        with sync_playwright() as pw:
            browser = pw.chromium.launch(**chromium_launch_kwargs())
            ctx = browser.new_context(viewport={"width": 390, "height": 844})
            register_static_routes(ctx)
            page = ctx.new_page()

            page.goto(f"{base_http}/l/{token}?lang=en")
            page.wait_for_load_state("networkidle")
            assert_screen(page, "pin_390")

            page.fill("#pin", "123456")
            page.click('button[type="submit"]')
            page.wait_for_load_state("networkidle")
            assert_screen(page, "pick_390")

            page.click(f'a[href*="/{res_id}"]')
            page.wait_for_load_state("networkidle")
            assert_screen(page, "step1_390")

            # Calm inline validation summary with zero sticky-bar occlusion and no duplicate country error.
            page.locator('[data-guest-step]:visible .g-wizard-nav .g-btn:not(.secondary)').click()
            page.wait_for_timeout(150)
            err_check = page.evaluate("""() => ({
              summaryCount: document.querySelectorAll('.g-step-error-summary').length,
              inlineErrors: document.querySelectorAll('.g-field-inline-err').length,
              comboErrVisible: Array.from(document.querySelectorAll('.g-combo-error')).filter(e => !e.hidden).length,
            })""")
            assert err_check["summaryCount"] == 1
            assert err_check["inlineErrors"] >= 3
            assert err_check["comboErrVisible"] == 0
            assert_screen(page, "step1_error_390")

            # A+ large-text toggle scales typography without setting any cookie.
            cookies_before = {c["name"] for c in ctx.cookies()}
            page.click("[data-text-size-toggle]")
            page.wait_for_timeout(100)
            assert {c["name"] for c in ctx.cookies()} == cookies_before
            assert_screen(page, "step1_large_390", min_body_font=20.0)
            page.click("[data-text-size-toggle]")
            page.wait_for_timeout(100)

            # Forgiving DOB normalization + full 3-step submit -> Review & Confirm -> All Done.
            page.fill("#first_name", "Margaret")
            page.fill("#surname", "Henderson")
            page.fill("#birth_date", "14/05/1951")
            page.locator("#birth_date").blur()
            page.wait_for_timeout(100)
            assert page.input_value("#birth_date") == "14.05.1951"
            assert "14 May 1951" in page.locator("#birth-date-readback").inner_text()
            page.fill("#nationality_search", "Germany")
            page.wait_for_timeout(120)
            page.locator("#nationality_list li").first.click()
            page.fill("#doc_number", "C01X00T47")
            page.locator('[data-guest-step]:visible .g-wizard-nav .g-btn:not(.secondary)').click()
            page.wait_for_timeout(150)
            assert_screen(page, "step2_390")

            page.fill("#res_street", "Lindenstrasse 18")
            page.fill("#res_city", "Munich")
            page.locator('[data-guest-step]:visible .g-wizard-nav .g-btn:not(.secondary)').click()
            page.wait_for_timeout(150)

            canvas = page.locator("canvas").first
            box = canvas.bounding_box()
            page.mouse.move(box["x"] + 36, box["y"] + box["height"] * 0.6)
            page.mouse.down()
            page.mouse.move(box["x"] + box["width"] - 36, box["y"] + box["height"] * 0.5, steps=8)
            page.mouse.up()
            page.wait_for_timeout(100)
            assert page.locator(".g-sign-ready").is_visible()
            page.locator("#legal_ack").check()
            assert_screen(page, "step3_sign_390")

            page.click("[data-guest-save]")
            page.wait_for_load_state("networkidle")
            assert_screen(page, "review_confirm_390")

            page.click("[data-confirm-registration]")
            page.wait_for_load_state("networkidle")
            assert_screen(page, "all_done_390")

            # Tablet 768px & Desktop 1280px & narrow 360px responsive layout checks.
            edit_href = page.locator('a[href*="/edit/"]').first.get_attribute("href")
            page.set_viewport_size({"width": 768, "height": 1024})
            page.goto(f"{base_http}{edit_href}")
            page.wait_for_load_state("networkidle")
            assert_screen(page, "tablet_768")
            tablet_card_w = page.evaluate(
                "() => Math.round(document.querySelector('.g-card:not([hidden])').getBoundingClientRect().width)"
            )
            assert tablet_card_w <= 650, f"Tablet form stretched too wide: {tablet_card_w}px"

            page.set_viewport_size({"width": 1280, "height": 900})
            page.wait_for_timeout(100)
            assert_screen(page, "desktop_1280")
            desktop_footer_gap = page.evaluate("""() => {
              const host = document.getElementById('host-contact');
              const foot = document.querySelector('.g-foot');
              return Math.round(foot.getBoundingClientRect().top - host.getBoundingClientRect().bottom);
            }""")
            assert desktop_footer_gap < 150, f"Desktop grid void before footer: {desktop_footer_gap}px"

            page.set_viewport_size({"width": 360, "height": 800})
            assert page.evaluate("() => document.documentElement.scrollWidth - window.innerWidth") <= 0
            page.click("[data-text-size-toggle]")
            assert page.evaluate("() => document.documentElement.scrollWidth - window.innerWidth") <= 0
            ctx.close()

            # No-JS fallback works cleanly.
            nojs_ctx = browser.new_context(viewport={"width": 390, "height": 844}, java_script_enabled=False)
            register_static_routes(nojs_ctx)
            nojs_page = nojs_ctx.new_page()
            nojs_page.goto(f"{base_http}/l/{token}?lang=en")
            nojs_page.fill("#pin", "123456")
            nojs_page.click('button[type="submit"]')
            nojs_page.wait_for_load_state("networkidle")
            assert f"/{res_id}" in nojs_page.content()
            nojs_ctx.close()
            browser.close()
    finally:
        if proc is not None:
            proc.terminate()
            proc.wait(timeout=5)
        admin = psycopg.connect(base_db, autocommit=True)
        admin.execute(f'DROP DATABASE "{db_name}" WITH (FORCE)')
        admin.close()
