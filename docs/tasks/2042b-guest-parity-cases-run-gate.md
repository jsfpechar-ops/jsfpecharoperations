# 2042b: V2 visual parity, guest pages: harness cookies, cases, seed, run (2042c inspects and adds the gate)

Status: todo
Depends on: 2042 steps 1-4 (done on this branch: `extra_cookies` in `App/scripts/go_page_parity_screenshots.py`, `scripts/e2e/seed_parity_guest.py` written), 2045 | Base commit: HEAD | Branch: current
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 100k tokens (stop at 25 calls; see section 8). Run order: 2042b, then 2042c.

## 1. Objective

Make the parity harness able to open guest and token-link pages with the cookies a real guest has, add the 23 + 2 cases, seed the data, and produce the run results for cs/en x 390/768/1280 (group H) and the PIN pass (group P). **Do not fix visible differences. Do not inspect images** (2042c does). Retired and never compared: booking site, payments, Stripe.

## 2. Context (verified by reading code, 2026-11-24)

- **Claim cookie**: name `ubyhost_claim` (`App/app/routes/guest.py:46` `CLAIM_COOKIE`; Go `go/internal/web/guest/pick_cookies.go:23`). Value = itsdangerous `URLSafeSerializer(secret, salt="ubyhost-guest-claim").dumps({"<reservation_id>": <token_version>})` (guest.py:111-112; `_claimed_claims` guest.py:246-271 requires a dict, else grants nothing; `_device_holds_claim` guest.py:279-286 also needs `reservation_claim.state='claimed'` and `token_version == generation`). Go reads the same (`claimedClaims`, pick_cookies.go:64-100, `urlSafeJSON(secret, claimCookieSalt, raw)`) and signs identically (`urlSafeSign`, pick_cookies.go:169-174: sha1 key `salt+"signer"+secret`, HMAC-SHA1, urlsafe base64). Both stacks take the secret from `UBYHOST_SECRET_KEY` (Go: `go/internal/secure/datakeys.go:67`; audit env value `e2e-secret-key-0123456789-abcdefghijkl`, `scripts/e2e/page_parity_audit.py:29`). **Result: ONE cookie value works on both stacks; no per-stack cookie.** The seed already computes it with `config.secret_key()` under the audit env.
- **Owned cookie**: name `ubyhost_owned` (pick_cookies.go:21), salt `ubyhost-guest-owned`, value = JSON list of guest ids. Same on both stacks.
- **`fill()`** (`scripts/e2e/page_parity_visual.py:76-81`) formats with `apt, res, guest, inv, hinv, fee_a, alfa, tok` plus `**extra`. So `{tok}` and `{apt}` work; `{res_unclaimed}`, `{res_provisional}`, `{res_claimed}`, `{res_locked}`, `{res_gone}`, `{guest_complete}`, `{guest_partial}`, `{share_token}`, `{unsub_token}` work ONLY if the seed JSON keys are merged into `extra`. `table_cases` (line ~96-110) already passes `extra`; a KeyError makes the row print `SKIPPED (seed block missing)`.
- **Harness**: it does NOT call `shots.run_case`. It uses its own `_capture` (line 97) and `run_case2` (line 161), which add only the `ubyhost_session` cookie. The `extra_cookies` of step 2 of brief 2042 do not reach it; this brief adds the parameter there.
- **`reservation_claim` columns** (`App/migrations_pg/00001_baseline.sql:1862-1879`): `reservation_id, state ('unclaimed'|'provisional'|'claimed'), email, email_masked, lang, token_hash, token_version (NOT NULL default 0), provisional_until, claimed_at, guest_access_locked_at, guest_access_reopened_at, declared_guests, completion_notified_at, created_at, updated_at`. All of the seed's columns exist. `guest` columns used (`:834-853`): `reservation_id, surname, first_name, birth_date, nationality, signature_png, is_lead`.
- **Claim landing** `GET /l/{token}/{id}/claim` (guest.py:1588-1642) takes no secret in the query (the secret is spent by the POST). With mail off (`mail.mail_enabled()` false, the audit env) it 303-redirects to the stay page; the compared page is then the redirect target. Do not add a query.
- **PIN pass**: `audit.start_py` runs in-process and reads `UBYHOST_GUEST_PIN` once, so it cannot enable PIN. Use `audit.start_py_process(port, db_url, public, audit.PIN_ENV)` (page_parity_audit.py:257, returns `(proc, base)`) and `audit.start_go(port, db_url, public, audit.PIN_ENV)` (:229) as `page_parity_audit.py:446-447` does. `audit.PIN_ENV` already gets `AI_ENV` in `main()`.

## 3. Files

| Path | Action | What |
|---|---|---|
| `scripts/e2e/page_parity_visual.py` | edit | `extra_cookies` in `_capture`/`run_case2`; guest seed hook; guest and PIN job tables; `PARITY_PIN` servers |
| `scripts/e2e/parity_cases.py` | edit | append `GUEST_CASES`, `PIN_CASES` |
| `scripts/e2e/seed_parity_guest.py` | edit only if step 4 fails | fix one wrong column/helper |
| `docs/tasks/2042b-report.md` | write | row counts, SKIPPED / WRONG STATE rows |

