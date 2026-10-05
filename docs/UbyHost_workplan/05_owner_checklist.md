# Owner checklist

Everything Joe does by hand, in order. Cursor does the code. Details for each step are in `notes/WPNN-*.md`.

**Do this first.** Ask the foreign police (Ředitelství služby cizinecké policie, UbyPort support) for access to the UbyPort test environment now, so Gate 2 does not wait on them.

## A. Hand the plan to Cursor (15 minutes)

1. Put this folder, except `skills/`, at `docs/plans/UbyHost_workplan/` in the repo (a docs-only PR you merge).
2. Copy `skills/poteto-mode/SKILL.md` and `skills/llm-council/SKILL.md` into Cursor's global skills folder (usually `~/.cursor/skills/<name>/SKILL.md`; check Cursor's settings if your version differs). In Claude they are already saved to your account.
3. Give Cursor this prompt:

   > Read `docs/plans/UbyHost_workplan/00_README_for_cursor.md`, then `AGENTS.md`. Apply `series/0001-*.patch` as described in "Procedure for each PR", read its notes, run the checks, open a draft PR and stop. Use poteto-mode.

4. After you merge each PR, say "next". Cursor takes the next number.

## B. Server setup now (infrastructure PRs 0001 to 0005)

Do these on the 8 GB Lightsail server as each PR is merged. Total about 2 hours.

**1. Accounts (before PR 0001).**
- healthchecks.io: free account. Notifications by e-mail to you.
- An uptime monitor (UptimeRobot or Better Stack, free): check `https://ubyhost.com/healthz` every minute, alerts by e-mail.
- Password manager entry "UbyHost production" for every secret below.

**2. PR 0001 WP05 Litestream.**
1. AWS console, region eu-central-1, S3: create bucket `ubyhost-litestream-<suffix>`. Block all public access on. Versioning on. Default encryption SSE-S3.
2. Lifecycle rule on the bucket: delete non-current versions after 30 days and remove expired delete markers. No rule that expires current versions.
3. IAM: user `ubyhost-litestream`, no console access, inline policy from `notes/WP05-litestream.md` with your bucket name. Create an access key.
4. Server `.env`: `LITESTREAM_S3_BUCKET`, `LITESTREAM_ACCESS_KEY_ID`, `LITESTREAM_SECRET_ACCESS_KEY`, `LITESTREAM_S3_PATH=ubyhost/production`, and `LITESTREAM_HEARTBEAT_URL` (healthchecks check, period 5 min, grace 10 min).
5. Save `UBYHOST_SECRET_KEY` (or the content of `/data/secret_key`) in the password manager. Without it a restored database cannot be decrypted.
6. Deploy. Run `docker compose logs --tail=30 litestream` (expect "snapshot complete"), then `./scripts/restore_test.sh`. Repeat the restore test every quarter.

**3. PR 0002 WP06 worker process.** The server is already 8 GB, so no resize step. Deploy, then check `docker compose logs worker` shows exactly one scheduler start and `docker compose logs ubyhost` shows none. If you ever roll back this PR, run `docker compose stop worker` first.

**4. PR 0003 WP07 heartbeats.** In healthchecks.io create these checks and put their URLs in `.env`:

| Check | `.env` key | Period | Grace |
|---|---|---|---|
| UbyPort submit sweep | `UBYHOST_HEARTBEAT_URL` | 10 min | 10 min |
| Calendar sync | `UBYHOST_HEARTBEAT_ICAL_URL` | 60 min | 30 min |
| Mail outbox | `UBYHOST_HEARTBEAT_MAIL_URL` | 5 min | 10 min |
| Nightly backup | `UBYHOST_BACKUP_PING_URL` | 1 day | 2 h |

**5. PR 0004 STEP0 staging.**
1. Second Lightsail instance, Frankfurt, 2 GB is enough. Static IP. DNS `staging.ubyhost.com` to it.
2. Staging `.env`: `UBYHOST_DEPLOYMENT=staging`, `UBYHOST_UBYPORT_ENV=mock` (switch to `test` for the real UbyPort test run in step D2), `UBYHOST_MAIL_BACKEND=console`, a new `UBYHOST_SECRET_KEY` (never the production one), the 2 GB sizes from step 6 below.
3. Litestream for staging: same bucket, `LITESTREAM_S3_PATH=staging/ubyhost`, a separate IAM user limited to `staging/*`.
4. GitHub, Settings, Environments: new `staging` (all branches) with `LIGHTSAIL_HOST`, `LIGHTSAIL_SSH_PRIVATE_KEY` (a key only for staging), `LIGHTSAIL_KNOWN_HOSTS`, variable `LIGHTSAIL_HEALTH_URL`. Restrict `production` to `main` and move its three secrets into that environment.
5. Never put real guest data on staging.

**6. PR 0005 WP32 sizing.** Production `.env`: `UBYHOST_WEB_WORKERS=4`. The memory limits default to web 2g, worker 1g, Litestream 256m, Caddy 256m; leave them. Once the Litestream check has been green for a day, set `UBYHOST_BACKUP_RETENTION_DAYS=7`. Staging `.env`: `UBYHOST_WEB_WORKERS=2`, `UBYHOST_WEB_MEM=896m`, `UBYHOST_WORKER_MEM=448m`, `UBYHOST_LITESTREAM_MEM=128m`, `UBYHOST_CADDY_MEM=128m`.

