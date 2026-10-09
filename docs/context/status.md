# Status

Updated: 2026-10-09 after PR cleanup.

## Production

- **Magic-link cutover:** phase 1 + phase 2 done ([0007](../tasks/0007-post-magic-link-deploy-phase2.md)). E-mail login only; `.env` admin + SES; Caddy access log off; all properties connection-tested.
- **112 reconcile:** dry run `guests answered with accepted codes only: 0` — no `--apply` needed (Oct 2026).
- Live app: `/healthz` `version` 1.1.0. Record deploy SHA when convenient: `git rev-parse HEAD` in `/opt/ubyhost`.

## Now

- Lawyer: **LAWYER REVIEW** on legal v1.7 (0005) if not yet signed off.
- Optional: deploy #280+#281 (admin preview) when you want it on production.

## Next

- Briefs ready for Cursor: [0017](../tasks/0017-archive-stay-on-page.md) (archive keeps you on the page); [0019](../tasks/0019-stay-invoice-rules.md) reviewed OK, merge `claude/bold-ride-leloxm` → main first; then [0020](../tasks/0020-stay-invoice-pages.md) stay-only invoices ([plan](../plans/stay-only-invoices.md)); 0021 alert later.
- Briefs ready (after PR #325 merges): [0021](../tasks/0021-one-lock-database-rule.md) one lock per property in the database; [0022](../tasks/0022-guest-door-code-waiting-messages.md) guest waiting messages. Later: demo (~2 months), TTLock error dictionary after TTLock support answers `-1026`.
- Plan [file-retention](../plans/file-retention.md): decided, no build now. Lawyer round: add a Terms/DPA line that the app is not the host's statutory archive.

- TTLock door codes: briefs 0008 to 0016 in [ttlock-door-codes](../plans/ttlock-door-codes.md) §11, run in order (0016 any time after 0010). Test mode first; live only after the §12 acceptance test and the lawyer (K-L row).

- PR cleanup 2026-10-09: 29 outdated PRs closed. Briefs for Cursor: [0030](../tasks/0030-door-codes-empty-lock-list.md) (was #327), [0031](../tasks/0031-door-code-view-tests.md) (was #316). #278 and #279 undecided.
- Doručenka smoke on a new filing after this cutover.
- TTLock on Render staging, 2026-10-08: lock shared as authorized admin, hand-added stay completed, PIN issued, TTLock window matched UbyHost (09:00 to 16:00) and **the code opened the lock** (owner-tested). Not yet tested: change, cancel and delete (no gateway), calendar stays, daylight saving.

## Blocked: needs owner, lawyer or council

- Lawyer review of legal texts (0005 and K-L rows in [known-issues](known-issues.md)).
- Stale signed dates (K-F18). HIGH RISK filing: K-F02, K-F03, K-F07; secret rotation K-S10.

## Owner steps already done (don't ask again)

- SES, Turnstile, healthchecks, Better Stack, Cloudflare, retention autopurge, Render staging, Litestream/backup drill, task 0001 (#281), **magic-link deploy + 0007 phase 2 (Oct 2026)**.
