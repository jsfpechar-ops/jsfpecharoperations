# 0620 report: pricing copy tidy

Status: review

## Files changed
- App/app/landing_i18n.py: plan names Standard/Max (EN+CS), Max features, band labels "from the 5th"/"from the 10th" (EN) and "od 5."/"od 10." (CS), band title, removed pricing.max.f6, pricing.final.large/write/subject.
- App/app/templates/pricing.html: Max list now 5 rows, no coming-soon row; removed the 10+ write-to-us line.
- App/app/static/landing.css: removed .pricing-coming-soon rule.
- App/app/templates/{landing,pricing,product,public_guide,public_legal_base}.html: landing.css?v=20261101-pricing-v4.
- App/tests/static_versions.json: regenerated.
- App/tests/test_public_seo.py: dropped asserts on removed pricing.max.f6 (OCR row).
- App/tests/test_0412_pricing_browser.py: Max row count 6 to 5; dropped the .pricing-coming-soon check.
- docs/tasks/screenshots-0620/cenik-cs-390.png

## Commands (last 5 lines)
- `.venv/bin/python -m pytest tests/test_public_*.py tests/test_landing_*.py tests/test_0412_pricing_browser.py tests/test_umami_guard.py tests/test_static_versions.py tests/test_no_em_dashes.py -q --tb=short -rs`: `168 passed in 50.69s` (0 skipped).
- `python3 scripts/context_lint.py`: `context lint: OK`.

## Acceptance (section 7)
- [x] /cenik shows Standard and Max, bands "od 5." / "od 10.", no OCR row, no "Napište nám" line, in CS and EN (verified by the 0412 browser test and the screenshot).
- [x] Section 6 green, 0 skipped.
- [x] One 390 px screenshot of /cenik (CS).

## Deviations
- Steps 1-2 share one commit, and steps 3-4 share one commit (same file each); step 5 and step 6 have their own commits. Step 6 has two commits (SEO test, browser test).
- Installed `playwright==1.63.0` into App/.venv (the same pin CI uses) to run the browser test. Not a repo change. Without it, tests/test_0412_pricing_browser.py skipped.
- Dropped the assertions listed in section 6 only where they named removed content.
- Done: steps 1 to 6 and the screenshot. Left: none.

## Questions
- The site header still shows the "UbyHost" brand word; the brief did not name it, so it is unchanged.

## Owner steps left
- Review and merge via scripts/merge-pr-on-green.sh. Production deploy is manual.
