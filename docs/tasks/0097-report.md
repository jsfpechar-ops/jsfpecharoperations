# 0097 report: Reporting & fees help, no guessed facility name

Base `3248c8d`. Executor: Claude (owner-authorized). Brief: [0097-reporting-help](0097-reporting-help.md).

## What changed (owner items 1–6)

1. **Letter generator removed.** Police reporting now shows one fine-print line under the login and password: "No web-service credentials yet? The Foreign Police explain how to request them:". It links [UbyPort data sending options](https://policie.gov.cz/reditelstvi-sluzby-cizinecke-policie/jake-jsou-moznosti-zasilani-dat-aplikaci-ubyport) and opens in a new tab. I chose that page over `co-to-jsou-prihlasovaci-udaje…` because it covers the web-service (robotic) module; the other one explains user name, password and PUK. The proxy blocked policie.gov.cz, so I checked the choice against `docs/UbyHost_workplan/compliance/05_manual_filing_fallback.md`, not the live page.
   - The line keeps `id="ws-request-letter"`, so old `#ws-request-letter` links still open Reporting.
   - `/apartments/{id}/ws-request.txt` was used nowhere else. It is now a 303 to `?view=settings&section=reporting#ubyport` (another owner gets 404). `_ws_request_letter` and the 15 `ws_request.*` strings per language are deleted.
   - The 0044 decision line (data box) stays, and so do audit records.
2. **Facility name is never prefilled.** `_apply_police_defaults` no longer copies `internal_name`. The abbreviation (part after `UBY-WS_`, decision 2026-10-11) and the contact (operator e-mail) stay. Nothing is rewritten in bulk. Tests show that a stored name survives a save, a blank one stays blank, and `validate_apartment` still reports `uby_name`.
3. **`?` help in plain words, EN/CS.**
   - IDUB: the "IDUB:" line.
   - Login: the "Přihlašovací jméno:" line; starts with UBY-WS; not the portal login.
   - Password: the "Přístupové heslo:" line. The saved-password state stays visible.
   - Abbreviation: the "Zkratka ubytovacího zařízení" line, else the part after UBY-WS_.
   - Facility name: the "Ubytovací zařízení:" line, first line only, max 35, never the listing name.
   - Contact: as given when registering in UbyPort.
4. **Example letter.** "See an example police letter (what is what)" is a small button beside the Police reporting heading (`…sample.pdf?v=20261004a`, opens in a new tab). On phones it sits right under the heading. The Guide copy is unchanged.
5. **Stay-fee example: none ever existed.** I searched:
   - `git log --all --diff-filter=D --name-only`;
   - every path ever under `App/app/static` (only the police sample PDF and TTLock guide images);
   - `-S`/`-G` for sample/example/ukázk/vzor/annotated in templates and i18n (only test fixtures with `example.test`);
   - the deleted `stay_fee_setup.html` (a plain form).

   `docs/plans/stay-fee-remittance*/` holds design mockups of the report UbyHost *produces*, not a guide to what the municipality gives you. Nothing was invented. Instead, every fee field has a `?`: rate, period, variable symbol, account, office name, address, contact, data box, payee, instruction. I also dropped the duplicate "(optional)" on the instruction label.
6. **Fee list summary.** The cause was the 0082 rule `margin: 0 0 10px`, which overrode the lane's `margin: auto`: at wide lanes the line sat at the wrap's left edge, outside the 1080 px lane. It is now `margin: 0 auto 10px`. The new assertion in `test_host_list_cards_browser` (760–1440 px, rail open and collapsed, EN/CS) and in `test_reporting_help_0097` (360/390/1280) checks the left edge equals the panel and filter row and the line sits above the table. It fails with the old CSS (checked).

Unchanged: payloads, credential encryption, code lists, readiness fields, form names/actions/CSRF, base.html `?v=`. host.css has no new `?v=`, so staging may need a hard refresh.

## Tests (App/, staging/mock, REQUIRE_BROWSER=1, pinned Chromium)

```
test_police_defaults test_ubyport_sample_pdf test_ws_request_letter test_property_readiness
test_fee_setup_compatibility test_host_fee_navigation test_stay_fee* (11 files) test_host_list_cards_browser
test_host_help_browser test_reporting_help_0097 test_host_i18n test_privacy_first
test_property_navigation_browser test_host_copy_corrections      → 216 passed, 9 failed, 8 errors, 0 skipped
```

All 9 failures and 8 errors come from 3248c8d (address now mandatory) and fixtures without a full address:
- `test_fee_setup_compatibility` (6): `NON_FEE` has only `addr_obec`;
- `test_stay_fee_property_panel` (8 setup errors): blank address;
- `test_property_navigation_browser` (1): the create is refused.

To prove it, I temporarily gave those two fee files a full address: 32 + 8 passed. I then restored them, because the parallel worker owns those fixtures. I updated `test_host_copy_corrections` for the new `aria-describedby="uby_ws_password-help uby_ws_password-hint"`.

Also run: `test_host_ux_acceptance`, `test_host_wide_geometry_browser` and 30 more files that mention uby_name, the fee fields or the summary: 501 passed, 1 skip (evidence capture), 27 failed, 12 errors. Every failure is a create or save refused for a missing address, in test_flash_next_step, test_new_property_defaults, test_property_create_browser, test_property_form_save, test_ui_consistency and test_property_navigation_browser. That is the parallel fixture worker's scope. Acceptance and wide geometry pass. ruff (E9,F63,F7,F82,F401,F841) is clean. context_lint: OK, with only the status.md WARN (orchestrator). `decisions.md` is at its 2000-token cap, so I did not add a decision line. Orchestrator: add one when compacting: "2026-10-13 | uby_name never prefilled; WS letter UI → policie.gov.cz link | owner | 0097".

## Tests changed for intentional behaviour

- `test_police_defaults`: the name-default tests now assert that the name is never derived. Added: readiness still flags `uby_name`; a save keeps a stored name and does not fill a blank one.
- `test_ws_request_letter`: rewritten. The old URL redirects; another owner gets 404; one fine-print line sits between the password and the abbreviation in EN/CS with and without a login; no letter strings remain.
- `test_ubyport_sample_pdf`: the section links the sample (EN/CS) and the Guide still does.

## Evidence (`UBYHOST_CAPTURE_0097=1`, synthetic data)

`docs/tasks/0097-evidence/`:
- `police-reporting-{en,cs}-{360,1280}.png`
- `stay-fee-{en,cs}-{360,1280}.png`
- `stay-fees-list-{en,cs}-{360,1280}.png`
- `tip-uby_name-*`
- `tip-stay_fee_vs-*`

## Owner decision proposed

An annotated stay-fee example would need a fictional municipality letter or registration confirmation with the following highlighted, mapped to UbyHost fields like the police sample:
- the office name and department address;
- the variable symbol;
- the municipality account;
- the data box;
- the decree with the rate.

It should come from a real (redacted) letter you provide, because municipalities differ.
