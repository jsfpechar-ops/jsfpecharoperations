"""Rigorous Chromium geometry, design, and layout-lint tests for Briefs 2087-2090."""
from __future__ import annotations

import os

import pytest

pytest_plugins = ("tests.go_web_harness",)

REQUIRE_BROWSER = os.environ.get("UBYHOST_REQUIRE_BROWSER") == "1"
if REQUIRE_BROWSER:
    import playwright.sync_api as sync_api
else:
    sync_api = pytest.importorskip("playwright.sync_api")

from tests.browser_support import chromium_launch_kwargs, settle_motion
from tests.comfy_ux_seed import seed_comfy_world, session_cookie
from tests.go_web_harness import (
    assert_no_layout_findings,
    lint_go_paths,
    register_static_routes,
)


@pytest.fixture(scope="module")
def comfy_world(go_web):
    return seed_comfy_world(
        go_web["database_url"], go_web["host_id"], go_web["apartment_id"]
    )


def test_comfy_ux_all_pages_pass_layout_lint_and_capture_shots(
    go_web, go_cookie, comfy_world
):
    paths = {
        "comfy-dashboard": "/",
        "comfy-cal-index": "/?cal_view=calendar",
        "comfy-cal-single": f"/?cal_view=calendar&cal_property={comfy_world['apt1']}",
        "comfy-stays": "/reservations",
        "comfy-stay-detail": f"/reservations/{comfy_world['stay_urgent']}",
    }
    findings = lint_go_paths(go_web, paths, go_cookie)
    assert_no_layout_findings(findings)


