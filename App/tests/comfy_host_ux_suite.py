"""Rigorous browser layout-lint, geometry, and visual-gate checks for Comfy Host UX."""

import pytest
from playwright import sync_api

from tests.browser_support import chromium_launch_kwargs
from tests.comfy_host_ux_stays_checks import (
    assert_stays_and_detail_desktop,
    assert_stays_and_detail_phone,
)
from tests.comfy_ux_seed import seed_comfy_world, session_cookie
from tests.go_web_harness import (
    assert_no_layout_findings,
    lint_go_paths,
    register_static_routes,
)

@pytest.fixture(scope="module")
def comfy_world(go_web):
    ids = seed_comfy_world(go_web["database_url"])
    return {
        **ids,
        "cookie": session_cookie(go_web["secret"], ids["host_id"]),
        "base": go_web["base_url"],
    }


def test_comfy_ux_all_pages_pass_layout_lint_and_capture_shots(go_web, comfy_world):
    paths = {
        "comfy-dashboard": "/",
        "comfy-dashboard-next7": "/?window=next7",
        "comfy-calendar-index": "/?cal_view=calendar",
        "comfy-calendar-prop": f"/?cal_view=calendar&cal_property={comfy_world['apt1']}",
        "comfy-stays": "/reservations",
        "comfy-stay-detail": f"/reservations/{comfy_world['stay_urgent']}",
    }
    findings = lint_go_paths(go_web, paths, comfy_world["cookie"])
    assert_no_layout_findings(findings)


