# 2042: V2 visual parity, part 3: guest and token-link pages, and the pre-deploy gate command

Status: todo
Depends on: 2040, 2041 | Base commit: HEAD | Branch: current
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 100k tokens (stop at 25 calls; see section 8)

## 1. Objective

Compare every page a guest sees through a token link (stay hub, claim steps, guest form, guide,
Leon, PIN page, payment QR) plus the other token-link pages that need no login (cleaner share,
booking manage, mail unsubscribe), cs and en, 390/768/1280 px, each state with the cookies a real
visitor would have. Then document one aggregate command that fails on any visible difference, for
use as a pre-deploy gate. **Do not fix visible differences.** Tooling, seed, run, report.
Fully anonymous pages (landing, login, legal, signup, public guides) stay out of scope.

## 2. Context

- A guest has no login. State lives in two signed cookies, both signed with `UBYHOST_SECRET_KEY`
  (same value for both stacks in the audit env) and read by both stacks with the same salt:
  `ubyhost_claim` = `URLSafeSerializer(secret, salt="ubyhost-guest-claim").dumps({"<reservation_id>": <token_version>})`
  (`App/app/routes/guest.py` `_claim_serializer`, `_remember_claim`; Go: `go/internal/web/guest/pick_cookies.go`
  `claimCookieSalt`), and the "owned" cookie (`salt="ubyhost-guest-owned"`, `_claim_serializer` neighbour at guest.py:108).
  The claim state itself is in table `reservation_claim` (`state`: unclaimed | provisional | claimed;
  `token_version`; `claimed_at`). `claim.ensure_row(reservation_id)`, `claim.is_claimed(row)`.
- `capture_png` / `run_case` in `App/scripts/go_page_parity_screenshots.py` take exactly one cookie
  (`cookie_name`, per-stack value). Guest states need several cookies, so this brief adds an
  `extra_cookies` list (same for both stacks).
- The PIN page appears only with `UBYHOST_GUEST_PIN=1`, read once at import (`audit.PIN_ENV`), so it
  needs its own run with its own servers (`PARITY_PIN=1`).
- Tokens: apartment `permalink_token` (`refs["token"]`), `payment_request.guest_token(row)`,
  `cleaning.new_share(...)` token, `lifecycle_mail.unsubscribe_token(...)`, booking manage token
  (grep `booking_manage` in `App/app/routes/property_page.py:503` for how the token is built).
