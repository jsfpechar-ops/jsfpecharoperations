# 1831: Deploy safety 2: smoke registration on the demo property after every deploy and Caddy reload, with a no-filing assertion

Status: todo, but the executor must stop at Step 0 unless the orchestrator has answered open questions A, B and C in this file (they gate anything that could file).
Depends on: 1830 (the smoke runs after the slot switch) | Base commit: current tip of the working branch | Branch: task/1831-deploy-smoke-registration
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens
Tier: A (guest data and filing adjacent; exact diffs only; fresh review of the full diff)
Plan: [guest-form-isolation](../plans/guest-form-isolation.md) section 6.

> **One PR mode.** Commit each step as `1831 step k`. Never push, merge or deploy.

## 1. Objective

After every deploy and every Caddy reload, `scripts/smoke-registration.sh` runs one full guest registration on the demo property through the public address, waits until it is processed, deletes it, and fails the deploy if any UbyPort submission row exists or anything was queued for filing for it.

## 2. Context

Rule 1 (AGENTS.md): UbyPort filing correctness beats every other feature. Rule 2: no real personal data. Rule 3: public repo, no secrets or server names.

**What the code says about demo exclusion (read for this brief):**
- `App/app/demo.py`: `is_demo_apartment` is true when `apartment["internal_name"]` is `"Vinohrady Studio (demo)"` or `"Karlín Loft (demo)"` (checked in every environment); `is_demo_stay` is true when `reservation.source == 'demo'`. Demo PINs are fixed in `DEMO_PINS` (`"246810"`, `"135790"`).
- `App/app/reporting.py` line 775 to 777: a demo stay or demo apartment gets `send_enabled: False`. Line 2352 to 2358: `submit_batch` returns `state: noop` for a demo apartment. Lines 1589 and 1792 drop demo stays (by source) before a batch.
- Go: `go/internal/ubyport/submit_test.go` line 257 to 268 pins that a stay with source `demo` makes 0 UbyPort calls.
- Tables: `submission` (`apartment_id`, `state`, `created_at`, `guest_ids`) and `submission_claim`, in `App/migrations_pg/00001_baseline.sql` lines 2102 and 2128. The job `submit` is a periodic sweep (`App/app/scheduler.py`), not one job per guest, so "queued for filing" means a reportable guest row, not a `job` row.

**What is NOT provable from the files read (so it is an open question, not a guess):**
- A. The setup guide's demo *stay* (`source = 'demo'`) is opened only by the signed-in host (`App/app/routes/guest.py` lines 825 to 831, and the real-guest picker at 779 to 781 excludes it). A real guest on a demo *apartment* gets a normal-source stay. The Python exclusion for that case is at `submit_batch` (line 2352) but `collect_sendable` (reporting.py around 1572 to 1592) was only seen filtering by stay source; the Go sweep (`go/internal/ubyport/sweep.go`) cites `is_demo_apartment` but the exact filter was not read. So it is not shown that a guest registered on a demo apartment is never picked up for a batch.
- B. How a smoke client gets a guest link of the demo apartment without a host login, and how it passes Turnstile (the guest form uses it) and the Cloudflare managed challenge that production puts on `/l/*` (`deploy/lightsail/scripts/smoke-remote.sh` comments say `/l/*` is challenged and the script treats it as neither pass nor fail).
- C. Whether a demo apartment exists on production at all: `demo.seed` runs only against the mock UbyPort, so production may need a dedicated apartment named with the `(demo)` suffix, created by the owner.

## 3. Files

| Path | Action | What |
|---|---|---|
| `deploy/lightsail/scripts/smoke-registration.sh` | create | the smoke, shellcheck-clean |
| `deploy/lightsail/scripts/deploy.sh` | edit | call it after the existing `Public smoke` block (anchor: `./scripts/smoke-remote.sh`) and after the `caddy reload` line |
| `docs/ENVIRONMENT.md` | edit | one row per new variable (section "Smoke") |
| `docs/tasks/1831-report.md` | create | the report |

No other file may change. Not `App/`, not `go/`, not any filing code.

## 4. Steps

