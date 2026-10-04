# UbyHost compliance pack

Drafted 4 October 2026 from the code at commit `8691757` (WP21) and from `../04_legal_positions.md`. Reasoned drafting, not attorney advice.

## Documents

| File | What it is | Published or internal | Where |
|---|---|---|---|
| `01_records_of_processing.md` | Art. 30 records: part A as controller, part B as processor | Internal. Show to the ÚOOÚ on request | Keep in this folder; replaces `docs/privacy/ROPA.md` |
| `02_dpia_identity_documents.md` | DPIA for guest document data and ID photos | Internal. Give to a host on request (DPA § 13) | Replaces `docs/privacy/DPIA.md` |
| `03_breach_response_runbook.md` | Breach steps, host e-mail templates CS and EN, ÚOOÚ checklist | Internal. Keep a printed or offline copy | Replaces `docs/privacy/INCIDENT_RESPONSE.md`; incidents are recorded at `/admin/incidents` |
| `04_terms_clauses.md` | Additions to the host Terms, CS and EN, with the existing clause numbers | Published once adopted | `/terms` (`App/app/terms_i18n.py`), as version 1.6 |
| `05_manual_filing_fallback.md` | Guide for hosts to file by hand in UbyPort, CS and EN | Published | New public guide `/pruvodce/rucni-hlaseni-ubyport` (`App/app/public_guides.py`); link it from Terms § 10.4, from the rejected, failed and unknown-outcome alerts, and from Help & support |

Already published and not changed here: `/privacy`, `/dpa`, `/subprocessors`, `/legal`.

## What the owner must fill in or decide

Fill in:
1. Your name, IČO and address (01 identification table; also env `UBYHOST_OPERATOR_*`).
2. The mailbox provider behind support@ubyhost.com, and its retention (01, row A4).
3. Where UbyHost's own invoices to hosts are made. The code has no billing of hosts; the in-app invoices are the hosts' own tool (01, row A12).
4. Your datová schránka ID and a test login (03, section 6). It is the safest channel to the ÚOOÚ.
5. A phone number for incident e-mails (03 templates).
6. DPIA sign-off with name and date (02, section 7).

Decide:
1. Turn on `UBYHOST_RETENTION_AUTOPURGE=1`. Until then the 6-year deletion of guest records, stay-fee records and invoices runs in dry-run only.
2. Retention after account deletion for acceptance records, the data-subject request register and incident records. The code deletes the first two with the workspace and keeps incidents indefinitely. Proposal: 3 years, 3 years, 5 years.
3. Liability floor in Terms § 17.2: keep CZK 5,000 or raise to CZK 10,000.
4. "opravňuje" or "zmocňuje" in Terms § 10a (recommendation: "opravňuje").
5. Keep or drop the maintenance-window promise in Terms § 13.
6. Whether Google Drive is used for production backups. If not, remove it from `/subprocessors` and DPA § 11; DPA § 11 also still lists Render.

Verify:
1. Whether the UbyPort web-service credentials also log in to the UbyPort web application (05 assumes they do not).
2. The menu names inside the UbyPort web application (Police handbook PDF not opened).
3. The ÚOOÚ DPIA list, and whether NÚKIB rules under zákon 264/2025 Sb. apply (assumed not).

## Code changes these documents imply

- Terms 1.6: new strings in `terms_i18n.py`, bump `TERMS_VERSION`, update `tests/test_legal_contents.py`, notify hosts 30 days ahead (§ 22).
- New public guide entry in `public_guides.py` (CS and EN), linked from the reporting alerts.
- Optional later: a "filed by hand" marker with Doručenka upload on the guest, which would remove the support step in 05.
- `docs/OPERATIONS.md` "If the secret key is lost or rotated" predates WP16 (it says the secret key derives the Fernet key). Update it to describe `UBYHOST_DATA_KEYS` and `scripts/reencrypt.py`. The same stale sentence is in the comment at the top of `deploy/lightsail/litestream.yml`.
