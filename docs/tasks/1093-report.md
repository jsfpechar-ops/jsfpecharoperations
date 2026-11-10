# 1093 report

Status: review

Strings used: cs `Registrace hosta`, es `Ficha de huésped`, fr `Fiche voyageur` (equal to section 1).
Files: App/app/i18n.py (3 lines), App/tests/test_guest_title_1091_browser.py (tests f, g added, docstring), docs/tasks/screenshots-1093/ (6), this report, brief status.

Commands:
1. title test file: 20 passed, 0 skipped.
2. guest tests + e2e: 765 passed, 0 skipped.
3. ocr geometry + layout lint browser: 13 passed, 0 skipped.
4. copy/i18n row: 46 passed.
5. ruff CI lint: All checks passed. context_lint: OK (warnings only, not from this brief).

Section 7: all ticked.

Screenshots (390 and 360, opened): cs, es, fr each have the title on one line, property name under it, language button not squeezed, no text cut.

Deviations: used wt-1091 venv; rerun rewrote 0402/1087 screenshots, restored from origin/main. No PR opened (per instruction).