0. **Gate (no edits).** Run `grep -nF "internal_name" App/app/demo.py | tail -30` and read `App/app/reporting.py` lines 1565 to 1600 and the collection query in `go/internal/ubyport/collect.go` (find with `grep -n "func Collect" go/internal/ubyport/collect.go`). Write the answer to A in the report. If you cannot show in code that a guest of a demo apartment (normal-source stay) is excluded in BOTH Python and Go before any lease, batch or `submission` insert: STOP, set `Status: blocked`, write the report. Do not continue to Step 1.
1. **Script** `smoke-registration.sh` with these rules (the HTTP driving is open question B; implement only what the orchestrator's answer says):
   - Reads `UBYHOST_PUBLIC_BASE_URL`, `UBYHOST_SMOKE_GUEST_URL` (the demo apartment's guest link, owner-provided), `UBYHOST_SMOKE_PIN` from `.env`. Exits 0 with the message `smoke registration skipped: UBYHOST_SMOKE_GUEST_URL not set` when unset (staging and fresh servers keep working).
   - Fake values only, exactly: given name `Smoke`, family name `Test`, date of birth `2000-01-01`, nationality `CZ`, document number `SMOKE0000`, email `smoke@example.test`, address `1 Example Street, Prague`. Mark every field value with the prefix `SMOKE`. No real person, no real document number.
   - Before: query `SELECT COUNT(*) FROM submission WHERE apartment_id = <demo id>` and `SELECT COUNT(*) FROM submission_claim` through `docker compose exec -T postgres psql` (use the same invocation as `deploy.sh` uses for its row counts; grep `psql` in `deploy.sh`).
   - Register, then poll for the processed state for at most 60 s.
   - After, always (also on failure, via `trap`): delete the smoke guest by calling the existing demo-delete path through the app container, never by raw SQL on guest tables. Which path exists for a non-`demo`-source stay is open question B.
   - Assertions, any failure exits 1 with the failing step name on one line: (1) processed within 60 s; (2) `submission` count for the demo apartment equals the count before; (3) `submission_claim` count equals the count before; (4) zero guest rows of the smoke stay in a reportable state (the exact state value comes from [submit_state](../OPERATIONS.md#the-submit_state-state-machine); open question D); (5) the guest rows are gone after delete.
   - Prints no guest data and no token. Logs only step names and counts.
2. **deploy.sh.** After the `Public smoke` block add `./scripts/smoke-registration.sh || { echo "smoke registration failed" >&2; exit 1; }`. Do NOT add `rollback` here; brief 1832 owns rollback. Add the same call directly after the `caddy reload` line.
3. **ENVIRONMENT.md.** Rows for `UBYHOST_SMOKE_GUEST_URL`, `UBYHOST_SMOKE_PIN`: unset by default; what they are; never commit values.

## 5. Do not touch

`rollback()` (1832); `reporting.py`, `demo.py`, `go/`, `ubyport`; any migration; Turnstile configuration; the Cloudflare settings. If the smoke needs a Turnstile or Cloudflare exception, hand that to the owner (§10), never loosen a check in code.

## 6. Commands

- `shellcheck -S error deploy/lightsail/scripts/*.sh 2>&1 | tail -30`
- `cd App && .venv/bin/python -m pytest tests/test_demo_stay_exclusion.py $(ls tests/test_demo_*.py) -q --tb=short -x 2>&1 | tail -30` (test-map row "Demo seed")
- `python3 scripts/context_lint.py 2>&1 | tail -30` from the repo root.

## 7. Acceptance

- [ ] Step 0 answer written in the report with the file and line that proves exclusion in Python and in Go.
- [ ] shellcheck and the demo tests green; `git diff --stat` lists only §3 paths.
- [ ] The script contains no real-looking personal data and no host name or IP.
- [ ] Assertions 2 and 3 are present and run even when assertion 1 failed.

## 8. Stop and ask

Step 0 cannot prove exclusion; a delete path would touch a real (non-smoke) record; Turnstile or Cloudflare needs a code change; a file outside §3; a test fails twice; 25 tool calls.

## 9. Report

`docs/tasks/1831-report.md`, 600 tokens at most: Step 0 answer, files, commands with last 5 lines, §7 ticked, deviations, questions, owner steps.

## 10. Staging first, owner steps

1. Staging uses the mock UbyPort (`deploy-staging.yml`, mock default), so a wrong exclusion cannot reach the police there. Owner: Deploy staging with this branch, set `UBYHOST_SMOKE_GUEST_URL` and `UBYHOST_SMOKE_PIN` in the staging `.env`, run `./scripts/smoke-registration.sh | tail -30` on the server: expect all five assertions to pass.
2. Prove the assertion bites: on staging only, with the mock, temporarily mark the smoke stay non-demo is NOT allowed; instead run the script against a staging apartment that is not a demo one and expect assertion 2 or 4 to fail. If you cannot do this safely, say so in the report.
3. Production: owner creates the `(demo)` apartment (question C), sets the two variables, only after steps 1 and 2.

## Rollback

Remove the two calls from `deploy.sh` (revert the PR). No data model change.

## Open questions for the orchestrator (answer before the executor starts)

A. Proof that a guest registered on a demo apartment is never collected for filing, in Python and in Go (Step 0 tries; if Go's collect query is not demo-aware, a Go brief must add it first and this brief waits).
B. How the smoke obtains and drives the guest link: Turnstile test/bypass for the smoke client, and a Cloudflare skip rule (for example by a secret header the owner sets in Cloudflare) for `/l/*`. Also whether a stdlib-only shell and python script is acceptable for driving the multipart form, or a Playwright script (already in the test venv, not on the server) is wanted.
C. Does a demo apartment exist on production, or must the owner create one with the `(demo)` name suffix?
D. The exact `claim` or `guest` column and value that means "queued for filing" (read `docs/OPERATIONS.md#the-submit_state-state-machine`).
