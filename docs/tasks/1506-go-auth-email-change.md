# 1506: Go login address change (dormant): `POST /account/email`, `GET`/`POST /account/email/confirm`

Status: review
Depends on: 1501 (built on go-wave3: `mail.QueueLinkMail`, `mail.QueueEmailChanged`, `mail.KindEmailConfirm`, `clientip.Key`), 1505 (its `acct_shell.go` shell and send hooks, `acct_i18n.json` with this brief's strings, and the golden harness `runAccountGolden` in `account_golden_test.go`; run 1505 first) | Base commit: 859d114d5 | Branch: go-wave3
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

**One big PR mode.** Work on the branch that is checked out now (go-wave3). Never create a branch, never push, never open a PR, never use `mcp__` tools. Commit after each step with the message `1506 step k` (k = the step number), and the report as `1506 report`. The orchestrator opens the one PR.

## 1. Objective

Port the login address change of `App/app/routes/admin_accounts.py` to Go: `POST /account/email` mails a one-hour confirmation link to the new address, `GET /account/email/confirm` shows the confirm button, `POST /account/email/confirm` makes the change (every session ends, the old address gets a notice) and sends the host to log in again. Tier A (account takeover surface): dormant until the owner lists the paths, and every answer (status, headers, cookies, page, rate-limit rows, login tokens, outbox rows, audit) is proven equal to Python's by 35 golden cases recorded from the real Python app.

## 2. Context

Rules (AGENTS.md): 2 privacy (no new field; the audit detail carries masked addresses only, `mail.mask_email`; no new outbound request: the mails go into the existing `email_outbox`); 3 test secrets and `example.test` addresses only; 4 no new dependency; 5 Postgres placeholders, no schema change; 6 the confirm form works without JavaScript; 7 and 10: the one new page template (`account_email_confirm`) is proven equal to Python's HTML (whitespace folded) by the golden test; Go pages cannot be screenshotted yet (orchestrator open item 7), say so in the report; 11 go-first: `App/scripts/auth_email_golden.py` is port plumbing (go-first.md exception 1, golden script). No file under `App/app/` changes.

**The code is in sidecar files.** `docs/tasks/1506-files/` mirrors the repo paths; every file has `.txt` appended. You only copy them (dropping `.txt`) and check their sha256 (step 0). Never type or edit the code. The two existing files (`auth.go`, `auth_test.go`) change by the scripted edits of step 2 only.

**Python source of truth** (`App/app/routes/admin_accounts.py` at the base commit):

- `account_email_request` 612-653: CSRF (router dependency), `auth.require_login` (signed out: `/login?next=/account/email`; acceptance pending: `/account/accept?next=/account/email`; `/account` is read-only-open for a paused plan); impersonating: back with `auth.error.admins_only`; login older than 10 minutes: `auth.error.recent_login`; `mail.normalise_email` empty: `users.email.error.invalid`; same as the current address: message `users.email.unchanged`; `login_link.request_blocked(ip_key, email)` (3 per 15 minutes and 10 per day per address, 10 per 15 minutes per visitor address): `auth.error.link_rate_limited`; else `record_request`, and only when no other account (active or not) has the address: `login_link.issue(purpose=email_change, email=new)`, `mail_notify.link_mail(kind="email_confirm", minutes=60, lang=lang_from_request)`, audit `email_change_requested` detail `to=<masked>`; always the message `settings.account.email_sent` with the address, and `mail.send_now(outbox_id)` as a background task when a mail was queued.
- `_email_confirm_page` 656-660: `account_email_confirm.html` with `Cache-Control: no-store` and `Referrer-Policy: no-referrer`; the template sets `lang_next = '/login'`, so the token never reaches the language form.
- `account_email_confirm_form` 663-669: `login_link.peek(t, (email_change,))` and `account_for` (`App/app/login_link.py` 140-160: the account is active and its address still differs): else 410 expired page.
- `account_email_confirm_submit` 672-713: `consume_blocked(ip_key)` (20 bad links per 15 minutes): 429 expired page; `consume` (spent once, compare-and-set), `account_for`, `email_taken`: else `record_consume_failure` and 410; `auth.set_account_email` (`App/app/auth.py` 728-749: new unverified address, `session_version` + 1, every open link of the account spent; a unique violation answers 410), `email_verified_at` now, audit `email_changed` detail `from=<masked> to=<masked> by=self` (no actor id: no `require_login`), `mail_notify.email_changed(notify_new=False)` (the notice to the old address), 303 `/login?notice=email_changed` with the session cookie cleared.

**What the new Go files do:**

- `account_email.go`: the three handlers, through the existing library (`session.LinkRequestBlocked`, `LinkRecordRequest`, `EmailTaken`, `IssueLoginLink`, `PeekLoginLink`, `ConsumeLoginLink`, `AccountForLink`, `LinkConsumeBlocked`, `LinkRecordConsumeFailure`, `SetAccountEmail`, `ClearSessionCookie`; `mail.QueueLinkMail`, `QueueEmailChanged`, `MaskEmail`; `clientip.Key`; the shell `acctRender` of brief 1505). The send after the redirect goes through 1505's `acctBackground` / `acctSendNow` hooks (a goroutine with `mail.SendNow` in production; the golden test records the id instead, as the Python script does).
- `acct_templates/account_email_confirm.tmpl`: the page (expired and confirm states).
- `account_email_test.go`: `TestAccountEmailGoldenDatabase` (35 cases through 1505's `runAccountGolden`), route rows.
- `App/scripts/auth_email_golden.py`: imports 1505's `auth_account_golden.py` (same seed, recording and normalisation) and writes `testdata/account_email.json`.

**Differences from Python, on purpose:**

1. The staging no-login and no-accounts bootstrap shortcuts of `current_user` / `require_login` are not ported (as in every route of `go/internal/web/auth`).
2. `mail.normalise_email` uses `email.utils.parseaddr`; Go uses the package's `normaliseEmail` (`go/internal/web/auth/account.go`), which takes the bare and the `Name <addr>` forms (both covered by golden cases) and refuses odder RFC 5322 forms that `parseaddr` would take. Fails safe: such an input gets `users.email.error.invalid`.

**Verified by the brief writer** in a throwaway worktree of 859d114d5 with brief 1505 applied and exactly these files and step 2's edits, PostgreSQL 16 on a disposable port: `gofmt -l` empty, `go build ./...`, `go vet ./internal/... ./cmd/...` clean, `go mod tidy -diff` empty; `go test ./internal/web/auth/ -count=1 -v`: every test PASS, 0 SKIP (including `TestAccountEmailGoldenDatabase`, 35 cases); the golden script run twice gives the same hash. Mutations caught: audit detail `to:`, session cookie not cleared, link minutes 15, the lede showing the token instead of the address, visitor default language English.

Anchors (step 0, each `grep -cF '<anchor>' <file>` prints 1):

| File | Anchor |
|---|---|
| `go/internal/web/auth/acct_shell.go` | `func (d deps) acctRender(w http.ResponseWriter, r *http.Request, p acctPage, at time.Time) error {` |
| `go/internal/web/auth/acct_shell.go` | `var acctBackground = func(f func()) { go f() }` |
| `go/internal/web/auth/account_golden_test.go` | `func runAccountGolden(t *testing.T, file string) {` |
| `go/internal/web/auth/account_setup.go` | `func (d deps) acctPageOr500(w http.ResponseWriter, r *http.Request, p acctPage, at time.Time) {` |
| `go/internal/web/auth/acct_i18n.json` | `"account.email_confirm.page_title": "Confirm your new login e-mail · UbyHost",` |
| `go/internal/web/auth/auth.go` | `{"POST /account/2fa/setup", "/account/2fa/setup", d.twoFactorSetupSubmit},` |
| `go/internal/web/auth/auth_test.go` | `t.Errorf("%d routes, want ` |
| `go/internal/mail/auth_queue.go` | `func QueueEmailChanged(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string, userID int64,` |
| `go/internal/session/accounts.go` | `func SetAccountEmail(ctx context.Context, db *pgxpool.Pool, userID int64, email string, now time.Time) error {` |
| `App/scripts/auth_account_golden.py` | `EMAIL_TOKEN = "golden-email-change-token-0123456789"` |
| `App/app/routes/admin_accounts.py` | `response = RedirectResponse("/login?notice=email_changed", status_code=303)` |

If one of the first seven anchors prints 0, brief 1505 has not run: STOP.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/auth/account_email.go` | create (copy) | the three handlers |
| `go/internal/web/auth/acct_templates/account_email_confirm.tmpl` | create (copy) | page |
| `go/internal/web/auth/account_email_test.go` | create (copy) | golden replay, route rows |
| `go/internal/web/auth/testdata/account_email.json` | create (copy, regenerated) | golden |
| `App/scripts/auth_email_golden.py` | create (copy) | writes the golden from Python |
| `go/internal/web/auth/auth.go` | edit (step 2 script) | three rows appended to the `Routes` slice |
| `go/internal/web/auth/auth_test.go` | edit (step 2 script) | route count + 3 |
| `docs/tasks/1506-report.md` | create | the report |

`docs/tasks/1506-files/` is part of this brief; do not edit it. No other file may change.

## 4. Steps

0. Checks (from the repo root, one call):

```bash
git status --short | tail -5; ls go/internal/web/auth/account_email.go go/internal/web/auth/account_email_test.go go/internal/web/auth/acct_templates/account_email_confirm.tmpl go/internal/web/auth/testdata/account_email.json App/scripts/auth_email_golden.py 2>&1 | grep -c 'No such file'
cd docs/tasks/1506-files && sha256sum -c <<'EOF' 2>&1 | tail -20
1171cb1b0f2ca72912de2cb035435964887290eb0e2d06111ada65df36e125d7  App/scripts/auth_email_golden.py.txt
81615fa8a06c38fcc0ea9bde102877c0e980716d85a03aedc1afe99d1f07bee7  go/internal/web/auth/account_email.go.txt
62fc8792c65e70f02c1742176b0162689cc89ea91ff620119883e2e7ae012285  go/internal/web/auth/account_email_test.go.txt
bad1e0178dcb297e45d6b74faed0d8d22e02c25dd09b5908017a9c70cfa450cb  go/internal/web/auth/acct_templates/account_email_confirm.tmpl.txt
2a0b01eaa78200c0356fddf830b8e9e49637ee5dbe24bb9225dcde9115cec7a3  go/internal/web/auth/testdata/account_email.json.txt
EOF
```

   Expected: `git status` prints nothing (other uncommitted files: STOP and ask), the `grep -c` prints `5`, then five `OK` lines. Then check each anchor of section 2 with `grep -cF '<anchor>' <file>` (one call, eleven commands joined with `;`): eleven `1`. Anything else: STOP (section 8). No commit for step 0.

1. Copy the five files (from the repo root), then build:

```bash
cd docs/tasks/1506-files && for f in $(find . -type f -name '*.txt' | sed 's|^\./||' | sort); do mkdir -p "../../../$(dirname "$f")"; cp "$f" "../../../${f%.txt}"; done; cd ../../..
git status --short --untracked-files=all | wc -l; cd go && gofmt -l internal/web/auth 2>&1 | tail -3; go build ./... 2>&1 | tail -5
```

   Expected: `5`, no gofmt or build output. Commit `1506 step 1`.

2. Register the routes and raise the route count (from the repo root). The rows go at the end of the `Routes` slice, after any rows other briefs added; the count goes up by 3 from whatever it is now:

```bash
python3 - <<'PY'
p = "go/internal/web/auth/auth.go"
s = open(p, encoding="utf-8").read()
start = s.index("\treturn []Route{\n")
end = s.index("\n\t}\n", start) + 1  # the line that closes the slice
rows = (
    '\t\t{"POST /account/email", "/account/email", d.accountEmailRequest},\n'
    '\t\t{"GET /account/email/confirm", "/account/email/confirm", d.accountEmailConfirmForm},\n'
    '\t\t{"POST /account/email/confirm", "/account/email/confirm", d.accountEmailConfirmSubmit},\n'
)
open(p, "w", encoding="utf-8").write(s[:end] + rows + s[end:])
PY
f=go/internal/web/auth/auth_test.go; n=$(grep -oE 'if len\(seen\) != [0-9]+ \{' $f | grep -oE '[0-9]+'); m=$((n+3)); sed -i "s/if len(seen) != $n {/if len(seen) != $m {/; s/routes, want $n\", len(seen))/routes, want $m\", len(seen))/" $f
grep -c 'd.accountEmailRequest}\|d.accountEmailConfirmForm}\|d.accountEmailConfirmSubmit}' go/internal/web/auth/auth.go; grep -n 'len(seen) !=\|routes, want' $f; git diff --stat | tail -3
cd go && gofmt -l internal/web/auth 2>&1 | tail -3; go vet ./internal/web/auth/ 2>&1 | tail -5; go test -count=1 ./internal/web/auth/ 2>&1 | tail -5
```

   Expected: `3`; two lines showing the same number, 3 higher than before (25 if no other brief than 1505 added routes); `git diff --stat` shows `auth.go | 3 +++` and `auth_test.go | 4 ++--`; no gofmt or vet output; `ok` (the database tests skip here; step 3 runs them). Commit `1506 step 2`.

3. PostgreSQL. If `UBYHOST_TEST_DATABASE_URL` is already set to a server you may create databases on, use it and skip the start. Else start a throwaway one (as root; `pg_ctl` refuses root, so it runs as `postgres`). Skip the start if it already runs (`su postgres -c '/usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg55506/data status' | tail -1` says `server is running`):

```bash
mkdir -p /var/tmp/pg55506 && chown postgres /var/tmp/pg55506 && su postgres -c '/usr/lib/postgresql/16/bin/initdb -D /var/tmp/pg55506/data -A trust >/dev/null && /usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg55506/data -o "-p 55506 -k /var/tmp/pg55506" -l /var/tmp/pg55506/log start' 2>&1 | tail -3
```

   Expected: `server started`. No PostgreSQL 16 binaries at that path: write "CI only" in the report and STOP before the test below. Then (from the repo root):

```bash
cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55506/postgres go test ./internal/web/auth/ -count=1 -v 2>&1 | grep -cE '^\s*--- SKIP'; UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55506/postgres go test ./internal/web/auth/ -count=1 -v -run 'TestAccountEmailGoldenDatabase|TestAcctEmailRoutesListed|TestAccountSetupGoldenDatabase|TestRoutesBuildWithoutPool' 2>&1 | grep -E '^(--- |ok|FAIL)' | tail -15
```

   Expected: `0` (no skipped test or subtest), then only `--- PASS` lines and `ok`. No commit when the tree is clean.

4. The golden script must reproduce the Python file (from the repo root). If `App/.venv/bin/python` is missing, first `cd App && python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt -r requirements-dev.txt 2>&1 | tail -5; cd ..`.

```bash
cd App && .venv/bin/python scripts/auth_email_golden.py 2>/dev/null | tail -3; cd .. && sha256sum go/internal/web/auth/testdata/account_email.json | tail -1 && git status --short | tail -5
```

   Expected: one `wrote go/internal/web/auth/testdata/account_email.json` line, the hash `2a0b01eaa78200c0356fddf830b8e9e49637ee5dbe24bb9225dcde9115cec7a3` (as in step 0), `git status` empty. A different hash: STOP (do not commit the regenerated file). No commit (nothing changed).

5. Run section 6. Write the report (section 9) and commit it as `1506 report`. Do not push or open a PR.

## 5. Do not touch

`go/internal/hostweb/`, `go/internal/session/`, `go/internal/mail/`, `go/internal/jobs/`, `go/internal/clientip/`, every existing file in `go/internal/web/auth/` except the two step-2 edits (brief 1505's files included: `acct_shell.go`, `acct_i18n*.`, `account_setup.go`, `account_golden_test.go` stay as they are), `go/cmd/ubyhost-web/`, `go/go.mod`, `go/go.sum`, `App/app/`, `App/scripts/auth_account_golden.py`, `deploy/` (no environment change, `UBYHOST_GO_PATHS` stays as it is), `docs/context/`, `docs/tasks/1506-files/`. Never print a secret, token, link or e-mail address. Rules 2, 3, 4, 5, 6, 7, 10 and 11 as in section 2.

## 6. Commands

From the repo root:

- `cd go && gofmt -l internal/web/auth 2>&1 | tail -5` prints nothing.
- `cd go && go build ./... 2>&1 | tail -30` prints nothing.
- `cd go && go vet ./internal/... ./cmd/... 2>&1 | tail -30` prints nothing.
- `cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55506/postgres go test ./internal/web/auth/... ./internal/session/... ./internal/mail/... ./cmd/ubyhost-web/... -count=1 2>&1 | tail -30` prints only `ok` lines.
- `cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55506/postgres go test ./internal/web/auth/ -count=1 -v 2>&1 | grep -cE '^\s*--- SKIP'` prints `0` (report this SKIP count).
- `cd go && go mod tidy -diff 2>&1 | grep -v downloading | tail -5` prints nothing.
- `cd App && .venv/bin/python -m pytest tests/test_go_auth_account.py -q --tb=short 2>&1 | tail -3` prints `2 passed`.
- `python3 scripts/context_lint.py 2>&1 | grep -v '^WARN' | tail -5` shows no error naming 1506.

Test-map: no row covers Go packages; the commands above are this brief's tests.

## 7. Acceptance

- [ ] `git log --oneline --grep='^1506 step'` lists steps 1 and 2 (and `git log --oneline --grep='^1506 report'` the report).
- [ ] `for c in $(git log --format=%h --grep='^1506 '); do git show --name-only --format= $c; done | sort -u` lists exactly the 8 files of section 3 (the report included) plus `docs/tasks/1506-go-auth-email-change.md` (the Status line): 9 lines.
- [ ] The copied files equal the sidecar: `cd docs/tasks/1506-files && for f in $(find . -type f -name '*.txt'); do cmp "$f" "../../../${f%.txt}"; done` prints nothing.
- [ ] `git show $(git log --format=%h --grep='^1506 step 2') -- go/internal/web/auth/auth.go | grep '^[-+]' | grep -v '^+++\|^---'` shows exactly the three `+` rows.
- [ ] Section 6 output exactly as stated, SKIP count 0.
- [ ] `for c in $(git log --format=%h --grep='^1506 '); do git show --name-only --format= $c; done | grep -E 'go\.mod|go\.sum|App/app/|hostweb/|cmd/ubyhost-web/|deploy/|docs/context/'` prints nothing.
- [ ] Report: "No screenshot: the Go page is proven equal to Python's HTML by `TestAccountEmailGoldenDatabase`; Go pages cannot be screenshotted yet (open item 7)."

## 8. Stop and ask

Stop, and write the report, if:

- an anchor is not found, a file to create exists, a sha256 differs, or the regenerated golden has another hash;
- a test fails twice (never change the code: it is fixed by hash);
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside section 3 needs a change;
- section 5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1506-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (the section 7 file list).
2. Each command, with the last 5 lines of its output, and the SKIP count.
3. Section 7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

Read the full diff of:

- `go/internal/web/auth/account_email.go`: the gates of `accountEmailRequest` in Python's order (CSRF, login, impersonation, freshness, address, rate limit) and that a taken address gets the same redirect with no token, no mail and no audit (no account enumeration); `accountEmailConfirmForm` changes nothing (a mail scanner opening the link must not confirm); `accountEmailConfirmSubmit` spends the token before anything else can use it, records a failure for every bad or stale link, changes the address only through `session.SetAccountEmail` (session version bump, open links spent) and clears the session cookie; `no-store` and `no-referrer` on every confirm page; nothing logs an address or token.
- `go/internal/web/auth/acct_templates/account_email_confirm.tmpl`: the token only in the hidden field, escaped; the language form posts `next=/login`.
- `go/internal/web/auth/auth.go`: three rows appended, nothing else.

Verified by the brief writer: see section 2.

## Owner steps

1. Nothing for this brief alone: it merges with the one big PR and changes nothing in production.
2. Before switching: (a) brief 1502's owner steps must have given the `ubyhost-go` service `UBYHOST_TRUSTED_PROXY_CIDRS` (else every visitor shares one rate-limit bucket, and 20 bad links from anyone would block every confirm for 15 minutes); (b) decide how the confirm mail leaves: the `ubyhost-go` service gets no SES settings today (`deploy/lightsail/docker-compose.yml`, service `ubyhost-go`: "no SES/AWS"), so Go's immediate send fails and the row waits for the outbox drain's retry, a delay of minutes. Either add `UBYHOST_AWS_ACCESS_KEY_ID`, `UBYHOST_AWS_SECRET_ACCESS_KEY`, `UBYHOST_SES_REGION` and the sender settings to that service (the same decision brief 1502's login links need), or accept the delay.
3. Then add `/account/email /account/email/confirm` to `UBYHOST_GO_PATHS` in the server's `.env`, run `deploy.sh`, change the login address of a test account in Settings, open the link from the mail, press the button, and check you are sent to log in with the new address. To go back, remove the two paths and run `deploy.sh` again.
