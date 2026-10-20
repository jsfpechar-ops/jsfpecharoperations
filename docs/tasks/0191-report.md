# 0191 report

Status: review

Files changed: App/app/static/tokens.css (row tokens 80 px / 16 / 20 / 16), App/app/static/host2.css (td vertical padding --space-4, .ui-sub gap, desktop badge gap), App/app/templates/base.html (tokens 0190a, host2 0190c), App/tests/static_versions.json, docs/design/catalog.json (classes ui-section-plain and ui-section-row added with class_notes), docs/tasks/0191-comfy-rows.md.

Commands:
- shell, static, a11y and guardrail browser tests: 26 passed, 0 skipped.
- python3 scripts/design_lint.py: OK on committed HEAD (clean export). On the shared working tree it fails: enforced template smart_locks.html is missing because another executor's staged rename to _smart_locks_panel.html is uncommitted, and that panel has unlisted classes (guide-steps, action-group, checkline, smart-lock-row).
- python3 scripts/context_lint.py: passes after this report.

Deviations: column horizontal padding stays 16 px; 20 px broke invoices at 1280 (page-scroll 1289 > 1280). Screenshots not taken; calendar-review job not run.

Left: owner review of Stays rows at 390 and 1280; the other executor must commit the smart_locks rename with a catalog update (enforced_templates and classes). Note: my first commit accidentally swept in that executor's staged files; I undid it (soft reset, recommit of my files only) before pushing, so the pushed commits contain only my files.
