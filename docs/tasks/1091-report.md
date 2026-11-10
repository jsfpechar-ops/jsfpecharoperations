# 1091 report

Files: App/app/static/guest.css (one 480px media rule), App/app/templates/guest/base.html (key 20261110-1091a), App/tests/static_versions.json (regenerated), App/tests/test_guest_title_1091_browser.py (new), docs/tasks/screenshots-1091/.

Commands (all with UBYHOST_REQUIRE_BROWSER=1, 0 skipped):
1. test_guest_title_1091_browser.py: 10 passed
2. test_guest_*.py + e2e: 755 passed
3. test_guest_ocr_geometry_browser.py: 13 passed (with geometry file); test_layout_lint_browser.py: 4 passed, no new findings
4. static_versions, wp07_cache_heartbeats, form_chrome, privacy_first: 43 passed
5. context_lint: OK (only pre-existing WARNs)

Section 7 ticked.

Screenshots (docs/tasks/screenshots-1091/form-{390,768,1280}.png):
- 390: title on one line at 24px, property name below, EN button not squeezed, first field higher than A-today.
- 768: unchanged, 28px one line.
- 1280: unchanged, 28px one line.

Line counts at 390: cs 2, es 2, fr 2, uk 1.

Deviations: playwright==1.63.0 pip-installed into the new .venv (not in requirements-dev; not committed).
Question for owner: shorter cs/es/fr titles (e.g. "Registrace hosta", "Registro de huesped", "Fiche des voyageurs") need approval and a native reader; separate brief.
