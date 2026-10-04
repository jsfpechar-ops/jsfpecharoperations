# WP24: Terms, DPA and manual-filing texts

Patch: `series/` (per-WP .patch files were removed; the series is the only code) (same commit as `series/0012-WP24-Terms-DPA-and-manual-filing-texts.patch`). Stacked: written on STEP0 (series 0011), so it needs 0001 to 0011, in particular WP09 (Privacy 1.6) and WP23 (the "I filed this stay by hand in UbyPort" button and the guide section).

## Summary
Text only, plus the small plumbing for one effective date.
- Terms 1.6 (EN, CS) with the clauses from `compliance/04_terms_clauses.md` and the owner's decisions applied (table below).
- DPA 1.6: § 11 names Render and Google Drive only as "only if used" subprocessors.
- `/terms`, `/privacy` and `/dpa` print one effective date, `config.LEGAL_EFFECTIVE_DATE`, next to the configured version. Terms and DPA go to 1.6 together with WP09's Privacy 1.6. A host who accepted the old versions sees one `/account/accept` page listing all three and accepts once (one `legal_accepted` audit line, three rows).
- The in-app guide section "If UbyHost cannot file in time" follows `compliance/05_manual_filing_fallback.md`: when to file by hand, what to check first, the UbyPort web application URL and helpline, the steps, keeping the Doručenka, the correction note, then pressing "I filed this stay by hand in UbyPort".

## Clause changes, before and after

