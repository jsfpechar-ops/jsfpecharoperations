# Go cutover, final session: the executor prompt (login, passkeys, invoices, stay fees)

Written 2026-11-15 for Josef to paste into the server operator AI. It continues [go-cutover-mega-prompt](go-cutover-mega-prompt.md): same state file, same guardrails, only the steps that are left and that the tests allow. Where the two differ, this file wins for G1, W9, W10 and S. Sources: the go/no-go matrix in [go-parity-suite](go-parity-suite.md), runbook wave 5 step (g), [stay-fee-go-rollout](stay-fee-go-rollout.md).

**State on 2026-11-15 (from the cutover record):** W1 to W8 (first set) and W10 step 1 are kept, including login and 2FA (W5a to W5f), so login is already on Go. Passkeys (#1037) and the mail and door_codes jobs (#1036) are merged and Josef says deployed.

**Left out on purpose:** W8b (the Havel and Leon budget variables are missing), job kind `mail` (needs the SES test M-P8), job kind `door_codes` (needs the TTLock test with a real lock), J1 and J2 (retention apply is Josef's decision; the `stay_fee_mail` mail branch is unproven), `/stay-fees/*` (wave 10 step 4), `/apartments`, `/entities`, `/demo`, `/settings/purge-expired`, `/webhooks/stripe`.

**Why there is no scheduler switch (S).** `UBYHOST_SCHEDULER=go` makes Go enqueue all 15 kinds and Python enqueue none, and Python refuses the switch unless all 15 are in `UBYHOST_JOB_QUEUE_KINDS` (brief 1451, `go_scheduler_problem()`). That includes `mail` and `door_codes`, which are excluded above, and the parity suite compared only the names and intervals of the other kinds, not a run on a shared queue. So no job kind is switchable on evidence today, and step S below only reads and reports. It adds nothing.

**The 24 h wait for W10 step 2.** Step 1 (`/stay-fees/pdfs.zip`, `/stay-fees/*/pdf`, `/stay-fees/*/csv`) is kept, but the rule of the rollout plan is one day between steps, counted from when step 1 was applied. The executor reads that time from the state file and refuses before it has passed; it never counts from "kept" and never shortens it. If Josef wants it shorter he must say so in his message, naming the step, and the executor then tells him in one line that it is overriding the plan on his word.

**`UBYHOST_STAY_FEE_GUEST_PAY`.** The executor never edits it. It only prints its current value (on or off, not a secret) and Josef's "go W10-2" message must repeat the value he decided. The parity run of the preview answered the same on both sides with guest pay on; the Go body is 140 characters shorter (soft difference, not yet read line by line), so Josef looks at the preview in the browser first.

## 1. Prompt to paste (copy everything in the box)

```text
SCOPE
- You may: read and edit .env with nano or one exact sed -i on one line; run ./scripts/caddy-validate.sh;
  run docker compose up -d --no-deps <service>; run docker compose ps and docker compose logs (read only);
  run curl -sI against the owner's domain; read and write ONE state file (below). Read-only extras, only
  as written in a step: docker stats --no-stream, df -h /, ls /var/log, grep -c on the named log files,
  and docker compose exec -T ubyhost-go with the exact read-only command written in the step.
- You may NOT: print, paste, log or send any secret value (keys, tokens, passwords, IBAN, ICO/DIC,
  operator e-mail). Check presence with grep -c or "set"/"MISSING" only. Do not run deploy.sh, backup or
  restore scripts, pg-cutover.sh, git, apt, or reboot. Do not touch the database. Do not sign in, send
  mail, issue invoices, or click anything. Never curl -X POST. Never add a path that is not written in a
  step below. These exact entries must never be in UBYHOST_GO_PATHS (compare whole entries, not prefixes;
  the longer paths written in the steps, such as /invoices/*/paid or /admin/users/*/invite, are allowed):
  /apartments /entities /apartments/* /apartments/*/guide/* /settings/purge-expired /demo /demo/reset
  /webhooks/stripe /stay-fees/* /invoices/* /admin/users /onboarding/* /* and any passkey path other than the six exact
  entries written in step G1 (and those only in G1).

GUARDRAILS (every step)
1. cd /opt/ubyhost/deploy/lightsail. Before the first edit of the session:
   cp -p .env ".env.bak-$(date +%Y%m%d-%H%M%S)"; confirm it exists; mode 600; never cat it.
2. Save the whole current line before each edit:  grep '^UBYHOST_GO_PATHS=' .env   (no -n, so no line-number
   prefix; it is the rollback). Also set T0=$(date -Iseconds) right before the edit.
   Entry count = grep '^UBYHOST_GO_PATHS=' .env | cut -d= -f2- | tr -d '"' | wc -w ; note it before the edit.
   UBYHOST_GO_PATHS stays inside double quotes, space-separated, existing entries kept, NEVER empty.
   To switch everything off use exactly "/__go_off__". If the line is missing: stop and report.
3. Only ADD the paths written in the step (R0 only removes). Never replace the value. Never widen a wildcard.
   A path already present is skipped, never added twice.
4. After every edit: grep -c '^UBYHOST_GO_PATHS=' .env must print 1; the entry count must equal the old count
   plus the number of paths added (minus the number removed in R0), and must be at least 1; every old entry
   that is not being removed is still there;
   ./scripts/caddy-validate.sh must finish without error; only then docker compose up -d caddy.
   If validate fails: put the saved line back, validate again, STOP.
5. AUTO-ROLLBACK: after docker compose up -d caddy wait 60 seconds, then run the step's verify.
   Roll back (saved line back, caddy-validate, docker compose up -d caddy) and STOP if ANY of:
   - docker compose ps shows a service restarting or unhealthy that was healthy before;
   - docker compose logs --since "$T0" ubyhost-go has a line with panic, or more than 3 lines with
     level=error;
   - docker compose logs --since 5m caddy shows 5xx for a path you just added;
   - a verify curl returns anything other than the expected status, EXCEPT status 403 together with a
     header "cf-mitigated: challenge" (check with curl -sI ... | grep -i cf-mitigated): that is the
     Cloudflare bot challenge against the server's address and means "cannot be proven from the
     server"; it is NOT a failure. Report it as UNVERIFIED and treat the step as GATE-WAIT (see 6).
     A 403 WITHOUT that header, or any other 4xx/5xx, is a failure: roll back.
   A "501" with "X-Ubyhost-Not-Ported: 1" on a GET means Go has no handler: roll back that step and report.
6. GATE-WAIT: when a step cannot be proven by curl, leave it applied, mark it "applied" (not "kept") in
   the state file, print the exact rollback (the added paths) and the pages for Josef's browser check, and
   STOP. Josef answers "ok W3" (status becomes "kept") or "rollback W3" (you do it). If a LATER session
   starts and a step is still "applied" without Josef's ok, ask Josef first; for W3, W4 and every W5 step
   the default is to roll it back unless his message says "ok <step>". Login, billing and admin steps
   (W3, W4, W5*) start only when Josef's message also says he is at a browser now.
7. STATE FILE: /opt/ubyhost/deploy/lightsail/.go-cutover-state (mode 600, paths and dates only, no secrets).
   One line per step: ID | applied-at (date -Is) | status (applied|kept|rolled-back|skipped) | paths added
   (the rollback is to remove exactly these entries from the CURRENT value, never to paste an older saved
   line over a newer one; the line saved in guardrail 2 is only for rolling back inside the same session).
   The file already exists from the first cutover session (W1 to W8 and W10 step 1 are recorded there). If it
   is missing: STOP and ask Josef; do not reseed it.
   Before each step read it: refuse a step whose WAIT has not passed, or whose
   predecessor is not "kept"; never repeat a step already "kept" or "applied".
8. ONE session = go from the first unfinished step forward and STOP at the first GATE, WAIT or failure.
   Never skip a step. Never run two waves in one edit or one session: after any wave (a step that adds
   paths) STOP, even when the next step is AUTO. R0, R1 and R2 are not waves. After each step run the
   verify and write the state file.
9. On ANY doubt or unexpected output: roll back the current step, STOP, report. Do not retry, do not
   try a different fix.


STEPS, in order. Domain: ubyhost.com (use https://ubyhost.com in every curl). New step ids: G1, W9a to W9g, W10-2,
W10-3, S. The state file already holds the older ids; write the new ones in the same format.

R1  AUTO  Read-only health record, as in the first session: docker compose ps (service, state, restarts);
    docker stats --no-stream for ubyhost-go; df -h / ; the switch names (UBYHOST_GO_PATHS entry count and paths,
    UBYHOST_GO_JOB_KINDS, UBYHOST_JOB_QUEUE_KINDS, UBYHOST_SCHEDULER, UBYHOST_SCHEMA_APPLY, COMPOSE_PROFILES,
    UBYHOST_GO_MEM). Print the state file. Check that W5a to W5f are "kept" (or W5f "skipped"); if any is
    "applied" or "rolled-back", STOP and ask Josef. Do this at the start of every session, then continue.

G1  GATE ("go G1")  Passkeys (runbook wave 5 step g, brief 1760, PR 1037).
    WAIT >= 24 h after W5f "kept" or "skipped" was written (read the time in the state file).
    Josef's message must also say a second logged-in session is open in another browser and that he is at a
    browser now. Login and 2FA are on Go; if /login or /login/2fa is not in UBYHOST_GO_PATHS, STOP.
    Preconditions (names and counts only):
      grep -c '^UBYHOST_PUBLIC_BASE_URL=https://' .env  -> 1, and the same name is passed to ubyhost-go:
      docker compose --profile go exec -T ubyhost-go sh -c '[ -n "$(printenv UBYHOST_PUBLIC_BASE_URL)" ] && echo set || echo MISSING'  -> set
      (WebAuthn on Go needs the https base URL; MISSING: STOP, tell Josef, change nothing.)
      Josef states PR 1037 is deployed.
    Add exactly these six entries, with the stars, nothing else (Caddy matches exactly):
      /login/passkey /login/passkey/options /account/passkeys /account/passkeys/options /account/passkeys/*/rename /account/passkeys/*/delete
    Entry count must rise by exactly 6. One edit, one caddy reload.
    Verify: UNVERIFIED expected (Cloudflare challenge). A 501 with X-Ubyhost-Not-Ported on a GET means Go has no handler: roll back.
    Mark "applied", then GATE-WAIT for Josef's M-G1. Rollback = remove exactly these six entries.

W9  Invoices, GATE per path. One path per session, in this order, never two in one edit:
      W9a /invoice/d/*    W9b /invoices/*.pdf    W9c /invoices/*/paid    W9d /invoices/*/cancel
      W9e /invoices/preview    W9f /invoices/new    W9g /invoices
    NEVER /invoices/* . The detail page /invoices/<id> and /invoices/*/send stay on Python.
    Message needed: "go W9x" naming the path step, and Josef is at a browser now.
    Preconditions every time: grep -c '^UBYHOST_BILLING_IBAN=\|^UBYHOST_OPERATOR_NAME=\|^UBYHOST_OPERATOR_ICO=' .env  -> 3;
      grep -c '^UBYHOST_BILLING_VAT_STATUS=non_payer' .env  -> 1 (the parity suite never ran a VAT-payer invoice:
      any other value, STOP and tell Josef); W4 and W3 "kept".
    WAIT: none before W9a. W9b needs W9a "kept". W9c to W9g each need the previous path "kept" and >= 24 h since
    the previous path was applied (these write invoices or issue them).
    Each path has four stages, and the next stage needs Josef's message:
      1. apply (one entry), verify, mark "applied", GATE-WAIT for Josef's browser check;
      2. "ok W9x" -> then Josef asks "rollback-test W9x": remove exactly that entry, validate, reload, write
         "rollback-tested" in the state file, ask Josef to confirm the page still works from Python;
      3. "re-apply W9x": add the entry again, verify;
      4. "ok W9x" again -> status "kept". A path is never "kept" without the rollback test.
    HIGH RISK: legally binding invoices. You never POST, never click, never issue anything.

W10-2  GATE ("go W10-2")  Add: /stay-fees/*/guest-pay-preview
    WAIT >= 24 h after W10 step 1 was APPLIED (state file). If less has passed, say how long is left and STOP.
    Needs W10 step 1 "kept". Josef's message states the decided value of UBYHOST_STAY_FEE_GUEST_PAY and that
    he looked at the preview in a browser. Print the current value (grep '^UBYHOST_STAY_FEE_GUEST_PAY=' .env,
    or "unset" which means off); if it differs from what Josef stated: STOP. You never edit that line.
    Verify: UNVERIFIED (POST route, Cloudflare). GATE-WAIT for Josef's M-W10-2. Rollback: remove the entry.

W10-3  GATE ("go W10-3")  Add: /stay-fees
    WAIT >= 24 h after W10-2 was applied; needs W10-2 "kept". Josef states it is not near a filing deadline.
    NEVER /stay-fees/* (step 4, the seal routes, is not yours and is recommended to skip).
    Verify: curl -sI https://ubyhost.com/stay-fees -> 303 to /login, or UNVERIFIED with the Cloudflare header.
    GATE-WAIT for Josef's M-W10-3. Rollback: remove the entry.

S   AUTO, read-only, never an edit. Report: the names in UBYHOST_JOB_QUEUE_KINDS and UBYHOST_GO_JOB_KINDS
    (how many of 15 each), which of the 15 are missing from the queue list, and whether UBYHOST_SCHEDULER is set
    (grep -c '^UBYHOST_SCHEDULER=' .env). Then write exactly: "Scheduler switch not done: it needs all 15 kinds
    including mail (SES test M-P8) and door_codes (lock test), which are not cleared." Do not add any kind to
    either variable and do not set UBYHOST_SCHEDULER.

NOT YOURS (tell Josef, do nothing): W8b, job kinds mail, door_codes, retention apply, stay_fee_mail; apt upgrades
and reboot; S3/IAM and lifecycle; SES test M-P8; browser checks; Cloudflare rules; /demo; /settings/purge-expired;
/stay-fees/*; the UBYHOST_STAY_FEE_GUEST_PAY value; anything about SQLite; PR 1033 (login button wording).

FINAL REPORT (always, even when you stop early). One block:
1. Session date/time, last step reached, the next step and what it waits for (a date or a GATE message).
2. Table: step | applied-at | result (OK / UNVERIFIED / ROLLED BACK / SKIPPED) | one-line reason.
3. Current UBYHOST_GO_PATHS (paths only) and entry count; UBYHOST_GO_JOB_KINDS and UBYHOST_JOB_QUEUE_KINDS (names only).
4. Rollback line for every step applied in this session.
5. docker compose ps summary and the error/panic count of ubyhost-go for the last hour.
6. For each UNVERIFIED step: the exact pages Josef must open and what he should see.
No secret values anywhere in the report.
```

## 2. What Josef does in a browser

Each item is the AI's GATE-WAIT. Have a second logged-in browser open for G1. Say "ok <step>" or "rollback <step>".

| Step | Do this | You should see |
|---|---|---|
| M-G1 passkeys | 1. In the first browser: Settings, add a passkey (Face ID, Windows Hello or a security key). 2. Log out. 3. Log in with the passkey button. 4. Settings, remove the passkey. 5. Repeat 1 to 3 in the second browser. 6. Open the audit page. | You land signed in each time. The audit page shows `passkey_added`, a `login` with method `passkey:<id>` and `passkey_removed`. The second browser's session still works throughout. Any error page: say "rollback G1". Not tested by the suite: a real device, so this check is the only one on hardware. |
| M-W9a | Open a public invoice link (`/invoice/d/<token>`) from a real invoice mail. | The invoice shows, with the same amount as before. |
| M-W9b | Open one invoice PDF from the invoices list. | The PDF downloads and opens. |
| M-W9c, M-W9d | Do not mark anything real as paid or cancelled. Open an invoice detail and check the Paid and Cancel buttons are still there. Optional: on a test invoice only, mark paid or cancel. | Same buttons, same result as on Python. |
| M-W9e | `/invoices/new`, pick a stay, press Preview. | Preview shows, with no invoice created. |
| M-W9f, M-W9g | Open the stay picker and the form; do not press Issue unless it is a test invoice. | Same fields as on Python. |
| Rollback test, every W9 path | After "rollback-test W9x", open the same page. | It still works (now from Python). Then say "re-apply W9x". |
| M-W10-2 | In `/stay-fees/<id>` use the guest-pay preview with a test rate. | A preview of the fee; nothing is saved. |
| M-W10-3 | Open `/stay-fees` and one detail page. | The same list as before. |

Not for the browser: the passkey button wording ("Face ID" and similar) is PR 1033 and is held.
