"""Playwright Chromium layout-lint and geometry invariants for Go 2091-2096 UX."""
from __future__ import annotations

import os
from pathlib import Path

import psycopg
import pytest

REQUIRE_BROWSER = os.environ.get("UBYHOST_REQUIRE_BROWSER") == "1"
if REQUIRE_BROWSER:
    import playwright.sync_api as sync_api
else:
    sync_api = pytest.importorskip("playwright.sync_api")

from tests.browser_support import chromium_launch_kwargs, settle_motion
from tests.go_web_harness import (
    SHOT_WIDTHS,
    assert_no_layout_findings,
    lint_go_paths,
    register_static_routes,
)


def _shots_dir() -> Path:
    base = os.environ.get("UBYHOST_SHOTS_DIR")
    out = Path(base) / "layout-lint" if base else Path("/tmp/ubyhost-layout-lint")
    out.mkdir(parents=True, exist_ok=True)
    return out


def _enc(plain: str) -> str:
    os.environ["UBYHOST_SECRET_KEY"] = "harness-fixture-secret-012345678901234567"
    from app import db

    return db.encrypt_field(plain)


@pytest.fixture(scope="module")
def autofiling_world(go_web):
    """Seed operator, scheduled + legacy-NULL apartments, and complete stays."""
    host_id = go_web["host_id"]
    now_iso = "2026-12-08T10:00:00+00:00"
    with psycopg.connect(go_web["database_url"]) as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO legal_entity
               (owner_user_id, name, seat, ico, contact_email, created_at)
               VALUES (%s, 'Karlin Stays s.r.o.', 'Sokolovska 10, 18600 Praha',
                       '12345678', 'ops@karlin.test', %s)
               RETURNING id""",
            (host_id, now_iso),
        )
        entity_id = cur.fetchone()[0]

        cur.execute(
            """INSERT INTO apartment
               (owner_user_id, legal_entity_id, internal_name, permalink_token, permalink_pin,
                city_en, addr_street, addr_house_no, addr_zip, addr_obec,
                uby_idub, uby_mark, uby_name, uby_contact, uby_ws_user, uby_ws_password_enc,
                automation_mode, submit_after_hours, checkin_hour, checkout_hour, active, created_at)
               VALUES (%s, %s, 'Karlin Loft', 'ux-karlin-loft', '654321',
                       'Prague', 'Sokolovska', '10', '18600', 'Praha 8',
                       '123456789012', 'KARLI', 'KARLIN LOFT', 'ops@karlin.test', 'UBY-WS_KARLI', %s,
                       'scheduled', 24, 15, 10, 1, %s)
               RETURNING id""",
            (host_id, entity_id, _enc("test-ws-pass"), now_iso),
        )
        apt_scheduled = cur.fetchone()[0]

        cur.execute(
            """INSERT INTO apartment
               (owner_user_id, legal_entity_id, internal_name, permalink_token, permalink_pin,
                city_en, addr_street, addr_house_no, addr_zip, addr_obec,
                uby_idub, uby_mark, uby_name, uby_contact, uby_ws_user, uby_ws_password_enc,
                automation_mode, submit_after_hours, checkin_hour, checkout_hour, active, created_at)
               VALUES (%s, %s, 'Legacy Flat', 'ux-legacy-flat', '112233',
                       'Prague', 'Dlouha', '5', '11000', 'Praha 1',
                       '987654321098', 'LEGAC', 'LEGACY FLAT', 'ops@karlin.test', 'UBY-WS_LEGAC', %s,
                       'immediate', 24, NULL, NULL, 1, %s)
               RETURNING id""",
            (host_id, entity_id, _enc("test-ws-pass"), now_iso),
        )
        apt_legacy = cur.fetchone()[0]

        def _seed_stay_and_guest(apt_id: int, uid: str) -> int:
            cur.execute(
                """INSERT INTO reservation
                   (apartment_id, source, uid, date_from, date_to,
                    expected_guests_override, registration_completed_at, status, created_at, updated_at)
                   VALUES (%s, 'manual', %s, '2026-12-10', '2026-12-13',
                           1, %s, 'active', %s, %s)
                   RETURNING id""",
                (apt_id, uid, now_iso, now_iso, now_iso),
            )
            res_id = cur.fetchone()[0]
            cur.execute(
                """INSERT INTO guest
                   (reservation_id, surname, first_name, birth_date, nationality,
                    doc_number_enc, res_street, res_city, res_country, purpose,
                    stay_from, stay_to, is_lead, submit_state, created_at, updated_at)
                   VALUES (%s, 'Weber', 'Lukas', '1985-04-12', 'DEU',
                           %s, 'Berliner Str. 12', 'Berlin', 'DEU', '10',
                           '2026-12-10', '2026-12-13', 1, 'ready', %s, %s)""",
                (res_id, _enc("C01X00T47"), now_iso, now_iso),
            )
            return res_id

        res_scheduled = _seed_stay_and_guest(apt_scheduled, "ux-res-sched")
        res_immediate = _seed_stay_and_guest(apt_legacy, "ux-res-immed")
        conn.commit()

    return {
        "apt_scheduled": apt_scheduled,
        "apt_legacy": apt_legacy,
        "res_scheduled": res_scheduled,
        "res_immediate": res_immediate,
    }


def _open_police_section(page) -> None:
    btn = page.locator('[data-prop-tab="police"], a[href*="section=police"]').first
    if btn.count() > 0 and btn.is_visible():
        btn.click()
        page.wait_for_timeout(120)
    page.evaluate(
        "() => { const d = document.getElementById('sec-police'); if (d && d.tagName === 'DETAILS') d.open = true; }"
    )


def test_checkin_autofiling_pages_pass_layout_lint(go_web, go_cookie, autofiling_world):
    w = autofiling_world
    paths = {
        "2093-apartments-new": "/apartments/new",
        "2093-property-settings": f"/apartments/{w['apt_scheduled']}",
        "2093-property-police": f"/apartments/{w['apt_scheduled']}?view=settings&section=police#sec-police",
        "2093-property-legacy-null": f"/apartments/{w['apt_legacy']}",
        "2093-wizard-property": f"/apartments/{w['apt_scheduled']}/setup/property",
        "2093-wizard-police": f"/apartments/{w['apt_scheduled']}/setup/police",
        "2093-stay-detail-scheduled": f"/reservations/{w['res_scheduled']}",
        "2093-stay-detail-immediate": f"/reservations/{w['res_immediate']}",
        "2093-stays-list": "/reservations",
        "2093-guide-reporting": "/guide#reporting",
    }
    findings = lint_go_paths(
        go_web, paths, go_cookie, after={"2093-property-police": _open_police_section}
    )
    assert_no_layout_findings(findings)


def test_checkin_autofiling_geometry_and_tooltips(go_web, go_cookie, autofiling_world):
    base = go_web["base_url"]
    w = autofiling_world
    shots = _shots_dir()
    problems: list[str] = []

    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        for width in SHOT_WIDTHS:
            context = browser.new_context(viewport={"width": width, "height": 1000})
            context.add_cookies(
                [
                    {"name": "ubyhost_session", "value": go_cookie, "url": base + "/"},
                    {"name": "ubyhost_lang", "value": "en", "url": base + "/"},
                ]
            )
            register_static_routes(context)
            page = context.new_page()

            card_pages = [
                (
                    "property-police",
                    f"/apartments/{w['apt_scheduled']}?view=settings&section=police#sec-police",
                    ("automation-scheduled-help", "automation-immediate-help", "automation-manual-help"),
                    True,
                ),
                (
                    "wizard-police",
                    f"/apartments/{w['apt_scheduled']}/setup/police",
                    ("wizard-scheduled-help", "wizard-immediate-help", "wizard-manual-help"),
                    False,
                ),
            ]
            for label, path, tip_ids, needs_open in card_pages:
                resp = page.goto(f"{base}{path}")
                assert resp and resp.status == 200
                page.wait_for_load_state("networkidle")
                if needs_open:
                    _open_police_section(page)
                settle_motion(page)

                overflow = page.evaluate("() => document.documentElement.scrollWidth - window.innerWidth")
                if overflow > 0:
                    problems.append(f"{label}@{width}: horizontal overflow by {overflow}px")

                cards = page.evaluate(
                    """() => Array.from(document.querySelectorAll('.ui-choice-cards .ui-choice-card')).map(c => {
                        const r = c.getBoundingClientRect();
                        const inp = c.querySelector('input[type="radio"]');
                        return {val: inp ? inp.value : '', l: Math.round(r.left), r: Math.round(r.right),
                                t: Math.round(r.top), b: Math.round(r.bottom), w: Math.round(r.width), h: Math.round(r.height)};
                    })"""
                )
                if [c["val"] for c in cards] != ["scheduled", "immediate", "manual"]:
                    problems.append(f"{label}@{width}: card order {[c['val'] for c in cards]}")
                min_h = 44 if label == "property-police" else 18
                for idx, c in enumerate(cards):
                    if c["w"] < 150 or c["h"] < min_h:
                        problems.append(f"{label}@{width}: card {c['val']} collapsed {c['w']}x{c['h']} (min_h={min_h})")
                    if c["l"] < 0 or c["r"] > width + 1:
                        problems.append(f"{label}@{width}: card {c['val']} out of viewport [{c['l']}..{c['r']}]")
                    if idx > 0:
                        p = cards[idx - 1]
                        if min(p["r"], c["r"]) - max(p["l"], c["l"]) > 1 and min(p["b"], c["b"]) - max(p["t"], c["t"]) > 1:
                            problems.append(f"{label}@{width}: card {p['val']} overlaps {c['val']}")

                hours = page.evaluate(
                    "() => { const e = document.querySelector('input[name=\"submit_after_hours\"]'); return e ? {min: e.min, max: e.max, val: e.value} : null; }"
                )
                if not hours or hours["max"] != "24" or hours["min"] != "1":
                    problems.append(f"{label}@{width}: submit_after_hours={hours}")

                for tip_id in tip_ids:
                    btn = page.locator(f'button.help-tip-btn[aria-controls="{tip_id}"]')
                    if btn.count() != 1:
                        problems.append(f"{label}@{width}: missing help-tip button for {tip_id}")
                        continue
                    btn.scroll_into_view_if_needed()
                    btn.click()
                    page.wait_for_timeout(120)
                    box = page.evaluate(
                        """(id) => {
                            const el = document.getElementById(id);
                            if (!el) return null;
                            const r = el.getBoundingClientRect();
                            const cs = window.getComputedStyle(el);
                            return {l: Math.round(r.left), r: Math.round(r.right), t: Math.round(r.top), b: Math.round(r.bottom),
                                    w: Math.round(r.width), h: Math.round(r.height), op: parseFloat(cs.opacity), text: (el.innerText || '').trim()};
                        }""",
                        tip_id,
                    )
                    if not box or box["w"] < 60 or box["h"] < 16 or box["op"] < 0.9:
                        problems.append(f"{label}@{width}: tooltip {tip_id} not visible on click: {box}")
                    else:
                        if box["l"] < 0 or box["r"] > width:
                            problems.append(f"{label}@{width}: tooltip {tip_id} clips viewport [{box['l']}..{box['r']}]/{width}")
                        if "15:00" not in box["text"]:
                            problems.append(f"{label}@{width}: tooltip {tip_id} missing 15:00 example: {box['text']!r}")
                        bleed = page.evaluate(
                            """(id) => {
                                const tip = document.getElementById(id);
                                const r = tip.getBoundingClientRect();
                                const btns = Array.from(document.querySelectorAll('.help-tip-btn')).filter(b => b.getAttribute('aria-controls') !== id);
                                for (const b of btns) {
                                    const br = b.getBoundingClientRect();
                                    const cx = (br.left + br.right) / 2, cy = (br.top + br.bottom) / 2;
                                    if (cx >= r.left && cx <= r.right && cy >= r.top && cy <= r.bottom) {
                                        const topEl = document.elementFromPoint(cx, cy);
                                        if (topEl && !tip.contains(topEl)) {
                                            return {controls: b.getAttribute('aria-controls'), topTag: topEl.tagName, topClass: topEl.className};
                                        }
                                    }
                                }
                                return null;
                            }""",
                            tip_id,
                        )
                        if bleed:
                            problems.append(f"{label}@{width}: tooltip {tip_id} occluded by sibling control {bleed}")
                    if tip_id.endswith("scheduled-help") and width in (390, 1280):
                        page.screenshot(path=str(shots / f"2093-{label}-tooltip-{width}.png"), full_page=False)
                    page.keyboard.press("Escape")
                    page.wait_for_timeout(60)

            for label, path in (
                ("apartments-new", "/apartments/new"),
                ("property-settings", f"/apartments/{w['apt_scheduled']}"),
                ("wizard-property", f"/apartments/{w['apt_scheduled']}/setup/property"),
            ):
                resp = page.goto(f"{base}{path}")
                assert resp and resp.status == 200
                page.wait_for_load_state("networkidle")
                settle_motion(page)
                tcheck = page.evaluate(
                    """() => {
                        const ci = document.querySelector('select[name="checkin_hour"]');
                        const co = document.querySelector('select[name="checkout_hour"]');
                        if (!ci || !co) return null;
                        const r1 = ci.getBoundingClientRect(), r2 = co.getBoundingClientRect();
                        return {ciReq: ci.required, coReq: co.required, r1r: Math.round(r1.right), r2r: Math.round(r2.right),
                                overflow: document.documentElement.scrollWidth - window.innerWidth};
                    }"""
                )
                if not tcheck or not tcheck["ciReq"] or not tcheck["coReq"]:
                    problems.append(f"{label}@{width}: checkin/checkout selects not required: {tcheck}")
                elif tcheck["overflow"] > 0 or tcheck["r1r"] > width + 1 or tcheck["r2r"] > width + 1:
                    problems.append(f"{label}@{width}: times layout overflow: {tcheck}")

            for label, path in (
                ("stay-scheduled", f"/reservations/{w['res_scheduled']}"),
                ("stay-immediate", f"/reservations/{w['res_immediate']}"),
            ):
                resp = page.goto(f"{base}{path}")
                assert resp and resp.status == 200
                page.wait_for_load_state("networkidle")
                settle_motion(page)
                if "15:00" not in page.inner_text("body"):
                    problems.append(f"{label}@{width}: missing 15:00 scheduled send time")
                overflow = page.evaluate("() => document.documentElement.scrollWidth - window.innerWidth")
                if overflow > 0:
                    problems.append(f"{label}@{width}: horizontal overflow {overflow}px")

            context.close()
        browser.close()

    assert not problems, "Geometry/design problems found:\n" + "\n".join(problems)
