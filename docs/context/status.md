# Status

Updated: 2026-10-11. Door codes: 0037 merged (#340); 0038 in PR #341, reviewed OK.

## Production

- **Magic-link:** phases 1–2 done ([0007](../tasks/0007-post-magic-link-deploy-phase2.md)); e-mail login, `.env` admin/SES, access log off, properties tested.
- **112 reconcile:** dry run `guests answered with accepted codes only: 0` — no `--apply` needed (Oct 2026).
- Live app: `/healthz` `version` 1.1.0. Record deploy SHA when convenient: `git rev-parse HEAD` in `/opt/ubyhost`.

## Now

- Lawyer: **LAWYER REVIEW** on legal v1.7 (0005) if not yet signed off.
- Optional: deploy #280+#281 (admin preview) when you want it on production.

## Next

- PostHog: PR #339 (337 + [0039](../tasks/0039-posthog-hardening.md)) approved; merge on green, close #337 unmerged. Key after the PostHog owner steps.
- Briefs ready for Cursor: [0017](../tasks/0017-archive-stay-on-page.md) (archive keeps you on the page); [0019](../tasks/0019-stay-invoice-rules.md) reviewed OK, merge `claude/bold-ride-leloxm` → main first; then [0020](../tasks/0020-stay-invoice-pages.md) stay-only invoices ([plan](../plans/stay-only-invoices.md)); 0021 alert later.
- Door codes: [0037](../tasks/0037-door-code-taken-period.md) merged; [0038](../tasks/0038-custom-code-revoke-until-end.md) PR #341. Next: 0037 and 0038 owner steps on staging. §12 check 6 passed 2026-10-10 (deleted untyped code does not open).
- Plan [file-retention](../plans/file-retention.md): decided, no build now. Lawyer round: add a Terms/DPA line that the app is not the host's statutory archive.

- TTLock door codes: briefs 0008 to 0016 in [ttlock-door-codes](../plans/ttlock-door-codes.md) §11, run in order (0016 any time after 0010). Test mode first; live only after the §12 acceptance test and the lawyer (K-L row).

- PR review 2026-10-09: #332, #328 merged. #331 approved, merge. #278, #279 undecided.
- Doručenka smoke on a new filing after this cutover.
- TTLock on Render staging, 2026-10-08: lock shared as authorized admin, hand-added stay completed, PIN issued, TTLock window matched UbyHost (09:00 to 16:00) and **the code opened the lock** (owner-tested). Lock has a gateway. Delete of a never-typed code tested 2026-10-10 (stops working). Not yet tested: change, calendar stays, daylight saving.

## Blocked: needs owner, lawyer or council

- Lawyer review of legal texts (0005 and K-L rows in [known-issues](known-issues.md)).
- Stale signed dates (K-F18). HIGH RISK filing: K-F02, K-F03, K-F07; secret rotation K-S10.

## Owner done

- SES, Turnstile, healthchecks, Better Stack, Cloudflare, autopurge, Render staging, backup drill, 0001 (#281), magic-link/0007 phase 2 (Oct 2026).

- [UI 0041](../tasks/0041-host-stay-actions.md): Paused; #338 CI imports: 0042; UI failures remain.
