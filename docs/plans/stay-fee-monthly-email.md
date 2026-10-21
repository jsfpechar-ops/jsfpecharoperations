# Stay fee monthly email (decided 2026-10-21, not built)

Owner decision: every period, UbyHost emails the operator the filled-in stay-fee report with the QR. **Clean periods are confirmed automatically** (frozen), so the host only forwards the PDF and scans the QR. No "paid" button anywhere.

## Behaviour

- Daily job (scheduler), acts from the 2nd day after a period ends (monthly: previous month; quarterly: previous quarter), Prague date.
- Per active fee property with no saved filing for that period:
  - No blockers (same checks as `stay_fee_finalize`: `report_issues` + `unsigned_stays`, collected = line amounts): save the filing (audit `stay_fee_auto_finalize`), then queue the full email.
  - Blockers: queue one "fix this" email per period naming each issue with a link to the report; keep re-checking daily, and confirm + send the full email once it is clean.
  - 0 Kč: confirm and send the PDF with "nothing to pay".
- Full email: PDF attached, QR as an attached PNG (Gmail blocks data URIs), amount, account, VS and the council data box in text, link to `/stay-fees?month=`.
- Recipient: the property's legal entity `contact_email` (`mail_notify._entity_contact_email`), same as other host notices.
- Off switch: workspace-level, like `user_account.onboarding_emails_opt_out` (`/account/onboarding-emails` form in Settings, account section). Default on. New migration `0011`. The stay fees list page gets one line saying what happens on the 2nd.

## Building blocks found

- `mail.enqueue(kind, idempotency_key, to_email, subject, payload, ...)`; new kinds go in `mail.KINDS`/`HOST_KINDS`. Idempotency keys: `stay_fee_report:{apartment}:{period_key}:{version}` and `stay_fee_blocked:{apartment}:{period_key}`.
- The outbox has **no attachment support**. Add it: payload names the filing id (never store PDF bytes in the outbox); at delivery `_send_ses` builds a raw MIME message (SESv2 `Content.Raw`) with `stay_fee_filing.pdf_bytes(row)` and the QR PNG (`payments` module); the console backend logs the attachment names.
- Seal: `stay_fee_filing.save(apartment, first, rate_czk=, collected=, issued_on=, cadence=)`; factor the checks out of `routes/stay_fees.stay_fee_finalize` into one shared function so the button and the job cannot diverge.
- Scheduler: `app/scheduler.py` (`add_job`, `_log_run`, `job_intervals`).
- PDF content: payer, property, bed-day totals (no guest names): fine to email.

## Cost

SES list price about $0.10 per 1,000 mails plus $0.12/GB attachments: about $1.50 a month at 10,000 properties.

## Suggested briefs

1. Mail attachments (outbox reference + SES raw + console) with tests.
2. Shared seal function + daily job + the two mail kinds + EN/CS/VI copy.
3. Opt-out switch (migration 0011, settings row, list-page line), screenshots.

Avoid the stay-fee bank fields (another thread is changing them).
