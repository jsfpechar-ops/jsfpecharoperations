# 1067 report

Status: blocked (steps 1-5 done; three browser tests fail, see below)

Files: base.html (inline data-mac line, byte-identical to deleted platform.js), platform.js deleted, test_shortcut_hint_no_flash.py, static_versions.json (only platform.js removed), docs/plans/speed-and-ease.md.

Findings: A no duplicate stylesheets (v2/classic branches). B inline, not defer. tokens.css:191 comment still mentions platform.js (left on purpose).

Commands: 1 (shortcut/static/cache/cookie) 23 passed. 2 test_host_*.py: 247 passed, 1 failed (test_host_ux_acceptance guide/cs/390 help-tip-btn right 393 > 390), plus test_host_flash_outcomes sticky_amber toast timeout (also fails on the base commit, deselected). 3 layout lint + guardrails: test_layout_lint_browser green; test_design_guardrails_browser guest-new 390 Cancel tap target 43 vs 44. Context lint OK.

Failures look environmental (fonts/rendering in this sandbox), not caused by a moved script; only the sticky_amber one was confirmed on base.

Screenshots: /tmp/shots/layout-lint/<page>-{390,768,1280}.png
