# Go cutover: manual steps (Josef)

Written 2026-11-14. Split out of [go-cutover-runbook](go-cutover-runbook.md). Docs only: nothing here has been run. The `.env` edits and the Caddy reload that go with each wave are in [go-cutover-env-commands](go-cutover-env-commands.md) and can be handed to an independent AI; everything below stays with you. The ids (M-W1 and so on) are the ones that file names.

**Fully on Go today is not possible** (runbook section 6). Production holds real-looking data (about 117 guests, 28 submissions, 14 stay-fee filings, 6 accounts, 2026-11-13). **UNVERIFIED:** whether a staging server exists. If not, read "staging" as "production with a test account and your own addresses", one wave per day.

## 1. How the work alternates

For each wave: you release the block to the AI (env file), the AI reports the new line, you do the hand checks here, then you wait the stated time. If anything looks off, hand the AI the rollback line from its report.

## 2. Before wave 1 (runbook P1 to P14)

| # | You do | Check |
|---|---|---|
| M-P1 | Merge #1026 first (and decide #1025; it changes nothing live). Then GitHub, Actions, Deploy production, type DEPLOY. | `curl -s https://<domain>/healthz` answers; `docker compose ps` shows `ubyhost`, `ubyhost-go`, `worker`, `caddy`, `postgres` Up |
| M-P3 | Backup: `./scripts/backup.sh 2>&1 \| tail -3` | prints `PostgreSQL dump bytes: ...`; new folder in Drive `UbyHost-backups`; WAL-G 7-day recovery confirmed on the monitoring card |
| M-P4 | Restore drill, part B of `docs/OPERATIONS.md` "Proofs before the SQLite rollback path ends". Also do A (decrypt test on your own computer) and C (off-site copies). | `exit: 0 0`, `COUNTS MATCH`, `CLEAN`. Rollback: drop the scratch database |
| M-P8 | After env Block C: invite your own address from Admin. | mail arrives in seconds. Without SES for Go, login mails wait up to 5 minutes (link lives 15). Rollback: revert the PR, redeploy |
| M-P10 | After #1026 is deployed: `docker compose exec ubyhost-go sh -c 'touch /data/.w && rm /data/.w && echo writable'` | prints `writable` (needed for guide photos, demo delete, purge). Rollback: put `:ro` back on the volume line in the compose file and `docker compose --profile go up -d ubyhost-go` |
| M-P13 | Check that you can supply the AI variables (names in env Block F). | values exist in your records |

Decide #1025 and #1026: #1026 must be merged and deployed before wave 3 and before I1.

## 3. Infrastructure

