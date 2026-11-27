"""Stays list and Stay Detail geometry & invariant assertions for Comfy Host UX."""

from playwright.sync_api import Page


def assert_stays_and_detail_phone(page: Page, base: str, stay_red: int) -> None:
    page.goto(f"{base}/reservations", wait_until="networkidle")
    stays_phone = page.evaluate(
        """() => {
        const cards = [...document.querySelectorAll('.stays-phone .card.stay')];
        return {
            docOverflow: document.documentElement.scrollWidth - window.innerWidth,
            cardCount: cards.length,
            journeyCount: document.querySelectorAll('.stays-phone .stay-journey').length,
            deskHidden: getComputedStyle(document.querySelector('.stays-desk')).display === 'none',
            bodyText: document.body.innerText,
        };
    }"""
    )
    assert stays_phone["docOverflow"] <= 0 and stays_phone["deskHidden"], stays_phone
    assert stays_phone["cardCount"] >= 5 and stays_phone["journeyCount"] >= 5, stays_phone
    assert "9999" not in stays_phone["bodyText"]

    page.goto(f"{base}/reservations/{stay_red}", wait_until="networkidle")
    detail_phone = page.evaluate(
        """() => {
        const back = document.querySelector('.airbnb-header');
        const bar = document.querySelector('.stay-journey-bar');
        const polIcon = document.querySelector('.stay-journey-bar-step[data-step="police"] svg');
        return {
            docOverflow: document.documentElement.scrollWidth - window.innerWidth,
            barBelowHeader: !!(back && bar && bar.getBoundingClientRect().top >= back.getBoundingClientRect().bottom - 2),
            policeIcon: polIcon ? polIcon.getAttribute('data-icon') : '',
            hasRequestPayment: !!document.querySelector('a[href*="/payments?reservation_id"]'),
            steps: [...document.querySelectorAll('.stay-journey-bar-step')].map(el => ({
                step: el.getAttribute('data-step'), tone: el.getAttribute('data-tone'),
            })),
        };
    }"""
    )
    assert detail_phone["docOverflow"] <= 0, detail_phone
    assert detail_phone["barBelowHeader"], "journey checklist must sit below the back button/header"
    assert detail_phone["policeIcon"] == "police", detail_phone
    assert not detail_phone["hasRequestPayment"], "retired Request payment link must be removed"
    assert [s["step"] for s in detail_phone["steps"]] == ["email", "opened", "form", "code", "police"], detail_phone
    assert [s["tone"] for s in detail_phone["steps"]] == ["done", "progress", "progress", "bad", "bad"], detail_phone


