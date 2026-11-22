# 2010: Go-Python page-parity fix index (audit 2026-11-21, main e7644e2a)

Status: todo | Branch: task/2010-go-parity-fix-index | Owner: orchestrator wrote; each child runs alone as Haiku 5.5
Source: `scripts/e2e/page_parity_audit.py` run on `main` e7644e2a — 137 paths, 411 rows: 250 pass, 11 pass-soft, 101 accepted, **49 fail**. Policy: any 501 / `X-Ubyhost-Not-Ported` / unregistered-GET row is a failure; only both-404 / both-410 (and harness K3) are accepted.

## 1. Order (run top-down, one brief per session)

1. **2011** auth + shell pages: `/login`, `/login/2fa`, `/login/link`, `/signup`, `/account/accept`, `/offline` — smallest drift, unblocks anon persona.
2. **2012** landing + dashboard: `/` (anon landing, host dashboard, admin home).
3. **2017** `/p/{slug}/thanks` — public booking close.
4. **2014** property pages: `/apartments/{id}/booking-site`, `/apartments/{id}/guide/questions`.
5. **2013** admin + dev: `/booking-sites`, `/admin/fakturace/export`, `/dev/ui`, `/api/command-palette`.
6. **2015** `/guests/{id}` — personal data; privacy row tests mandatory.
7. **2018** `/reservations`, `/reservations/{id}/guests/new`.
8. **2016** guest link hub `/l/{slug}...` — last: touches UbyPort claim/filing; needs UBYPORT_CORE review and the two status mismatches fixed.

## 2. Review of merged PRs #1230-#1248 (correctness, privacy, UbyPort filing risk)

1. **No secrets leaked** in `f91c1874..e7644e2a` (scan for keys/tokens/passwords: only secret-loading code identifiers). #1230 ships `App/app/static` in the Go image — static assets only, OK.
2. **#1232 `UBYHOST_STAGING_NO_LOGIN` in Go — highest residual risk.** `envguard` makes `ubyhost-web` exit if the flag is set with production; owner must confirm `deploy-production.yml` never sets it (test-map: `test_env_guard.py`). If the guard ever fails open, Go would issue first-admin sessions on production. Verify before Python retirement.
3. **#1235 windowed `rate_limit_event` without per-request DELETE prune** — rows (IP, UA) persist until TTL purge; check `App/app/retention.py` has a line (rule 2) and compare retention vs Python's prune.
4. **#1241/#1240 claim device gate stays OFF** while `formPagesRequireClaim` / `stayClaimDeviceGate` are stubs: Go `/l/...` claim is reachable without the device gate — UbyPort filing risk (`docs/UBYPORT_CORE.md`: `claim_sendable` / submission state machine is the guard). Close in **2016**; do not enable claim-dependent flows on Go before then.
5. **#1246 full guest form port + u15 signer fields** — UBYPORT_CORE forbids changing guest field semantics; the added field-name parity test is the right control, and **2016** must also diff the UbyPort submission payload mapping (`App/app/ubyport/`) for every form field.
6. **#1240 `return_to` on PIN redirects** — must accept same-origin paths only (no open redirect).
7. **#1245 / #1248 / #1233 are harness-only** (Python sessions re-issued after DB clone, DB env before `app.main` import, acceptance policy "501 never accepted"): earlier runs over-reported fails; the current 49 are real. Note: audit artifacts are written to the runner store path (`STORE_DOC` in the script), not committed to the repo — keep attaching the md/json to PRs for traceability.
8. **#1237 ported `GET /apartments` live list only**; archived rows and POST actions stay on Python — documented partial; those paths must pass via fallback, never 501.

## 3. Gates after all children merge

```bash
python3 scripts/go_parity_check.py --all 2>&1 | tail -30      # expect 342/342
python3 scripts/e2e/diff_harness.py 2>&1 | tail -5            # expect 0 hard
cd App && UBYHOST_E2E_PG=postgresql://postgres@127.0.0.1:5433 .venv/bin/python ../scripts/e2e/page_parity_audit.py 2>&1 | tail -5   # expect fail: 0
python3 scripts/context_lint.py 2>&1 | tail -10
```
