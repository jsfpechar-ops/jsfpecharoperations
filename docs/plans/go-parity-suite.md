# Go parity suite: results and go/no-go per wave

Run 2026-11-15 on `main` (`45c0180`) with PR #1036 (mail and door_codes jobs) and PR #1037 (passkeys) merged into a scratch copy. Nothing touched production: Postgres 16 on a throwaway port, Python on 8101, Go on 8102.

## What the suite is

| Piece | File | Question it answers |
|---|---|---|
| Route inventory | `scripts/py_routes.py` | Which `METHOD /path` does Python have (341)? Read from source, no venv. |
| Handler check | `scripts/go_parity_check.py --paths "<UBYHOST_GO_PATHS value>"` | For every Python `METHOD /path` that a Caddy entry catches, does the real Go mux have a handler? Fails on a missing POST even when GET exists, and on a Go wildcard that only looks like a handler (`GET /apartments/{id}/guide/{item}` also catches Python `.../guide/questions`). `--all` prints the whole matrix. |
| Job kinds | `scripts/go_jobs_parity.py` | Does Go register every Python job kind with the same interval? |
| Differential e2e | `scripts/e2e/diff_harness.py` (+ `seed.py`) | Same requests to Python and Go, each on its own clone of one seeded Postgres. Diffs status, redirect, headers, cookie flags, amounts and invoice numbers, then the table contents. |
| Preflight | `scripts/go_switch_preflight.sh "<entries>" [--e2e]` | Runs the first two, and the harness with `--e2e`. Run it before every change to `UBYHOST_GO_PATHS`. |

Run the harness (needs the Postgres binaries and the app venv, about 6 minutes):

    /var/tmp/ubyvenv/bin/python scripts/e2e/diff_harness.py --report out.json          # everything
    ... --go-paths "/predplatne /predplatne/*"                                          # only what Caddy would send to Go

It exits 1 on any hard difference. Hard: status, `Location`, `Content-Disposition`, content type of a 2xx, Set-Cookie names and flags, amounts or invoice numbers on a page, any table row that differs afterwards, a failed DB expectation. Soft (counted, not failing): body text, other headers, Python-only crashes, both sides 5xx, Go answering 501 "not ported" (Caddy sends a GET back to Python).

The seed data is the billing golden (12 users, about 70 platform invoices with a voided invoice and its storno, overdue and paid ones), plus host `h1` with an apartment, three real platform invoices (stored PDF), a legal entity and three host invoices, host `h2` and `h3` with TOTP, and the admin.

## Results

| Area | Cases | Result |
|---|---|---|
| Go unit tests (`go test ./...`, 50 DB tests on Postgres) | all | pass |
| Python golden and parity tests (113 on Postgres, 11 SQLite-only) | 124 | pass; 1 fails only because this container runs Python 3.13 (reason phrase "Unprocessable Content", prod is 3.12) |
| Job kinds | 15 | 15 of 15 in Go **with #1036**; `main` alone has 13 (no `mail`, `door_codes`) |
| Handler check, every wave path list below | 11 lists | 0 missing with #1037 (W5g) and the rest on `main` |
| Route sweep: every Go-handled route x anon, empty host, host with billing data, admin; POST with no CSRF, valid CSRF and empty body, valid CSRF and a foreign Origin | 1,640 | 0 hard differences |
| Login link (valid, replay, bad token, no CSRF), TOTP (wrong, tampered pending token, empty, right, recovery code, replay, 7 wrong codes then 429), logout | about 40 | same |
| Passkeys: software authenticator registers and logs in on both servers; bad origin, replayed challenge, bad signature, unknown credential, another host's passkey | 12 | same |
| Platform invoices: mark paid and storno as admin, owner, other host, anonymous; double submit; paid, storno and deleted-workspace invoices; PDF and ZIP downloads; IDOR on invoice PDFs | 38 | same, and the DB expectations hold on both (one paid, one voided with exactly one storno) |
| Host invoices: list, detail, PDF, mark paid, cancel with and without a reason, other host, anonymous, public `/invoice/d/<token>` | 29 | same, same table rows afterwards |
| Stripe webhook: valid signature, duplicate event id, wrong signature, old timestamp, altered body, missing header | 6 | same (200, 200, 400, 400, 400, 400) |
| `next=` open redirects (`//evil`, `https://evil`, `/\evil`, `%2F%2Fevil`, `javascript:`) on `/login`, `/account/accept` | 18 | same, none leave the site |
| Python and Go mixed (a cutover serves one user from both): Go session cookie on Python and the reverse, CSRF token and nonce from one side's form posted to the other, 2FA pending token from Go finished on Python | 7 | pass |
| Table contents after the run (platform_invoice, invoice, billing_account, audit, login_token, user_account, legal_acceptance, email_outbox, stripe_webhook_event, passkey, and the row count of every other table) | 10+ | identical |