Never touch `App/app/**`, `go/**`, `scripts/e2e/seed.py`, `page_parity_audit.py`.

## 4. Steps

1. Environment: `cd /home/user/jsfpecharoperations && source scripts/e2e/parity_env.sh 2>&1 | tail -3; grep -n 'extra_cookies' App/scripts/go_page_parity_screenshots.py | head -4; grep -n 'seed_parity_guest' scripts/e2e/*.py | head -3`. If `extra_cookies` is missing, stop. Commit nothing yet.
2. `scripts/e2e/page_parity_visual.py`, extra cookies. Anchors: `def _capture(playwright, base, path, width, dest, cookie, mask, texts):`, `context.add_cookies([{"name": "ubyhost_session", "value": cookie, "url": base + "/"}])`, `def run_case2(name, base_name, path, out_dir, py_base, go_base, widths, py_cookie, go_cookie, pre_sql):`, the two `_capture(pw, ...)` calls in `run_case2`. Check each with `grep -nF`.
   - `_capture(..., texts, extra_cookies=None)`; after the `if cookie:` block add `if extra_cookies: context.add_cookies([{"name": n, "value": v, "url": base + "/"} for n, v in extra_cookies])`.
   - `run_case2(..., pre_sql, extra_cookies=None)`; both `_capture` calls get `extra_cookies=extra_cookies` as last argument (same list for both stacks: see section 2).
   Check: `cd App && .venv/bin/python -m py_compile ../scripts/e2e/page_parity_visual.py && echo ok 2>&1 | tail -3`.
3. `scripts/e2e/parity_cases.py`: append at the end, exactly (the 2042 list; the claim landing keeps its plain path, see section 2):
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
    ("t-cleaner-share", "/cleaning/shared/{share_token}", [], "H"),
    ("t-unsubscribe", "/mail/unsubscribe/{unsub_token}", [], "H"),
]
PIN_CASES = [
    ("g-pin-hub", "/l/{tok}", [], "P"),
    ("g-pin-demo", "/l/{tok}/demo/{res_claimed}", [], "P"),
]
```
   Count must be 20 + 2 rows (the 2042 text said 23 but listed 20; use the 20 listed). Check: `.venv/bin/python -c "import sys; sys.path.insert(0,'../scripts/e2e'); import parity_cases as p; print(len(p.GUEST_CASES), len(p.PIN_CASES))" 2>&1 | tail -3` prints `20 2` (run from `App/`).
4. `scripts/e2e/page_parity_visual.py`, seed hook. After `def run_extra_seed(...)` add a sibling `run_guest_seed(seed, refs)` that is a copy of it calling `scripts/e2e/seed_parity_guest.py` with args `str(seed["h1"]["id"]), str(refs["apartment_id"])` (same env, `cwd=APP`, echo stderr, parse last stdout line as JSON). In `main()` after `extra = run_extra_seed(seed, refs)` add `extra.update(run_guest_seed(seed, refs))`. Anchor: `extra = run_extra_seed(seed, refs)`.
   Check the seed on its own once (needs the db: it is seeded by `audit.seed_db()`, so run through the probe in step 6; if the first run prints `{"skipped": ...}` lines on stderr, fix that ONE block in `seed_parity_guest.py` using the column list in section 2, once).
5. `scripts/e2e/page_parity_visual.py`, jobs and PIN. Anchors: `jobs += list(table_cases(refs, seed, py, go, extra))`, `_, py_base = audit.start_py(py_port, db_url, public)`, `rows = []`, `for r in run_case2(name, base_name, path, out_dir, py_base, go_base, widths, py_cookie, go_cookie, pre):`.
   - After the `table_cases` line add: for each `(name, path, keys, group)` in `parity_cases.GUEST_CASES` and `parity_cases.PIN_CASES`, for `lang in ("cs", "en")`: `filled = fill(path, refs, seed, extra)` inside `try/except KeyError as exc: print(f"SKIPPED (seed block missing): {name} needs {exc}"); continue`; `ck = []`, `if "claim" in keys: ck.append(("ubyhost_claim", extra["claim_cookie"]))`, `if "owned" in keys: ck.append(("ubyhost_owned", extra["owned_cookie"]))` (a missing key is the same KeyError skip); append `(f"{name}-{lang}", f"{filled}{sep}lang={lang}", None, None, group, ck)` with `sep = "&" if "?" in filled else "?"`. Other jobs get an empty `ck` list: make the job tuple 6-wide everywhere (`jobs` entries made by `legacy_cases`, `table_cases`, `MODAL_CASES` get `, []` appended; keep the edit minimal, one list comprehension at the end: `jobs = [j if len(j) == 6 else (*j, []) for j in jobs]`) and the loop `for name, path, py_cookie, go_cookie, group, ck in jobs:`; pass `ck` as `extra_cookies=ck` to `run_case2`.
   - `PARITY_PIN`: `pin = os.environ.get("PARITY_PIN") == "1"`. If `pin`: use `groups = {"P"}` and start the servers with `_, py_base = audit.start_py_process(py_port, db_url, public, audit.PIN_ENV)` (it returns `(proc, base)`) and `_, go_base = audit.start_go(go_port, db_url, public, audit.PIN_ENV)`; else the existing `start_py`/`start_go` lines stay. If not `pin`, drop group `P` jobs. Guest cases of group `H` run only when `H` is in `PARITY_GROUP` (the default `A,B,C,D` already excludes it; add nothing to the default).
   Check: `cd App && .venv/bin/python -m py_compile ../scripts/e2e/page_parity_visual.py && echo ok 2>&1 | tail -3`.
6. Run (Bash timeout 600000 each, from `App/`):
   a. Smoke one case: `PARITY_GROUP=H PARITY_ONLY=g-stay-claimed PARITY_WIDTHS=390 .venv/bin/python ../scripts/e2e/page_parity_visual.py 2>&1 | tail -12`. Expect 2 rows (cs, en) and no `SKIPPED`. Fix wiring once if the probe crashes; if the row says `link not valid` on both stacks (`status` 404 in the note) the cookie or seed is wrong: check `extra["claim_cookie"]` is non-empty and `reservation_claim.state='claimed'`, token_version 1.
   b. Full guest group: `PARITY_GROUP=H .venv/bin/python ../scripts/e2e/page_parity_visual.py 2>&1 | tail -12` (20 x 2 x 3 = 120 rows). On timeout split with `PARITY_ONLY='g-*'` then `PARITY_ONLY='t-*'`.
   c. PIN: `PARITY_PIN=1 PARITY_GROUP=P .venv/bin/python ../scripts/e2e/page_parity_visual.py 2>&1 | tail -8` (2 x 2 x 3 = 12 rows).
   Do NOT open any PNG here. The tail output and `report-H.md` / `report-P.md` names go into the report.
7. Write `docs/tasks/2042b-report.md` (at most 600 tokens): tally per run (the last JSON line), list of `SKIPPED` and `error` rows with their reason from the note, the `report-*.md` paths, the PNG directory `OUT`, and `Done: steps 1 to 7`. Commit by explicit path: `git add scripts/e2e/page_parity_visual.py scripts/e2e/parity_cases.py scripts/e2e/seed_parity_guest.py docs/tasks/2042b-report.md && git commit -m "2042b: guest parity cases, cookies, run" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" -m "Claude-Session: https://claude.ai/code/session_014N5J8NCpdqN2TbR61gYRQf" 2>&1 | tail -3`. Commit after steps 3, 5 and 6 too (message `2042b step k`). Set Status of this file to `review`.

