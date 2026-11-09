# 1032 report

Status: review

## Files changed (local commits on claude/project-thread-73qjig, not pushed)
- `df4b8a2b` step 1: `App/app/templates/guest/_fee_pay.html`
- `6ece6348` step 2: `App/app/static/guest.css`
- `064ed194` step 3: `App/app/i18n.py`, `App/app/guest_uk_i18n.py` (fee_now_body)
- `0a71eb3b` step 4: `App/app/mail_notify.py`, `App/app/claim.py`, receipt keys in `App/app/i18n.py`, `App/app/guest_uk_i18n.py`
- `fbd75572` step 5: `App/tests/test_guest_mail.py` (3 receipt tests); `App/app/i18n.py`, `App/app/guest_uk_i18n.py` (payment-details sentence moved into `mail_completion_fee_ways`, 6 languages)
- step 6: `docs/tasks/screenshots-1032/receipt.txt`, `docs/tasks/screenshots-1032/receipt.html`
- step 7: this report

## Commands
- `App/.venv/bin/python -m pytest tests/test_guest_mail.py tests/test_guest_languages.py tests/test_mail_label_case.py tests/test_mail_side_padding.py -q --tb=short -x 2>&1 | tail -30`
  Last line: `113 passed in 2.01s`
- `App/.venv/bin/python -m pytest tests/test_guest_*.py tests/test_guest_browser_e2e.py -q -rs --tb=short 2>&1 | tail -30` (test-map guest row)
  Last lines: `516 passed, 6 skipped in 30.20s`
  Skipped: `test_guest_browser_e2e.py:40` (4), `test_guest_guide_table_browser.py:13` (1), `test_guest_ocr_geometry_browser.py:20` (1), all `could not import 'playwright.sync_api': No module named 'playwright'`.
- Not run: `tests/test_0896_fee_pay_geometry_browser.py` (host stay-fees pay step, same playwright reason).

## Done vs brief section 7
- [x] No radio marks; all enabled options visible at once (code only, not viewed in a browser)
- [x] Receipt shows total, per-guest calc, ways, VS; no method claim (tests and receipt.txt)
- [ ] Tests pass with 0 skipped: NOT MET, 6 browser tests skipped
- [ ] Screenshots of the guest hub pay box at 390/768/1280: NOT PRODUCED
- [x] receipt.txt and receipt.html written
- [x] Report written (this file)

## Deviations
- `playwright` is not installed in `App/.venv` and is not in `requirements*.txt`. Adding it is a new dependency (rule 4, needs an owner line in decisions.md), so I did not install it. Browser and geometry tests cannot run here: "browser tests could not run, playwright is not installed".
- Screenshots were not taken for the same reason. Google Chrome exists at `/usr/bin/google-chrome`, but no capture script was written.
- Owner answer applied without a code change in `mail_notify`: the "payment details are on your stay page" sentence now sits in `mail_completion_fee_ways` ("Pay by: %(ways)s. The payment details are on your stay page."), so it shows whenever at least one way is listed. `mail_completion_fee_vs` keeps only the VS sentence. Still 5 keys.
- Receipt files were rendered from a fake stay and host (example.test), not guest data.

## Questions
- None open. Both earlier questions were answered by the owner.

## Owner steps left
1. Decide whether `playwright` may be added to the dev requirements (needs a decisions.md line).
2. If yes: `cd App && .venv/bin/pip install playwright && .venv/bin/python -m playwright install chromium`, then the browser run and screenshots (or let CI run them).
3. Push the branch and open the PR after the browser run is green.

## Follow-up by orchestrator
Browser tests ran with UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium and a local-only playwright in the venv (no requirements change). Updated test_guest_browser_e2e.py selectors (details to div.g-fee-opt). Fee tests 8 passed; pay-box screenshots in screenshots-1032/.