def test_comfy_ux_rigorous_geometry_and_design_invariants(
    go_web, go_cookie, comfy_world
):
    base = go_web["base_url"]
    solo_cookie = session_cookie(go_web["secret"], comfy_world["solo_uid"])

    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())

        # === 1. PHONE (390x844) ===
        ctx = browser.new_context(viewport={"width": 390, "height": 844})
        register_static_routes(ctx)
        ctx.add_cookies(
            [
                {"name": "ubyhost_session", "value": go_cookie, "url": base + "/"},
                {"name": "ubyhost_lang", "value": "cs", "url": base + "/"},
            ]
        )
        page = ctx.new_page()

        # 1a. Phone Dashboard (Briefs 2087 + 2088 + 2090)
        resp = page.goto(f"{base}/")
        assert resp and resp.status == 200
        page.wait_for_load_state("networkidle")
        settle_motion(page)
        dash_geom = page.evaluate(
            """() => {
            const rails = [...document.querySelectorAll('[data-prop-rail]')].map(r => {
                const calLink = r.querySelector('.prop-rail-cal');
                const track = r.querySelector('[data-prop-rail-track]');
                const cards = [...r.querySelectorAll('.prop-rail-card')];
                return {
                    title: r.querySelector('.prop-rail-title')?.innerText.trim() || '',
                    calHeight: calLink ? calLink.getBoundingClientRect().height : 0,
                    trackScrollable: track ? (track.scrollWidth > track.clientWidth + 4) : false,
                    cardHeights: cards.map(c => Math.round(c.getBoundingClientRect().height)),
                    card2Peeks: cards.length >= 2 ? (
                        cards[1].getBoundingClientRect().left < window.innerWidth &&
                        cards[1].getBoundingClientRect().right > window.innerWidth
                    ) : null,
                    hasEmptyPlaceholder: !!r.querySelector('.prop-rail-empty'),
                };
            });
            const bodyText = document.body.innerText;
            const htmlText = document.body.innerHTML;
            return {
                docOverflow: document.documentElement.scrollWidth - window.innerWidth,
                hasOldHs: !!document.querySelector('.hs'),
                rails,
                nyVisibleCount: document.querySelectorAll('#needs-action > .needs-you-list > li').length,
                hasOldBackfillInNy: bodyText.includes('Old Backfill Guest'),
                hasUrgentStayInNy: bodyText.includes('Lukas Weber'),
                hasNudgeCard: !!document.querySelector('[data-needs-you="guest_link_nudge"]'),
                rawI18nKey: /\\b(?:needs_you|stays|dashboard|calendar)\\.[a-z0-9_]+\\.[a-z0-9_]+/.test(bodyText),
                pdotSizes: [...document.querySelectorAll('.prop-rail-title .ui-pdot')].map(el => Math.round(el.getBoundingClientRect().width)),
                leaksSecret: htmlText.includes('SECRET-PIN-9988') || htmlText.includes('SECRET-CODE-7744') || htmlText.includes('secret-anna@example.test'),
                journeyCount: document.querySelectorAll('.stay-journey').length,
            };
        }"""
        )
        assert dash_geom["docOverflow"] <= 0, f"phone dashboard overflow: {dash_geom}"
        assert not dash_geom["hasOldHs"], "old .hs carousel must be replaced"
        assert len(dash_geom["rails"]) == 3, dash_geom["rails"]
        assert dash_geom["rails"][0]["title"] in {"Vinohrady Loft", "Smichov Studio"}, dash_geom["rails"]
        assert dash_geom["rails"][2]["title"] == "Karlin Suite", dash_geom["rails"]
        assert dash_geom["rails"][0]["trackScrollable"], dash_geom["rails"][0]
        assert dash_geom["rails"][0]["card2Peeks"], dash_geom["rails"][0]
        assert all(h <= 140 for h in dash_geom["rails"][0]["cardHeights"]), dash_geom["rails"][0]
        assert all(r["calHeight"] >= 44 for r in dash_geom["rails"]), dash_geom["rails"]
        assert dash_geom["rails"][2]["hasEmptyPlaceholder"], dash_geom["rails"][2]
        assert dash_geom["nyVisibleCount"] <= 3, dash_geom["nyVisibleCount"]
        assert not dash_geom["hasOldBackfillInNy"]
        assert dash_geom["hasUrgentStayInNy"]
        assert dash_geom["hasNudgeCard"]
        assert not dash_geom["rawI18nKey"], "raw i18n key leaked into visible text"
        assert dash_geom["pdotSizes"] == [10, 10, 10], dash_geom["pdotSizes"]
        assert not dash_geom["leaksSecret"]
        assert dash_geom["journeyCount"] >= 4

        # 1b. Phone Calendar Property Index (Brief 2089)
        resp = page.goto(f"{base}/?cal_view=calendar")
        assert resp and resp.status == 200
        page.wait_for_load_state("networkidle")
        settle_motion(page)
        cal_idx = page.evaluate(
            """() => {
            const index = document.querySelector('[data-cal-prop-index]');
            const cards = [...document.querySelectorAll('[data-cal-prop-card]')];
            const calShell = document.querySelector('.cal-desk-shell');
            return {
                docOverflow: document.documentElement.scrollWidth - window.innerWidth,
                indexVisible: !!index && getComputedStyle(index).display !== 'none',
                calShellVisible: !!calShell && getComputedStyle(calShell).display !== 'none',
                cardCount: cards.length,
                minCardHeight: Math.min(...cards.map(c => c.getBoundingClientRect().height)),
                svgDots: cards.map(c => c.querySelectorAll('.mini-cal-dot').length),
                barsByName: Object.fromEntries(cards.map(c => [
                    c.querySelector('.cal-prop-card-name').innerText.trim(),
                    c.querySelectorAll('.mini-cal-bar').length,
                ])),
                svgToday: cards.map(c => c.querySelectorAll('.mini-cal-today').length),
            };
        }"""
        )
        assert cal_idx["docOverflow"] <= 0, cal_idx
        assert cal_idx["indexVisible"] and not cal_idx["calShellVisible"], cal_idx
        assert cal_idx["cardCount"] == 3 and cal_idx["minCardHeight"] >= 88, cal_idx
        assert cal_idx["svgDots"] == [35, 35, 35] and cal_idx["svgToday"] == [1, 1, 1], cal_idx
        assert cal_idx["barsByName"]["Vinohrady Loft"] >= 2, cal_idx
        assert cal_idx["barsByName"]["Smichov Studio"] >= 2, cal_idx
        assert cal_idx["barsByName"]["Karlin Suite"] == 0, cal_idx

        # 1c. Phone Single-Property Calendar (Brief 2089)
        resp = page.goto(f"{base}/?cal_view=calendar&cal_property={comfy_world['apt1']}")
        assert resp and resp.status == 200
        page.wait_for_load_state("networkidle")
        page.wait_for_selector("#calendar .cal-body:not([hidden])", timeout=10000)
        settle_motion(page)
        cal_single = page.evaluate(
            """() => {
            const back = document.querySelector('.cal-prop-back-link');
            const propSelect = document.querySelector('#calendar [data-cal-property]');
            const viewSeg = document.querySelector('#calendar .cal-view-segment');
            return {
                docOverflow: document.documentElement.scrollWidth - window.innerWidth,
                backVisible: !!back && getComputedStyle(back).display !== 'none',
                backHeight: back ? back.getBoundingClientRect().height : 0,
                propSelectHidden: !propSelect || getComputedStyle(propSelect).display === 'none',
                viewSegHidden: !viewSeg || getComputedStyle(viewSeg).display === 'none',
                hasCalendarCells: document.querySelectorAll('#calendar .cal-body button, #calendar .cal-body a, #calendar .cal-day').length > 0,
            };
        }"""
        )
        assert cal_single["docOverflow"] <= 0, cal_single
        assert cal_single["backVisible"] and cal_single["backHeight"] >= 44, cal_single
        assert cal_single["propSelectHidden"] and cal_single["viewSegHidden"], cal_single
        assert cal_single["hasCalendarCells"], cal_single

        # 1d. Phone Stays List (Briefs 2087 + 2088)
        resp = page.goto(f"{base}/reservations")
        assert resp and resp.status == 200
        page.wait_for_load_state("networkidle")
        settle_motion(page)
        stays_phone = page.evaluate(
            """() => {
            const journeys = [...document.querySelectorAll('.stays-phone .stay-journey')].map(j =>
                [...j.querySelectorAll('.stay-journey-step')].map(s => ({
                    step: s.getAttribute('data-step'), tone: s.getAttribute('data-tone'),
                }))
            );
            const html = document.body.innerHTML;
            return {
                docOverflow: document.documentElement.scrollWidth - window.innerWidth,
                hasOldUnfilledStrip: !!document.querySelector('[data-old-unfilled-strip]'),
                journeys,
                leaksSecret: html.includes('SECRET-PIN-9988') || html.includes('SECRET-CODE-7744'),
            };
        }"""
        )
        assert stays_phone["docOverflow"] <= 0, stays_phone
        assert stays_phone["hasOldUnfilledStrip"]
        assert not stays_phone["leaksSecret"]
        assert {len(j) for j in stays_phone["journeys"]} >= {3, 4}, stays_phone["journeys"]

        # 1e. Phone Stay Detail 4-step Checklist (Brief 2088)
        resp = page.goto(f"{base}/reservations/{comfy_world['stay_urgent']}")
        assert resp and resp.status == 200
        page.wait_for_load_state("networkidle")
        settle_motion(page)
        detail_phone = page.evaluate(
            """() => ({
            docOverflow: document.documentElement.scrollWidth - window.innerWidth,
            steps: [...document.querySelectorAll('.stay-journey-bar-step')].map(el => ({
                step: el.getAttribute('data-step'), tone: el.getAttribute('data-tone'),
            })),
        })"""
        )
        assert detail_phone["docOverflow"] <= 0, detail_phone
        assert [s["step"] for s in detail_phone["steps"]] == ["link", "form", "code", "police"]
        assert [s["tone"] for s in detail_phone["steps"]] == ["progress", "progress", "bad", "bad"]
        ctx.close()

        # === 2. SOLO 1-PROPERTY HOST AT 390px (Brief 2089 auto-skip) ===
        solo_ctx = browser.new_context(viewport={"width": 390, "height": 844})
        register_static_routes(solo_ctx)
        solo_ctx.add_cookies(
            [
                {"name": "ubyhost_session", "value": solo_cookie, "url": base + "/"},
                {"name": "ubyhost_lang", "value": "cs", "url": base + "/"},
            ]
        )
        spage = solo_ctx.new_page()
        resp = spage.goto(f"{base}/?cal_view=calendar")
        assert resp and resp.status == 200
        spage.wait_for_load_state("networkidle")
        spage.wait_for_selector("#calendar .cal-body:not([hidden])", timeout=10000)
        solo_cal = spage.evaluate(
            """() => ({
            docOverflow: document.documentElement.scrollWidth - window.innerWidth,
            hasPicker: !!document.querySelector('[data-cal-prop-index]'),
            hasBack: !!document.querySelector('[data-cal-prop-back]'),
            hasCalendar: !!document.querySelector('#calendar'),
        })"""
        )
        assert solo_cal["docOverflow"] <= 0 and not solo_cal["hasPicker"] and not solo_cal["hasBack"] and solo_cal["hasCalendar"], solo_cal
        solo_ctx.close()

        # === 3. DESKTOP (1280x900) ===
        dctx = browser.new_context(viewport={"width": 1280, "height": 900})
        register_static_routes(dctx)
        dctx.add_cookies(
            [
                {"name": "ubyhost_session", "value": go_cookie, "url": base + "/"},
                {"name": "ubyhost_lang", "value": "cs", "url": base + "/"},
            ]
        )
        dpage = dctx.new_page()

        resp = dpage.goto(f"{base}/")
        assert resp and resp.status == 200
        dpage.wait_for_load_state("networkidle")
        settle_motion(dpage)
        desk_dash = dpage.evaluate(
            """() => {
            const rails = document.querySelector('[data-prop-rails]');
            const sw = document.querySelector('[data-window-switch]');
            const fab = document.querySelector('.havel-fab, .help-fab, button[data-havel-open]');
            const swRect = sw ? sw.getBoundingClientRect() : null;
            const fabRect = fab ? fab.getBoundingClientRect() : null;
            const overlapsFab = !!(swRect && fabRect && !(
                swRect.right < fabRect.left || swRect.left > fabRect.right ||
                swRect.bottom < fabRect.top || swRect.top > fabRect.bottom
            ));
            return {
                docOverflow: document.documentElement.scrollWidth - window.innerWidth,
                railsHidden: !rails || getComputedStyle(rails).display === 'none',
                switchVisible: !!sw && getComputedStyle(sw).display !== 'none',
                overlapsFab,
                ganttLinks: [...document.querySelectorAll('.cal-row-prop-link')].map(a => a.getAttribute('href')),
                tableJourneys: document.querySelectorAll('.ov-table .stay-journey').length,
            };
        }"""
        )
        assert desk_dash["docOverflow"] <= 0 and desk_dash["railsHidden"] and desk_dash["switchVisible"], desk_dash
        assert not desk_dash["overlapsFab"], "window switcher must not collide with floating help button"
        assert any("cal_property=" in h for h in desk_dash["ganttLinks"]), desk_dash["ganttLinks"]
        assert desk_dash["tableJourneys"] >= 1, desk_dash

        resp = dpage.goto(f"{base}/?window=next7")
        assert resp and resp.status == 200
        dpage.wait_for_load_state("networkidle")
        assert dpage.locator(".ov-table tbody tr.dashboard-row").count() >= 4

        resp = dpage.goto(f"{base}/reservations")
        assert resp and resp.status == 200
        dpage.wait_for_load_state("networkidle")
        stays_desk = dpage.evaluate(
            """() => ({
            docOverflow: document.documentElement.scrollWidth - window.innerWidth,
            rowHeights: [...document.querySelectorAll('.stays-desk tbody tr')].map(r => Math.round(r.getBoundingClientRect().height)),
            journeyCount: document.querySelectorAll('.stays-desk .stay-journey').length,
        })"""
        )
        assert stays_desk["docOverflow"] <= 0 and stays_desk["journeyCount"] >= 4, stays_desk
        assert max(stays_desk["rowHeights"]) <= 84, stays_desk["rowHeights"]

        resp = dpage.goto(f"{base}/reservations/{comfy_world['stay_urgent']}")
        assert resp and resp.status == 200
        dpage.wait_for_load_state("networkidle")
        detail_desk = dpage.evaluate(
            """() => {
            const steps = [...document.querySelectorAll('.stay-journey-bar-step')];
            return {
                docOverflow: document.documentElement.scrollWidth - window.innerWidth,
                stepCount: steps.length,
                rowCount: new Set(steps.map(s => Math.round(s.getBoundingClientRect().top))).size,
            };
        }"""
        )
        assert detail_desk["docOverflow"] <= 0 and detail_desk["stepCount"] == 4 and detail_desk["rowCount"] == 1, detail_desk
        dctx.close()
        browser.close()
