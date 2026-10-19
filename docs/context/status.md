# Status

Updated: 2026-10-19.

## Production

- Filing watchdog: owner confirmed the server digest interval changed from 6 to 72 hours on 2026-10-15; repository default is still 6 hours (K-OPS72).

- **Magic-link:** phases 1–2 done ([0007](../tasks/0007-post-magic-link-deploy-phase2.md)); e-mail login, `.env` admin/SES, access log off, properties tested.
- **112 reconcile:** dry run `guests answered with accepted codes only: 0` — no `--apply` needed (Oct 2026).
- Live app `/healthz`: 1.1.0; deploy SHA: `git rev-parse HEAD` in `/opt/ubyhost`.

## Now

- Host design reset: PR #402 (branch claude/project-thread-5hw8cf) finishes 0138-0146 and 0154-0163; every host and admin page passes the CI layout guard (MASTER 11.0), shots in project files design-reset/checkpoint-3. Waiting on owner review and merge.
- Cleaning 0104: #396 CI/staging review pending ([brief](../tasks/0104-cleaning-management.md)); calendar 0103 on main.
- Host #397: b51e0bb; CI 8/8, zero browser skips ([brief](../tasks/0123-dashboard-stays-only.md)).

- Check production `/healthz`. The credential letter goes to data box ybndqw9.
- Lawyer: **LAWYER REVIEW** on legal v1.7 (0005) if not yet signed off.

## Next


- Door codes 0037 and 0038 are on main. Next: those owner steps on staging.
- Merged 0067 (#371) and 0068 (#372). TTLock answered all questions ([TTLOCK](../TTLOCK.md#what-ttlock-support-confirmed-2026-10-12)). Next: [0069](../tasks/0069-same-period-shared-pin.md), same-hours rebooking must not reuse a PIN (K-D04).
- Plan [file-retention](../plans/file-retention.md): decided, no build now. Lawyer round: add a Terms/DPA line that the app is not the host's statutory archive.

- TTLock door codes: briefs 0008 to 0016 in [ttlock-door-codes](../plans/ttlock-door-codes.md) §11, run in order (0016 any time after 0010). Test mode first; live only after the §12 acceptance test and the lawyer (K-L row).

- Doručenka smoke on a new filing after this cutover.
- TTLock on Render staging, 2026-10-08: lock shared as authorized admin, hand-added stay completed, PIN issued, TTLock window matched UbyHost (09:00 to 16:00) and **the code opened the lock** (owner-tested). Lock has a gateway. Delete of a never-typed code tested 2026-10-10 (stops working). Not yet tested: change, calendar stays, daylight saving.

## Blocked: needs owner, lawyer or council

- Lawyer review of legal texts (0005 and K-L rows in [known-issues](known-issues.md)).
- Stale signed dates (K-F18). HIGH RISK filing: K-F02, K-F03, K-F07; secret rotation K-S10.

## Owner done

- SES, Turnstile, healthchecks, Better Stack, Cloudflare, autopurge, Render staging, backup drill, 0001 (#281), magic-link/0007 phase 2 (Oct 2026).

- [UI 0041](../tasks/0041-host-stay-actions.md): Paused; #338 CI imports: 0042; UI failures remain.