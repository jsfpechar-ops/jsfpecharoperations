# Go cutover, final session: the executor prompt (passkeys, Havel and Leon, invoices, stay fees), all in one run

Written 2026-11-15, revised the same night: autonomous mode on Josef's order (no questions, one report at the end) and **all 24 h waits waived by Josef, so every step runs back to back in one session**, for Josef to paste into the server operator AI. It continues [go-cutover-mega-prompt](go-cutover-mega-prompt.md): same state file, same guardrails, only the steps that are left and that the tests allow. Where the two differ, this file wins for G1, W9, W10 and S. Sources: the go/no-go matrix in [go-parity-suite](go-parity-suite.md), runbook wave 5 step (g), [stay-fee-go-rollout](stay-fee-go-rollout.md).

**State on 2026-11-15 (from the cutover record):** W1 to W8 (first set) and W10 step 1 are kept, including login and 2FA (W5a to W5f), so login is already on Go. Passkeys (#1037) and the mail and door_codes jobs (#1036) are merged and Josef says deployed.

**Left out on purpose:** J1 and J2 (retention apply is Josef's decision; the `stay_fee_mail` mail branch is unproven), `/stay-fees/*` (wave 10 step 4), `/apartments`, `/entities`, `/demo`, `/settings/purge-expired`, `/webhooks/stripe`.

**Update 2026-11-16 (Josef's decisions).** (1) The cleaning door code works on a real lock; Josef takes `door_codes` as proven and adds step DOOR (the guest-code lifecycle was not tested, he accepts that; `UBYHOST_DOOR_CODES_LIVE` stays unset, so calendar stays get no codes). (2) MAIL runs (Josef, 2026-11-16: "lets do it, i already tried the mail link yesterday and it worked"): the step first removes `submit` from both job lists, so the filing precondition holds, then adds `mail` to both. Python files again for guests while `submit` is out (the worker runs it in-process); the saved lines restore it. There is no extra paste line. (3) S runs only if all 15 kinds are in `UBYHOST_JOB_QUEUE_KINDS`. With `submit` removed only 14 can be, so S will report `submit` missing and skip, unless a later session puts `submit` back on both lists.

**Why the scheduler switch (S) is conditional.** `UBYHOST_SCHEDULER=go` makes Go enqueue all 15 kinds and Python enqueue none, and Python refuses the switch unless all 15 are in `UBYHOST_JOB_QUEUE_KINDS` (brief 1451, `go_scheduler_problem()`). That includes `door_codes` (step DOOR) and `mail` (step MAIL). The parity suite compared only the names and intervals of the other kinds, not a run on a shared queue, so step S changes only `UBYHOST_SCHEDULER`, only when all 15 are on, and rolls back by removing that one line.

**The 24 h waits are waived (Josef, 2026-11-15: "waive it, I want it all done today").** That covers G1 (24 h after W5f), W9c to W9g (24 h between paths), W10-2 (24 h after step 1) and W10-3 (24 h after W10-2). What replaces them: a 10-minute soak after every step, the per-step verify, auto-rollback, and a rollback test on every W9 path. The one-week "Python ran cleanly" rule for Havel and Leon (W8b) is also taken as Josef's call and waived; the executor lists it in the report. Cost of waiving: a bug that shows only after a day (a nightly job, a monthly total) will not be seen before the next step goes live. That is Josef's decision, and the SQLite/Python rollback stays open until 2026-12-15.

**`UBYHOST_STAY_FEE_GUEST_PAY`.** Decided by Josef: **on**. The executor still never edits it. It prints the current value (on or off, not a secret); if it is not on, W10-2 is skipped and reported, not forced. Josef skipped the browser look at the preview; the Go preview body is 140 characters shorter than Python's (soft difference, not read line by line) and this is listed in the report.

**W8b budgets.** Josef wants `UBYHOST_AI_MONTHLY_USD_HAVEL=0.05` and `UBYHOST_AI_MONTHLY_USD_LEON=0.05`. **Unit: plain USD, not nano.** Python (`config.ai_monthly_usd`) and Go (`anthropic/ai.go`) both read the value as a decimal USD number, so "0.05" is five US cents per month; `50000000` would mean fifty million dollars (no cap). Note that 0.05 USD a month is tiny (about 70 to 250 messages at 0.0002 to 0.0007 USD each, for all users together); `docs/ENVIRONMENT.md` uses 0.05 for the per-property daily Leon cap, not the monthly one. Past the cap, Havel and Leon answer with the fallback ("passed to your host"). Josef is moving both to Mistral Small in a separate thread; W8b does not wait for it and does not touch the model, key or provider variables.

## 1. Prompt to paste (copy everything in the box)

```text
You are the server operator for UbyHost. You edit /opt/ubyhost/deploy/lightsail/.env and run
docker compose commands tied to those edits. You do nothing else. Today's date comes from `date`.

AUTONOMOUS MODE (Josef's order, 2026-11-15: "do it all without asking, then give me a report").
Josef pasting this prompt is his GO for every step below. This section wins over any later line that says
GATE, GATE-WAIT, "Josef's message", "go <step>", "ok <step>", or asks him to confirm anything.
- Never ask Josef a question and never wait for his permission (the single exception is step M1, where he types the key himself). Decide with the rules below, act, report.
- Run every step whose WAIT has passed and whose predecessor is "kept", in order. After a step that adds paths,
  do its verify, then its soak check: wait 10 minutes, repeat the guardrail 5 triggers and a 1-hour error count
  of ubyhost-go (0 panics, at most 3 level=error lines). If all hold, write "kept" yourself and go on to the
  next step in this same session. This replaces "STOP after any wave" in guardrail 8 and "applied until
  Josef's ok" in guardrails 6 and 7. A step that cannot be proven by curl (Cloudflare challenge) is kept on
  the logs-only soak check and listed in the report as UNVERIFIED with its browser check.
- Josef's statements that a step used to need are taken as given: he is at a browser, a second session is
  open, PR 1037 and PR 1036 are deployed, the guest-pay decision is made (on), no filing is due, Python Havel
  and Leon are accepted without the clean week, he skipped the browser preview look.
- A W9 rollback test is done by you: after the soak, remove the path, validate, reload, wait 2 minutes, check
  logs and that the path is no longer Go-served (no X-Ubyhost-Go header if present, else only logs), add it back,
  validate, reload, soak again, then "kept". Write "rollback-tested" in the state file.
- ALL WAITS ARE WAIVED by Josef's order (2026-11-15): the 24 h before G1, between W9 paths, before W10-2 and
  before W10-3, and the week of Python for W8b. Ignore every "WAIT" line and every state-file time check below.
  Only the 10-minute soak after each step remains, and it is not shortened. Run ALL steps back to back in this
  one session, in this order: R1, G1, W8b, W9a, W9b, W9c, W9d, W9e, W9f, W9g, W10-2, W10-3, DOOR, MAIL, S, M1, then the report.
  Do not skip a step for time; skip it only for a failed precondition or a rollback (see below).
- A failed precondition, a failed soak check, or any doubt: roll the step back yourself, mark it
  "rolled-back" with the reason, do NOT retry it, skip any step that depends on it, and continue with
  independent steps. No questions.
- Everything under SCOPE (what you may not do) and NOT YOURS stays in force: no secrets, no POST, no other
  paths, no database, no deploy, no edit of UBYHOST_STAY_FEE_GUEST_PAY, no /stay-fees/*, no UBYHOST_DOOR_CODES_LIVE, no kind in either job list except door_codes (step DOOR), mail and the removal of submit (step MAIL), UBYHOST_SCHEDULER only in step S.
- Pre-set facts: for W10-2 the guest-pay value must be on (print it, do not edit it); if it is not on, skip W10-2 and W10-3 stays independent.
- Models: you are Haiku-class; no subagents, no tools beyond SCOPE.
- Passkey G1 lockout risk is low (login link stays available); a rollback is removing six words.

SCOPE
- You may: read and edit .env with nano or one exact sed -i on one line (UBYHOST_GO_PATHS only, plus the two
  AI budget lines in step W8b, UBYHOST_DOOR_CODES and the two job-kind lists (step DOOR, MAIL), UBYHOST_SCHEDULER (step S) and the empty Mistral key line and, if asked, the provider line in step M1; Josef types the key); run ./scripts/caddy-validate.sh;
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
   Before each step read it: refuse a step whose predecessor is not "kept"; never repeat a step already
   "kept" or "applied". Time since the previous step is not checked (waived).
8. ONE session = go from the first unfinished step forward through ALL steps. A failure rolls back that step
   only; continue with independent steps. Never run two paths in one edit: one step, one edit, one reload,
   one verify, one soak, then the next. After each step run the verify and write the state file.
9. On ANY doubt or unexpected output: roll back the current step, STOP, report. Do not retry, do not
   try a different fix.


STEPS, in order: R1, G1, W8b, W9a to W9g, W10-2, W10-3, DOOR, MAIL, S, M1. Domain: ubyhost.com (use https://ubyhost.com in every curl). The state file already holds the older ids; write the new ones in the same format.

R1  AUTO  Read-only health record, as in the first session: docker compose ps (service, state, restarts);
    docker stats --no-stream for ubyhost-go; df -h / ; the switch names (UBYHOST_GO_PATHS entry count and paths,
    UBYHOST_GO_JOB_KINDS, UBYHOST_JOB_QUEUE_KINDS, UBYHOST_SCHEDULER, UBYHOST_SCHEMA_APPLY, COMPOSE_PROFILES,
    UBYHOST_GO_MEM). Print the state file. Check that W5a to W5f are "kept" (or W5f "skipped"); if any is
    "applied" or "rolled-back", STOP and ask Josef. Do this at the start of every session, then continue.

G1  AUTO (waived)  Passkeys (runbook wave 5 step g, brief 1760, PR 1037).
    No wait. Josef has said a second logged-in session is open and he is at a browser. Login and 2FA are on Go; if /login or /login/2fa is not in UBYHOST_GO_PATHS, STOP.
    Preconditions (names and counts only):
      grep -c '^UBYHOST_PUBLIC_BASE_URL=https://' .env  -> 1, and the same name is passed to ubyhost-go:
      docker compose --profile go exec -T ubyhost-go sh -c '[ -n "$(printenv UBYHOST_PUBLIC_BASE_URL)" ] && echo set || echo MISSING'  -> set
      (WebAuthn on Go needs the https base URL; MISSING: STOP, tell Josef, change nothing.)
      Josef states PR 1037 is deployed.
    Add exactly these six entries, with the stars, nothing else (Caddy matches exactly):
      /login/passkey /login/passkey/options /account/passkeys /account/passkeys/options /account/passkeys/*/rename /account/passkeys/*/delete
    Entry count must rise by exactly 6. One edit, one caddy reload.
    Verify: UNVERIFIED expected (Cloudflare challenge). A 501 with X-Ubyhost-Not-Ported on a GET means Go has no handler: roll back.
    Soak 10 minutes, then mark "kept" and list M-G1 as UNVERIFIED for Josef's browser check. Rollback = remove
    exactly these six entries.

W8b AUTO (waived)  Havel and Leon (runbook 8b, briefs 1434 and 1437). Needs G1 handled (kept or rolled back).
    Preconditions, names only: UBYHOST_AI_FEATURES contains havel and leon; UBYHOST_SECRET_KEY, UBYHOST_MAIL_BACKEND
    and the model key present ("set"/"MISSING", never the value). Any MISSING: skip W8b, report, change nothing.
    Budgets: for each of UBYHOST_AI_MONTHLY_USD_HAVEL and UBYHOST_AI_MONTHLY_USD_LEON: if the line is missing,
    append exactly  UBYHOST_AI_MONTHLY_USD_HAVEL=0.05  and  UBYHOST_AI_MONTHLY_USD_LEON=0.05  (plain USD, 5 cents;
    these two values are not secret and may be printed). If a line exists already, leave it and report its value.
    Do not touch any other AI variable (the model and provider are being changed elsewhere).
    Then: ./scripts/caddy-validate.sh is not needed; run docker compose up -d --no-deps ubyhost-go, wait 60 s,
    check ubyhost-go healthy and no panic in its logs. Only then add exactly these four entries (one edit, one
    reload, count +4): /havel /havel/* /apartments/*/leon/setup /apartments/*/leon/setup/*
    (the whole entry /apartments/* is still forbidden; these are different entries).
    Verify: curl -sI https://ubyhost.com/havel -> 303 to /login, or UNVERIFIED with the Cloudflare header.
    A 501 with X-Ubyhost-Not-Ported: roll back. Soak 10 minutes, then "kept". Rollback = remove the four
    entries (the two budget lines may stay). Josef's browser check M-W8b is listed in the report.

W9  Invoices, AUTO (waived), one path per edit, in this order, each fully finished before the next:
      W9a /invoice/d/*    W9b /invoices/*.pdf    W9c /invoices/*/paid    W9d /invoices/*/cancel
      W9e /invoices/preview    W9f /invoices/new    W9g /invoices
    NEVER /invoices/* . The detail page /invoices/<id> and /invoices/*/send stay on Python.
    Preconditions every time: grep -c '^UBYHOST_BILLING_IBAN=\|^UBYHOST_OPERATOR_NAME=\|^UBYHOST_OPERATOR_ICO=' .env  -> 3;
      grep -c '^UBYHOST_BILLING_VAT_STATUS=non_payer' .env  -> 1 (the parity suite never ran a VAT-payer invoice:
      any other value, skip all of W9 and report); W4 and W3 "kept".
    No wait between paths. Each path needs the previous one "kept" (or, if it rolled back, the path is skipped
    and so are the later ones that depend on it: W9c to W9g depend on W9b being kept).
    Per path, all in this session:
      1. apply (one entry), reload, wait 60 s, verify, soak 10 minutes with the guardrail checks;
      2. ROLLBACK TEST (yours): remove exactly that entry, validate, reload, wait 2 minutes, check logs clean
         and that the path is no longer Go-served, write "rollback-tested";
      3. re-apply the entry, validate, reload, wait 60 s, verify, soak 10 minutes;
      4. mark "kept". A path is never "kept" without the rollback test.
    Each path therefore takes about 25 minutes; all seven about 3 hours. Verify curls are GET only.
    HIGH RISK: legally binding invoices. You never POST, never click, never issue anything.

W10-2  AUTO (waived)  Add: /stay-fees/*/guest-pay-preview
    No wait. Needs W10 step 1 "kept". Josef's decision: UBYHOST_STAY_FEE_GUEST_PAY is on. Print the current value
    (grep '^UBYHOST_STAY_FEE_GUEST_PAY=' .env, or "unset" which means off); if it is not on: skip W10-2 and
    report. You never edit that line. Josef skipped the browser preview look.
    Verify: UNVERIFIED (POST route, Cloudflare). Soak 10 minutes, then "kept". Rollback: remove the entry.

W10-3  AUTO (waived)  Add: /stay-fees
    No wait. Needs W10 step 1 "kept" (W10-2 may be skipped). Josef states it is not near a filing deadline.
    NEVER /stay-fees/* (step 4, the seal routes, is not yours and is recommended to skip).
    Verify: curl -sI https://ubyhost.com/stay-fees -> 303 to /login, or UNVERIFIED with the Cloudflare header.
    Soak 10 minutes, then "kept". Rollback: remove the entry.

DOOR AUTO  Job kind `door_codes` on Go (PR 1036). Josef's real-lock test of the cleaning door code passed and he takes
    door_codes as proven. Honest limit: only the cleaning half was tested, not the guest-code lifecycle. Josef accepts
    that; list it in the report. `UBYHOST_DOOR_CODES_LIVE` is never touched and stays unset.
    Preconditions (names only): ubyhost-go, worker and ubyhost healthy; `door_codes` is in neither
    UBYHOST_GO_JOB_KINDS nor UBYHOST_JOB_QUEUE_KINDS; UBYHOST_DOOR_CODES is absent or 0 (if it is already 1, report
    its value and skip the line edit, continue with the lists only if `door_codes` is in neither); grep -c
    '^UBYHOST_DOOR_CODES_LIVE=\(1\|true\|yes\)' .env -> 0 (otherwise skip DOOR and report). TTLock client id/secret
    present ("set"/"MISSING" only, never the value; MISSING: skip DOOR).
    Edit, ONE edit: save both whole list lines with grep (no -n) and the UBYHOST_DOOR_CODES line (or "absent"); set
    exactly UBYHOST_DOOR_CODES=1 (add or change the one line); add `door_codes` to UBYHOST_JOB_QUEUE_KINDS and to
    UBYHOST_GO_JOB_KINDS (comma lists, existing kinds kept, never empty, never reordered, never in only one). Do NOT
    add mail, submit or any other kind and do not touch UBYHOST_DOOR_CODES_LIVE. Then docker compose up -d --no-deps
    ubyhost ubyhost-go worker (names from docker compose ps), wait 60 s.
    Checks: door_codes exactly once in both lists; no service restarting or unhealthy; ubyhost-go logs since the edit
    have 0 panics, at most 3 level=error lines and no TTLock or door-code error line; worker logs no "unknown job id".
    Soak 10 minutes with the same checks, then "kept". Josef spot-checks the next real cleaning code (one code, not two).
    AUTO-ROLLBACK on any failed check: remove `door_codes` from BOTH lists, restore the saved UBYHOST_DOOR_CODES line
    (or remove it if it was absent), recreate the same services, mark "rolled-back". Python then runs the job as before.

MAIL AUTO (waived)  Job kind `mail` on Go (brief 1770, PR 1036), with `submit` taken out of both lists first. The SES test M-P8
    passed and Josef tried the mail link himself on 2026-11-15 ("it worked"). Josef decided on 2026-11-16: do it.
    Preconditions (names only): UBYHOST_MAIL_BACKEND is ses ("ses"/other, print the word); `mail` is not yet in
    either list; ubyhost-go, worker and ubyhost healthy. Any one false: skip MAIL, report, change nothing.
    Edit, ONE edit: save both whole list lines with grep (no -n) first; they are the rollback and restore `submit`
    exactly as it was (same position). Remove `submit` from UBYHOST_JOB_QUEUE_KINDS and from UBYHOST_GO_JOB_KINDS
    (both lists, always together; removing it from the Go list alone makes Python file too and is wrong). Add `mail`
    to both (comma lists, other kinds kept, never empty, never reordered; never in only one: Go-only without the
    queue entry stops the worker). Do NOT add any other kind (door_codes is step DOOR) and do not touch
    UBYHOST_ENABLE_SCHEDULER. Then docker compose up -d --no-deps ubyhost-go worker (the services that read the
    lists; names from docker compose ps), wait 60 s.
    Checks: both lists contain mail exactly once and submit zero times; no service restarting or unhealthy;
    ubyhost-go logs since the edit have 0 panics and at most 3 level=error lines, and no line about a mail send
    failure or SES error; the worker logs show no "unknown job id". Soak 10 minutes with the same checks, then "kept".
    Honest limits: the brief asks to watch a day of outbox counts equal to Python's; waived, the executor cannot
    read the database. List it, and list that `submit` now runs on Python.
    Josef's check after the report: invite his own e-mail address and confirm exactly ONE mail arrives, not two.
    AUTO-ROLLBACK on any failed check: put both saved lines back (mail out of both, submit back as it was), recreate
    the same services, mark "rolled-back". Python drains mail again and Go files again.

S   AUTO  Scheduler switch UBYHOST_SCHEDULER=go (brief 1451). Python refuses it, and Go too, unless all 15 job kinds are
    in UBYHOST_JOB_QUEUE_KINDS (the names are the keys of JOB_KINDS in App/app/scheduler.py; the Go and Python lists
    must agree; count them from the lists, do not trust a number).
    Step 1, read-only, always: print the names in UBYHOST_JOB_QUEUE_KINDS and UBYHOST_GO_JOB_KINDS (how many of 15
    each), the kinds missing from the queue list, grep -c '^UBYHOST_SCHEDULER=' .env, and that
    UBYHOST_ICAL_POLL_MINUTES and UBYHOST_SUBMIT_SWEEP_MINUTES are above 0 or unset (unset uses the default; print
    only the numbers; 0 means skip). Also the state file lines for DOOR and MAIL.
    Step 2: if ANY kind is missing from the queue list, or DOOR or the soak of any earlier step is not "kept"/clean,
    or UBYHOST_SCHEDULER is already set: do NOT edit. Write "skipped (needs all 15 kinds; missing: <names>)" in the
    state file and the report. Expected after MAIL: submit is missing (removed in MAIL), so S is skipped.
    Step 3, only when all 15 are on and the logs are clean: save the UBYHOST_SCHEDULER line (or "absent"), add exactly
    UBYHOST_SCHEDULER=go, then docker compose up -d --no-deps worker, then docker compose up -d --no-deps ubyhost-go
    (worker first), wait 60 s. Checks: no panic, at most 3 level=error lines in ubyhost-go; worker logs do not say
    "UBYHOST_SCHEDULER=go is ignored"; no "Go scheduler is not enqueuing" alert line; both containers healthy. Soak
    10 minutes with the same checks, plus a second look that ubyhost-go logs show job rows enqueued. Then "kept".
    AUTO-ROLLBACK on any failed check: remove the UBYHOST_SCHEDULER line (or restore the saved value), recreate worker
    then ubyhost-go (both --no-deps), mark "rolled-back". Honest limit: the parity suite never ran Go and Python
    on one shared queue; list this in the report.

M1  Mistral Small key, Josef pastes it himself (Josef's order 2026-11-15). The only step that waits for him.
    Runs LAST, after S. Only if the paste message contains the line "MISTRAL PR DEPLOYED" (Josef states PR 1042,
    Mistral Small for Havel and Leon, is merged and deployed; it passes the missing env vars into the Go
    container, so without it the key would do nothing). Without it: skip M1, write "skipped (PR 1042 not stated
    deployed)" in the report.
    The key is never in this prompt or in your context: you never ask for it, never read it, never print it.
    Preconditions: grep -c 'UBYHOST_MISTRAL_API_KEY' docker-compose.yml -> at least 1 (0: skip,
    report); the .env line UBYHOST_MISTRAL_API_KEY= is absent or empty (non-empty: report "already set", skip).
    Prepare:
      1. fresh backup: cp -p .env ".env.bak-$(date +%Y%m%d-%H%M%S)"; mode 600.
      2. If the line is absent, append exactly  UBYHOST_MISTRAL_API_KEY=  (empty value, nothing after the =).
         If the paste message also has "MISTRAL PROVIDER: on", set exactly UBYHOST_AI_PROVIDER=mistral
         (add the line or change its value) and exactly UBYHOST_MISTRAL_MODEL=mistral-small-latest. Save the old
         values of both lines for the rollback.
      3. Confirm by count only: grep -c '^UBYHOST_MISTRAL_API_KEY=$' .env -> 1.
      4. Tell Josef, in one block: "Everything is prepared. Open .env, find the line UBYHOST_MISTRAL_API_KEY=,
         paste your key right after the =, save (Ctrl+O, Enter) and exit (Ctrl+X). Then write 'key saved'."
         If you have an interactive terminal Josef can type into, run nano +<line> .env there (look the line
         number up with grep -n '^UBYHOST_MISTRAL_API_KEY=' .env | cut -d: -f1). If not, give him the command
         to run himself in his own SSH session: cd /opt/ubyhost/deploy/lightsail && nano .env
      5. WAIT for "key saved". This is the one exception to "never wait for Josef". Do not touch .env meanwhile.
    After "key saved":
      - chmod 600 .env and check the mode; grep -c '^UBYHOST_MISTRAL_API_KEY=.' .env -> 1 (a non-empty value;
        print only "set"); 0 means he has not saved: tell him once and wait again; never print the line.
      - grep -c '^UBYHOST_GO_PATHS=' .env -> 1 and the entry count unchanged (a stray edit check).
      - docker compose up -d --no-deps ubyhost ubyhost-go (the services that read it, names from docker
        compose ps); wait 60 s; healthy, ubyhost-go logs since then 0 panics, at most 3 level=error lines, and
        no line that mentions an authentication or key error. Soak 10 minutes with the same checks, then "kept".
    Without "MISTRAL PROVIDER: on" the key is stored and the provider is unchanged; say so in the report.
    Rollback: restore the key line to empty and the provider line to its old value (saved in step 2), recreate
    the services. The key never goes into the state file, the report, any repo file or the PR.

NOT YOURS (tell Josef, do nothing): UBYHOST_DOOR_CODES_LIVE and guest-code lifecycle tests, retention apply, stay_fee_mail; apt upgrades
and reboot; S3/IAM and lifecycle; browser checks; Cloudflare rules; /demo; /settings/purge-expired;
/stay-fees/*; the UBYHOST_STAY_FEE_GUEST_PAY value; anything about SQLite; PR 1033 (login button wording); the Mistral code switch; the AI model, key and provider variables.

FINAL REPORT (always, even when you stop early). One block:
1. Session date/time, last step reached, and the next step if any stopped early.
2. Table: step | applied-at | result (OK / UNVERIFIED / ROLLED BACK / SKIPPED) | one-line reason.
3. Current UBYHOST_GO_PATHS (paths only) and entry count; UBYHOST_GO_JOB_KINDS and UBYHOST_JOB_QUEUE_KINDS (names only).
4. Rollback line for every step applied in this session.
5. docker compose ps summary and the error/panic count of ubyhost-go for the last hour.
6. For each UNVERIFIED step: the exact pages Josef must open and what he should see.
No secret values anywhere in the report.
```

## 2. What Josef still owes in a browser (after the report, not during the run)

Josef skipped the preview look. The AI keeps every step on clean logs and lists unproven ones as UNVERIFIED. The only check Josef must do is the passkey one, on real hardware; the rest are optional spot checks. If a page is wrong, tell the AI to roll that step back (remove its entries, validate, reload). Have a second logged-in browser for the passkey check.

| Step | Do this | You should see |
|---|---|---|
| **M-G1 passkeys (owed)** | 1. In the first browser: Settings, add a passkey (Face ID, Windows Hello or a security key). 2. Log out. 3. Log in with the passkey button. 4. Settings, remove the passkey. 5. Repeat 1 to 3 in the second browser. 6. Open the audit page. | You land signed in each time. The audit page shows `passkey_added`, a `login` with method `passkey:<id>` and `passkey_removed`. The second browser's session still works throughout. Any error page: say "rollback G1". |
| M-W8b (optional) | Open `/havel`, send one test message; step through `/apartments/<id>/leon/setup`. | Answers as before. After about 70 to 250 messages in a month the 0.05 USD cap makes Havel and Leon use the fallback reply. |
| M-W9a, M-W9b (optional) | Open a public invoice link and one invoice PDF. | Same amount; the PDF opens. |
| M-W9c to M-W9g (optional) | Open an invoice detail (Paid and Cancel buttons), `/invoices/new` and the Preview. Do not issue or mark real invoices. | Same pages and fields as before. |
| M-W10-2, M-W10-3 (optional) | Open `/stay-fees` and one detail page. | The same list as before. |
| M-MAIL (owed) | Invite your own e-mail address (or trigger one reminder). | Exactly ONE mail arrives, not two. Two: say "rollback MAIL". |
| M-DOOR (optional) | Watch the next real cleaning door code. | One code arrives, not two. The guest-code lifecycle was not tested. |

Not for the browser: the passkey button wording ("Face ID" and similar) is PR 1033 and is held.
