# Stay fee: legal audit and implementation handoff

Status: code implemented and merged with the selected host-app redesign on `fix/stay-fee-legal-audit` on 30 September 2026; the external legal decisions listed below remain open. This document supersedes section 15 and the conflicting calculation, grouping, register, and download assumptions in `PLAN_STAY_FEE_REMITTANCE.md`. The UX redesign's shared host-app standards govern visual presentation; the legal and data contracts here govern behavior.

## Decisions from the seven open items

| Item | Decision and implementation | Remaining external decision |
| --- | --- | --- |
| 1. Month boundary | The statutory base is commenced **days after arrival**, through departure (§ 3c). A 30 Aug–3 Sep stay contributes 31 Aug to August and 1–3 Sep to September. `nights_in` and the overlap query use this convention. | None for this example. |
| 2. 60-day scope | § 3a says at most 60 consecutive calendar days; the frequently described 60-night boundary can be interpreted differently. A stay of exactly 60 nights is blocked from finalization until the municipality's written answer is recorded for that facility. Other stays use calendar days. The answer and its reference are stored on the facility. | Written answer from each relevant fee authority for the 60-night/61-day case. Do not invent one. |
| 3. 18th birthday | Under-18 status is evaluated on each chargeable day. A birthday during the stay splits its exempt and liable days. The host's manual charge decision cannot bill a known minor day. | This is the best reading of §§ 3b–3c, not an express published birthday ruling; obtain written confirmation for contested cases. |
| 4. Sensitive exemptions | Hosts select a statutory exemption category. A local-bylaw exemption also requires the bylaw provision. The category and provision appear in the protected CSV register; the PDF remains aggregate. DPA, host privacy policy, and guest notice name the register and the possibility of disability data. | Controller counsel must document a valid GDPR Art. 9 condition and safeguards. Art. 6(1)(c) alone is insufficient for special-category data; Art. 9(2)(b) is not a general stay-fee basis. Do not assert Art. 9(2)(g) without the necessary national-law analysis. |
| 5. Art. 18 restriction | A restricted guest remains in the statutory register with complete identity and is counted. Restriction is not treated as permission to silently blank mandatory § 3g fields. CSV access remains host authenticated and downloads use `no-store`. | Controller must review any individual restriction request; this code does not decide whether a particular exceptional request overrides disclosure. |
| 6. Durable records | Finalizing a period stores encrypted copies of its PDF, CSV, and figures. Re-download returns those bytes even after rate, VS, identity, or cadence changes. A correction creates a new version and retains the earlier version. Historical periods remain accessible when fee settings are disabled. Retention keeps the facility's last-entry anchor even after old guest rows are purged, then removes files only after six years from that anchor. | A sealed period is a durable export, but this release does **not** provide an immutable, chronological ledger of each guest entry from the time it is made. Treat the live guest/housebook records and periodic exports as the working register; have counsel validate whether that meets § 3g(3). If not, add an append-only guest-entry journal before calling UbyHost the sole statutory evidenční kniha. |
| 7. Several facilities, same VS | One report and one CSV are produced **per facility**. Sharing a VS does not combine facilities. This follows § 3g's per-facility register and avoids assuming a shared VS authorizes one combined municipal filing. | Ask Praha 1/Praha 3 before offering optional combined submissions. |

## Other audit findings addressed

- Finalization is blocked if a stay has missing signed guest forms, an archived guest record, an incomplete statutory identity, a local-bylaw exemption without its provision, an unfinished period, or incomplete payer/authority/VS setup. The host sees the blockers before the save action.
- Changing monthly/quarterly cadence cannot create a new period that overlaps a saved one. Correcting an old period uses its original cadence.
- The register records **actual amount collected** per guest, entered at finalization, separately from the calculated amount due. Calculated amounts are prefilled, so the host must explicitly confirm checking each amount; the detail page flags a difference. A zero-guest completed period can still be finalized.
- The CSV is UTF-8 with BOM and spreadsheet-formula escaping. Sensitive reasons are absent from PDF and audit log. Exemption reasons and the register/PDF snapshots are encrypted at rest with the app's existing field-encryption mechanism. Startup moves older plaintext reasons into the encrypted column.
- The workspace termination ZIP now contains **every version** of every sealed register CSV and report PDF, so the controller can keep its statutory copy after account closure. The operator must provide and verify that export before the workspace is deleted.
- A guest access export includes that guest's rows from saved register versions without copying another guest's rows. Raw encrypted database columns are excluded from its JSON response.
- The guest notice and DPA/privacy copies were revised and versioned. Existing operator acceptance/version workflows apply.
- Cancelled, unpaid/interrupted, or manually deleted stay data must be checked operationally before finalization. The application counts active reservations and non-archived signed guest rows, and blocks an active stay with an archived guest row. Do not treat a generated report as evidence that source data was complete unless the host checked the source records. A future journal should record deletions and corrections explicitly.
- The scope calculation uses each guest's recorded continuous stay. Two adjacent reservations for the same person with the same provider are not automatically joined; the host must reconcile such stays before filing. The same review applies to a stay later extended past the 60-day boundary, which can require a correction to an earlier saved period.

