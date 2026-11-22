# 2029 step 7 report

Status: review

## PR
(open after push)

## Proof (UBYHOST_PAYMENTS_RETIRED=1)
- Go: `go test ./internal/ubyport/... ./internal/hostweb/...` → ok (ubyport, hostweb, layout)
- Go nav: `go test ./internal/hostweb/layout/ -run PaymentsHidden` → ok (Payments / Booking site absent when hidden/retired)
- Python guide: `test_guest_guide.py test_guide_translate.py test_guest_guide_view.py` → 45 passed
- Python filing sample: `test_ubyport_faults.py test_ubyport_transport_retry.py test_soap.py test_submission_retry_cap.py` → 75 passed
- `gofmt -l .` (go/) → clean
- `python3 scripts/context_lint.py` → OK

## Browser / UX (step 7)
- `test_layout_lint_browser.py` with RETIRED=1: **fails** at `payments/320` (HTTP 404). Harness still visits `/payments` and `/booking-sites`; no code change in step 7 per brief.
- Playwright binary not on this VM (`/opt/pw-browsers/chromium` missing); no 390/768/1280 screenshots here. CI `test_layout_lint_browser` on main does not set RETIRED; owner check on staging after flag (brief owner step 4).

## Per-page notes (Go layout unit tests + grep, not live screenshots)
- Side nav with `PaymentsHidden`: no Payments or Booking sites entry (layout_test `TestSideNavPaymentsHidden`).

## §7 (brief acceptance)
- [x] UbyPort Go tests green with RETIRED=1
- [x] Guide Python tests green with RETIRED=1
- [x] Filing sample tests green
- [ ] `test_layout_lint_browser.py` green with RETIRED=1 (needs follow-up: skip retired routes in harness)
- [ ] 390/768/1280 screenshots (blocked: no browser on executor VM; owner staging)

## Deviations
Report-only step; layout lint + screenshots deferred as above.

## Questions
Should a follow-up brief update `test_layout_lint_browser.py` page list when `PAYMENTS_RETIRED`?

## Owner
After merge, set `UBYHOST_PAYMENTS_RETIRED=1` on server and run brief owner step 4 (browser check + `/guide`).