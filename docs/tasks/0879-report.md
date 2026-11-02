# 0879 report

Status: blocked
Executor: Haiku 5.5 (Haiku session). Branch claude/project-thread-6ozz7x. Not pushed, no PR.

## Files changed
- App/app/doc_ocr.py: constants, mrz_band (flip option), whitelist + timeout 15, read_document over three attempts, __all__.
- App/tests/test_doc_ocr.py: 7 new tests (a, b, c, d, e, f, g).
- App/app/host_i18n.py: plan_max sentence EN and CS.
- App/scripts/ocr_readrate.py (new).
- docs/context/decisions.md, docs/context/known-issues.md: one line each.
- docs/tasks/0879-report.md (this file).

## Commands (last lines)
- tests/test_doc_ocr.py + tests/test_guest_ocr_geometry_browser.py + tests/test_privacy_first.py: `29 passed, 1 skipped` (geometry browser file skipped: playwright not installed in local venv).
- tests/test_billing_order.py: `1 failed, 7 passed`. FAILED test_the_page_orders_without_javascript: asserts the old copy "Skenování dokladů (OCR): připravujeme" (line 132).
- python3 scripts/context_lint.py: `context lint: FAIL` (ERROR decisions.md ~2260 > cap 2200; known-issues.md ~2531 > cap 2500; docs/tasks/0879-passport-ocr.md missing sections 1-9 headings).

## Section 7 checklist
- [x] steps 1-8 committed as "0879 step k"
- [ ] browser tests 0 skipped (playwright missing)
- [ ] billing order test green
- [ ] context lint green
- [ ] 390 px screenshots: not needed (no template change)

## Deviations
- Done: steps 1 to 8. Left: §4 browser run (0 skipped), billing test fix, context lint fix.
- Created App/.venv (gitignored) with requirements.txt and requirements-dev.txt.
- mrz_band final rotation uses expand=False so the output width equals BAND_WIDTH (test a).
- Row-variance uses Image.getdata as the brief says; Pillow 13 warns it is deprecated.
- Brief places no location for mrz_band; placed before run_tesseract.

## Questions
1. Update tests/test_billing_order.py line 132 to the new copy? It is not in brief §2, so not changed.
2. Lint: decisions.md and known-issues.md are over token cap; compaction is needed (owner or orchestrator decision).
3. Brief §8 and §6 references do not exist (brief has §4 tests and §6 report).

## Owner steps left
1. Approve the billing test copy update (or let the next executor do it).
2. Install playwright 1.63.0 and Chromium locally, or let CI run the browser file.
3. Compact decisions.md and known-issues.md, and fix the 0879 brief headings for the lint.
4. Run `App/scripts/ocr_readrate.py DIR` on about 30 real photos (outside the repo).
5. Review and open the draft PR yourself (no push by executor).
