# Workplan merge sequence (prepared branches)

Merge **in numeric order** `0001` → `0034`. Each row is a draft branch on `origin`; open or use the matching draft PR. After each merge, the next branch’s diff is only that patch (cumulative tips).

**Owner setup (secrets, AWS, healthchecks, gates):** see [OWNER_MANUAL_SETUP.md](OWNER_MANUAL_SETUP.md).

**One-shot option:** merge draft PR [#237](https://github.com/jsfpechar-ops/jsfpecharoperations/pull/237) (`cursor/workplan-ordered-682e` → `main`). Same end state as merging through `cursor/wp-stack-34-682e` (tip includes owner manual, merge docs, and the WP33 query-budget test fix).

**Per-patch drafts:** branches `cursor/wp-stack-01-682e` … `cursor/wp-stack-34-682e` are on `origin`. Each targets `main` and is cumulative; merge in table order (or close the per-patch drafts and merge #237 only).

| # | WP | Draft branch | PR title |
|---|-----|--------------|----------|
| 0001 | WP05 | `cursor/wp-stack-01-682e` | WP05: Litestream continuous backup to S3 |
| 0002 | WP06 | `cursor/wp-stack-02-682e` | WP06: Scheduler in its own process, web workers |
| 0003 | WP07 | `cursor/wp-stack-03-682e` | WP07: Job heartbeats, static caching, compression |
| 0004 | STEP0 | `cursor/wp-stack-04-682e` | STEP0: Staging deploy target |
| 0005 | WP32 | `cursor/wp-stack-05-682e` | WP32: Size the containers for the 8 GB server |
| 0006 | WP30 | `cursor/wp-stack-06-682e` | WP30: Request and store the Doručenka PDF correctly |
| 0007 | WP31 | `cursor/wp-stack-07-682e` | WP31: Exactly one automatic resend per interrupted filing |
| 0008 | WP01 | `cursor/wp-stack-08-682e` | WP01: Deadline shows the filing time once a stay is reported |
| 0009 | WP02 | `cursor/wp-stack-09-682e` | WP02: Property names in guest e-mails |
| 0010 | WP03 | `cursor/wp-stack-10-682e` | WP03: Guide second pass |
| 0011 | WP04 | `cursor/wp-stack-11-682e` | WP04: Admin access to guest data |
| 0012 | WP25 | `cursor/wp-stack-12-682e` | WP25: House book layout, filed-guest locking, Doručenka button |
| 0013 | WP28 | `cursor/wp-stack-13-682e` | WP28: UI bug sweep |
| 0014 | WP08 | `cursor/wp-stack-14-682e` | WP08: Passport upload hardening |
| 0015 | WP09 | `cursor/wp-stack-15-682e` | WP09: Umami on public pages only |
| 0016 | WP27 | `cursor/wp-stack-16-682e` | WP27: Privacy first |
| 0017 | WP22 | `cursor/wp-stack-17-682e` | WP22: Retention aligned to law |
| 0018 | WP23 | `cursor/wp-stack-18-682e` | WP23: Filing watchdog |
| 0019 | WP24 | `cursor/wp-stack-19-682e` | WP24: Terms, DPA and manual-filing texts |
| 0020 | WP26 | `cursor/wp-stack-20-682e` | WP26: Guest pages in German, Spanish, French |
| 0021 | WP33 | `cursor/wp-stack-21-682e` | WP33: Overdue stays, guest languages behind a switch |
| 0022 | WP10 | `cursor/wp-stack-22-682e` | WP10: Admin Operations page |
| 0023 | WP13 | `cursor/wp-stack-23-682e` | WP13: Per-request query, DB-time and lock-time logging |
| 0024 | WP14 | `cursor/wp-stack-24-682e` | WP14: One database connection per thread, remove N+1 |
| 0025 | WP15 | `cursor/wp-stack-25-682e` | WP15: Skip unchanged iCal feeds |
| 0026 | WP17 | `cursor/wp-stack-26-682e` | WP17: Copy cleanup on guest and host pages |
| 0027 | WP11 | `cursor/wp-stack-27-682e` | WP11: Admin funnel page and CSV export |
| 0028 | WP12 | `cursor/wp-stack-28-682e` | WP12: Three lifecycle e-mails |
| 0029 | WP16 | `cursor/wp-stack-29-682e` | WP16: Separate data-encryption key |
| 0030 | WP18 | `cursor/wp-stack-30-682e` | WP18: Prepare a later Postgres move |
| 0031 | WP19 | `cursor/wp-stack-31-682e` | WP19: Readable guest links |
| 0032 | WP20 | `cursor/wp-stack-32-682e` | WP20: Self sign-up page with Google Ads conversion |
| 0033 | WP21 | `cursor/wp-stack-33-682e` | WP21: Meta Conversions API sign-up conversion |
| 0034 | WP29 | `cursor/wp-stack-34-682e` | WP29: No em dashes in user-visible copy |

Supersedes early single-patch branch `cursor/wp05-litestream-682e` (PR #236) — use `cursor/wp-stack-01-682e` instead.
