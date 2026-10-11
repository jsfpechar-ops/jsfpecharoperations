# 0051: Stay fee "Ready to send by data box" panel + sent/paid marks

Status: done
Depends on: none | Branch: task/0051-stay-fee-send-panel
Executor: Cursor local agent | Fits one session
Next free migration: 0009

## 1. Objective
On a finalized stay-fee period, the host sees one panel with everything needed to file it: the municipality's data-box ID, a subject and a short text (each copyable), the PDF, and a link to log in to their data box. After sending they press "Mark as sent" (optional message ID), and after paying, "Mark as paid". The status then reads "Sent" / "Paid", and only because the host said so.

## 2. Context
- `App/app/db.py` table `stay_fee_filing` (id, apartment_id, period_key, version, …, pdf_enc, created_at, superseded_at). The current row = superseded_at IS NULL.
- `App/app/routes/stay_fees.py`: `stay_fee_detail` (GET `/stay-fees/{apartment_id}`), `_row_status` (attention/saved/waiting/ready), finalize at POST `/stay-fees/{apartment_id}/finalize`.
- `App/app/templates/_stay_fee_fields.html`: authority name/address/contact inputs; `routes/admin.py` `_apartment_payload` saves `stay_fee_authority_*` (limit 200).
- HOST_APP_DESIGN §1 rule 4: never imply UbyHost sent a municipal filing or watches payments.
- Rule 5: SQL via `db.py` helpers, Postgres-portable; schema change = new migration file.
- New personal-data field? No (data-box IDs of municipalities are public). The message ID is an operational record: add it to `retention.py` with the filing's retention.

## 3. Files
| Path | Action | What |
|---|---|---|
| App/app/migrations/0009_stay_fee_send.sql | new | `ALTER TABLE apartment ADD COLUMN stay_fee_authority_databox TEXT;` `ALTER TABLE stay_fee_filing ADD COLUMN sent_at TEXT; ADD COLUMN sent_message_id TEXT; ADD COLUMN paid_at TEXT;` (one statement per column, portable) |
| App/app/validation.py | edit | `normalise_databox(value) -> str`: strip, lower-case, must match `^[a-z0-9]{7}$`, else "" |
| App/app/routes/admin.py | edit | save `stay_fee_authority_databox` via `normalise_databox` |
| App/app/templates/_stay_fee_fields.html | edit | field "Municipality data-box ID" with hint "7 characters, e.g. abc1234. You find it on the municipality's website." |
| App/app/routes/stay_fees.py | edit | POST `/stay-fees/{apartment_id}/filings/{filing_id}/sent` and `/paid` (owner check, CSRF, idempotent, undo = POST with `undo=1`); extend `_row_status` with "sent" and "paid" after "saved" |
| the stay-fee detail template (grep `stay_fee_detail` render name) | edit | the panel below the finalized summary |
| App/app/host_i18n.py | edit | EN + CS keys |
| App/app/retention.py | edit | line for `sent_message_id` |
| App/tests/test_stay_fee_send_panel.py | new | tests |

## 4. Steps
1. Migration as in §3. Run the app's migration test.
2. Panel (only when the period has a current finalized filing):
   - Recipient: authority name + data-box ID with Copy. If the ID is missing: "Add the municipality's data-box ID" → link to the fee settings anchor.
   - Subject (CS, it goes to the municipality): `Ohlášení poplatku z pobytu – {period label CS} – {property name}` (Notification of the stay fee – {period} – {property}). Copy.
   - Text (CS): 3 lines: who files (operator name, IČO if set), the period, the amount due; "Podrobnosti v příloze." (Details in the attachment.) Copy.
   - "Download PDF" (the existing finalized PDF route).
   - Link "Open your data box" → `https://www.mojedatovaschranka.cz/` (target _blank, rel noopener; plain link, no request from our server).
   - Then two buttons: "Mark as sent" (with an optional message-ID input) and "Mark as paid". Each shows its date once set, plus "Undo".
3. Status order in the list: attention → waiting → ready → saved → sent → paid. Paid without sent is allowed (some municipalities only want payment).
4. Tests: ID normalisation (valid, uppercase → lowercase, wrong length → ""); panel hidden before finalize; sent/paid set and undo; another owner → 404; the list status shows "Sent"/"Paid" only from the stored fields.

## 5. Do not touch
Fee calculation, PDF content, guest pages, door codes. No outbound HTTP request.

## 6. Commands
From App/: `.venv/bin/python -m pytest tests -q`. Root: `python3 scripts/context_lint.py`. Browser and geometry tests 0 skipped.

## 7. Acceptance
- [ ] Demo property: finalize September → panel with ID, subject, text, PDF; mark sent → list shows "Sent"; mark paid → "Paid".
- [ ] Screenshots at 360, 390 and 1280 px.

## 8. Stop and ask
1. The finalized filing has no stable id the template can post to.
2. The fee detail template isn't a single file you can edit without touching the calculation views.

## 9. Report
Files, migration output, test tail, screenshots.
