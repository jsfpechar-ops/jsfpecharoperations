# 1008 report

Status: blocked

Done: steps 1 to 4 and the §6 test runs. Left: UX gate screenshots (step 5 seeded lint passed, but the screenshots and §7 items 1 to 3 are not done).

Files changed: App/app/templates/booking_site_setup.html, App/app/templates/property_page_review.html, App/app/static/host.css, App/app/templates/base.html, App/tests/static_versions.json.

Commits: 5199520a (step 1), 466fce25 (step 2), 2d6536e7 (step 3 CSS plus base.html key bump), 2568477a (step 4 static versions).

Tests:
- test_property_page_photos, test_booking_site_host, test_static_versions: 22 passed.
- test_zz_r2_lint_direct (seeded lint), test_layout_lint_browser, test_host_geometry, test_design_guardrails_browser: 17 passed, 1 failed, 0 skipped. The failure is test_every_host_page_passes_the_layout_guard on guest-new 390 px, Cancel tap-target 43 px vs 44 px. The brief names this as a known font-metric issue of non-CI machines. Guest pages are not touched by this change.
- Acceptance §7 item 4 (grep for style="display:flex" in property_page_review.html): prints nothing.

Deviations:
- Step 3 commit also includes the base.html key bump (step 4 content). Commits 1 to 4 lack the attribution trailers; the report commit has them.
- Seed script has no declined direct row (requested, expired, paid direct and paid card only). Not added, to avoid guessing its seeding.

Screenshots: not taken (budget). Path for next session: /mnt/project-files/pr803-review/after1008/.

Questions: none.
Owner steps left: none.
