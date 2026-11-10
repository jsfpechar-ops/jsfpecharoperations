# 1071 report

Status: blocked (UX gate; §8: fix needs CSS, outside §3/§5)

Steps 1-9 done and committed. Targeted tests pass: stay-fee/invoice 1007 pass, alerts 65 pass, new 1071 tests + alert_language 44 pass, scheduler/i18n/copy 72 pass.

Failing, same on main (sandbox): guest-new Cancel 43 px; test_host_flash_outcomes sticky warning toast; test_host_ux_acceptance guide cs 390 help-tip-btn past right edge.

Blocking: test_layout_lint_browser, new card findings: button-overlap "Fix stay fee payment" at dashboard@768; tight-row (action less than 12 px from the dismiss cross) at dashboard 1024/1280/1440/1920. Also stay-detail@320 tight-stack (h2 "Guests"), not seen touched by this change. Fixing needs alert-stack CSS, which §5 forbids.

Screenshots (dashboard only; the card shows only on the dashboard needs-you stack): docs/tasks/screenshots-1071/dashboard-{390,768,1280}.png. Seen: 390 title on 2 lines, full-width action under it, cross top right, no overlap. 768 same, clean. 1280 single line, action and cross in a row, gap visually small.
Owner/orchestrator decision: allow a CSS gap fix in the alert stack, or accept.
