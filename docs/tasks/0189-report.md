# 0189 report

Status: blocked

Done: steps 1 to 5. Left: smart-locks flat blocks, 1280/2000 screenshot review, full test rerun after screenshots.

Files changed: App/app/static/host2.css (nested .ui-section rule, cleaning-panel rule, ?v=0189b), App/app/templates/base.html, App/tests/static_versions.json, App/app/templates/guide.html (ui-section-plain), App/app/templates/reservation_detail.html (guests, money, reports sections), App/app/templates/cleaning_settings.html (two sections), App/tests/test_design_guardrails_browser.py (test_host_sections_are_bordered_panels).

Pages checked by the guardrail test: /settings, /housebook, /reservations/{id}, /apartments/{id}/setup/property, /setup/police, /setup/stay_fee (11 top-level panels on settings, 3 on reservation, 1 on housebook).

Screenshots at 390 px (scratch DB): stay-fees, settings, reservation-detail, admin-users, smart-locks in checkpoint-4-shell-fixes. 1280 and 2000 captured, not reviewed.

Findings: smart-locks property cards and guest-link blocks are still flat (no .ui-section). Admin users "Create a host" heading sits tight to the panel top edge.

Questions: property-section panels in _property_editor.html get border-top only and padding 20px 0 from host-design0123.css; not changed.