- Every guest page runs under a fresh DB state: claim state changes must be set by SQL before the run
  and must not be changed by the page render (the pages are GET only; the form POSTs are not exercised).
  Reading `/l/{tok}/{res}/claim` may spend a secret: use a fresh secret per stack (see step 4).

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/scripts/go_page_parity_screenshots.py` | edit | `extra_cookies` in `capture_png` and `run_case` |
| `scripts/e2e/seed_parity_guest.py` | new | guest persona rows, prints a JSON of ids and cookies |
| `scripts/e2e/parity_cases.py` | edit | append `GUEST_CASES` (group H) |
| `scripts/e2e/page_parity_visual.py` | edit | guest seed hook, `PARITY_PIN=1`, per-case cookie lists, `--gate` mode |
| `scripts/e2e/parity_gate.sh` | new | the aggregate command (step 8) |
| `docs/tasks/2042-report.md` | write | verdict table, visible causes, gate command, exclusions |

Never touch `App/app/**`, `go/**`, `scripts/e2e/seed.py`.

## 4. Steps

1. Environment: `cd /home/user/jsfpecharoperations && source scripts/e2e/parity_env.sh 2>&1 | tail -3; ls scripts/e2e/parity_cases.py; grep -n 'EXTRA_CASES' scripts/e2e/parity_cases.py | head -2`.
   If missing, stop (2040/2041 not on this branch; 2041 missing is allowed, only skip its placeholders).
2. Edit `App/scripts/go_page_parity_screenshots.py` (anchors `def capture_png(`, `cookies = []`, `def run_case(`):
   - `capture_png(..., extra_cookies: list[tuple[str, str]] | None = None)`: after the existing `cookies.append(...)` block add
     `for n, v in (extra_cookies or []): cookies.append({"name": n, "value": v, "url": base + "/"})`.
   - `run_case(..., extra_cookies=None)`: pass `extra_cookies=extra_cookies` to both `capture_png` calls.
   - The existing `if cookie_name and cookie_value:` stays unchanged, so old callers behave the same.
   Test (test-map row for this file): `cd App && .venv/bin/python -m pytest tests/test_go_page_parity_screenshots.py -q --tb=short -x 2>&1 | tail -30` green.
3. Learn the guest routes, 4 greps/reads (each at most 60 lines):
   `sed -n 1407,1454p App/app/routes/guest.py` (hub: when `pick` vs `unavailable`),
   `sed -n 1455,1480p App/app/routes/guest.py` (demo PIN page),
   `sed -n 1612,1643p App/app/routes/guest.py` (claim landing: what query/secret it needs),
   `grep -n -B2 -A25 '^def start_claim' App/app/claim.py | head -60` (how a claim secret and `token_hash` are created).
4. Create `scripts/e2e/seed_parity_guest.py` (run from `App/` on `parity_run`, args `owner_user_id apartment_id`; same style as 2041's extra seed; every block in try/except printing `{"skipped": ...}` to stderr). It creates synthetic rows only (`Parity Guest`, `*@e2e.test`), uses `db.insert` / `db.execute`, and for each guest state a separate reservation of the same apartment (dates in the next 30 days, `uid` `e2e-guest-<state>`):
   | key | state to build |
   |---|---|
   | `res_unclaimed` | `reservation_claim.state='unclaimed'` |
   | `res_provisional` | `state='provisional'`, `provisional_until` in the future, `email='parity@e2e.test'`, `email_masked='p***@e2e.test'`, `token_hash=claim.token_hash(SECRET)` with `SECRET='e2e-claim-secret'`, token_version 1 |
   | `res_claimed` | `state='claimed'`, `claimed_at=db.utcnow()`, token_version 1, `declared_guests=2`, 1 guest row complete (`first_name`, `surname`, `birth_date`, `nationality`, signature) and 1 incomplete -> out["guest_complete"], out["guest_partial"] |
   | `res_locked` | claimed and `guest_access_locked_at` set (the "locked" page) |
   | `res_gone` | `status='cancelled'` (the unavailable page) |
   Also: 4 guide items visible to guests (reuse the 2041 seed if the 2041 seed ran; else call `guest_guide.add_kind`/`save`), a Leon config row, a payment request (`payment_request.create`, then `payment_request.guest_token`), a cleaning share token (`cleaning.new_share`), a booking in 'requested' state (as 2041 item 5, reuse its code), an unsubscribe token. Print everything as JSON: ids, tokens, and `claim_cookie` = `URLSafeSerializer(config.secret_key(), salt="ubyhost-guest-claim").dumps({str(res_claimed): 1, str(res_locked): 1})` computed with the audit env, and `owned_cookie` for the guest rows (find how `_owned_*` is dumped: `grep -n 'ubyhost-guest-owned' -B3 -A12 App/app/routes/guest.py | head -40`).
   Check: `cd App && .venv/bin/python -m py_compile ../scripts/e2e/seed_parity_guest.py && echo ok | tail -3`.
5. Append to `scripts/e2e/parity_cases.py`: `GUEST_CASES`, rows `(name, path, cookies, group)` where `cookies` is `[]` or a list of cookie keys `["claim"]`, `["claim","owned"]` and persona `guest`. Placeholders `{tok} {res_unclaimed} {res_provisional} {res_claimed} {res_locked} {res_gone} {guest_complete} {guest_partial} {pay_open} {pay_paid} {share_token} {booking_id} {unsub_token}` (and `{apt}` `{booking_slug}`):
```
GUEST_CASES = [
    # H1: hub and stay states (no cookie = a stranger with the link)
    ("g-hub", "/l/{tok}", [], "H"),
    ("g-hub-claimed", "/l/{tok}", ["claim"], "H"),
    ("g-privacy", "/l/{tok}/privacy", [], "H"),
    ("g-stay-unclaimed", "/l/{tok}/{res_unclaimed}", [], "H"),
    ("g-stay-provisional", "/l/{tok}/{res_provisional}", [], "H"),
    ("g-stay-claimed", "/l/{tok}/{res_claimed}", ["claim"], "H"),
    ("g-stay-claimed-nocookie", "/l/{tok}/{res_claimed}", [], "H"),
    ("g-stay-locked", "/l/{tok}/{res_locked}", ["claim"], "H"),
    ("g-stay-gone", "/l/{tok}/{res_gone}", [], "H"),
    ("g-claim-landing", "/l/{tok}/{res_provisional}/claim", [], "H"),
    # H2: the guest form
    ("g-form-new", "/l/{tok}/{res_claimed}/new", ["claim"], "H"),
    ("g-form-edit-complete", "/l/{tok}/{res_claimed}/edit/{guest_complete}", ["claim", "owned"], "H"),
    ("g-form-edit-partial", "/l/{tok}/{res_claimed}/edit/{guest_partial}", ["claim", "owned"], "H"),
    ("g-remove", "/l/{tok}/{res_claimed}/remove/{guest_complete}", ["claim", "owned"], "H"),
    # H3: guide and Leon
    ("g-guide-apt", "/g/{tok}", [], "H"),
    ("g-guide-stay", "/l/{tok}/{res_claimed}/guide", ["claim"], "H"),
    ("g-leon-apt", "/g/{tok}/leon", [], "H"),
    ("g-leon-stay", "/l/{tok}/{res_claimed}/guide/leon", ["claim"], "H"),
    # H4: other token links (no login)
    ("t-pay-open", "/pay/{pay_open}/{pay_open_token}", [], "H"),
    ("t-pay-paid", "/pay/{pay_paid}/{pay_paid_token}", [], "H"),
    ("t-cleaner-share", "/cleaning/shared/{share_token}", [], "H"),
    ("t-booking-manage", "/p/{booking_slug}/b/{booking_id}/{booking_token}", [], "H"),
    ("t-unsubscribe", "/mail/unsubscribe/{unsub_token}", [], "H"),
]
PIN_CASES = [
    ("g-pin-hub", "/l/{tok}", [], "P"),
    ("g-pin-demo", "/l/{tok}/demo/{res_claimed}", [], "P"),
]
```
   `/l/{tok}/{res}/claim` may need a secret query: use what step 3 found (e.g. `?t=e2e-claim-secret`) and edit that one path; if it only redirects without mail, keep the redirect target as the compared page and note it. Rows whose seed block was skipped are `SKIPPED`, listed in the report. Expected row count: 23 + 2.
6. Edit `scripts/e2e/page_parity_visual.py` (anchors `seed, refs = audit.seed_db()`, `shots.run_case(`, `def main()`): (a) after the 2041 hook (or `seed_db()` if absent) run `seed_parity_guest.py` the same way and merge its JSON into `extra`; (b) a case tuple with a cookie-key list maps `claim` -> `("ubyhost_claim", extra["claim_cookie"])`, `owned` -> `("ubyhost_owned", extra["owned_cookie"])` (use the real cookie name found in step 4) and goes to `run_case(extra_cookies=...)`, with NO session cookie (`py_cookie_value=None`); (c) group `H` is in the default `PARITY_GROUP` list only when asked (`PARITY_GROUP=H`); group `P` runs only with `PARITY_PIN=1`, which passes `env=audit.PIN_ENV` to `audit.start_py` / `audit.start_go` (anchor: the two `audit.start_*` calls) and refuses to run other groups; (d) `--gate`/`PARITY_GATE=1`: after the run print `GATE: PASS` (no visible/error) or `GATE: FAIL <n> visible <m> error` and exit 0/1.
7. Run (timeout 600000 each): `cd App && PARITY_GROUP=H .venv/bin/python ../scripts/e2e/page_parity_visual.py 2>&1 | tail -12` (23x2x3 = 138 rows; if it times out split it by `PARITY_ONLY='g-*'` and `PARITY_ONLY='t-*'`), then `PARITY_PIN=1 PARITY_GROUP=P .venv/bin/python ../scripts/e2e/page_parity_visual.py 2>&1 | tail -8`.
   For each guest page check the `*-py.png` once at 390 to be sure the intended state rendered (a guest page that shows the "link not valid" card in both stacks means the seed or the cookie is wrong: fix the seed once, else mark the row `WRONG STATE`).
8. Gate command: create `scripts/e2e/parity_gate.sh` (chmod +x) with exactly:
```
#!/usr/bin/env bash
# Pre-deploy gate: Python vs Go pixel parity for every host, admin and guest page. Exit 1 on any visible or error row.
set -u
cd "$(dirname "$0")/../.."
source scripts/e2e/parity_env.sh
rc=0
cd App
for g in A B C D E F G H; do
  PARITY_GATE=1 PARITY_GROUP=$g .venv/bin/python ../scripts/e2e/page_parity_visual.py 2>&1 | tail -3 || rc=1
  [ "${PIPESTATUS[0]}" -eq 0 ] || rc=1
done
PARITY_GATE=1 PARITY_PIN=1 PARITY_GROUP=P .venv/bin/python ../scripts/e2e/page_parity_visual.py 2>&1 | tail -3
[ "${PIPESTATUS[0]}" -eq 0 ] || rc=1
exit $rc
```
   Run it ONCE only with `PARITY_ONLY` narrowed (`PARITY_ONLY=admin-home PARITY_WIDTHS=390 bash scripts/e2e/parity_gate.sh 2>&1 | tail -15`; groups without a match print 0 rows, that is fine) to prove the wiring; do not run the full gate here.
9. Inspect visible/error rows as in 2040 step 6 (max 12 image reads, plain-words causes, one-shot state re-run). Write `docs/tasks/2042-report.md`: totals; all-rows table; the visible causes; exclusions (below); the gate command and its measured wall time per group (from 2040/2041 reports) so the owner knows the full gate takes roughly the sum; "Next briefs": one line per visible cause.
   Exclusions to state in the report: anonymous pages (landing, login, signup, signup/verify, legal, terms, privacy, dpa, subprocessors, jak-to-funguje, cenik, pruvodce/*, /p/{slug} public page, /p/{slug}/thanks, /terms/booking, /account/email/confirm), by the owner's scope decision.
10. `python3 scripts/context_lint.py 2>&1 | tail -3`. Commit only the files of section 3: `2042: parity guest and token pages, gate command (report)`.

## 5. Do not touch

`App/app/**`, `go/**`, `scripts/e2e/seed.py`, `page_parity_audit.py`. No new dependency.

## 6. Commands

```
source scripts/e2e/parity_env.sh
cd App && PARITY_GROUP=H .venv/bin/python ../scripts/e2e/page_parity_visual.py 2>&1 | tail -12
cd App && PARITY_PIN=1 PARITY_GROUP=P .venv/bin/python ../scripts/e2e/page_parity_visual.py 2>&1 | tail -8
bash scripts/e2e/parity_gate.sh 2>&1 | tail -15      # full gate, owner or CI only
```

## 7. Acceptance

- [ ] `go_page_parity_screenshots.py` test file green; old callers unchanged.
- [ ] 23 guest/token cases + 2 PIN cases have verdicts for cs/en x 3 widths, or a named SKIPPED / WRONG STATE reason.
- [ ] `parity_gate.sh` exists, proven with the narrowed run; the report documents the full command and when to run it.
- [ ] Report lists every row, plain-words causes for visible rows, and the exclusion list.
- [ ] Only section 3 files changed; `context_lint` passes.

## 8. Stop and ask

- 2040 files missing, or environment not up: stop.
- Step 3 shows the claim landing needs mail you cannot fake in 2 tries: mark `g-claim-landing` SKIPPED and go on.
- 25 tool calls used: stop, commit, report the missing parts.
- Never edit Python or Go to fix a row. Never use real guest data.

## 9. Report

`docs/tasks/2042-report.md`.