## C. Filing PRs 0006 and 0007

1. Deploy 0006 (Doručenka) to staging with `UBYHOST_UBYPORT_ENV=test` and file one test stay against the real UbyPort test endpoint. Check the report page shows "Download Doručenka (PDF)". If UbyPort rejects the header, revert 0006 and tell me; the element order was inferred from the official document because the WSDL could not be downloaded.
2. 0007 (one automatic resend): nothing on the server.

## D. Before the first real host (PRs 0008 to 0021)

| PR | You do |
|---|---|
| 0011 WP04 | Read the HIGH RISK hunks. Optional: open one Doručenka PDF; if it shows no passport numbers, tell Cursor to unblock receipts during admin support. |
| 0015 WP09 | Umami Cloud account in the EU region, add the site, accept and save the DPA, put `UMAMI_SCRIPT_URL`, `UMAMI_WEBSITE_ID` (and `UMAMI_HOST_URL` if the snippet has one) in `.env`. After deploy check that `/login` and a `/l/...` page load nothing from Umami. |
| 0018 WP23 | healthchecks.io check "Filing" (period 30 min, grace 30 min, e-mail). URL into `UBYHOST_HEARTBEAT_FILING_URL`. Force it red once to see the e-mail arrive. |
| 0017 WP22 | When you accept the retention text: `UBYHOST_RETENTION_AUTOPURGE=1`, deploy. |
| 0019 WP24 | Set `UBYHOST_LEGAL_EFFECTIVE_DATE` to the release day in `.env`, deploy (no lawyer wait required). |
| 0020 WP26 | Ask a native speaker to read the German, Spanish and French guest pages, legal notice first. Until then they stay off. |
| 0021 WP33 | Put `UBYHOST_GUEST_LANGS=en,cs` in `.env`. After a native speaker has read a language, add it (for example `en,cs,de`) and restart. Check on staging that a past stay still waiting for filing shows on the Stays page. |

Production `.env` facts (never in the repo): `UBYHOST_OPERATOR_NAME`, `_ICO`, `_DIC`, `_ADDRESS`, `_EMAIL` exactly as registered. Confirm in Lightsail that the region is Frankfurt (eu-central-1).

First real host day:

1. One end-to-end filing on staging against the UbyPort test endpoint: a Friday arrival before a public holiday and one EU guest (EU guests must be filed).
2. Every healthchecks.io check green.
3. `UBYHOST_RETENTION_AUTOPURGE=1`.
4. Send each new host `compliance/05_manual_filing_fallback.md`.
5. Gate 4 in `00_README_for_cursor.md` is met.

## E. Later PRs (0022 to 0034)

| PR | You do |
|---|---|
| 0023 WP13 | Weekly perf report: the command is in the notes. |
| 0028 WP12 | Keep `UBYHOST_LIFECYCLE_MAIL=0` until self sign-up is live. |
| 0029 WP16 | Four stages in the notes: backup, deploy, add the new data key (password manager), run the re-encryption tool, later switch off the legacy key. |
| 0032 WP20 | Only when ads run: Google Ads "Import > Conversions from clicks" action, auto-tagging on, customer data terms accepted. Test on staging with `?gclid=TEST123`. |
| 0033 WP21 | Only when Meta ads run: Events Manager dataset, Conversions API token, domain verified, test with `test_event_code` on staging. `utm_source=facebook` on group posts. |

## F. Decisions I made for you

Change any of these by telling Cursor in plain words.

| Topic | Default | Where |
|---|---|---|
| Alerts | E-mail only (healthchecks.io and the app). No SMS. | WP07, WP23 |
| Liability cap | Fees paid in the 12 months before the claim, at least CZK 10,000; never limited for intent or gross negligence | WP24 |
| UbyPort credentials clause | "zmocňuje", used only for filing | WP24 |
| Availability | Best effort, notice of planned downtime where possible | WP24 |
| Legal versions | Terms, Privacy and DPA 1.6, one effective date, accepted once | WP09, WP24 |
| Filed guests | Reported fields and the signature are locked after filing; corrections go through UbyPort | WP25 |
| Guest languages | EN, CS, DE, ES, FR, picked from the browser language; no IP location | WP26 |
| Privacy claim | "We keep only what Czech law and your registration need, and use no tracking cookies." A test fails if any non-essential cookie appears. | WP27 |
| Account closure | Guest data deleted 30 days after closure; invoices kept 10 years | WP22 |
| Photos | Deleted when verified, else 7 days after check-in, 30 days at most | WP22 |
| Ads consent | Separate unticked boxes for Google and Meta, shown only with a click ID | WP20, WP21 |
| Payments | Not built. Testing phase. A Stripe Checkout and Billing integration (cards, Apple Pay and Google Pay through Stripe) is planned as a later WP when you set a price. | 03_when_triggered.md |
| Lawyer | Operator may ship WP22/WP24 without external review; optional paid hour still useful | 06_council_verdict.md |

## G. Getting the first hosts

- Facebook groups: ask each admin before a product post. Onboard the first 10 hosts personally.
- Meta ads: interest targeting for Czech hosts; `utm_source`, `utm_medium`, `utm_campaign` on every link.
- Google Ads: problem keywords such as "hlášení cizinců UbyPort" and "evidence ubytovaných Airbnb", not the brand name.
