# Go cutover: `.env` commands for an independent AI

Written 2026-11-14. Split out of [go-cutover-runbook](go-cutover-runbook.md). Docs only: nothing here has been run. The other half (everything a person must do by hand) is [go-cutover-manual-steps](go-cutover-manual-steps.md).

Use: Josef gives the owner **one block at a time** (the prompt in section 1 plus one wave from section 3) to an AI that has a shell on the server. Josef decides when each block is released; the AI never moves on to the next block by itself.

## 1. Prompt to paste (copy everything in the box)

```text
You are editing the server file /opt/ubyhost/deploy/lightsail/.env for UbyHost and running the
docker compose commands tied to that edit. You do nothing else.

SCOPE
- You may: read and edit .env with nano (or sed -i on one exact line), run ./scripts/caddy-validate.sh,
  run docker compose up -d for the named service, run the read-only checks listed in the block,
  and run curl -sI against the owner's own domain.
- You may NOT: print, paste, log or send any secret value from .env (keys, tokens, passwords, IBAN,
  ICO/DIC, e-mail of the operator). Check presence with grep -c or "set"/"MISSING" only.
  Do not run deploy.sh, backup scripts, restore scripts, pg-cutover.sh, git, or anything that
  writes to the database. Do not sign in to the app, send mail, issue invoices or click anything.
  Do not touch production data. Do not add a path that is not written in the block you were given.

GUARDRAILS (every block)
1. Work in /opt/ubyhost/deploy/lightsail. Do ONE block (one wave) per session, then stop and report.
2. First: cp -p .env ".env.bak-$(date +%Y%m%d-%H%M%S)" and confirm the backup file exists.
   The backup contains secrets: never cat it, never move it out of that folder, keep mode 600.
3. Before editing, save the current value of the variable you will change:
   grep -n '^UBYHOST_GO_PATHS' .env   (copy the whole line into your report; it is the rollback).
4. UBYHOST_GO_PATHS must stay inside double quotes, paths space-separated, existing entries kept,
   and NEVER empty. To switch everything off, use exactly "/__go_off__".
   If the line is missing, do not invent it: stop and report.
5. Only ADD the paths in the block. Never replace the value. Never use a wider wildcard than written
   (never /invoices/*, never /admin/users, never /apartments/*/guide/*, never a bare /* ).
6. After the edit run ./scripts/caddy-validate.sh. It must finish without an error. If it fails,
   restore the previous line (rollback below) and stop. Only then run: docker compose up -d caddy
7. Run the block's verify commands. Compare to the expected result.
8. On ANY failure, unexpected output, or doubt: run the block's rollback, run
   ./scripts/caddy-validate.sh and docker compose up -d caddy, then STOP and report. Do not retry,
   do not try a different fix.
9. Edit with nano or one targeted sed on the exact line; afterwards run
   grep -c '^UBYHOST_GO_PATHS=' .env  and expect 1 (no duplicate line).
10. Report: block id, the old line (paths only), the new line (paths only), each command with its
    result (OK / FAILED + output with secrets removed), and the rollback line.
```

## 2. Placeholders and where real values come from

Never write real values into this repository, the prompt, or the report.

| Placeholder | Meaning | Where the real value comes from |
|---|---|---|
| `<DOMAIN>` | public domain of the app | Josef tells the AI in the prompt (not a secret) |
| `<OLD_LINE>` | the saved `UBYHOST_GO_PATHS=...` line | `grep -n '^UBYHOST_GO_PATHS' .env` before the edit |
| `<IBAN>`, `<BANK_ACCOUNT>`, `<VAT_STATUS>`, `<OPERATOR_NAME>`, `<ICO>`, `<DIC>`, `<ADDRESS>`, `<EMAIL>` | seller data for invoices (block E) | Josef types them into nano himself, or gives them in the session; they come from his company records and bank |
| `<SES_FROM>`, `<SES_REGION>`, `<AWS_KEY_ID>`, `<AWS_SECRET>` | Amazon SES mail (block C) | AWS console: SES verified sender, region, and the IAM user's access key. Josef enters the secret himself |
| `<TURNSTILE_*>`, `<CIDRS>` | Cloudflare Turnstile and proxy ranges (block L check only) | Cloudflare dashboard. Block L only checks them, never sets them |

## 3. Blocks, in order

Run them in this order. After each block the AI stops; the waits and the hand checks are in [go-cutover-manual-steps](go-cutover-manual-steps.md) (the section number is named in each block). Blocks marked **needs Josef's go** must not start until Josef says so in the same message that releases the block.

### Block A. Read-only record and urgent fix (runbook P2, P5, P6)

