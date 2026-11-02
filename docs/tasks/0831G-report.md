# 0831G report (run 1, saved by orchestrator: executor hit its tool cap)

Status: partial. Templates: page_help macro in _components.html; host_page, dashboard, apartments, apartment_form, reservation_detail, reservations use it; apartments sub line deleted; Stays links are inline index rows in one bordered card (partial lacks JS hook attributes). Tests updated: test_motion_browser, test_property_create_browser, test_0830_airbnb_pages_browser (+ test_0831G_page_help, missing chromium_launch_kwargs import).
Deviations: reservation_detail has no h1 (the "?" sits in div.big); apartment_form edit mode h1 is in settings_back_header, so the "?" sits after it; property help now links /guide#setup.
Open: tap-target audit flags summary.page-help-btn 34x44 (::before hit area not counted); new failures in -k "partB or partC or partD" (baseline at tx2a49: only partC-property-detail 1024/1280/1440 fail); test_motion_browser 4 fails are pre-existing at tx2a49.
