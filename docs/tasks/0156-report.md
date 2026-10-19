# 0156 report

Status: done

Files: App/tests/design_guard.js, App/tests/test_design_guardrails_browser.py, .github/workflows/ci.yml, docs/context/test-map.md.

Run: 1 failed, 0 skipped, 34 s. 130 findings, all real layout findings (no 404, no fixture error).
Kinds: tap-target-small 101, button-heights-differ 19, menu-holds-form 10.

By route (one example each):
- dashboard, stays: menu-holds-form (390 open, 5 each); stays, stays-archive: button-heights-differ "Save this view" 40 vs "Export stays (CSV)" 32 (1280 open)
- properties, operators, operator-add, operator-edit, fee-setup, invoice-new-picker, invoice-settings, property-new, guest-links, automation, settings, smart-locks, settings-account, setup-property, setup-police: tap-target-small button.help-tip-btn "?" 22x22 (390)
- operators, operator-add, operator-edit: tap-target-small phone-code input 45x42; sr-only file input 2x44
- fee-detail, invoice-new-selected, invoice-detail, guest-new: tap-target-small text inputs 358x40 (390)
- stay-detail: tap-target-small input#stay-link.sr-only 2x44
- property-detail, property-detail-configured: button-heights-differ "Continue" 44 vs link-button "Hide setup guide" 21; tap-target-small "Hide setup guide" 116x21
- cleaning: button-heights-differ "Property instructions & codes" 61 vs "Share schedule" 44; tap-target-small "Year" 40x44

Full list: /tmp/ubyhost-layout-guard.json (set UBYHOST_GUARD_REPORT to change).
Deviations: none. Owner steps: none.
