# Guest details in mail (decided 2026-11-11, not built)

Owner decision: after a guest sends the check-in form, the host gets a mail that shows who registered, so the host need not open the app. The guest gets their own receipt as a separate mail. Efficiency wins where the law leaves room; the limits below are the legal floor.

## Behaviour

- **Host mail** (new, one per submitted form, to the host contact address that is copied on the receipt today):
  - Always: property, stay dates, each guest's name, nationality, head count filled / expected, filing status, stay fee total if any, link to the stay.
  - With **full details** (below): per guest also date of birth, home address, document type, and the document number as `•••• 1234` (last 4 only).
- **Full details** is a workspace setting, **on by default**, with a switch on the host settings page. It takes effect only once the workspace owner has accepted the DPA version that describes it (`acceptance.pending(owner)` has no `dpa`). Until then the host mail is the "always" list. New hosts accept at sign-up; existing hosts at their next sign-in after the version bump.
- **Guest receipt** (the existing completion mail, `build_completion`): stays a separate mail to the verified claim address only. It gains a "What you sent" block: the submitter's own details with the document number masked the same way, and co-guests by name only. The host is no longer copied on it (Reply-To stays), because the host has their own mail.
- **Never in any mail:** full document or visa number, signature, ID photo.
- **Stored bodies:** the outbox must not hold guest field values. The body is rendered at send time from the database (same idea as `CLAIM_SECRET_MARKER`), so a queued row carries ids only.
- **Transport:** SES delivery for these mails requires TLS.
- Not in scope: the head-count digest stays as decided on 2026-11-10 (field names, not values).

## Why these limits (legal)

- Host is the controller; the DPA clause plus the default-on setting is the host's documented instruction to us (GDPR Art. 28(3)(a)). That is why default-on is fine, and why it must wait for DPA acceptance.
- Masked document number, no cc, verified address only, no stored bodies: Art. 32 (security fit to risk). A full identity set in an inbox, or sent to a mistyped address, is a reportable breach.
- Co-guests by name only on the guest receipt: one guest must not receive another guest's document data.
- The host's own mailbox is outside our six-year purge. The DPA says so.

## Interface between briefs

`App/app/guest_mail_pref.py` (brief 1120):

```python
def full_details(owner_user_id: int) -> bool:
    """True when the workspace switch is on AND the owner accepted the current DPA."""
```

Briefs 1121 and 1122 call only this function; they never read the column.

## Briefs

| # | What | Brief by | Depends on |
|---|---|---|---|
| 1120 | Migration + setting + settings-page switch + `guest_mail_pref.full_details` | Sonnet | none |
| 1121 | Host mail: builder, queue on submit, send-time render, drop host cc on the receipt | Opus | 1120 |
| 1122 | Guest receipt "What you sent" block | Opus | 1121 |
| 1123 | DPA, privacy policy and guest-notice sentences, ROPA, RETENTION, `retention.py` line, DPA version bump, SES TLS | Sonnet | 1121 |

1123 stays a **draft PR until the lawyer confirms the wording** (it joins the open lawyer package). Until its version bump is live, no workspace gets full details, so 1120 to 1122 can ship first.

## Open for the lawyer

1. DPA wording for "guest details by e-mail to the controller's contact address", and that the host's mailbox is the host's responsibility.
2. Whether default-on plus acceptance at next sign-in is enough notice for existing hosts, or a notice mail is also needed.
3. The sentence in the guest privacy notice.