| # | You do | Check | Rollback |
|---|---|---|---|
| M-I1 | After env Block D added `UBYHOST_SCHEMA_APPLY=go`, deploy once (quiet day, #1026 deployed first). | deploy log shows `==> Applying PostgreSQL goose migrations (new Go image)` and `Goose migrations applied.` | ask the AI to delete the line, deploy again |
| M-I2 | Choose the time (not 03:00 to 07:30 Prague; never the same day as a login wave); be at the terminal for brief 1451 (about 20 min). After env Block S, wait 15 min and run the queue query of brief 1451 step 10. Next morning after 07:15 check that the five daily kinds each appear once. | no red dashboard card | Block S rollback. One daily kind may run twice on the switch day. |

## 4. Hand checks per wave

Before any wave with host pages, ask the orchestrator for the 390/768/1280 screenshots. Brief 1412 (UX gate) is paused, so no Go host page has passed on a Go-served build yet; either ask for them or look yourself at phone width. After every wave also look at the dashboard for a red "Background job ... failed" card and at Grafana for 5xx on `ubyhost-go`.

| Id | Wave | You do | Wait |
|---|---|---|---|
| M-W1 | Public pages | Look at the screenshots in `ux-shots/public-pages` first. Then open `/jak-to-funguje`, `/cenik`, a `/pruvodce/...` page in Czech and English and compare. | same day |
| M-W1b | Unsubscribe | Send yourself one mail, click its unsubscribe link: form shows, submit shows done, a bad token shows invalid (screenshots in `ux-shots/public-unsubscribe`). Use your own address only: the submit writes a real mail opt-out. | same day |
| M-W2 | Exports | UX check for `/settings/archived`. Download one registration form PDF and compare with Python's; open the housebook zip; archived page lists the same rows. PDFs contain guest data. | one day |
| M-W2b | Privacy | Host with and without requests: same requests, same order. Signed out answers 303 to `/login`. Do not record a test request. | one day |
| M-W3 | Billing | Confirm the Go container can reach `ares.gov.cz`. Try one real bank statement on a **copy** of the data first. Check `/predplatne` in its four states and `/admin/fakturace`: same plan page and same invoices as Python. HIGH RISK: real invoices, statement import, storno. | one day |
| M-W4 | Customer admin | Test customer only: extend a trial by 1 day; change status and back; discount 10 then 0 (an unpaid invoice is cancelled and re-issued and the mail is queued). MRR/ARR on the home page show 1/100 of the real value in Go and Python alike (F2 of 1593): ask for a fix brief if wanted. HIGH RISK. | one day |
| M-W5 | Login and accounts | **Keep a second logged-in session in another browser and have the rollback line ready.** Have a second admin account. (a) private window: request a link, open the mail, press Log in, land signed in, Czech and English. (b) test account with an authenticator: wrong code once, right code once. (c) accept an invite and set up 2FA with a test account. (d) change a test account's address, confirm it. (e) invite a host: "Invitation link sent", mail arrives. (f) signup only if `UBYHOST_SIGNUP_ENABLED=1`. One part per day. HIGH RISK: a mistake locks you out. | one day each |
| M-W6 | Onboarding | Checklist unchanged; dismiss and resume return 303 to `/?msg=...`; audit log shows `onboarding.dismissed` and `.resumed`. | same day |
| M-W7 | Setup wizard | Walk a new, empty property through all steps (calendar, guest link, police, property, finish, try-it); hide and resume. The try-it demo and "Delete and continue" need `/demo`, which stays on Python. The wizard saves police and property data. | one day |
| M-W8 | Guide editor | Check the QR page and one card save. For photos (after writable `/data` and memory): add a photo at 390/768/1280 px, view it, delete it. Do not add the card paths `/discard /skip /delete`. | one day |
| M-W8b | Havel and Leon | Python must have run cleanly for a week first. Open `/havel`, send one test message; step through `/apartments/<id>/leon/setup`. Monthly AI caps apply. | one week of Python first |
| M-W9 | Invoices | Optional, safe to skip. After each path, a rollback test. Issue nothing real: use the preview, download one PDF. HIGH RISK: legally binding invoices. Detail page and `/send` stay Python. | one day |
| M-W10 | Stay fees | Before anything: seal one period on Go and download it from Python and the reverse; open one real hlášení PDF from each side; UX gate on `/stay-fees` and `/stay-fees/<id>`; decide `UBYHOST_STAY_FEE_GUEST_PAY` (lawyer view) before step 2. HIGHEST RISK: sealing is a filing write. Not near a filing deadline. Recommendation: skip step (4) `/stay-fees/*`. | one day per step |

## 5. Decisions only you can make

- #1025 and #1026: merge or not. The SQLite rollback ends 2026-12-15 (owner decision 2026-11-15, [go-sqlite-final](go-sqlite-final.md) §6), only if the P4 proofs are recorded by 2026-12-01. Do not end it earlier.
- `UBYHOST_STAY_FEE_GUEST_PAY` (with the lawyer). Retention apply: `UBYHOST_GO_RETENTION_APPLY=1` and `UBYHOST_RETENTION_AUTOPURGE=1` only after three nights of matching dry-run counts (personal-data deletion, lawyer relevant).
- Waiting items (runbook section 5): `/settings/purge-expired` (three matching retention mornings and writable `/data`); jobs `retention` and `stay_fee_mail`; `/webhooks/stripe` (check the Go webhook yourself; Stripe is in test mode); `/demo` and `/demo/reset` stay on Python together.
- Whether to run wave 9 at all, and wave 10 step (4).
- Open owner items: security audit K-S11 to K-S15; 0990 to 0992 (deploy, `pg_schema.py apply`, Cloudflare, Grafana); Hetzner DR copy (#946, #948, #953, #957); lawyer items K-L, K-F18, K-S10 (K-F03 and K-F07: AI-reviewed 11-15, see go-sqlite-final §7). **UNVERIFIED:** the 11-13 server chat is not in the repository; paste it to the orchestrator if you want it folded in.

## 6. Monitoring after every wave

1. `docker compose logs --since 15m ubyhost-go 2>&1 | grep -i -E 'error|panic' | tail` and the dashboard for a red job card.
2. Grafana: 5xx on `ubyhost-go`.
3. Paste the AI's reported `UBYHOST_GO_PATHS` value (paths only) into the orchestrator chat so the repo can record it.
4. Anything off: stop, give the AI the wave's rollback line.

## 7. Suggested order

1. Merge #1026, deploy, P1 to P4, env Blocks A, B, C, F, E.
2. I1 (env Block D, then your deploy).
3. W1, W1b, W2, W2b the same day or one per day.
4. W3 and W4 the next day, test customers only.
5. W5 on its own day with a second session open; I2 on a different evening.
6. W6 to W8; W9 and W10 optional, W10 step (4) later.