def assert_stays_and_detail_desktop(page: Page, base: str, stay_red: int) -> None:
    page.goto(f"{base}/reservations", wait_until="networkidle")
    stays_desk = page.evaluate(
        """() => {
        const statuses = [...document.querySelectorAll('.stays-desk .stay-rep-status')];
        const statusXs = statuses.map(el => Math.round(el.getBoundingClientRect().left));
        const okPills = [...document.querySelectorAll('.stays-desk .stay-rep-status .stay-journey-summary[data-tone="done"]')].map(el => ({
            text: el.innerText.trim(),
            title: el.getAttribute('title') || '',
        }));
        const polIcons = [...document.querySelectorAll('.stays-desk .stay-journey-step[data-step="police"] svg')].map(
            s => s.getAttribute('data-icon')
        );
        const dateAlignDiffs = [...document.querySelectorAll('.stays-desk tbody tr')].map(tr => {
            const tds = tr.querySelectorAll('td');
            const arrRect = tds[2]?.getBoundingClientRect();
            const depRect = tds[3]?.getBoundingClientRect();
            return arrRect && depRect ? Math.abs(Math.round(arrRect.top - depRect.top)) : 99;
        });
        const headBtnCount = document.querySelectorAll('.stays-head-actions > button, .stays-head-actions > a').length;
        const toolsDetails = document.querySelector('details.stays-tools');
        const hasStaysSearch = !!document.querySelector('.stays-search input[name="q"]');
        return {
            docOverflow: document.documentElement.scrollWidth - window.innerWidth,
            journeyCount: document.querySelectorAll('.stays-desk .stay-journey').length,
            hasRequestPayment: !!document.querySelector('a[href*="/payments?reservation_id"]'),
            statusXs,
            okPills,
            polIcons,
            dateAlignDiffs,
            headBtnCount,
            hasStaysSearch,
            toolsCollapsed: !!toolsDetails && !toolsDetails.open,
            toolsLinks: toolsDetails ? toolsDetails.querySelectorAll('a.airbnb-index-row').length : 0,
        };
    }"""
    )
    assert stays_desk["docOverflow"] <= 0 and stays_desk["journeyCount"] >= 5, stays_desk
    assert not stays_desk["hasRequestPayment"], "retired Request payment link must be removed from Stays menu"
    assert len(stays_desk["statusXs"]) >= 5 and len(set(stays_desk["statusXs"])) == 1, (
        f"Reporting status column must align vertically like Excel columns: {stays_desk}"
    )
    assert stays_desk["okPills"] and all("Filed" in p["text"] or "house book" in p["text"] for p in stays_desk["okPills"]), stays_desk
    assert all(ic == "police" for ic in stays_desk["polIcons"]) and stays_desk["polIcons"], stays_desk
    assert all(d <= 1 for d in stays_desk["dateAlignDiffs"]), stays_desk
    assert stays_desk["headBtnCount"] == 1 and stays_desk["hasStaysSearch"], stays_desk
    assert stays_desk["toolsCollapsed"] and stays_desk["toolsLinks"] == 4, stays_desk

    # Verify stays-scoped search filters stays directly by guest name.
    page.fill('.stays-search input[name="q"]', "Anna")
    page.press('.stays-search input[name="q"]', "Enter")
    page.wait_for_url("**q=Anna**", timeout=5000)
    page.wait_for_load_state("networkidle")
    search_rows = page.locator(".stays-desk tbody tr").count()
    assert search_rows == 1 and "Anna Novakova" in page.inner_text(".stays-desk"), search_rows

    page.goto(f"{base}/reservations/{stay_red}", wait_until="networkidle")
    detail_desk = page.evaluate(
        """() => {
        const steps = [...document.querySelectorAll('.stay-journey-bar-step')];
        const tops = new Set(steps.map(s => Math.round(s.getBoundingClientRect().top)));
        const head = document.querySelector('#now');
        const bar = document.querySelector('.stay-journey-bar');
        const issuesDetails = document.querySelector('details.guest-issues');
        return {
            docOverflow: document.documentElement.scrollWidth - window.innerWidth,
            stepCount: steps.length,
            rowCount: tops.size,
            barBelowHead: !!(head && bar && bar.getBoundingClientRect().top >= head.getBoundingClientRect().bottom - 2),
            hasCollapsibleIssues: !!issuesDetails && !issuesDetails.open,
            issuesSummaryText: issuesDetails ? (issuesDetails.querySelector('summary')?.innerText.trim() || '') : '',
            hasRequestPayment: !!document.querySelector('a[href*="/payments?reservation_id"]'),
        };
    }"""
    )
    assert detail_desk["docOverflow"] <= 0 and detail_desk["stepCount"] == 5 and detail_desk["rowCount"] == 1, detail_desk
    assert detail_desk["barBelowHead"], "journey checklist must sit below the #now header on desktop"
    assert detail_desk["hasCollapsibleIssues"], "multi-field missing details must collapse into a disclosure pill"
    assert ":" in detail_desk["issuesSummaryText"] and "+" in detail_desk["issuesSummaryText"], detail_desk
    assert not detail_desk["hasRequestPayment"], "retired Request payment link must be removed"
