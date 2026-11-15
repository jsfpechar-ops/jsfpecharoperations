# Go cutover runbook (owner)

Written 2026-11-14 from the briefs and plans on `main` (`bdfaa4d`) and the open PRs #1025 and #1026. Docs only: nothing here has been run, and production was not touched. Where a statement could not be checked from the repository, it says **UNVERIFIED**.

## 0. Read this first

**"Fully on Go today" is not possible.** The pages and jobs below stay on Python after every step of this runbook (section 6). Python also stays the owner of the SQLite rollback copy until decision 3 of [sqlite-retirement](sqlite-retirement.md) is dated. What you can do today is move every area that has a finished Go port, in the order below. Plan for 2 to 3 hours of work plus one-day waits between the risky waves; a one-day wait is the rule of [stay-fee-go-rollout](stay-fee-go-rollout.md) and of the invoice brief 1427.

**Production holds real-looking data** (2026-11-13 check: about 117 guests, 28 submissions, 14 stay-fee filings, 6 accounts). Every step marked **RISK** can write real rows, send real mail, issue a real invoice or seal a real filing.

**Staging:** the briefs say "staging first", but brief 1412 was paused on 2026-11-13 because there was no Lightsail staging server, while status.md lists staging as done. **UNVERIFIED:** whether a staging server exists today. If it does not, replace each "on staging" line with "on production with a test account and your own addresses", and do the waves one per day.

**The one rule for every wave:** change `UBYHOST_GO_PATHS`, validate, reload Caddy, check, wait. The commands never change:

```bash
cd /opt/ubyhost/deploy/lightsail
grep -n '^UBYHOST_GO_PATHS' .env          # copy this whole line into a note first: it is your rollback
nano .env                                 # keep the double quotes, add the new paths, space separated
./scripts/caddy-validate.sh               # must end without an error, else do not continue
docker compose up -d caddy
```

Rollback of any wave: put the noted line back with `nano .env`, run `./scripts/caddy-validate.sh`, then `docker compose up -d caddy`. Never leave the value empty (Caddy will not start); to switch everything off set `"/__go_off__"`.

How to see which side served a page: `curl -sI https://<your domain><path>`. A Go page that is not ported yet answers 501 with `X-Ubyhost-Not-Ported: 1` and Caddy re-asks Python for GET and HEAD (brief 1630). POST is not re-asked, so a POST to a Go-listed path that Go lacks fails. That is why the paths below are exact and why wildcards are chosen with care.

## 1. Pre-flight (do all of it before wave 1)