```bash
cd /opt/ubyhost/deploy/lightsail
cp -p .env ".env.bak-$(date +%Y%m%d-%H%M%S)" && ls -l .env.bak-*
# P5: record the switches (no secrets in these lines). Report the output.
grep -E '^(UBYHOST_GO_PATHS|UBYHOST_GO_JOB_KINDS|UBYHOST_JOB_QUEUE_KINDS|UBYHOST_SCHEDULER|UBYHOST_SCHEMA_APPLY|COMPOSE_PROFILES|UBYHOST_GO_MEM)=' .env
# P2: do the exact words /apartments or /entities appear as separate entries?
grep -n '^UBYHOST_GO_PATHS' .env | tr ' "' '\n\n' | grep -x -E '/apartments|/entities' || echo "none found"
```

If P2 prints `/apartments` or `/entities`: run `nano .env`, delete only those exact words (not `/entities/...` or `/apartments/*/...`), then:

```bash
grep -c '^UBYHOST_GO_PATHS=' .env                # 1
./scripts/caddy-validate.sh
docker compose up -d caddy
grep -n '^UBYHOST_GO_PATHS' .env | tr ' "' '\n\n' | grep -x -E '/apartments|/entities' || echo "gone"
```

P6: `grep '^COMPOSE_PROFILES' .env` must contain `go`; `docker compose ps | grep -i go` shows `ubyhost-go` Up. Verify: as written. Rollback: restore the saved line.

### Block B. `UBYHOST_GO_MEM` (P9)

Edit: add or set the single line `UBYHOST_GO_MEM=768m`.

```bash
grep -c '^UBYHOST_GO_MEM=' .env                  # 1 after the edit
docker compose --profile go up -d ubyhost-go
docker inspect $(docker compose ps -q ubyhost-go) --format '{{.HostConfig.Memory}}'   # 805306368
```

Rollback: delete the line, `docker compose --profile go up -d ubyhost-go`.

### Block C. SES for Go (P8) **needs Josef's go, and PR #1026 deployed**

Variables: `UBYHOST_MAIL_FROM`, `UBYHOST_SES_REGION`, `UBYHOST_AWS_ACCESS_KEY_ID`, `UBYHOST_AWS_SECRET_ACCESS_KEY`. Values are placeholders `<SES_FROM>`, `<SES_REGION>`, `<AWS_KEY_ID>`, `<AWS_SECRET>`. Most are probably already present for Python: check first, add only what is missing, and do not retype a present value.

```bash
for k in UBYHOST_MAIL_FROM UBYHOST_SES_REGION UBYHOST_AWS_ACCESS_KEY_ID UBYHOST_AWS_SECRET_ACCESS_KEY; do
  grep -q "^$k=.\+" .env && echo "$k set" || echo "$k MISSING"; done
```

If something is missing, stop and ask Josef for the value (he types it into nano himself; the AI never sees or echoes it). Verify: `grep -cE '^UBYHOST_(MAIL_FROM|SES_REGION|AWS_ACCESS_KEY_ID|AWS_SECRET_ACCESS_KEY)=.+' .env` prints `4` (`3` is fine only if Josef confirms the region is Frankfurt). Then `docker compose up -d --no-deps ubyhost-go`, then run the "Go service" count check from `docs/SES.md` (expected as written there) and `docker compose logs --since 5m ubyhost-go 2>&1 | grep -ci incomplete` must print `0`. Rollback: remove only the lines you added; `docker compose up -d --no-deps ubyhost-go`. Hand test afterwards: manual steps M-P8.

### Block D. Schema apply by Go (I1) **needs Josef's go, #1026 deployed**

```bash
docker compose --profile go build ubyhost-go
docker compose --profile go run --rm --no-deps -T ubyhost-go migrate check --expect-database ubyhost
# must print: PostgreSQL schema check OK  -- if it prints "failed": STOP, report that one line, change nothing.
```

Only if it printed OK: add the single line `UBYHOST_SCHEMA_APPLY=go` to `.env`. **Do not run deploy.sh yourself**: report "line added", and Josef deploys (manual steps M-I1). Rollback: delete the line (Josef redeploys).

### Block E. Seller variables for invoices (P7) **needs Josef's go**

Names only: `UBYHOST_BILLING_ENABLED`, `UBYHOST_BILLING_IBAN`, `UBYHOST_BILLING_BANK_ACCOUNT`, `UBYHOST_BILLING_VAT_STATUS`, `UBYHOST_OPERATOR_NAME`, `UBYHOST_OPERATOR_ICO`, `UBYHOST_OPERATOR_DIC`, `UBYHOST_OPERATOR_ADDRESS`, `UBYHOST_OPERATOR_EMAIL`.