## Data and route contract for the UX session

- `stay_fee.property_period(apartment, month)` returns a frozen summary when a filing exists; otherwise it returns live figures and `unsigned_stays`, `archived_stays`, `incomplete_guests`, and `threshold_stays`. `report_group` contains exactly one facility. `report_issues` returns translation keys for blockers.
- `POST /stay-fees/{id}/scope-ruling` saves `rule` (`calendar_days` or `nights`) and a written `reference`. Show it only when the exact boundary is relevant, with plain wording.
- `POST /stay-fees/guest-decision` accepts a controlled `reason`, optional `reason_reference` (required for `local_rule`), and decision. Preserve CSRF, apartment ownership, and guest-to-apartment checks.
- `POST /stay-fees/{id}/finalize` accepts `month`, integer `rate_czk` (0–50), `collected_{guest_id}` for every current row, and `confirm_collected=1` when guest rows exist. The action runs only after blockers are resolved. A saved period is read-only by default; `?correct=1` explicitly starts a versioned correction, using the original period cadence even if settings have since changed.
- `GET /stay-fees/{id}/pdf` and `/csv` serve stored bytes only, after access checks. Never regenerate silently. Keep one primary action: **Save period**, then downloads. Payment instructions appear after the period is saved so their amount matches the frozen report.
- The screen should show facility, period, due amount, amount actually collected, number of chargeable/exempt days, blockers, guest rows, and clear correction state. Follow the UX session's warm light mode, compact rows, accessible native controls, and concise copy. No legal disclaimer wall on the primary path.

## Files and migration

- Calculation, statutory rows, sealed files: `App/app/stay_fee.py`; the PDF's counted-day explanation is in `App/app/stay_fee_remittance_pdf.py`.
- Tables/columns: `App/app/db.py` adds `stay_fee_filing`, facility scope answer/reference, encrypted guest reason, and guest bylaw reference. Existing guest fields and rates remain intact. `CREATE TABLE IF NOT EXISTS` and `ADDED_COLUMNS` handle existing databases; startup backfills plaintext legacy reasons.
- Host endpoints and form: `App/app/routes/stay_fees.py`, `App/app/templates/stay_fee_detail.html`, `App/app/host_i18n.py`.
- Privacy, access requests, retention, and workspace handoff: `App/app/{i18n,dpa_i18n,privacy_policy_i18n,terms_i18n,config,dsr,retention,workspace_export}.py`.
- Backups: `App/scripts/backup_data.sh` remains compatible with the local macOS test environment and copies the SQLite database that contains encrypted snapshots. Restore testing still belongs to the operator's deployment procedure.

## Verification and release checklist

1. Run `cd App && .venv/bin/python -m pytest tests -q` and `git diff --check` in the target checkout. Test the production migration on a copy of the database before deploying.
2. In both languages, check the exact month-boundary example, birthday split, 59/60/61-night stays, missing identity, missing signatures, exemption selection, restricted guest, shared VS, zero period, collected/due mismatch, and versioned correction.
3. Finalize a period, download both files, change the property rate and guest record, download again, and compare bytes. Correct it; confirm version 1 remains stored and version 2 downloads. Check unauthorized requests and CSRF.
4. Review the DPA/privacy and guest notice with the controller. Confirm the Art. 9 basis and issue any required updated notice before hosts enter sensitive exemption categories.
5. Obtain the office's written exact-boundary interpretation and record the source in each affected facility. Confirm municipality-specific cadence, rate, VS, form, deadline, and facility reporting instructions before a real filing.

## Primary sources

- [Act No. 565/1990 Coll., §§ 3–3g](https://www.zakonyprolidi.cz/cs/1990-565) (current consolidated text).
- [Ministry of Finance: one-night stay and day of arrival](https://mf.gov.cz/cs/dane-a-ucetnictvi/dane/mistni-spravni-a-soudni-poplatky/odpovedi-na-dotazy/2020/mp-05-2020--poplatek-z-pobytu--vybirani-37299).
- [GDPR, especially Arts. 6, 9, 18](https://eur-lex.europa.eu/eli/reg/2016/679/oj).
- [Praha 3 local fee guidance](https://www.praha3.cz/urad/informace-pro-cizince/informace-pro-cizince-zivotni-situace/mistni-poplatky). Local rules and instructions should always be checked for the facility's authority before filing.