| # | Step | Check | Rollback |
|---|---|---|---|
| P1 | Deploy `main` the normal way (GitHub, Actions, Deploy production, type DEPLOY). #1010 and #1021 are merged and were built switched off. | `curl -s https://<domain>/healthz` answers; `docker compose ps` shows `ubyhost`, `ubyhost-go`, `worker`, `caddy`, `postgres` Up | previous release |
| P2 | **URGENT, remove `/apartments` and `/entities` from `UBYHOST_GO_PATHS` if they are there** (only these exact words; `/entities/...` form paths are separate). Go serves only GET on them; POST (add property, add entity) would break. Brief 1630 now falls back for GET, not for forms. | `grep -n '^UBYHOST_GO_PATHS' .env` shows neither word. Then `./scripts/caddy-validate.sh` and `docker compose up -d caddy` | n/a |
| P3 | Backup now: `./scripts/backup.sh 2>&1 \| tail -3` prints `PostgreSQL dump bytes: ...`. WAL-G gives 7-day point-in-time recovery; confirm with the Grafana/monitoring card you already have. | the line above; a new folder in Drive `UbyHost-backups` | none needed |
| P4 | Restore drill, B part of `docs/OPERATIONS.md` "Proofs before the SQLite rollback path ends" (needs the PR of brief 1473 deployed, which it is). Do A (decrypt test on your own computer) and C (off-site copies) as well. All three are "not yet" in the table today. | `exit: 0 0` then `COUNTS MATCH`, then `CLEAN` | drop the scratch database as in step 11 |
| P5 | Record the current switches: `grep -E '^(UBYHOST_GO_PATHS\|UBYHOST_GO_JOB_KINDS\|UBYHOST_JOB_QUEUE_KINDS\|UBYHOST_SCHEDULER\|UBYHOST_SCHEMA_APPLY\|COMPOSE_PROFILES\|UBYHOST_GO_MEM)=' .env` and copy the output (no secrets in it). **UNVERIFIED:** the repo does not record the live `UBYHOST_GO_PATHS`; status.md only says "Go routes live (11-12)" and "W1-W3 on Go" on 11-13. Anything below already in your line is simply skipped. | n/a | n/a |
| P6 | `COMPOSE_PROFILES` contains `go` (status says `walg,monitoring,go`). | `docker compose ps \| grep -i go` shows `ubyhost-go` Up | n/a |
| P7 | **Seller variables for invoicing in Go** (brief 1594). Needed before any wave that can issue an invoice (waves 4 and 5). `grep -c '^UBYHOST_BILLING_IBAN=\|^UBYHOST_OPERATOR_NAME=\|^UBYHOST_OPERATOR_ICO=' .env` must print `3`. The compose file passes these to `ubyhost-go`: `UBYHOST_BILLING_ENABLED`, `_BILLING_IBAN`, `_BILLING_BANK_ACCOUNT`, `_BILLING_VAT_STATUS`, `_OPERATOR_NAME`, `_ICO`, `_DIC`, `_ADDRESS`, `_EMAIL` (names only, never paste values). Then `docker compose --profile go up -d ubyhost-go`. Less than 3: stop; Python cannot issue invoices either. | prints `3` | n/a |
| P8 | **SES for Go** (brief 1632, in draft PR #1026, not yet merged). `UBYHOST_MAIL_FROM`, `UBYHOST_SES_REGION`, `UBYHOST_AWS_ACCESS_KEY_ID`, `UBYHOST_AWS_SECRET_ACCESS_KEY` must exist in `.env`; run the count check from `docs/SES.md` "Go service" (prints 4, no "incomplete" log line). Without this, login, e-mail change and invite mails wait for Python's mail job (up to 5 minutes; the login link lives 15). **Merge #1026 and deploy before wave 3.** | count 4; an admin invite to your own address arrives in seconds | remove the four lines |
| P9 | **`UBYHOST_GO_MEM=768m`** in `.env` (default 128m; image decoding for guide photos needs room; brief 1447/#1026). | `docker compose --profile go up -d ubyhost-go`, then `docker inspect $(docker compose ps -q ubyhost-go) --format '{{.HostConfig.Memory}}'` prints `805306368` | delete the line, `up -d ubyhost-go` |
| P10 | **Writable data volume** for Go (brief 1640, in #1026): the Go container mounts `/data` read-only today. After #1026 is deployed: `docker compose exec ubyhost-go sh -c 'touch /data/.w && rm /data/.w && echo writable'` prints `writable`. Needed for guide photo upload, `/settings/purge-expired`, demo delete. | `writable` | revert the compose change |
| P11 | Turnstile and proxy variables visible to Go (brief 1502): `docker compose --profile go exec ubyhost-go sh -c 'for k in TURNSTILE_SITE_KEY TURNSTILE_SECRET TURNSTILE_HOSTNAMES UBYHOST_TRUSTED_PROXY_CIDRS; do [ -n "$(printenv $k)" ] && echo "$k set" \|\| echo "$k MISSING"; done'` all four `set`. A missing `UBYHOST_TRUSTED_PROXY_CIDRS` makes every visitor share one rate-limit bucket. | four `set` | n/a |
| P12 | Retention variables (brief 1609): `grep RETENTION .env` shows none of `UBYHOST_AUDIT_RETENTION_DAYS`, `UBYHOST_ALERT_RETENTION_DAYS`, `UBYHOST_RATE_LIMIT_RETENTION_HOURS`, `UBYHOST_RETENTION_NOTICE_DAYS`, or each is also passed to `ubyhost-go` first (separate brief). | empty output | n/a |
| P13 | AI variables for Havel and Leon in Go (brief 1437/1434): `UBYHOST_AI_FEATURES` contains `havel` and `leon`, model key, `UBYHOST_AI_MONTHLY_USD_HAVEL`, `_LEON`, `UBYHOST_APIFY_TOKEN`, `UBYHOST_SECRET_KEY`, `UBYHOST_MAIL_BACKEND`. Names only. | set | n/a |
| P14 | **Decide #1025 and #1026.** #1026 must be merged for P8 to P10. #1025 changes nothing live (three Go ports for the demo, no route). | PRs merged, deploy done | revert PR |

## 2. Infrastructure switches (before the page waves)

| # | Step | Detail | Verify | Rollback | Risk |
|---|---|---|---|---|---|
| I1 | **Schema apply by Go** (brief 1261, plan S8) | `docker compose --profile go build ubyhost-go && docker compose --profile go run --rm --no-deps -T ubyhost-go migrate check --expect-database ubyhost` must print `PostgreSQL schema check OK`. If `failed`, stop and send that line to the orchestrator. Then add `UBYHOST_SCHEMA_APPLY=go` to `.env` and deploy once. | deploy log shows `==> Applying PostgreSQL goose migrations (new Go image)` and `Goose migrations applied.` | delete the line, deploy again; both write the same `goose_db_version` rows | Medium, quiet day. Brief 1640 (in #1026) assumes Go-only columns can exist; the Python boot check refuses a goose-only column unless 1640 is deployed. Deploy #1026 first. |
| I2 | **Scheduler switch** (brief 1451, plan J7) | Only after 1450, 1451, 1452 are deployed. Not between 03:00 and 07:30 Prague time. Follow the 12 steps of brief 1451 exactly; the key ones: `UBYHOST_JOB_QUEUE_KINDS` holds all 15 names (`ical submit deadlines mail photo_sweep meta_capi retention stay_fee_mail stripe_sweep billing billing_snapshot door_codes posthog push guide_import`), no `UBYHOST_SCHEDULER` line yet; add `UBYHOST_SCHEDULER=go`; `docker compose up -d --no-deps ubyhost-go`; wait 90 s, check the log; `docker compose up -d --no-deps worker`; wait 15 min and run the queue query of step 10. Always `--no-deps`, or the web container restarts too. | log lines `scheduler started owner=go kinds=15`, `Go scheduler is not enqueuing` count `0`, no red dashboard card; next morning after 07:15 the five daily kinds appear once each | delete `UBYHOST_SCHEDULER=go`, `up -d --no-deps worker` first, then `ubyhost-go` | **RISK:** it controls filing deadline and submit timing. One daily kind may run twice on the switch day. |
| I3 | Job kinds already on Go | `billing_snapshot stripe_sweep ical push submit posthog meta_capi deadlines` (status.md). `mail` and `door_codes` stay Python. `retention` and `stay_fee_mail` are the open ones (section 5). | `grep UBYHOST_GO_JOB_KINDS .env` matches status | remove a kind from `UBYHOST_GO_JOB_KINDS` | n/a |

## 3. Page waves: exact `UBYHOST_GO_PATHS` additions

Add each block to the existing value, never replace it. One wave per sitting; wait the stated time. After every wave: log in as yourself, open the pages in the wave, and look at `docker compose logs --since 10m ubyhost-go 2>&1 | grep -i -E 'error|panic' | tail`.

**UX check (required, once per wave that has host pages).** Rule 10 says the orchestrator does this, not you: it needs `test_layout_lint_browser.py` green and the 390, 768 and 1280 px screenshots of every moved host page, with a line per page in a PR. As the owner you only need to know it is outstanding: brief 1412 (UX gate for the Go host pages) is paused, so **no Go host page has passed the gate on a Go-served build yet**. Existing public-page screenshots are in the project files under `ux-shots/public-pages` and `ux-shots/public-unsubscribe` (390/768/1280); they cover wave 1 only. Ask the orchestrator for the other screenshots before each wave, or accept the risk consciously and look at the page yourself at phone width.

| Wave | Add to `UBYHOST_GO_PATHS` | Needs first | Verify | Wait | Risk |
|---|---|---|---|---|---|
| 1 Public pages | `/jak-to-funguje /cenik /pruvodce/*` (1622) | owner has looked at the screenshots (`ux-shots/public-pages`) | pages load in Czech and English; compare with the screenshots | same day | Low, read only |
| 1b Unsubscribe | `/mail/unsubscribe/*` (1624) | links in the mail job checked once (send yourself one mail, click its unsubscribe link). Screenshots: `ux-shots/public-unsubscribe` (form, done, invalid). | form shows, submit shows done, a bad token shows invalid | same day | **RISK low:** the submit writes a mail opt-out for a real address. Use your own address. |
| 2 Exports | `/guests/*/form.pdf /housebook/pdfs.zip /settings/workspace-export /settings/archived` (1605 to 1609) | UX check for `/settings/archived` | download one registration form PDF and compare with Python's; open the housebook zip; archived page lists the same rows. **Do not add `/settings/purge-expired`** (section 5). | one day | Medium: PDFs contain guest data; read only |
| 2b Privacy | `/privacy-requests /privacy-requests/*` (1615), always both together | UX check (host with and without requests) | same requests, same order; signed out answers 303 to `/login` | one day | **RISK:** write nothing; do not record a test request there. |
| 3 Billing | `/predplatne /predplatne/* /admin/fakturace /admin/fakturace/*` (1556 to 1560) | P7, container may reach `ares.gov.cz` (Python's does), UX check of `/predplatne` in its four states and `/admin/fakturace`, one real bank statement tried on a copy of the data | the plan page matches Python; admin page lists the same invoices | one day | **RISK HIGH:** real invoices, bank statement import (mark paid), storno. Do the statement import only after comparing a copy. Python still shows "13 / 13 missing" in the older remaining list; it is outdated, 1555 to 1560 landed. |
| 4 Customer admin | `/admin /admin/customers /admin/customers/*` (1594). `/admin` has no star on purpose. Then separately `/admin/operations` (1508). | P7, UX check of `/admin` and one customer | on a test customer: extend a trial by 1 day; change status and back; set a discount 10 then 0 (an unpaid invoice is cancelled and re-issued and the invoice mail is queued). MRR and ARR on the home page show 1/100 of the real value in Go and Python alike (F2 of 1593); ask for a fix brief if you want it. | one day | **RISK HIGH:** discount and plan changes issue real invoices. Use a test customer only. |
| 5 Login and accounts | In this order, one deploy each, check, then the next: (a) `/login /login/link` (1502), then (b) `/login/2fa` (1503), then (c) `/account/accept /account/2fa/setup` (1505), (d) `/account/email /account/email/confirm` (1506), (e) `/admin/users/*/invite /admin/users/*/email /admin/users/*/schedule-deletion /admin/users/*/export` (1504, 1509, 1510), (f) `/signup /signup/verify` only if `UBYHOST_SIGNUP_ENABLED=1` (1507), and last (g) the six passkey paths `/login/passkey /login/passkey/options /account/passkeys /account/passkeys/options /account/passkeys/*/rename /account/passkeys/*/delete` (1760, built and dormant, never earlier than (a) and (b)) | P8, P11, P14 (#1026 merged), UX check of `/login`. Never add the bare `/admin/users` (Python's `POST /admin/users` creates users and Go may not serve it, see the collision table in go-full-move-remaining). Passkey paths stay on Python until step (g) (section 6); step (g) is one deploy with all six paths, then rollback is trimming those six words. | (a) private window: request a link, open it from the mail, press Log in, land signed in, Czech and English both. (b) a test account with an authenticator: wrong code once, right code once. (d) change a test account's address, confirm it. (e) invite a host: "Invitation link sent" and the mail arrives. (g) in a fresh login add a passkey in Settings, log out, log in with it, remove it; try the same on a second browser; the audit page shows `passkey_added`, `login` method `passkey:<id>`, `passkey_removed`. | one day | **RISK HIGH:** a mistake locks you out. Keep a second session open in another browser, and have the rollback line ready. Do (a) with a second admin account existing. |
| 6 Onboarding | `/onboarding` (1595); then `/onboarding/dismiss /onboarding/resume /welcome-back/dismiss /celebrations/dismiss` (1598). Do not add `/onboarding/*`. | UX check of `/onboarding` | checklist unchanged; dismiss and resume return 303 to `/?msg=...`; audit log has `onboarding.dismissed` and `.resumed` | same day | Low |
| 7 Setup wizard | `/apartments/*/setup /apartments/*/setup/*` (1602, 1604) | #1026 deployed (1603 demo delete) and P10; UX check of six wizard pages (calendar, guest link, police, property, finish, try-it) | on a new property walk every step, hide and resume. The try-it demo and "Delete and continue" need `/demo` which stays Python (1597). | one day | **RISK:** the wizard saves police and property data. Walk a new, empty property only. |
| 8 Guide editor | `/apartments/*/guide /apartments/*/guide/cards /apartments/*/guide/import /apartments/*/guide/qr /apartments/*/guide/qr.png /apartments/*/guide/qr/rotate /apartments/*/guide/quick /apartments/*/guide/quick/* /apartments/*/leon /apartments/*/guide/*/photos/* /apartments/*/guide/*/photos/*/delete` (1446). Also `/apartments/*/guide/*/photos` (without the trailing star) only after #1026 and P9, P10 (1447). Do **not** add `/apartments/*/guide/*` (it catches `/guide/questions`, still Python) or the card paths `/discard /skip /delete` until the 1446 notes say so. | UX check of guide overview, a card, QR page, Quick answers, done page, Leon page. Photo upload: P9 and P10, then add a photo at 390/768/1280 px, view it, delete it. | QR page and one card save | one day | **RISK:** photo upload writes files into `/data` (writable volume). |
| 8b Havel and Leon | `/havel /havel/* /apartments/*/leon/setup /apartments/*/leon/setup/*` (1437). Havel and Leon on Python must first have run cleanly for a week. | P13 | open `/havel`, send one test message; step through `/apartments/<id>/leon/setup` | one week of Python first | AI cost: monthly caps apply (`UBYHOST_AI_MONTHLY_USD_*`) |
| 9 Invoices | One by one, in this order, each followed by the rollback test: `/invoice/d/*`, `/invoices/*.pdf`, `/invoices/*/paid`, `/invoices/*/cancel`, `/invoices/preview`, then `/invoices/new`, then `/invoices` (moves the list and the issue POST together) (1420 to 1427). **Never `/invoices/*`.** The detail page `/invoices/<id>` and `/invoices/*/send` stay on Python (1429 blocked: no Go mail builder for `invoice_issued`). | P7, UX check of list, picker, form (one and two operators, payer and non-payer, the 422 state) | issue nothing real: use the preview; download one PDF | one day | **RISK HIGH:** issues legally binding invoices. Optional today; safe to skip. |
| 10 Stay fees | Per [stay-fee-go-rollout](stay-fee-go-rollout.md): (1) `/stay-fees/pdfs.zip /stay-fees/*/pdf /stay-fees/*/csv`, wait a day; (2) `/stay-fees/*/guest-pay-preview` (only after `UBYHOST_STAY_FEE_GUEST_PAY` is decided); (3) `/stay-fees`; (4) `/stay-fees/*` last, because it also moves the seal routes `finalize` and `confirm-ready`. Steps 1 to 3 of its checks (seal one period on Go and download from Python and the reverse; open one real hlášení PDF from each side) come first. | all four checks of the rollout plan; UX gate on `/stay-fees` and `/stay-fees/<id>` | as in the plan | one day per step | **RISK HIGHEST:** sealing is a filing write. Do step (4) not on a day when a filing deadline is near. **Recommendation: skip step (4) today**; steps 1 to 3 are enough. |

## 4. After each wave

1. Check `docker compose logs --since 15m ubyhost-go | grep -i -E 'error|panic' | tail` and the dashboard for a red "Background job ... failed" card.
2. Open Grafana/monitoring and check 5xx on `ubyhost-go`.
3. Write the new `UBYHOST_GO_PATHS` value (paths only, no secrets) into the orchestrator chat so the repo can record it. The repo has no record of the live value (**UNVERIFIED** today).

## 5. Things that must wait even though a port exists

| Item | Condition |
|---|---|
| `/settings/purge-expired` (1609) | P10 writable `/data` and three mornings where the retention dry-run counts of Go and Python match. A real purge deletes data permanently. |
| `retention` and `stay_fee_mail` job kinds | `retention`: dry-run counts matched three mornings (status.md 11-13 notes a retention dry-run, outcome UNVERIFIED), then add to `UBYHOST_GO_JOB_KINDS` (it is in the queue list already). `stay_fee_mail`: add to `UBYHOST_JOB_QUEUE_KINDS` and `UBYHOST_GO_JOB_KINDS` together, only after wave 10 steps 1 to 3 and one dry week of sealed periods matching Python. |
| `/webhooks/stripe` | Add only after you have checked the Go webhook; booking-site events are forwarded to Python by `UBYHOST_PY_WEBHOOK_URL`. Stripe is in test mode (status.md). |
| `/demo` and `/demo/reset` | Brief 1597 (demo seed) is blocked; 1596 says both move together. Keep both on Python. |
| `/stay-fees/*` seal routes | See wave 10. |

## 6. What stays on Python after all of this (so "fully" is not possible)

Source: [go-full-move-remaining](go-full-move-remaining.md) (dated 11-13, before wave 3; waves 3 areas above are now done, the rest still stands).

- **Guest registration and guest pages** (`/l/*`, `/g/*`, 19 + 4 + 5 routes in `guest.py`, `guest_leon.py`, `guest_questions.py`, and the guest guide view 1629). Not started. The Go port waits for the filing port (F2).
- **Guest editing by the host** (`/guests/<id>*`, 11 routes) and **stays and filing** (`/reservations*`, 20 routes, `POST /reservations/<id>/submit`, `submit-ready`). F1 and F2 filing is HIGH RISK and "last" by your rule (K-F03 and K-F07 got an AI review on 11-15 and are not lawyer items: see [go-sqlite-final](go-sqlite-final.md) §7).
- **Passkeys** are no longer in this list once wave 5 step (g) is done: they move to Go with the six paths of step (g) (PR 1037, go-webauthn v0.18.0, owner decision 2026-11-15, brief 1760). Until step (g) is kept they stay on Python. Executor prompt: [go-cutover-final-prompt](go-cutover-final-prompt.md).
- **Properties and entities forms:** `/apartments/<id>`, `/apartments/new`, `POST /apartments`, `POST /entities`, `/settings*`, `/menu`, `/housebook` page, smart locks (1526, no Go TTLock client), the property page (1525 to 1527). Brief 1525 is replaced by 1704; 1526 by 1707; 1527 stays blocked.
- **Booking and payments guest side:** `/p/<slug>*` and booking pages (1550 blocked; 1546 and 1553 replaced by 1710 and 1712), guest `/pay/*` (1545 replaced by 1713), booking-site host pages.
- **Cleaning pages:** 11 of 16 routes (the 11 missing; some may have landed in #1021, UNVERIFIED).
- **Demo seed** (`POST /demo`, 1597), **invoice detail and send** (1429), **dashboard `/`**, `main.py` utility routes (`/robots.txt`, `/sitemap.xml`, `/sw.js`, `/manifest.webmanifest`, `/offline`, `POST /language`, `/favicon.ico`), `/dev/ui`.
- **Jobs:** `mail` and `door_codes` run in the Python worker; `retention` and `stay_fee_mail` until section 5.
- **Containers that must keep running:** `ubyhost` (Python web), `worker`, `ubyhost-go`, `caddy`, `postgres`. Python code cannot be deleted; lane X is far off.

## 7. Database: Postgres and the SQLite rollback

- **Postgres is already live** (status.md: "Postgres live ... SQLite rollback via pg-cutover only"). There is no further Postgres cutover to do. The open question is when to end the SQLite rollback path (decision 3 of [sqlite-retirement](sqlite-retirement.md), "confirm the cutover date (not found in the docs)").
- **Owner decision 2026-11-15:** the rollback path ends **2026-12-15** if the four proofs of P4 are recorded by 2026-12-01 (otherwise the date moves later by one day per day of delay); see [go-sqlite-final](go-sqlite-final.md) §6. Do not end it before that date. It is blocked by the four proofs in P4 (A, B, C, and the offline copy) and then by S11/S12 which need a 30-day window. A date has to come from you; a reasonable one is 30 days after P4 is recorded.
- **Rollback while it still exists:** `pg-cutover.sh rollback` switches `.env` back to SQLite. It loses every write made on Postgres since the cutover. It is a disaster path, not a wave rollback; wave rollbacks are the `UBYHOST_GO_PATHS` lines.
- **Schema authority:** after I1, Go applies goose files. Do not add SQLite migrations to `App/app/migrations/` (frozen at 0045).

## 8. Server follow-ups from 11-13

The repository records only: retention dry-run on the server; DR items #946/#948/#953/#957 (Hetzner copy pending); security audit 0990 to 0992 (deploy, `pg_schema.py apply`, Cloudflare, Grafana); K-S11 to K-S15. The text of the 11-13 server chat itself is not in the repository, so **UNVERIFIED:** whether anything else was promised. Paste it to the orchestrator if you want it folded in here.

## 9. One-page order for today

1. P1 to P14 (about 1 hour). Merge #1026 first.
2. I1 schema apply by Go (deploy once).
3. Waves 1, 1b, 2, 2b the same day.
4. Wave 3 billing and wave 4 customer admin next day, with test customers only.
5. Wave 5 login and accounts on its own day, with a second admin session open.
6. Waves 6 to 8 after that; I2 scheduler on an evening before 03:00 or after 07:30, never together with a login wave.
7. Waves 9 and 10 are optional and can wait; wave 10 step (4) should.
8. Stop after each wave if anything in section 4 looks off, and use the wave's rollback line.
