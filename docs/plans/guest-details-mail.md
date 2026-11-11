# Guest details in mail (decided 2026-11-11, not built)

Owner decision: after a guest sends the check-in form, the host gets a mail that shows who registered, so the host need not open the app. The guest gets their own receipt as a separate mail. Efficiency wins where the law leaves room; the limits below are the legal floor.

## Behaviour

- **Host mail** (new, one per submitted form, to the host contact address that is copied on the receipt today):
  - Always: property, stay dates, each guest's name, nationality, head count filled / expected, filing status, stay fee total if any, link to the stay.
  - With **full details** (below): per guest also date of birth, home address, document type, and the document number as `•••• 1234` (last 4 only).
- **Full details** is a workspace setting, **on by default**, with a switch on the host settings page. It takes effect only once the workspace owner has accepted the DPA version that describes it (`acceptance.pending(owner)` has no `dpa`). Until then the host mail is the "always" list. New hosts accept at sign-up; existing hosts are sent to the accept page on their next request to any host page after the version bump.
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
| 1120 | Migration 0044 + `guest_mail_pref` module | Sonnet | none |
| 1120b | Settings-page switch (UX gate) | Sonnet | 1120 |
| 1121 | Host mail: builder, queue on submit, send-time render, drop host cc on the receipt | Opus | 1120 |
| 1122 | Guest receipt "What you sent" block | Opus | 1121 |
| 1123 | DPA, privacy policy and guest-notice wording (replaces the old "host gets a copy" sentences) | Sonnet | 1121 |
| 1123b | DPA and Privacy version bump to 1.8, ROPA, RETENTION, ENVIRONMENT, SES TLS owner steps | Sonnet | 1123 |

1123 and 1123b follow the normal PR flow (wording decided below). Until the version bump of 1123b is live, no workspace gets full details, so 1120 to 1122 can ship first.

## What the code changed in this plan (found while briefing)

- The host mail goes **once per completed stay**, when the receipt goes (`completion_notified_at`), not once per form.
- The code cannot tell which guest row is the person who claimed the stay. So the receipt shows a masked document number for guests typed in by the guest after the claim, names only for everyone else, and **no date of birth or address for anyone**.
- The "(host only)" link leaves the receipt, since the host is no longer copied.
- Follow-ups, not briefed: the fee-update mail (`fee_update.py`) still copies the host; nationality and document type print as codes, not words.

## Legal positions (decided 2026-11-11 by the orchestrator acting as counsel, on the owner's instruction; no outside lawyer has reviewed them)

1. **DPA wording:** as written in brief 1123. The setting is the controller's documented instruction (Art. 28(3)(a)); the clause names the default, the switch, and that the host's mailbox is the host's responsibility.
2. **Notice to existing hosts:** the accept page for DPA and Privacy 1.8 is enough. Full details start only after that acceptance, so no host receives them unannounced. No separate notice mail. Effective date 2026-11-11: only test accounts exist. Once real hosts exist, later changes follow the 30-day notice in Terms section 22.
3. **Guest notice:** "Your host receives your registration details by e-mail." It adds no new recipient (the host is the controller), so it is information under Art. 13, not a consent.
