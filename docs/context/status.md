# Status

Updated: 2026-10-10; host geometry review.

## Production

- **Magic-link cutover:** phase 1 + phase 2 done ([0007](../tasks/0007-post-magic-link-deploy-phase2.md)). E-mail login only; `.env` admin + SES; Caddy access log off; all properties connection-tested.
- **112 reconcile:** dry run `guests answered with accepted codes only: 0` — no `--apply` needed (Oct 2026).
- Live `/healthz`: version 1.1.0. Record SHA: `git rev-parse HEAD` in `/opt/ubyhost`.

## Now

- [UI 0040](../tasks/0040-host-wide-geometry-audit.md): PR #338 checked: 3,030 passed, zero skips; CI/staging pending.
- Lawyer: **LAWYER REVIEW** v1.7 (0005).
- Optional: #280+#281 admin preview.

## Next

- [PostHog plan](../plans/posthog-analytics.md): Composer briefs 0033–0036.
- Briefs ready for Cursor: [0017](../tasks/0017-archive-stay-on-page.md) (archive keeps you on the page); [0019](../tasks/0019-stay-invoice-rules.md) reviewed OK, merge `claude/bold-ride-leloxm` → main first; then [0020](../tasks/0020-stay-invoice-pages.md) stay-only invoices ([plan](../plans/stay-only-invoices.md)); 0021 alert later.
- Briefs ready: [0037](../tasks/0037-door-code-taken-period.md), then [0038](../tasks/0038-custom-code-revoke-until-end.md). §12 check 6 passed 2026-10-10 (deleted untyped code does not open).
- Plan [file-retention](../plans/file-retention.md): decided, no build now. Lawyer round: add a Terms/DPA line that the app is not the host's statutory archive.

- TTLock door codes: briefs 0008 to 0016 in [ttlock-door-codes](../plans/ttlock-door-codes.md) §11, run in order (0016 any time after 0010). Test mode first; live only after the §12 acceptance test and the lawyer (K-L row).

- PR review 2026-10-09: #327, #316, #330 closed. #332: run [0032](../tasks/0032-guide-picture-switch-on.md) (drop the form picture), then merge. #331: approved (no ID check, 1-day link window), merge after #332. #328 after #331. #278, #279 undecided.
- Doručenka smoke on a new filing after this cutover.
- TTLock on Render staging, 2026-10-08: lock shared as authorized admin, hand-added stay completed, PIN issued, TTLock window matched UbyHost (09:00 to 16:00) and **the code opened the lock** (owner-tested). Lock has a gateway. Delete of a never-typed code tested 2026-10-10 (stops working). Not yet tested: change, calendar stays, daylight saving.

## Blocked: needs owner, lawyer or council

- Lawyer review of legal texts (0005 and K-L rows in [known-issues](known-issues.md)).
- Stale signed dates (K-F18). HIGH RISK filing: K-F02, K-F03, K-F07; secret rotation K-S10.

## Owner steps already done (don't ask again)

- SES, Turnstile, healthchecks, Better Stack, Cloudflare, retention autopurge, Render staging, Litestream/backup drill, task 0001 (#281), **magic-link deploy + 0007 phase 2 (Oct 2026)**.
