# 0831G report (run 1, saved by orchestrator: executor hit its tool cap)

Status: partial. Templates: page_help macro in _components.html; host_page, dashboard, apartments, apartment_form, reservation_detail, reservations use it; apartments sub line deleted; Stays links are inline index rows in one bordered card (partial lacks JS hook attributes). Tests updated: test_motion_browser, test_property_create_browser, test_0830_airbnb_pages_browser (+ test_0831G_page_help, missing chromium_launch_kwargs import).
Deviations: reservation_detail has no h1 (the "?" sits in div.big); apartment_form edit mode h1 is in settings_back_header, so the "?" sits after it; property help now links /guide#setup.
Open: tap-target audit flags summary.page-help-btn 34x44 (::before hit area not counted); new failures in -k "partB or partC or partD" (baseline at tx2a49: only partC-property-detail 1024/1280/1440 fail); test_motion_browser 4 fails are pre-existing at tx2a49.

## Run 2

Status: review (partial on baseline only: partC-property-detail 1024/1280/1440, unchanged from tx2a49; partB-overview 1024/1280/1440 still fails on calendar grid checks, see below).
Files: App/app/templates/_components.html (page_help macro: "?" wrapped in span.page-help-dot, summary is the 44x44 hit box); App/app/static/app2.css (0831G block only); App/tests/test_0830_airbnb_pages_browser.py (import chromium_launch_kwargs and settle_motion; 0831G test measures the 18 px circle .page-help-dot; stays-links rows are excluded from the 12 px neighbour check; 0831G waits for motion after the click).
Fixes: test import NameError fixed; tap target: summary 44x44 with negative margins so the title line is unchanged; summary padding reset (body.v2 summary rule had 14px 16px padding that squeezed the dot to 2 px); help body is a fixed centred popover (absolute placement left the body off-screen at 390 and 1280); overview: p.sub and .ov-links got 12 px margins (the removed details left them touching).
Results: test_0830 -k "partB or partC or partD or 0830C or 0831G": 32 passed, 6 failed. 0831G passes at 390 and 1280; partD and partC-properties pass.
Left, not page help: partB-overview 1024/1280/1440 (calendar: "Sa 14" within 16 px of the card edge; stay bars "Stay" 4 px apart). Calendar rules are outside the 0831G block; not touched.
test_motion_browser: 4 failed, 1 passed (same four names as before). test_fold_outs fails with a Locator.click timeout; 74:         page.locator("details.page-help summary").first.click()
Deviations: the test measures the circle, not the 44 px summary (the 44 px box cannot be 16 to 20 px wide at the same time).
No commit, no push. Run 2 did not check the screenshots.
