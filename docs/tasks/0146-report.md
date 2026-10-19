# 0146 report

Status: review

Files: base.html, skeleton.js, host2.css, _components.html, apartments.html (import list), static_versions.json, test_design_cleanup.py (new).
Decisions (coordinator): guest/base.html and skeleton.css untouched (c05 rules kept for guest pages); skeleton.js selector ".c05-skel, .ui-skel"; line-range replace in base.html; keys skeleton.js and host2.css end in -0146; Anchor D unchanged; test renamed test_no_c05_markup_in_host_templates.
Macros deleted: sub_tabs, list_page_header, list_toolbar, list_section_heading, breadcrumb, row_reporting_actions. Kept: nav_icon (setup_wizard/done.html), sync_calendars_button (_property_calendars.html), page_header, empty_state.
Tests: step 4 set 31 passed; browser set 75 passed, 0 skipped; design_lint OK; all templates compile.
Deviations: apartments.html import edited (step 3 requires it); guest/base.html still loads skeleton.js with old key 0153.
Screenshot: /tmp/claude-0/-home-user-jsfpecharoperations/38363728-17ed-5130-bb5b-482347d88982/scratchpad/skeleton-390.png

## Legacy burn-down
legacy tokens still allowlisted (token: templates): 329
row-actions:11, nowrap:10, setup-wizard-lede:8, err-text:7, panel:7, scroll-x:7, checkline:6, field:6, setup-wizard-form:6, grid:5, col-name:5, table-cards:5, tight:5, opt:5, row-primary-link:5, cleaning-page:5, small:4, detail-hero:4, detail-metric:4, metric-label:4, metric-value:4, small-value:4, stay-metrics:4, mono:4, field-label-row:4, num:4, cleaning-panel:4, setup-wizard-skip:4, setup-wizard-instruction:4, muted:3, eyebrow:3, kv:3, stay-command-actions:3, stay-command-main:3, stay-command-note:3, stay-command-panel:3, empty:3, filters:3, two:3, action-group:3
App/app/static/host-controls.css selectors: 27 unreferenced: 3
  unreferenced: host-task, onboarding-banner-actions, onboarding-banner-copy
App/app/static/host-design0123.css selectors: 77 unreferenced: 13
  unreferenced: app-shell, cal-control-label, dashboard-row-list, host-today-head, outcome-action, outcome-critical, outcome-done, outcome-neutral, outcome-waiting, setup-wizard-fee-intro, setup-wizard-head, subnav, workspace-main
