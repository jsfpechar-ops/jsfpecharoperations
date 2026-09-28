# Security incident response runbook

**Status:** input for counsel. The thresholds, the notification wording and the
retention of incident records need a qualified Czech/EU data-protection lawyer's
sign-off before they are relied on. This is not legal advice.

Companion to the incident register at `/admin/incidents` (platform admins only,
BE-13). The register is the record Art 33(5) GDPR requires.

## Detection sources

- **Application alerts** — `submission_transport`, `submission_rejected`,
  `mail_failed`, `guest_pin_abuse`, `job_failed` and the `incident_review`
  suggestion (BE-13) raised when guest links are rate-limited repeatedly.
- **Cloudflare** — WAF, Bot Fight Mode alerts, leaked-credential mitigation and
  Managed Challenge events (see `docs/CLOUDFLARE.md`).
- **AWS** — Lightsail and SES notices, IAM changes, billing anomalies.
- **Host reports** — a host telling support that something looked wrong.
- **The operator** — anything noticed while working on the service.

## Triage (target: within 24 hours of awareness)

1. Open an incident at `/admin/incidents` as soon as one is suspected, even if
   the facts are thin; it can be edited.
2. Decide the **risk level** (`none`/`low`/`high`) and whether personal data is
   involved. A breach is only reportable when it is likely to result in a risk
   to data subjects' rights.
3. Identify the **affected workspaces** and tick them on the incident.

## Containment

- **Rotate `UBYHOST_SECRET_KEY`** if it may be exposed, following
  `docs/OPERATIONS.md` § "If the secret key is lost or rotated". Remember that
  this invalidates sessions, guest cookies, and re-reads of encrypted document
  numbers and TOTP secrets.
- **Invalidate sessions**: increment `session_version` for affected accounts.
- **Rotate guest permalinks/PINs** for the affected properties.
- **Preserve evidence before rotation**: capture the container logs (OPS-3;
  bounded, so capture them early), the relevant `audit` rows and the Cloudflare
  events. Store them with the incident record.

## Notification

- **Processor → controller, without undue delay (target ≤ 24 hours from
  awareness).** Use the draft on the incident page
  (`incidents.controller_notification_draft`), which names each affected
  workspace's legal-entity contact and states the statutory position. It is a
  draft to copy — nothing is sent automatically.
- **Controller → supervisory authority, within 72 hours** of the controller
  becoming aware (Art 33(1)). The operator's draft reminds the controller of
  this; the controller decides whether the threshold is met.
- **Subjects** are told by the controller where the risk is high (Art 34).
- Record each notification time on the incident row
  (`controllers_notified_at`, `authority_notified_at`, `subjects_notified_at`).

## After

- Close the incident (`closed_at`) and write the post-incident review in
  `notes`: what happened, what was contained, and what changed.
- Feed any code or configuration fix into the normal review process.
- Review whether the detection thresholds in this runbook and in BE-13 need to
  change. **Counsel approves the thresholds.**
