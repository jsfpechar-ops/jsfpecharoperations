# Plan: staging renders 1:1 identical to prod on every page

Owner requirement (2026-11-22): Lightsail staging must look identical to production on every page. This plan defines what "identical" means, why the two differ today, and the gates that prove 1:1.

## Why staging differs from prod today

1. **Stack shape.** Staging is the Go-only stack (compose `go` profile; Caddy default to Go since #1782) — no Python fallback. Prod routes only `UBYHOST_GO_PATHS` to `ubyhost-go` and everything else to Python (`docs/ENVIRONMENT.md:190`). So any staging-vs-prod visual diff on a Go-served path *is* the Go-vs-Python DOM diff measured by `scripts/e2e/page_parity_audit.py` — the 49 fail rows of the 2026-11-21 run (e.g. `/` host: Python 658 chars vs Go 319, sim 0.05 — the Go dashboard is missing needs-you, month stats, calendar, today table; exactly what the staging screenshot shows).
2. **Version skew.** Green `main` auto-deploys to staging; production is manual-only (brief 1865). Until prod is deployed, the two run different commits.
3. **Intentional mock layer** (whitelist below).

## Intentional-difference whitelist (only these may differ)

1. `_env_banner.html` mock banner — renders only when `UBYHOST_UBYPORT_ENV=mock` (staging/local).
2. Sidebar `env.mock` label ("UKÁZKA · Nic se neodesílá", `host_i18n.py`) — mock only.
3. Demo/seed data rows and the "Clear demo" control (`demo_loaded`, `App/app/demo.py`, `source='demo'` filtered from real lists).
4. Staging no-login session (`UBYHOST_STAGING_NO_LOGIN`; fatal on production per `App/app/env_guard.py`).
5. Stripe test-mode UI (staging) vs live (prod).
6. `/healthz` version string until prod is deployed.
7. Data values themselves (property names, guest counts) — the DOM **structure** must still match.

Everything else — every page, every persona, class names, structure, copy — must be byte-equal after normalisation.

## Method: two gates

- **Gate A (static, every commit):** `scripts/e2e/page_parity_audit.py` → fail: 0 (501 / not-ported always fail), `scripts/go_parity_check.py --all` → 342/342, `scripts/e2e/diff_harness.py` → 0 hard. This is the py-vs-go 1:1 proof for all 137 audited paths × 3 personas.
- **Gate B (live, per deploy):** new `scripts/e2e/staging_prod_audit.py` (brief **2020**) diffs live staging vs live prod over the union of all registered GET routes × personas, whitelist-normalised. Runs on the owner machine; prod session cookie via env var, never committed; no prod screenshots/DOM with guest data committed (rule 3).

## Order

1. Merge fix briefs **2011–2018** (PR #1249) → Gate A green (fail: 0).
2. Owner deploys prod manually and adds the newly ported paths to prod `UBYHOST_GO_PATHS` per `ENVIRONMENT.md:190` (kills version skew and stack-shape diffs).
3. Run Gate B live audit on both envs. Any diff outside the whitelist → new brief in `docs/tasks/`, fix, re-run both gates.
4. Update `docs/context/status.md` with the 1:1 milestone.

## Acceptance

- Gate A: audit fail: 0; parity check 342/342; harness 0 hard; `context_lint.py` OK.
- Gate B: report shows zero non-whitelisted diffs across every page and persona.
