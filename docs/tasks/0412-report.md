# 0412 report (executor, Haiku 5.5)

Status: review

## Files changed (git diff --stat fb5978a)
17 files, 729 insertions, 233 deletions: App/app/landing_i18n.py, App/app/routes/legal.py, App/app/static/landing.css, App/app/static/pricing.js (new), App/app/templates/landing.html, App/app/templates/pricing.html, App/app/templates/product.html, App/app/templates/public_guide.html, App/app/templates/public_legal_base.html, App/tests/static_versions.json, App/tests/test_0412_pricing_browser.py (new), App/tests/test_landing_decoration.py, App/tests/test_owner_decisions.py, App/tests/test_public_seo.py, docs/tasks/0412-cenik-calculator.md (Status line only), docs/tasks/0412-report.md, docs/tasks/screenshots-0412/cenik-390.png (new).

## Commands (last lines)
- Step 6: `replaced 106 lines with 91`; grep for removed classes: `0`.
- §6 cmd 1: `136 passed in 7.84s`
- §6 cmd 2: `71 passed in 11.20s`
- §6 cmd 3 (browser, UBYHOST_REQUIRE_BROWSER=1): `1 passed in 6.01s`, no skips.
- Lint (repo root): `context lint: OK` (WARN lines are existing open-brief notes, not failures).

## Brief §7
- [x] cs without JS shows 99 / 163 and "Platíte 1 190 Kč jednou ročně" / "1 950" (test_public_seo, in cmd 1).
- [x] Browser: 476 yearly, 715 / 1 090 monthly, 960 with TTLock, no sideways scroll (0 skipped).
- [x] EN and CS each have 87 `pricing.*` keys, identical sets; no `pricing.card.*`, `pricing.includes.*`, `pricing.factor*` left.
- [x] "domovní" count in landing_i18n.py is 4 before and 4 after; 0 inside `pricing.*` lines.
- [x] docs/tasks/screenshots-0412/cenik-390.png exists; viewed once: cards stack, no sideways scroll.
- [x] Diff lists only §3 files plus the brief Status line, this report and the screenshot.

## Deviations
Done: steps 1 to 12. Step 5 to 11 each committed as `0412 step k`. Browser test run with UBYHOST_BROWSER_EXECUTABLE set to the installed Chromium. Step 6 printed the count 91 (new block length), not 106.

## Questions
None.

## Owner steps left
1. Open the PR's 390 px screenshot and check the page reads well on a phone.
2. After merge, deploy as usual and open https://ubyhost.com/cenik on your phone: change the apartment count and switch Ročně/Měsíčně once.