```bash
grep -c '^UBYHOST_BILLING_IBAN=\|^UBYHOST_OPERATOR_NAME=\|^UBYHOST_OPERATOR_ICO=' .env     # must print 3
docker compose --profile go up -d ubyhost-go
```

Less than `3`: stop and report which names are missing; do not guess values (Python cannot issue invoices either). Rollback: remove only lines you added.

### Block F. Retention and Turnstile checks (P11, P12), read-only

```bash
docker compose --profile go exec ubyhost-go sh -c 'for k in TURNSTILE_SITE_KEY TURNSTILE_SECRET TURNSTILE_HOSTNAMES UBYHOST_TRUSTED_PROXY_CIDRS; do [ -n "$(printenv $k)" ] && echo "$k set" || echo "$k MISSING"; done'
grep RETENTION .env | cut -d= -f1      # names only; expected: empty, see runbook P12
```

Any `MISSING`: report, change nothing. P13 (AI variables) is the same names-only check: `UBYHOST_AI_FEATURES` contains `havel` and `leon`, plus `UBYHOST_AI_MONTHLY_USD_HAVEL`, `_LEON`, `UBYHOST_APIFY_TOKEN`, `UBYHOST_SECRET_KEY`, `UBYHOST_MAIL_BACKEND` present (print `set`/`MISSING` only).

### Waves of `UBYHOST_GO_PATHS`

All waves use the same procedure (guardrails 2 to 9). Per wave: add the paths, validate, reload, verify, report.

```bash
cd /opt/ubyhost/deploy/lightsail
cp -p .env ".env.bak-$(date +%Y%m%d-%H%M%S)"
grep -n '^UBYHOST_GO_PATHS' .env          # save as <OLD_LINE>
nano .env                                 # inside the double quotes, append the paths, one space between
grep -c '^UBYHOST_GO_PATHS=' .env         # 1
grep '^UBYHOST_GO_PATHS' .env | grep -c '=""'   # 0 (not empty)
./scripts/caddy-validate.sh               # no error
docker compose up -d caddy
```

Rollback for every wave: `nano .env`, put `<OLD_LINE>` back, `./scripts/caddy-validate.sh`, `docker compose up -d caddy`. Generic verify for every wave:

```bash
docker compose logs --since 10m ubyhost-go 2>&1 | grep -i -E 'error|panic' | tail     # expect nothing new
curl -sI "https://<DOMAIN><path>" | head -5     # one request per listed path that is a plain GET page
```

A `501` with `X-Ubyhost-Not-Ported: 1` on a GET means Go has no handler and Caddy falls back to Python: report it, do not "fix" it. Never `curl -X POST`.