Total 1,832 harness cases, 0 hard differences; 433 soft (373 body text such as whitespace, a 5-character difference on most pages; 127 content type on redirect bodies).

## Findings

| # | Where | What | Impact | Status |
|---|---|---|---|---|
| F1 | Python `admin_billing.html` line 22 | A misplaced bracket made the "watch" row two columns instead of three. `/admin/fakturace` returned 500 as soon as any invoice was overdue. | None today (W3 runs on Go). A rollback of W3 to Python would have shown a 500 on the admin billing page. | **Fixed in this PR** with a test that fails without the fix. |
| F2 | Python, several JSON endpoints | `POST /account/push/*`, `/account/passkeys`, `/login/passkey` with a form body, and `POST /stay-fees/<unknown id>/paid`, answer 500; Go answers 400 or 303. | None for cutover (Go is stricter). | Not fixed. |
| F3 | Go push device delete | Redirects to `/settings#settings-group-phone`; Python to `/settings/phone`. | Cosmetic (both end on the phone settings). Accepted, listed as K1 in the harness. | Open |
| F4 | Go settings switches | Audit rows for `guest_details_mail_*` and `stay_fee_emails_*` carry the username in the actor column; Python writes `host` (username only in the detail). | Audit reading only. The harness masks this column for those four actions. | Open |
| F5 | Go routes `GET /apartments/{id}/guide/{item}` and `POST .../{item}/{action}` | Also catch Python's `guide/questions` routes. | Only if `/apartments/*` is ever added to `UBYHOST_GO_PATHS` (it must not be). The handler check reports it. | Open |
| F6 | Go cleaning shared page, 404 case | `Referrer-Policy: strict-origin-when-cross-origin` and `Cache-Control: no-store` where Python sends `no-referrer` / `no-store, private`. The 200 page is correct. | Low (404 for an invalid token). | Open |
| F7 | Go `/p/{slug}/thanks`, `/terms/booking` for a logged-in host | Public layout without the host chrome (Python shows the host menu). | Cosmetic. | Open |
| F8 | Container, not code | A venv built from `requirements.txt` instead of `requirements.lock` installs different versions; Python 3.13 changes one reason phrase. | Only the test environment. | Noted |

## Independent review

An Opus reviewer read the first version of the harness and found 22 gaps. The ones that mattered were true of that version: the CSRF token was empty for every logged-in user, so no POST got past the CSRF check; nothing compared database state; body differences never failed; no money mutation ever succeeded; the Stripe signature was never checked; Python and Go were never mixed; no ownership test used real objects. All of those are fixed in the version described above (the numbers above come from it). Still open from its list:

- Not run behind Caddy: no `X-Forwarded-Proto`, no real Caddyfile, so the `Secure` cookie flag, absolute URLs in mail and the path matcher itself are not exercised. `go_parity_check.py` copies Caddy's matching rules.
- No session fixation check, no remember-me (`Max-Age`) comparison, no impersonation flow, no rate limit shared across the two processes (the limiter is in the database, so it is shared in production; here each side has its own database).
- No successful `POST /signup` (the form fields need the Turnstile bypass), no valid bank statement upload, no `/predplatne/zmena|zrusit` with a valid body, no VAT-payer invoice.
- Jobs: only names and intervals are compared; the Go job unit tests and goldens pass, but no job ran on the same queue fixture in Python and Go and had its mail diffed.
- Stay fees: no stay-fee fixture (apartment, reservation, guest pay), so `/stay-fees*` was checked for routes, auth, CSRF and ownership only.
- Havel and Leon: routes, auth and CSRF only; the AI calls were not made.
- Browser-level behavior and real authenticators (Face ID, Windows Hello).

## Go or no-go per remaining wave

"Go" means the tests give no reason to wait; each still needs Josef's usual browser check and the rollback line ready.

| Wave | Verdict | Why |
|---|---|---|
| W5g passkeys (`/login/passkey /login/passkey/options /account/passkeys /account/passkeys/*`) | **Go once #1037 is merged and deployed** | 6 of 6 handlers present. A full register and login ceremony behaves the same on both servers, including replay, bad signature, bad origin, unknown credential and another host's passkey. A Go session works on Python and the reverse. `ubyhost-go` gets `UBYHOST_PUBLIC_BASE_URL` in compose (WebAuthn needs an https host there). Not tested: a real device. #1033 (button wording) is a separate, held PR. |
| W8b Havel and Leon setup | **No-go until the two budget variables are set** | Routes, auth, CSRF and ownership match (8 of 8 handlers). The runbook stops on `UBYHOST_AI_MONTHLY_USD_HAVEL` and `_LEON` missing, and the AI answers themselves were not compared. The "Python ran a week" condition is Josef's call. |
| W9 `/invoice/d/*`, `/invoices/*.pdf`, `/invoices/*/paid`, `/invoices/*/cancel` | **Go** (one path per run, Josef's rollback test after each) | Real host invoices: PDF 200 for the owner and a login redirect for others, public download token valid and garbage, paid and cancel make the same table rows, double cancel makes one storno, foreign host and missing CSRF change nothing. |
| W9 `/invoices/preview`, `/invoices/new`, `/invoices` | **No-go until a stay fixture is added** | Issuing an invoice needs a finished stay; only empty-body requests were tested. These are last in the runbook order anyway. VAT-payer invoices were not tested. |
| W10 step 2 `/stay-fees/*/guest-pay-preview` | **No-go** | Waits for Josef's `UBYHOST_STAY_FEE_GUEST_PAY` decision, and no stay-fee fixture ran. |
| W10 step 3 `/stay-fees` | **No-go until a stay-fee fixture run** | Handlers present, golden tests pass, but no live comparison with data. A fixture (apartment, reservation, rates) is the next piece to add. |
| J2 `stay_fee_mail` job | **No-go until W10 is done** | Kind and interval match, Go tests pass; no queue-fixture run in both languages. The runbook already requires W10 steps 1 to 3 first. |
| S scheduler | **Go once #1036 is deployed** | With #1036 Go has all 15 kinds with Python's intervals (without it only 13, and `UBYHOST_SCHEDULER=go` would log kinds=13). Scheduler and switch tests pass. Check `scheduler started owner=go kinds=15` after the switch; not tested: both schedulers enqueuing at once (the one-open-row index is the guard). |

Money and login waves were reviewed by an independent Opus pass as asked; its remaining points are the list above.

## Reading the soft differences

Body text differs on most pages by a few characters (whitespace, an HTML attribute order). Pages where amounts or invoice numbers differ are hard failures and there are none. Use `--report out.json` and filter `soft` when a page needs a closer look; the byte-equal goldens (`App/tests/test_go_*_golden.py`) remain the strict check for page text.