| Clause | Before (1.5) | After (1.6) |
|---|---|---|
| Terms § 5 Roles | Host responsible for Act 326/1999, house book, GDPR. Stay fee not mentioned. | Same, plus: the Host alone is responsible for the stay fee under Act 565/1990 and the municipal ordinance (collecting, record book, reporting, paying). Fee figures, reports, registers and QR codes from the Service are aids; the Operator files and pays nothing; the Host checks figures. |
| Terms § 10 UbyPort | One paragraph: transmits "under the Host's configured instructions"; no guarantee; Host verifies, keeps proof, keeps "contingency procedures (including manual filing where required)". | 10.1 duty is the Host's; Service transmits only on the Host's instruction, with the Host's own web-service access and in the Host's name; Operator is not the Host's representative or agent toward the police. 10.2 no guarantee (unchanged substance). 10.3 Host checks every result and Doručenka, keeps proof. 10.4 concrete triggers (rejected, failed, unknown outcome, deadline warning, Service or UbyPort down): Host files by hand within 3 working days, guide section "If UbyHost cannot file in time", check for duplicates before resending, then record it with "I filed this stay by hand in UbyPort". 10.5 notices in the Service and to the Account e-mail; Host keeps the address working. |
| Terms § 10a (new) | Not covered. | "10a. UbyPort access credentials": Host "authorises and mandates" (CS "zmocňuje") the Operator to store the web-service user name and password and use them only to file and to test the connection; this covers only the credentials, not representation toward the police (§ 10.1); encrypted, never shown, not used or given for anything else; Host can change or delete them (sending stops); Host keeps its own web-application login; misuse: new credentials from the police and tell the Operator; Operator reports a possible exposure without undue delay; ends on deletion or account closure, then deleted. |
| Terms § 13 Availability | "Commercially reasonable efforts"; no uptime guarantee. | "Best-effort basis" (CS "podle možností Provozovatele (best effort)"); planned downtime announced in the Service in advance where possible; an outage of the Service, UbyPort or a provider does not extend statutory time limits, Host follows § 10.4. No maintenance window promise (the draft's 8:00 to 20:00 sentence is dropped). |
| Terms § 17 Liability | Excludes indirect, incidental, special, consequential, punitive damage and loss of data; cap: greater of 12 months' fees or CZK 5,000; exception "including intentional harm or gross negligence where such limits are impermissible". | 17.1 no liability for lost profit, lost opportunity, other indirect or consequential damage (loss of data no longer excluded). 17.2 total per calendar year limited to the fees paid in the 12 months before the claim, and at least CZK 10,000. 17.3 no liability for fines where the Host did not check or did not file by hand under § 10.4. 17.4 liability for intent or gross negligence is never excluded or limited; 17.1 to 17.3 also do not apply to harm to natural rights or to consumers and weaker parties (§ 2898 Act 89/2012); no limit toward data subjects or authorities under GDPR. 17.5 fair allocation of risk for business users. |
| DPA § 11 Subprocessors | "including, where enabled, AWS Lightsail and SES, Cloudflare, Render, Google Drive and Amazon S3 backups" (CS similar). | AWS Lightsail, Amazon SES, Amazon S3 backups and Cloudflare; then "Only if used:" (CS "Jen pokud se používají:") Render (demo hosting only, no production Guest Data) and Google Drive (off-site backups, only when the Operator configures the backup job). Rest unchanged. |
| Effective line (Terms, Privacy, DPA) | Hard-coded per document: Terms and DPA "19 September 2026, Version 1.5", Privacy "4 October 2026, Version 1.6". | One date from `config.LEGAL_EFFECTIVE_DATE`, written out per language ("16 November 2026", "16. listopadu 2026"), with the version from `config` (all 1.6). |
| Guide "If UbyHost cannot file in time" | Lede about the 24-hour mail; 4 short steps (sign in to the web application, enter guests, keep the receipt, press the button); duty. | Lede: legal duty within 3 working days, the 24-hour mail, the four triggers from 05. New "before" paragraph: outcome unknown means check for an existing report first (duplicate); web-application login differs from the web-service access; helpline +420 731 670 444 (working days 8:00 to 11:00), ubyport@pcr.cz, IDUB or IČO. Steps: open https://ubyport.pcr.cz/UbyPort/Home/Login; web form, guest data from Stays or the guest PDF; send, "Stažení dokumentu DORUČENKA – doporučeno", check the accepted list, keep the receipt 6 years; press "I filed this stay by hand in UbyPort" (unchanged behaviour text). New correction note (PŘEDCHOZÍ OZNÁMENÍ OBSAHOVALO CHYBY). Duty unchanged. |

## Files changed
- `App/app/terms_i18n.py`: § 5, § 10, new § 10a, § 13, § 17 (EN, CS); effective line with placeholders.
- `App/app/dpa_i18n.py`: § 11 (EN, CS); effective line with placeholders.
- `App/app/privacy_policy_i18n.py`: effective line with placeholders (text unchanged).
- `App/app/config.py`: `TERMS_VERSION` and `DPA_VERSION` 1.6; new `LEGAL_EFFECTIVE_DATE` (`UBYHOST_LEGAL_EFFECTIVE_DATE`).
- `App/app/acceptance.py`: `effective_date_text(lang)` (EN and Czech genitive month names).
- `App/app/templating.py`: template global `legal_effective(doc)`.
- `App/app/templates/terms.html`, `dpa.html`, `privacy.html`: use `legal_effective`.
- `App/app/routes/legal.py`: `TERMS_SECTION_IDS` includes `10a` between `10` and `11`.
- `App/app/guide_i18n.py`: manual-filing section rewritten, new keys `manual_filing_before`, `manual_filing_correction` (EN, CS).
- `App/app/templates/guide.html`: renders the two new paragraphs.
- `docs/ENVIRONMENT.md`: versions 1.6, new variable.
- `App/tests/test_wp24_terms_dpa.py`: new.
- `App/tests/test_accounts.py`: expected versions 1.6.
- `App/tests/test_legal_contents.py`: anchor regex accepts `s10a`.
- `App/tests/test_filing_watchdog.py`: guide text compared HTML-escaped (the new step 3 contains quotes).

## Tests added
`tests/test_wp24_terms_dpa.py`, 14 tests:
- § 10a sits between § 10 and § 11;
- `/terms` renders every new clause in EN and CS (anchor and contents link `s10a`);
- old liability and maintenance wording is gone (no CZK 5,000, no "impermissible", no 8:00 or 20:00);
- § 10a uses "zmocňuje" and "authorises and mandates"; 10.1 still says no representative toward the police;
- § 10 quotes the real button label and guide title and no unpublished `/pruvodce/` slug;
- DPA § 11: Render and Google Drive appear only after "Only if used:" / "Jen pokud se používají:", in strings and on `/dpa`;
- all three versions are 1.6;
- one effective date on `/terms`, `/privacy`, `/dpa` in EN and CS, following the config value;
- date formatting (EN, Czech genitive);
- no effective string hard-codes a date or version;
- a malformed `UBYHOST_LEGAL_EFFECTIVE_DATE` stops import of `app.config`;
- a host with 1.5 acceptances is sent to `/account/accept` once, sees all three documents, one submit records all three (one audit line `terms_v1.6 privacy_v1.6 dpa_v1.6`), and the next login asks nothing;
- the guide strings carry the 05 facts (URL, helpline, e-mail, Doručenka button, correction note, 3 working days, duplicate, 6 years, exact button label);
- the guide page renders the whole section in order.

## Test commands and results
From `App/`, `/tmp/pr230/App/.venv/bin/python -m pytest -q -p no:cacheprovider`:
- On the WP24 commit (series 0012): `tests/test_wp24_terms_dpa.py`: 14 passed. With `test_legal_* test_public_legal test_terms_copy test_privacy_legal_positions test_accounts test_login_acceptance test_guide test_filing_watchdog test_filed_by_hand test_host_i18n test_umami_guard test_cookie_inventory test_public_*`: 268 passed.
- On the final tree (0026): `test_wp24_terms_dpa test_legal_contents test_public_legal test_accounts test_filing_watchdog test_signup test_meta_capi test_copy_cleanup test_guide test_privacy_legal_positions test_legal_acceptance`: 204 passed.
- Full suite on the final tree in chunks: `[a-c]` 333 passed, 2 skipped; `[d-f]` 396 passed; `g` 326 passed, 7 skipped; `[h-m]` 414 passed, 1 skipped, 1 failed; `[n-r]` 493 passed; `s` 407 passed; `[t-z]` 230 passed. Total 2599 passed, 10 skipped, 1 failed. The failure is `test_host_geometry::test_the_month_filter_shares_its_page_edges` (no Chromium here, fails the same on `wpbase`).
- Ruff `--select E9,F63,F7,F82,F401,F841`: all checks passed (on 0012 and on the final tree).

## Deviations from the spec and why
- § 10.4: the draft linked a public guide at `/pruvodce/rucni-hlaseni-ubyport` [OWNER TO CONFIRM] and asked hosts to tell support which guests they filed by hand. That page does not exist, and WP23 now has the "filed by hand" mark. So 10.4 points to the in-app guide section "If UbyHost cannot file in time" and to the button. No public guide page was added (text-only WP).
- § 10a: one sentence added, saying the authorisation covers only the credentials and does not make the Operator the Host's representative toward the police (§ 10.1). It answers the draft's own note that "zmocňuje" could read as contradicting 10.1, while keeping the owner's word.
- § 17.2: "before the claim" (owner wording) instead of the draft's "before the event giving rise to the claim". CS keeps the existing "před vznikem nároku". The draft's "greater of (a) or (b)" is written as "the fees ..., and at least CZK 10,000".
- § 17.4 starts with a plain sentence that intent and gross negligence are never limited, then keeps the draft's natural rights, consumer and GDPR carve-outs.
- § 13: the draft's maintenance-window sentence is replaced by the owner's "notice of planned downtime where possible". "Best effort" replaces "commercially reasonable efforts".
- DPA § 11: there is no app config that says whether Render or Google Drive is in use (Drive backups are a shell script, Render is a demo host), so they are marked "only if used" in the text, the way `/subprocessors` already marks them "Conditional". Umami is not named in DPA § 11 (it processes no Guest Data); it stays in the register.
- Guide: 05's "switch the reporting mode to Manual until support sorts it out" and "e-mail support with the receipt" are left out, because the WP23 mark already stops UbyHost from sending those guests and records the filing. 05's own note says this feature would remove the support step.
- Sub-clauses (10.1 to 10.5, 17.1 to 17.5) are in one paragraph each, as the template renders one body per section. No template or CSS change for paragraphs.
- Privacy text is unchanged; only its effective line now uses the shared date. Its printed date changes from 4 October 2026 to the release date.

## What Cursor must verify or adapt when applying on the real main
- If main has changed any of `terms.s05/s10/s13/s17_body` or `dpa.s11_body`, merge by hand and keep the 1.6 texts.
- If main has a public manual-filing guide by then, § 10.4 may link it; keep the in-app section name in sync with `guide.reporting.manual_filing_title`.
- `TERMS_SECTION_IDS` is no longer purely numeric; any other code that parses section ids as integers must accept `10a` (none in this tree).
- If main sets `UBYHOST_TERMS_VERSION`, `UBYHOST_PRIVACY_VERSION` or `UBYHOST_DPA_VERSION` in a server `.env`, remove them, or the 1.6 bump does not happen.

## Manual steps for the owner
- Have counsel review Terms 1.6 and DPA 1.6, especially § 10a ("zmocňuje"), § 17 and DPA § 11.
- Tell hosts about the changes at least 30 days ahead (Terms § 22), then set `LEGAL_EFFECTIVE_DATE` in `App/app/config.py` (or `UBYHOST_LEGAL_EFFECTIVE_DATE=YYYY-MM-DD` in the server `.env`) to the release date before deploying. The default `2026-11-16` is a placeholder.
- Hosts are asked to accept on their next sign-in after deploy, whatever date is printed. Deploy on or after the date you announce.
- If Google Drive backups or Render are dropped for good, delete them from `/subprocessors` and DPA § 11.
