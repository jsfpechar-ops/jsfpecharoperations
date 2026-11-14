# 1624: Go mail unsubscribe page, part 2 (GET and POST /mail/unsubscribe/{token})

Status: todo
Depends on: [1623](1623-go-public-unsubscribe-golden.md) | Base commit: none (one-big-PR mode) | Branch: current branch
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens (about 15 calls)

> **One big PR mode.** Work on the current branch. After each step that changes a file, commit with `git add -A <the files of the step> && git commit -m "1624 step k"`. Never create a branch, never push, never open a PR. Acceptance checks use `git log --oneline --grep='^1624 step'` and `git show --stat` on those commits, not a fixed base commit.

## 1. Objective

Serve `GET` and `POST /mail/unsubscribe/{token}` (Python `mail_unsubscribe.py`, `mail_unsubscribe.html`, `auth_base.html`) from `go/internal/web/public`: the same signed-token check, the same rate limit, the same rows written (opt-out flag, `mail_suppression`, audit line), the same page in every state, with no login and no JavaScript needed. Tier B: it changes a mail preference. The code is dormant until the owner lists `/mail/unsubscribe/*`.

## 2. Context

Rules (AGENTS.md): 1 filing is not touched; 2 privacy: the page loads no analytics and no outside script (it is not on `analytics.PUBLIC_ANALYTICS_TEMPLATES`; `TestUnsubLoadsNothingFromOutside` sets a PostHog key and checks nothing changes), no new cookie beyond the two Python sets (`ubyhost_csrf`, `ubyhost_lang`), no new outbound request; 4 no new dependency; 5 plain PostgreSQL, the Python SQL with `$n` placeholders, no schema change; 6 light mode only, the button is a plain form post; 7 and 10 screenshots (steps 8 to 10); 8 never push to `main`; 11 Go first.

