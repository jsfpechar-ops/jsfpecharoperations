# Data-subject request runbook

**Status:** input for counsel (LD-6). The right-by-right notes and the reply
templates need a qualified Czech/EU data-protection lawyer's sign-off.

The register and the per-guest export live at `/privacy-requests` and
`/guests/{id}/export.json` (BE-8).

## Who handles a request

- A request **to a host about that host's guest** is the host's to answer; the
  host is the controller. UbyHost provides the register, the export and the
  deadline tracking.
- A request **to the operator** about the operator's own processing (a host
  account, security logs, support) is answered by the operator.
- A request that arrives at support about a guest's stay is passed to the host
  and recorded on the register.

## Identity

Verify the requester's identity before disclosing anything. For a guest, the
claim link / PIN session already proves control of the reservation; for a
written request, ask for enough to match the record (do not over-collect). The
register has an "identity checked" marker (`identity_checked_at`).

## The deadline

One month from receipt (Art 12(3)), extendable by up to two months for complex
requests; the register computes the due date and the deadline job warns five
days before. Record the outcome and close the row.

## What each right means here

Guest registration data is processed under **Art 6(1)(c)** as a legal
obligation (Act 326/1999).

| Right | Position (counsel to confirm) |
|---|---|
| Access (15) | Provide the `/guests/{id}/export.json` bundle plus the registration PDF |
| Rectification (16) | Host edits the guest; the record is re-sent if it was filed |
| Erasure (17) | Limited while § 101 requires the house book; a record past the six-year cutoff is deleted by retention |
| Restriction (18) | The BE-9 flag; whether a restricted record may still be filed is counsel's call |
| Portability (20) | **Generally not applicable**: the basis is 6(1)(c), not consent or contract |
| Objection (21) | **Not available** against 6(1)(c) processing |

## Reply templates

Draft replies (acknowledgement, fulfilled, refused with the § 101 reason,
extension) are for counsel to approve before use. Do not invent statutory
wording; use the forms counsel provides.
