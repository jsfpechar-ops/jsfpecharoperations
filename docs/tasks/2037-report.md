# 2037 report: Go staging candidate and signup

**Status: blocked** · **Release verdict: NO** (staging SHA drift; auth/signup acceptance not run on candidate)

## Candidate and deploy

| Source | SHA |
|--------|-----|
| `origin/main` (2026-11-23 fetch) | `1eb6ef741365666e4fbce671ab6ae8ce959b4578` |
| Brief base | `bd961426570f07a214f9840bf165a0bca397b450` |
| Staging `/healthz` (live) | `2528d7db434f113e527b4e33bd32a75fbe7f0d09` |
| Latest Deploy staging workflow | `skipped` for `1eb6ef741…` (runs #88–90) |

Staging is **not** on the published release candidate. Recent staging deploy workflows did not apply a new image.

## Executor commands (last lines)

```text
git rev-parse origin/main → 1eb6ef741365666e4fbce671ab6ae8ce959b4578
curl /healthz → 200 {"status":"ok","version":"2528d7db…","data_dir_writable":true}
curl /signup → 404
curl -I /login → 303 Location: /
curl -X POST /cenik → 405 (matches prior http-checks evidence)
```

## Route / profile (sanitized)

- Go serves staging (`/healthz` JSON, Caddy headers, `/webhooks/stripe` → `ignored`).
- `UBYHOST_SIGNUP_ENABLED` unset → signup 404 via `signup.Enabled` in `signup_pages.go` (anchors confirmed).
- `UBYHOST_STAGING_NO_LOGIN` active → `/login` 303 to `/` (dashboard), not a login form.
- Host UI click-through under no-login is **unrepresentative** for signup/login acceptance.

## §7 acceptance

- [ ] Health version agrees with deploy candidate — **FAIL** (drift).
- [ ] Signup/auth profile — **not run** (owner must set flags + test sink).
- [ ] Audit A–F on matched SHA — **partial prior audit only** (`UbyHost_Go_staging_audit` on `2528d7db4`); many FAIL/UNVERIFIED; 2032–2039 not closed on current main.
- [ ] Release verdict without assuming prod deploy — **NO**.

## Prior audit subset (SHA `2528d7db4`, not candidate)

FAIL: party POST 404, missing property branded 404, booking terms, guide import 422, signup 404. UNVERIFIED: claim/registration, guest-pay on latest merge, police Doručenka E2E. PASS: guest PIN, static 404, POST 405, Stripe webhook, several host pages.

## Deviations

**Done:** steps 1 (SHA compare, curl checks), brief copy to `docs/tasks/2037-go-staging-candidate-and-signup.md`.  
**Left:** steps 2–5 (owner staging profiles, full auth flow, A–F on aligned SHA, config reset).

## Questions

None beyond owner gates below.

## Owner steps

1. GitHub → Actions → **Deploy staging** → run workflow for `main` at `1eb6ef741…` (mock police reporting if prompted).
2. Confirm `https://staging.ubyhost.com/healthz` version matches that run.
3. On the staging instance only: for host sweep set `UBYHOST_STAGING_NO_LOGIN=1`; for auth/signup set `UBYHOST_STAGING_NO_LOGIN` off, `UBYHOST_SIGNUP_ENABLED=1`, test mail sink; use a fresh browser for signup. Restore isolated staging profile after.
4. Re-run 2037 steps 3–4 and sibling briefs 2032–2036, 2038–2039 on the aligned SHA before production promotion.

**Files changed:** `docs/tasks/2037-go-staging-candidate-and-signup.md`, `docs/tasks/2037-report.md`.