**PR text (hard rule 2):** no new outbound request and no new personal-data field. The routes read and write the rows Python writes: `user_account.onboarding_emails_opt_out(_at)`, `mail_suppression` (a keyed hash of the address, never the address), one `audit` line, and `rate_limit_event` (the visitor's address and scope, purged by the existing retention step `rate_limit_events`). No retention line changes.

**Behaviour that must not change (from `mail_unsubscribe.py`):**

- GET shows the page with one button and changes nothing, so a link scanner cannot unsubscribe a host. It checks the rate limit first (30 views per hour per address; a blocked address gets 429 and is not counted again), then counts the view, then reads the token: forged or unknown account: 404 page; already opted out: the confirmation.
- POST works for any valid token with no rate check and no CSRF check (RFC 8058 one-click posts come from the mailbox provider with no cookie and no form token). It suppresses the address hash from the token (when it has one, scope `onboarding`), sets the account's flag and writes `audit` (`actor` `unsubscribe_link`, action `onboarding_emails_opted_out`, owner = the account) only when the flag changed. Only a failed attempt is counted; past the limit it answers 429.
- Token: `itsdangerous.URLSafeSerializer`, salt `ubyhost-lifecycle-unsubscribe`, no expiry, over `{"u": id, "h": hash}` (`lifecycle_mail.read_unsubscribe_token`); `unsub_token.go` reads it (the writer is `go/internal/lifecyclemail`, read-only here). `TestUnsubTokenFromGo` reads tokens from Python and from Go and rejects six forgeries.
- Page: the whole `auth_base.html` shell (language form posting to `/language`, env banner, `?notice=` line, "not you" logout form for a signed-in host, footer links, hero panel). A signed-in host without a language choice gets English, a visitor Czech, `vi` is kept. The CSRF token and cookie follow `security.csrf_token` (the Go copy is `csrfToken` in `unsub_page.go`; `go/internal/hostweb/layout` has an unexported twin).

Deviations from Python (say them in the PR text): the POST writes its rows in one transaction (Python commits each statement alone); nothing else.

Caddy and paths: Python serves exactly `GET` and `POST` on `/mail/unsubscribe/{token}` and Go serves both, so `/mail/unsubscribe/*` is fully served by Go once listed. Assumed: it is not in `UBYHOST_GO_PATHS` yet. Nothing goes live on deploy. A tip mail sent by the Go mail job already links to this path with `?lang=`.

Database tests: they need `UBYHOST_TEST_DATABASE_URL` (CI sets it; each test makes and drops its own database from the migrations). Without it they skip.

Anchors (Phase 0 checks them; if one is missing, STOP, §8):

- `go/internal/web/public/golden_test.go`: `type goldenCookie struct`, `func normalize(s string) string`, `func firstDiff(`, `func around(`, `func itoa(` (5 lines)
- `go/internal/web/public/public.go`: `func supportedLanguage(`, `appDefault `, `publicDefault `, `func loadConfig(`; `render.go`: `langCookieMaxAge`
- `go/internal/lifecyclemail/token.go`: `func UnsubscribeToken(`, `func EmailHash(`; `go/internal/secure/signer.go`: `func NewTimedSerializer(`; `go/internal/session/`: `func UTCNow(`
- `go/cmd/ubyhost-web/register_web_public.go`: `for _, path := range public.Paths {`

## 3. Files

| sha256 | file (repo path; sidecar = `docs/tasks/1624-files/<path>.txt`) | action | lines |
|---|---|---|---|
| `f6dc780e2a5e90a3d54285d8c5345fbe27f337c42c405b2e243b1c3f0c28676c` | `go/internal/web/public/templates/unsub/unsubscribe.tmpl` | create | 107 |
| `64937c22ea02b6ee6d20c1cc71affb21ef6f5265a25c61b430c1171ae3c7e34e` | `go/internal/web/public/unsub_page.go` | create | 285 |
| `092cdad702650767257f1ffd6540e50241d54056f5ca0022fa93939a531cf17e` | `go/internal/web/public/unsub_shots_test.go` | create | 25 |
| `5280cfd2d2a16f7046f8dc71825c484b3ca1335a35d9c54112819c674f631cb6` | `go/internal/web/public/unsub_store.go` | create | 129 |
| `06b00ae05d7598287cb0b1104f74eb132271be451f565a507c63e9538000e10d` | `go/internal/web/public/unsub_test.go` | create | 478 |
| `3d3492b6004a411a265fb0380171fa1187466442fa4f6533da231b0be8f3e722` | `go/internal/web/public/unsub_token.go` | create | 77 |

Edited: `go/cmd/ubyhost-web/register_web_public.go` (step 4: one block of lines before the `for` loop), `docs/tasks/1624-go-public-unsubscribe.md` (`Status:` line only). New: `docs/tasks/1624-report.md`. Screenshots go to `/mnt/project-files/ux-shots/public-unsubscribe/` (outside the repo).

No other file may change.

## 4. Steps

Work from the repo root unless a step says `go/` or `App/`. Stay on the current branch.

### Phase 0: check (1 call)

0. Run:
```bash
ls go/internal/web/public/catalog_unsub.json go/internal/web/public/testdata/unsub/cases.json; cd go/internal/web/public && grep -c -E 'type goldenCookie struct|func normalize\(s string\) string|func firstDiff\(|func around\(|func itoa\(' golden_test.go; grep -c -E 'func supportedLanguage\(|appDefault +=|publicDefault +=|func loadConfig\(' public.go; grep -c 'langCookieMaxAge' render.go; grep -c -E 'func UnsubscribeToken\(|func EmailHash\(' ../../lifecyclemail/token.go; grep -c 'func NewTimedSerializer(' ../../secure/signer.go; grep -rc 'func UTCNow(' ../../session/ | grep -v ':0'; grep -c 'for _, path := range public.Paths {' ../../../cmd/ubyhost-web/register_web_public.go
```
Expected: the two paths printed, then `5`, `4`, a number of at least `1`, `2`, `1`, one line `...:1`, `1`. Anything else (also a missing `catalog_unsub.json`: brief 1623 has not run): STOP.

### Phase 1: copy (1 call)

1. Copy the sidecars into place and check them. From the repo root:
```bash
cd docs/tasks/1624-files && for f in $(find . -name '*.txt' | sed 's|^\./||; s|\.txt$||'); do mkdir -p "../../../$(dirname "$f")" && cp "$f.txt" "../../../$f"; done; cd ../../.. && sha256sum -c - <<'EOF'
f6dc780e2a5e90a3d54285d8c5345fbe27f337c42c405b2e243b1c3f0c28676c  go/internal/web/public/templates/unsub/unsubscribe.tmpl
64937c22ea02b6ee6d20c1cc71affb21ef6f5265a25c61b430c1171ae3c7e34e  go/internal/web/public/unsub_page.go
092cdad702650767257f1ffd6540e50241d54056f5ca0022fa93939a531cf17e  go/internal/web/public/unsub_shots_test.go
5280cfd2d2a16f7046f8dc71825c484b3ca1335a35d9c54112819c674f631cb6  go/internal/web/public/unsub_store.go
06b00ae05d7598287cb0b1104f74eb132271be451f565a507c63e9538000e10d  go/internal/web/public/unsub_test.go
3d3492b6004a411a265fb0380171fa1187466442fa4f6533da231b0be8f3e722  go/internal/web/public/unsub_token.go
EOF
```
Expected: `: OK` for all 6 files, no `FAILED`. Never retype or edit a copied file.

Commit: `git add -A go/internal/web/public && git commit -m "1624 step 1"`.

### Phase 2: format, vet, tests without a database (2 calls)

2. From `go/`: `gofmt -l internal/web/public; go vet ./internal/web/public/ 2>&1 | tail -5`. Expected: no output.
3. From `go/`: `go test ./internal/web/public/ -count=1 -v -run 'TestUnsubTokenFromGo|TestCSRFTokenBinding|TestUnsubEveryActionEscapes' 2>&1 | grep -E '^(--- |ok|FAIL)' | tail -8`. Expected: `--- PASS` for the three, then `ok`.

### Phase 3: register the routes (2 calls)

4. In `go/cmd/ubyhost-web/register_web_public.go`, find (verbatim):
```go
		for _, path := range public.Paths {
```
and replace it with:
```go
		unsub := public.UnsubDeps{Pool: pool, Getenv: os.Getenv, SignedIn: deps.SignedIn}
		mux.Handle("GET /mail/unsubscribe/{token}", m.wrap("/mail/unsubscribe/{token}", public.UnsubscribeForm(unsub)))
		mux.Handle("POST /mail/unsubscribe/{token}", m.wrap("/mail/unsubscribe/{token}", public.UnsubscribeSubmit(unsub)))
		for _, path := range public.Paths {
```
What changes for live traffic: nothing yet (Caddy sends `/mail/unsubscribe/*` to Go only when it is listed in `UBYHOST_GO_PATHS`).
5. From `go/`: `gofmt -l cmd internal/web/public; go build ./... 2>&1 | tail -5; go vet ./internal/web/public/... ./cmd/ubyhost-web/... 2>&1 | tail -5; go test ./internal/web/public/... ./cmd/ubyhost-web/... -count=1 2>&1 | tail -8`. Expected: no output from the first three, then `ok` for both packages (the database tests skip without `UBYHOST_TEST_DATABASE_URL`). Commit: `git add -A go/cmd/ubyhost-web/register_web_public.go && git commit -m "1624 step 5"`.

### Phase 4: database tests and screenshots (5 calls)

6. Database tests. Optional, if a local PostgreSQL 16 is at `/usr/lib/postgresql/16`: start one as the postgres user with its data directory outside `/tmp/claude-0` (for example `/var/tmp/pg1624`, port `55624`; `initdb -D /var/tmp/pg1624/data -A trust -U postgres`, then `pg_ctl ... -o "-p 55624 -k /var/tmp/pg1624 -c listen_addresses=127.0.0.1"`), then from `go/`: `UBYHOST_TEST_DATABASE_URL='postgresql://postgres@127.0.0.1:55624/postgres?sslmode=disable' go test ./internal/web/public/ -count=1 -v -run 'TestUnsub' 2>&1 | grep -E '^(--- |ok|FAIL)' | tail -8`. Expected: `--- PASS: TestUnsubGolden`, `TestUnsubSignedInHost`, `TestUnsubLoadsNothingFromOutside`, `TestUnsubTokenFromGo`, `TestUnsubEveryActionEscapes`, then `ok`. Without PostgreSQL write "DB tests: CI only" in the report and skip steps 7 to 10.
7. Start the screenshot server in the background (same `UBYHOST_TEST_DATABASE_URL`): from `go/`, `PUBLIC_UNSUB_SHOTS_ADDR=127.0.0.1:8766 go test -run TestServeUnsubscribeForScreenshots -count=1 -timeout 0 ./internal/web/public > /var/tmp/shots-unsub.log 2>&1 &` then `sleep 10; curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8766/mail/unsubscribe/x`. Expected: `404` (a forged token shows the 404 page).
8. Write `/var/tmp/unsub_shots.py` with exactly this content and run it from the repo root: `App/.venv/bin/python /var/tmp/unsub_shots.py http://127.0.0.1:8766 /mnt/project-files/ux-shots/public-unsubscribe 2>&1 | tail -12`. Expected: 9 lines, each ending `ok` (a `horizontal-overflow` line is a finding: report it).
```python
import json
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

base, out = sys.argv[1], Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)
tokens = json.load(open("go/internal/web/public/testdata/unsub/cases.json"))["tokens"]
with sync_playwright() as p:
    browser = p.chromium.launch()
    for width in (390, 768, 1280):
        for state in ("form", "done", "invalid"):
            token = tokens["forged"] if state == "invalid" else tokens["host"]
            page = browser.new_page(viewport={"width": width, "height": 900})
            page.goto(f"{base}/mail/unsubscribe/{token}?lang=cs", wait_until="networkidle")
            if state == "done":
                page.click("button.auth-submit")
                page.wait_for_load_state("networkidle")
            overflow = page.evaluate("document.documentElement.scrollWidth > window.innerWidth")
            page.screenshot(path=str(out / f"{state}-{width}.png"), full_page=False)
            print(state, width, "horizontal-overflow" if overflow else "ok")
            page.close()
    browser.close()
```
9. Open the three `-390.png` files with Read and write one line per page in the report: what you saw (logo, language buttons, title, the button or message; anything cut off or overlapping).
10. Stop the server and, if you started PostgreSQL, stop it and delete its directory: `pkill -f TestServeUnsubscribeForScreenshots; echo stopped`.

### Phase 5: lint and report (1 call)

11. From the repo root: `python3 scripts/context_lint.py 2>&1 | grep -v '^WARN' | tail -5`. Expected: no line naming a 1624 file. Write the report, set `Status: review`, commit `1624 step 11`.

## 5. Do not touch

Every file not in §3, in particular `go/internal/lifecyclemail/` (owner: the mail thread), `go/internal/hostweb/`, `go/internal/session/`, `go/internal/secure/`, the legal and marketing pages' files in `go/internal/web/public/`, `App/app/`. Hard rules 2, 4, 5, 6, 8.

## 6. Commands

Steps 2, 3, 5 and 6 are the test commands. No Python tests: nothing in Python changed.

## 7. Acceptance

- [ ] Step 1 printed `: OK` for all 6 files.
- [ ] Step 3 shows three `--- PASS` and `ok`; step 5 shows `ok` twice.
- [ ] Step 6 shows `--- PASS: TestUnsubGolden` (or the report says "DB tests: CI only").
- [ ] `git log --oneline --grep='^1624 step'` lists steps 1 and 5 (and 11); the step 5 commit changes only `register_web_public.go`.
- [ ] 9 PNGs in `/mnt/project-files/ux-shots/public-unsubscribe/`, all `ok`, one line per page in the report (or "DB tests: CI only" and no screenshots).

## 8. Stop and ask

Stop, and write the report as `Status: blocked`, if:

- a Phase 0 check or an anchor does not give the expected result;
- a `sha256sum -c` line says FAILED;
- a test fails twice (read the last 30 lines, fix once, rerun);
- you reach 25 tool calls or about 50k tokens (write `Done: steps 1 to k. Left: steps k+1 to n.`);
- a new dependency, a schema change or a file outside §3 seems needed;
- a step is unclear.

## 9. Report

Write `docs/tasks/NNNN-report.md` (600 tokens at most) and set `Status: review`. The report has: 1. the files changed (`git show --stat` of the `NNNN step` commits); 2. each command with the last 5 lines of its output; 3. §7 ticked; 4. Deviations; 5. Questions; 6. Owner steps left.

## Risk list (for the reviewer)

Read: `unsub_store.go` (the SQL: `unsubscribe` writes the flag, the suppression and the audit line), `unsub_token.go` (signature check before anything is trusted), `unsub_page.go` (`UnsubscribeSubmit`: no CSRF and no rate check for a valid token, on purpose), `go/cmd/ubyhost-web/register_web_public.go` (the only existing file that changes). The page itself is pinned by 21 golden cases.

## Owner steps

None in this brief. The switch is a separate step the orchestrator writes: `UBYHOST_GO_PATHS` gets `/mail/unsubscribe/*` (`docs/ENVIRONMENT.md`, row `UBYHOST_GO_PATHS`). Do it only after the mail job's links have been checked once on staging.