def test_comfy_ux_rigorous_geometry_and_design_invariants(comfy_world):
    base = comfy_world["base"]
    stay_red = comfy_world["stay_urgent"]
    prop_vin = comfy_world["apt1"]

    with sync_api.sync_playwright() as p:
        browser = p.chromium.launch(**chromium_launch_kwargs())
        context = browser.new_context(viewport={"width": 390, "height": 844})
        context.add_cookies(
            [
                {"name": "ubyhost_session", "value": comfy_world["cookie"], "url": base + "/"},
                {"name": "ubyhost_lang", "value": "en", "url": base + "/"},
            ]
        )
        register_static_routes(context)
        page = context.new_page()

        # 1. Phone Dashboard: property rails + calm Needs you + zero overflow.
        page.goto(f"{base}/", wait_until="networkidle")
        dash_geom = page.evaluate(
            """() => {
            const rails = [...document.querySelectorAll('[data-prop-rail]')];
            const railInfo = rails.map(r => {
                const track = r.querySelector('[data-prop-rail-track]');
                const cards = [...r.querySelectorAll('.prop-rail-card')];
                return {
                    id: r.getAttribute('data-prop-rail'),
                    cardCount: cards.length,
                    scrollable: track ? track.scrollWidth > track.clientWidth : false,
                    hasEmptyMsg: !!r.querySelector('.prop-rail-empty'),
                };
            });
            return {
                docOverflow: document.documentElement.scrollWidth - window.innerWidth,
                nyVisibleCount: document.querySelectorAll('#needs-action > .needs-you-list > li').length,
                hasUrgentStayInNy: !!document.querySelector('[data-needs-you="stay"]'),
                hasNudgeCard: !!document.querySelector('[data-needs-you="guest_link_nudge"]'),
                railInfo,
                railOrder: rails.map(r => r.querySelector('.prop-rail-title')?.innerText.trim()),
                tableHidden: getComputedStyle(document.querySelector('.ov-table')).display === 'none',
            };
        }"""
        )
        assert dash_geom["docOverflow"] <= 0, dash_geom
        assert dash_geom["nyVisibleCount"] <= 3, dash_geom
        assert dash_geom["hasUrgentStayInNy"] and dash_geom["hasNudgeCard"], dash_geom
        assert dash_geom["tableHidden"], "desktop Today table must be hidden on 390px phone"
        assert len(dash_geom["railInfo"]) == 3 and dash_geom["railOrder"][-1] == "Karlin Suite", dash_geom

        # 2. Phone Calendar property picker -> single-property month calendar.
        page.goto(f"{base}/?cal_view=calendar", wait_until="networkidle")
        cal_idx = page.evaluate(
            """() => ({
            docOverflow: document.documentElement.scrollWidth - window.innerWidth,
            cardCount: document.querySelectorAll('[data-cal-prop-card]').length,
            svgCount: document.querySelectorAll('[data-cal-prop-card] .cal-prop-card-mini svg').length,
        })"""
        )
        assert cal_idx["docOverflow"] <= 0 and cal_idx["cardCount"] == 3 and cal_idx["svgCount"] == 3, cal_idx

        page.goto(f"{base}/?cal_view=calendar&cal_property={prop_vin}", wait_until="networkidle")
        assert page.locator("[data-cal-prop-back] a").count() == 1

        # 3. Phone Stays & Stay Detail.
        assert_stays_and_detail_phone(page, base, stay_red)

        # 4. Desktop Dashboard: compact Needs you, Today above Calendar, aligned Status column, clickable Gantt bars.
        page.set_viewport_size({"width": 1280, "height": 900})
        page.goto(f"{base}/", wait_until="networkidle")
        desk_dash = page.evaluate(
            """() => {
            const rails = document.querySelector('[data-prop-rails]');
            const sw = document.querySelector('[data-window-switch]');
            const fab = document.querySelector('[data-havel-launcher]');
            const workHead = document.querySelector('.ov-work-head');
            const calHead = document.querySelector('.ov-cal-heading');
            const metaBar = document.querySelector('.cal .crow .bar.has-meta');
            const nyList = document.querySelector('#needs-action .needs-you-list');
            const statusXs = [...document.querySelectorAll('.ov-table .stay-rep-status')].map(
                el => Math.round(el.getBoundingClientRect().left)
            );
            const okPills = [...document.querySelectorAll('.ov-table .stay-rep-status .pill.p-ok')].map(
                el => el.innerText.trim()
            );
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
                nyHeight: nyList ? Math.round(nyList.getBoundingClientRect().height) : 0,
                todayAboveCalendar: !!(workHead && calHead && workHead.getBoundingClientRect().top < calHead.getBoundingClientRect().top),
                metaBarJustify: metaBar ? getComputedStyle(metaBar).justifyContent : '',
                metaCount: document.querySelectorAll('.cal .crow .bar .bar-meta').length,
                statusXs,
                okPills,
                tableJourneys: document.querySelectorAll('.ov-table .stay-journey').length,
            };
        }"""
        )
        assert desk_dash["docOverflow"] <= 0 and desk_dash["railsHidden"] and desk_dash["switchVisible"], desk_dash
        assert not desk_dash["overlapsFab"], "window switcher must not collide with floating help button"
        assert desk_dash["nyHeight"] <= 140, f"What needs you should stay compact: {desk_dash}"
        assert desk_dash["todayAboveCalendar"], "Today section must sit above Calendar on desktop"
        assert desk_dash["metaBarJustify"] == "space-between" and desk_dash["metaCount"] >= 3, desk_dash
        assert len(desk_dash["statusXs"]) >= 2 and len(set(desk_dash["statusXs"])) == 1, desk_dash
        assert desk_dash["okPills"] == ["Reported"], desk_dash
        assert desk_dash["tableJourneys"] >= 1, desk_dash

        # Verify clicking a Gantt bar navigates straight to that stay's detail page.
        first_bar = page.locator(".cal .crow .bar[href^='/reservations/']").first
        target_href = first_bar.get_attribute("href")
        assert target_href and target_href.startswith("/reservations/"), target_href
        first_bar.click()
        page.wait_for_url("**/reservations/**", timeout=5000)
        assert "/reservations/" in page.url, page.url

        # 5. Desktop Stays & Stay Detail.
        assert_stays_and_detail_desktop(page, base, stay_red)
        browser.close()