## 5. Do not touch

`App/app/**`, `go/**`, `scripts/e2e/seed.py`, `page_parity_audit.py`, `App/scripts/go_page_parity_screenshots.py`. No new dependency.

## 6. Commands

```
cd App && .venv/bin/python -m py_compile ../scripts/e2e/page_parity_visual.py ../scripts/e2e/parity_cases.py ../scripts/e2e/seed_parity_guest.py 2>&1 | tail -3
cd App && PARITY_GROUP=H .venv/bin/python ../scripts/e2e/page_parity_visual.py 2>&1 | tail -12
cd App && PARITY_PIN=1 PARITY_GROUP=P .venv/bin/python ../scripts/e2e/page_parity_visual.py 2>&1 | tail -8
```

## 7. Acceptance

- [ ] `_capture`/`run_case2` take `extra_cookies`; old cases unchanged (a group `A` single-case smoke still passes, optional).
- [ ] 20 guest + 2 PIN cases have a verdict row for cs/en x 3 widths, or a named SKIPPED / error reason.
- [ ] Smoke row shows the claimed stay rendered (not 404) on both stacks.
- [ ] Report lists tallies; only section 3 files changed.

## 8. Stop and ask

- Any anchor not found verbatim: stop.
- A step-6 run fails to start servers twice: stop and report the last 30 lines.
- 25 tool calls used: commit, report `Done: steps 1 to k. Left: steps k+1 to 7`.
- Never edit Python or Go app code to fix a row.

## 9. Report

`docs/tasks/2042b-report.md`.

## Step 0 (orchestrator, do first): stop the leaked Go server

`scripts/e2e/page_parity_visual.py` ~line 220 does `_, go_base = audit.start_go(go_port, db_url, public)`: the Go process handle is thrown away, so every run leaves a `/var/tmp/ubyhost-web-parity` process running its scheduler against `parity_run` (the orchestrator found 10+ of them, up to an hour old). Fix: keep the handle (`go_proc, go_base = audit.start_go(...)`) and stop it in a `try/finally` around the code that uses it (`go_proc.terminate()`, then `go_proc.wait(timeout=10)`, and `go_proc.kill()` if it is still alive), the same way `page_parity_audit.py` stops its own servers (~lines 253, 279, 451-452). Do the same for any other process this file starts (grep `start_py`, `Popen`). Verify: after one short run (`PARITY_ONLY=<one host case> PARITY_WIDTHS=390`), `ps -eo pid,cmd | grep -c '[u]byhost-web-parity'` prints 0. Commit "2042b step 0".