| Wave | Paths to add (exact) | Extra verify | Starts only when | Manual part |
|---|---|---|---|---|
| W1 Public pages | `/jak-to-funguje /cenik /pruvodce/*` | `curl -sI` on `/jak-to-funguje` and `/cenik` shows 200 | Josef says go | M-W1 |
| W1b Unsubscribe | `/mail/unsubscribe/*` | none by curl (needs a real token) | Josef says go | M-W1b |
| W2 Exports | `/guests/*/form.pdf /housebook/pdfs.zip /settings/workspace-export /settings/archived` | `/settings/archived` answers 200 or 303 to `/login` | one day after W1; Josef says go. **Never add `/settings/purge-expired`** | M-W2 |
| W2b Privacy | `/privacy-requests /privacy-requests/*` (both always together) | `curl -sI https://<DOMAIN>/privacy-requests` answers `303` to `/login` | one day after W2; Josef says go | M-W2b |
| W3 Billing | `/predplatne /predplatne/* /admin/fakturace /admin/fakturace/*` | `303` to `/login` on both bare pages | Block E done, container can reach `ares.gov.cz`, Josef says go | M-W3 |
| W4 Customer admin | `/admin /admin/customers /admin/customers/*` (`/admin` has no star). Separate later wave: `/admin/operations` | `303` to `/login` | Block E done, Josef says go | M-W4 |
| W5a Login | `/login /login/link` | `curl -sI https://<DOMAIN>/login` answers 200 | Blocks C, F done; #1026 merged; **Josef confirms a second logged-in session is open** | M-W5 |
| W5b 2FA | `/login/2fa` | as W5a | one day after W5a, Josef confirms second session | M-W5 |
| W5c Account | `/account/accept /account/2fa/setup` | `303` to `/login` | one day after W5b, Josef confirms second session | M-W5 |
| W5d E-mail | `/account/email /account/email/confirm` | `303` to `/login` | same | M-W5 |
| W5e Users | `/admin/users/*/invite /admin/users/*/email /admin/users/*/schedule-deletion /admin/users/*/export`. **Never the bare `/admin/users`** | none by curl | same | M-W5 |
| W5f Signup | `/signup /signup/verify` | only if `grep -c '^UBYHOST_SIGNUP_ENABLED=1' .env` prints `1`, else do not run the wave | Josef says go | M-W5 |
| W6 Onboarding | first `/onboarding`; later (separate run) `/onboarding/dismiss /onboarding/resume /welcome-back/dismiss /celebrations/dismiss`. **Never `/onboarding/*`** | `303` to `/login` | Josef says go | M-W6 |
| W7 Setup wizard | `/apartments/*/setup /apartments/*/setup/*` | none by curl | #1026 deployed, Block B done, Josef says go | M-W7 |
| W8 Guide editor | `/apartments/*/guide /apartments/*/guide/cards /apartments/*/guide/import /apartments/*/guide/qr /apartments/*/guide/qr.png /apartments/*/guide/qr/rotate /apartments/*/guide/quick /apartments/*/guide/quick/* /apartments/*/leon /apartments/*/guide/*/photos/* /apartments/*/guide/*/photos/*/delete`. Later, separate run, after writable `/data` and Block B: `/apartments/*/guide/*/photos`. **Never `/apartments/*/guide/*`** | none by curl | Josef says go | M-W8 |
| W8b Havel and Leon | `/havel /havel/* /apartments/*/leon/setup /apartments/*/leon/setup/*` | Block F P13 check passed | one clean week of Python first, Josef says go | M-W8b |
| W9 Invoices | one path per run, in this order: `/invoice/d/*`, `/invoices/*.pdf`, `/invoices/*/paid`, `/invoices/*/cancel`, `/invoices/preview`, `/invoices/new`, `/invoices`. **Never `/invoices/*`** | none by curl | optional; Block E done, Josef says go for each | M-W9 |
| W10 Stay fees | per [stay-fee-go-rollout](stay-fee-go-rollout.md), one step per run: (1) `/stay-fees/pdfs.zip /stay-fees/*/pdf /stay-fees/*/csv`, (2) `/stay-fees/*/guest-pay-preview`, (3) `/stay-fees`. Step (4) `/stay-fees/*` is **not** in this document: recommended to skip | none by curl | all checks of the rollout plan done, Josef says go | M-W10 |

Not for this AI at all (the runbook keeps them on Python or behind a decision): `/settings/purge-expired`, `/demo`, `/demo/reset`, `/webhooks/stripe`, passkey paths, `/stay-fees/*`.

### Block S. Scheduler switch (I2) **needs Josef's go, and brief 1451 steps in his hands**

Only when Josef states the time is outside 03:00 to 07:30 Prague time and that briefs 1450, 1451, 1452 are deployed. Follow brief 1451 step by step; the `.env` and compose part is:

```bash
grep -n '^UBYHOST_JOB_QUEUE_KINDS' .env | tr ' ,"' '\n\n\n' | grep -c -x -E 'ical|submit|deadlines|mail|photo_sweep|meta_capi|retention|stay_fee_mail|stripe_sweep|billing|billing_snapshot|door_codes|posthog|push|guide_import'   # 15
grep -c '^UBYHOST_SCHEDULER=' .env           # 0 before
# add the single line: UBYHOST_SCHEDULER=go
docker compose up -d --no-deps ubyhost-go
# wait 90 seconds, then:
docker compose logs --since 3m ubyhost-go 2>&1 | grep -E 'scheduler started owner=go kinds=15'
docker compose logs --since 3m ubyhost-go 2>&1 | grep -c 'Go scheduler is not enqueuing'     # 0
docker compose up -d --no-deps worker
```

Always `--no-deps`; otherwise the web container restarts too. Fewer than 15 kinds, a missing "started" line, or a count other than `0`: roll back at once and stop. Rollback: delete `UBYHOST_SCHEDULER=go`, `docker compose up -d --no-deps worker` first, then `docker compose up -d --no-deps ubyhost-go`. The queue query and the next-morning check are Josef's (M-I2). The job-kind lists (`UBYHOST_GO_JOB_KINDS` etc.) change only on Josef's explicit instruction; `retention` and `stay_fee_mail` are not covered here (runbook section 5).

## 4. After every block

Report the new `UBYHOST_GO_PATHS` value (paths only) so Josef can record it in the orchestrator chat. The repository still has no record of the live value.
