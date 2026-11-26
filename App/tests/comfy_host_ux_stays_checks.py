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
    assert [s["step"] for s in detail_phone["steps"]] == ["link", "form", "code", "police"], detail_phone
    assert [s["tone"] for s in detail_phone["steps"]] == ["progress", "progress", "bad", "bad"], detail_phone


def assert_stays_and_detail_desktop(page: Page, base: str, stay_red: int) -> None:
    page.goto(f"{base}/reservations", wait_until="networkidle")
    stays_desk = page.evaluate(
        """() => {
        const statuses = [...document.querySelectorAll('.stays-desk .stay-rep-status')];
        const statusXs = statuses.map(el => Math.round(el.getBoundingClientRect().left));
        const okPills = [...document.querySelectorAll('.stays-desk .stay-rep-status .pill.p-ok')].map(el => ({
            text: el.innerText.trim(),
            title: el.getAttribute('title') || '',
        }));
        const polIcons = [...document.querySelectorAll('.stays-desk .stay-journey-step[data-step="police"] svg')].map(
            s => s.getAttribute('data-icon')
        );
        return {
            docOverflow: document.documentElement.scrollWidth - window.innerWidth,
            journeyCount: document.querySelectorAll('.stays-desk .stay-journey').length,
            hasRequestPayment: !!document.querySelector('a[href*="/payments?reservation_id"]'),
            statusXs,
            okPills,
            polIcons,
        };
    }"""
    )
    assert stays_desk["docOverflow"] <= 0 and stays_desk["journeyCount"] >= 5, stays_desk
    assert not stays_desk["hasRequestPayment"], "retired Request payment link must be removed from Stays menu"
    assert len(stays_desk["statusXs"]) >= 5 and len(set(stays_desk["statusXs"])) == 1, (
        f"Reporting status column must align vertically like Excel columns: {stays_desk}"
    )
    assert stays_desk["okPills"] and all(p["text"] == "Reported" for p in stays_desk["okPills"]), stays_desk
    assert all(ic == "police" for ic in stays_desk["polIcons"]) and stays_desk["polIcons"], stays_desk

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
    assert detail_desk["docOverflow"] <= 0 and detail_desk["stepCount"] == 4 and detail_desk["rowCount"] == 1, detail_desk
    assert detail_desk["barBelowHead"], "journey checklist must sit below the #now header on desktop"
    assert detail_desk["hasCollapsibleIssues"], "multi-field missing details must collapse into a disclosure pill"
    assert ":" in detail_desk["issuesSummaryText"] and "+" in detail_desk["issuesSummaryText"], detail_desk
    assert not detail_desk["hasRequestPayment"], "retired Request payment link must be removed"
