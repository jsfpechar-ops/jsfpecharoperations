# 2019: Staging renders 1:1 identical to prod — index brief

Status: todo | Depends on: 2010 (child fix briefs 2011-2018), 2020 (live audit) | Branch: task/2019-staging-prod-identical-index
Executor: orchestrator runs the order; children run alone as Haiku 5.5
Plan: [staging-prod-identical](../plans/staging-prod-identical.md)

## 1. Objective

Make every page on Lightsail staging visually identical to production, except the documented intentional-difference whitelist (mock banner, UKÁZKA label, demo/seed rows, no-login session, Stripe test mode, healthz version, data values). Today they differ because staging is the Go-only stack while prod serves most paths from Python — the diff is exactly the Go-vs-Python DOM drift measured by the 2026-11-21 audit (49 fail rows; `/` host sim 0.05 = missing dashboard widgets on Go) — plus version skew (staging auto-deploys green main, prod manual-only).

## 2. Context

- Gate A (static): `scripts/e2e/page_parity_audit.py` fail: 0; `scripts/go_parity_check.py --all` 342/342; `scripts/e2e/diff_harness.py` 0 hard.
- Gate B (live): `scripts/e2e/staging_prod_audit.py` from brief **2020**, run by the owner on both envs, whitelist-normalised.
- Fix order: 2011, 2012, 2017, 2014, 2013, 2015, 2018, 2016 (per `2010` §1). Whitelist details in the plan doc.

## 3. Files

- `docs/plans/staging-prod-identical.md` (plan + whitelist)
- `docs/tasks/2019-staging-prod-identical-index.md` (this file), `docs/tasks/2020-staging-prod-live-audit.md`
- `docs/tasks/2011`–`2018` (fix briefs, PR #1249)
- `docs/context/status.md` (1:1 milestone line, orchestrator updates)

## 4. Steps

1. Run child briefs 2011→2016 in the 2010 order, one Haiku session each; each leaves a merged PR and a report.
2. Gate A green: audit fail: 0.
3. Owner: deploy prod manually; add newly ported paths to prod `UBYHOST_GO_PATHS` (`ENVIRONMENT.md:190` rules; POST paths stay off).
4. Run brief 2020's live audit on staging + prod; triage every non-whitelisted diff into a new docs/tasks brief; fix; re-run both gates.

## 5. Do not touch

`App/` and `go/` except via the child briefs; Caddy config; server `.env`; `UBYHOST_GO_PATHS` (owner step); no secrets or prod guest data in the repo (rule 3).

## 6. Commands

```bash
python3 scripts/go_parity_check.py --all 2>&1 | tail -30
cd App && UBYHOST_E2E_PG=postgresql://postgres@127.0.0.1:5433 .venv/bin/python ../scripts/e2e/page_parity_audit.py 2>&1 | tail -5
python3 scripts/e2e/diff_harness.py 2>&1 | tail -5
python3 scripts/e2e/staging_prod_audit.py --staging https://staging.ubyhost.com --prod "$UBYHOST_PUBLIC_BASE_URL" 2>&1 | tail -30   # owner-run; prod cookie via env
python3 scripts/context_lint.py 2>&1 | tail -10
```

## 7. Acceptance

- Gate A fail: 0; parity 342/342; harness 0 hard; lint OK.
- Gate B live report: zero diffs outside the whitelist on every page × persona.
- `status.md` notes the staging=prod 1:1 milestone and the date.

## 8. Stop and ask

Stop and surface to the owner: any non-whitelisted diff that looks like a deliberate design difference (not a port gap); any request to commit prod session cookies, screenshots or DOM containing guest data; any urge to edit `UBYHOST_GO_PATHS` outside the owner step.

## 9. Report

`docs/tasks/2019-report.md`, <=600 tokens: gate results (command tails), live-audit summary counts, diffs triaged, owner steps left.
