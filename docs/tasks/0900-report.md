# 0900 report (steps 5-6)

Status: review

## Files changed

- App/tests/test_booking_terms_browser.py (new): 390 px geometry, no horizontal scroll, first h1 visible, CS/EN switch height >= 44, CS and EN.
- docs/tasks/screenshots-0900/terms-390.png (new): 390 px full-page screenshot of /terms/booking (CS). Looked at once; layout fine.
- docs/context/decisions.md: added the 0900 booking-terms line. To get under the 2200-token cap, compacted wording in older lines (2026-10-24 anthropic, 2026-10-25 VAT, 2026-10-28 Stripe and property pages, 2026-10-31 Postgres, Grafana line, 2026-10-09 workflow, 2026-10-10 type-3 period, 2026-10-17 workflow, 2026-10-19 design, 2026-10-27 Grafana, 2026-10-29 Stripe). No decision meaning removed.

## Commands

- `cd App && .venv/bin/python -m pytest tests/test_booking_terms_browser.py -q -rs --tb=short -x 2>&1 | tail -30`
  Output: `2 passed in 11.24s`. No skipped lines.
- `python3 scripts/context_lint.py | tail -30`
  decisions.md now passes. Still FAIL: `docs/tasks/0900-booking-site-guest-terms.md` and `docs/tasks/0901-...md` lack sections `## 3. Files` through `## 9. Report`. These are brief files from d0b4ef63, not touched here.

## Deviations

- The page sets `ubyhost_lang` and `ubyhost_csrf` cookies. The browser test therefore does not check for "no cookie"; it only checks layout. The brief's no-cookie check (step 3b) is in the non-browser test file, not this one.
- Screenshot: one 390 px only, as the brief asks.

Done: steps 1 to 6. Left: fix brief section headings for lint (owner or orchestrator).

## Questions

- Confirm that the brief lint failure is acceptable for review, or fix the 0900 and 0901 brief headings.
