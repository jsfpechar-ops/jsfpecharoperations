# 2020: Live staging-vs-prod parity audit script (Gate B)

Status: todo | Depends on: none (runs alongside 2011-2018) | Branch: task/2020-staging-prod-live-audit
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens | Tier: B — **privacy-critical: no secrets, no prod guest data in the repo**

## 1. Objective

Create `scripts/e2e/staging_prod_audit.py` that captures live **staging** and live **prod** for every registered GET route × persona (anon, host, admin), applies the whitelist normalisation from [staging-prod-identical](../plans/staging-prod-identical.md), and writes `docs/staging-prod-parity-audit.md` + `.json` with verdicts `pass` / `whitelisted-diff` / `fail-diff`. Exit non-zero on any `fail-diff`. Read-only GETs only.

## 2. Context

- Reuse from `scripts/e2e/page_parity_audit.py`: `norm_dom`, the ROUTES list + `concretize` fixture refs, `score_row` ideas. Extend the path list with all routes from `scripts/go_parity_check.py --all` so "every page" is covered.
- Bases: `--staging` (default `https://staging.ubyhost.com`, Go-only stack, no-login admin via `UBYHOST_STAGING_NO_LOGIN`) and `--prod` (owner's `UBYHOST_PUBLIC_BASE_URL`). Follow the `BASE` arg pattern of `deploy/lightsail/scripts/smoke-remote.sh`.
- Sessions: staging admin/host via the no-login flag; **prod cookie only from env var `STAGING_PROD_AUDIT_PROD_COOKIE`** (owner supplies at run time; abort with a clear message if missing). Never write cookies, tokens or URLs-with-tokens into the repo or the report.
- Whitelist normalisation (strip before comparing): `.env-banner` nodes, the `env.mock` sidebar label, demo/seed rows and "Clear demo" (`demo_loaded`), `/healthz` version string, Stripe test-mode badges. Implement as a small pure function `whitelist_normalize(html) -> html` so it is unit-testable.
- Playwright is available in `App/.venv` (as in `page_parity_audit.py`). Screenshots: local only, under `/tmp`, never committed if they can contain guest data (rule 3); the committed report contains verdicts, lengths and similarity only.

## 3. Files

- New `scripts/e2e/staging_prod_audit.py`.
- New `App/tests/test_staging_prod_audit_normalize.py` — unit tests for `whitelist_normalize` and verdict logic (import the script via importlib from the scripts path).
- `docs/staging-prod-parity-audit.md` — generated report template; commit only a scrubbed run (no guest data, no cookies).
- `docs/context/test-map.md` — add one row: "Live staging/prod audit script | `test_staging_prod_audit_normalize.py`".

## 4. Steps

0. Anchors: `grep -n 'def norm_dom\|ROUTES\|def concretize\|def score_row' scripts/e2e/page_parity_audit.py`; `grep -n 'def \|routes' scripts/go_parity_check.py | head -20`.
1. Path collection: union of page_parity_audit ROUTES and go_parity_check routes, concretized with the same fixture refs where they exist on live data.
2. Session acquisition: staging no-login; prod from env cookie; anon = no cookie. Abort cleanly when the prod cookie is absent.
3. Capture both bases per path × persona (httpx or Playwright; keep it light — httpx is enough for DOM diff, no JS: note in the report that this audits the no-JS render, matching rule 6 and the `ph-*` server markup).
4. `whitelist_normalize` both DOMs, compare with `norm_dom` + similarity like `score_row`; classify verdicts; write md + json.
5. Tests for the normaliser and verdict classifier.

## 5. Do not touch

`go/`; `App/` except the one test file named above; Caddy; server `.env`; `UBYHOST_GO_PATHS`; no secrets in git; no prod DOM/screenshots with guest data committed.

## 6. Commands

```bash
python3 -m py_compile scripts/e2e/staging_prod_audit.py 2>&1 | tail -5
cd App && .venv/bin/python -m pytest tests/test_staging_prod_audit_normalize.py -q --tb=short -x 2>&1 | tail -30
python3 scripts/e2e/staging_prod_audit.py --staging https://staging.ubyhost.com --prod "$UBYHOST_PUBLIC_BASE_URL" 2>&1 | tail -30   # owner-run live pass
python3 scripts/context_lint.py 2>&1 | tail -10
```

## 7. Acceptance

- Unit tests green; script compiles; a staging-only dry run (`--prod ""` → skipped with a note) works.
- Live owner run produces the md/json with only `pass` and `whitelisted-diff` rows; any `fail-diff` is listed for triage in 2019.
- Test-map row added; lint OK; no secrets or guest data in any committed artifact.

## 8. Stop and ask

Stop if the prod cookie env var is missing (ask the owner to run the live pass), if any captured output contains guest-looking personal data (scrub, never commit), or if the path union exceeds what one run can capture in the session (split the report by prefix and note it).

## 9. Report

`docs/tasks/2020-report.md`, <=600 tokens: files changed, command tails, live-run verdict counts, any fail-diffs triaged, owner steps left.
