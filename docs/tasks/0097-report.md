# 0097 report: Reporting & fees help, no guessed facility name

Base `3248c8d`. Executor: Claude (owner-authorized). Brief: [0097-reporting-help](0097-reporting-help.md).

## Changes

1. **Letter generator removed.** One fine-print line under the login and password now links [jake-jsou-moznosti-zasilani-dat-aplikaci-ubyport](https://policie.gov.cz/reditelstvi-sluzby-cizinecke-policie/jake-jsou-moznosti-zasilani-dat-aplikaci-ubyport) (new tab).
   - I chose it because it covers the web-service module; the other page covers name, password and PUK. The proxy blocks policie.gov.cz, so I checked this against `compliance/05_manual_filing_fallback.md`.
   - `id="ws-request-letter"` is kept, so old anchors still work.
   - `/ws-request.txt` was used nowhere else. It now sends a 303 to Police reporting; another owner gets 404.
   - The helper and `ws_request.*` strings are deleted. Decision and audit records stay.
2. **`uby_name` is never prefilled** from `internal_name`. The abbreviation (UBY-WS_) and contact (operator e-mail) defaults stay. No bulk rewrite. Readiness still requires the name.
3. **`?` help (EN/CS)**, each naming the line on the police letter:
   - IDUB: "IDUB:"
   - Login: "Přihlašovací jméno:", not the portal login
   - Password: "Přístupové heslo:". The saved state stays visible.
   - Abbreviation: "Zkratka ubytovacího zařízení", else the part after UBY-WS_
   - Name: "Ubytovací zařízení:", first line, max 35, never the listing name
   - Contact
4. **Example letter**: a small button beside the heading (`…sample.pdf?v=20261004a`, new tab). The Guide copy stays.
5. **Stay-fee example: none ever existed.** I searched:
   - deleted files;
   - every path ever under `App/app/static` (only the police PDF and TTLock images);
   - `-S`/`-G` for sample/example/ukázk/vzor/annotated;
   - the deleted `stay_fee_setup.html`.

   `docs/plans/stay-fee-remittance*/` holds mockups of the report UbyHost outputs, not an input guide. Nothing was invented. Every fee field has a `?`, and the duplicate "(optional)" on the instruction label is gone.
6. **Fee list summary**: the 0082 rule `margin: 0 0 10px` cancelled the lane's `margin: auto`, so the line sat left of the lane. It is now `0 auto 10px`. Two tests assert its left edge matches the panel and filter row and that it sits above the table: `test_host_list_cards_browser` (760–1440, rail open and collapsed, EN/CS) and `test_reporting_help_0097` (360/390/1280). The assertion fails on the old CSS (checked).

Unchanged: payloads, encryption, code lists, readiness fields, form names, actions and CSRF, base.html `?v=`. host.css has no `?v=` bump, so staging may need a hard refresh.

## Tests (App/, staging/mock, REQUIRE_BROWSER=1)

The brief's set plus i18n, privacy, navigation browser and copy corrections: **216 passed, 9 failed, 8 errors, 0 skipped**. All failures are fixtures without an address hitting 3248c8d: `test_fee_setup_compatibility` (6), `test_stay_fee_property_panel` (8 setup errors) and `test_property_navigation_browser` (1). With a full address added temporarily, the two fee files pass (32 + 8); I then reverted them, because the parallel worker owns them.

Wider run: acceptance, wide geometry and 30 files that mention uby_name or the fee fields: **501 passed, 1 skip (evidence), 27 failed, 12 errors**. All are refusals for a missing address. ruff is clean. context_lint is OK.

**Orchestrator:** `decisions.md` is at its cap, so I added no line. Add "2026-10-13 | uby_name never prefilled; WS letter UI → policie.gov.cz link | owner | 0097" when compacting.

## Tests changed on purpose

- `test_police_defaults`: never derived; readiness flags it; save keeps a stored name and leaves a blank one blank.
- `test_ws_request_letter`: redirect, 404, the line in EN/CS with and without a login, strings gone.
- `test_ubyport_sample_pdf`: the section links the sample.
- `test_host_copy_corrections`: the password `aria-describedby` now lists help and hint.

## Evidence

`docs/tasks/0097-evidence/`, captured with `UBYHOST_CAPTURE_0097=1`:
- `police-reporting-*`
- `stay-fee-*`
- `stay-fees-list-*`
- `tip-uby_name-*`
- `tip-stay_fee_vs-*`

Each at {en,cs}-{360,1280}.

## Owner decision

Should we make an annotated stay-fee example? It needs a real, redacted municipality letter from you, with these highlighted: the office name and address, the variable symbol, the account, the data box and the decree rate.
