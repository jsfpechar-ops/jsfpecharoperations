# 2015: Host guest detail `/guests/{id}` to exact Python DOM

Status: todo | Depends on: 2011 | Branch: task/2015-go-parity-guest-detail
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens | Tier: B — **personal-data page; privacy row tests mandatory**

## 1. Objective — failing audit row

| Persona | Path | py/go | Note |
|---|---|---|---|
| host | `/guests/1` | 200/200 | len 10851 vs 68, sim 0.01 — Go renders a stub |

## 2. Context

- Python (read-only): `App/app/templates/guest_form_admin.html` (host-side guest detail: filing fields, documents, notes).
- Go: handler for `GET /guests/{guest_id}` — `grep -rn 'guests/{guest_id}' go/cmd/ubyhost-web --include='*_test.go' | head -3` (stays package).
- DOM to match: the full admin guest form — every field label/input with identical `name=`, document links, UbyPort submission status block. Never print real guest PII in tests/reports (public repo, rule 3); use the audit fixture ids only.

## 3. Files

- Go stays guest-detail handler + template; tests with fixture data only.

## 4. Steps

0. Anchors: `grep -n 'name=\|ubyport\|submission' App/app/templates/guest_form_admin.html | head -30`; find the Go handler.
1. Port the template block-by-block; field semantics must not change (UBYPORT_CORE).
2. Golden test vs Python render; privacy tests green.

## 5. Do not touch

`App/`, `App/app/ubyport/`, PII encryption, Caddy, `UBYHOST_GO_PATHS`.

## 6. Commands

```bash
cd go && go test ./internal/web/stays/... ./cmd/ubyhost-web/... 2>&1 | tail -30
cd App && .venv/bin/python -m pytest tests/test_guest_*.py tests/test_guest_browser_e2e.py tests/test_ubyport_*.py tests/test_claim_*.py tests/test_privacy_*.py tests/test_pii_encryption.py tests/test_cookie_inventory.py tests/test_retention*.py tests/test_host_*.py -q --tb=short -x 2>&1 | tail -30
cd App && UBYHOST_E2E_PG=postgresql://postgres@127.0.0.1:5433 .venv/bin/python ../scripts/e2e/page_parity_audit.py 2>&1 | tail -5
# filter rows path == '/guests/1'
```

## 7. Acceptance

0 fail rows for `/guests/1`; rows green 0 skipped; 1820 §6 screenshots (fixture data only).

## 8. Stop and ask

At the 25-call / 50k-token checkpoint; if the Python page embeds data the Go query must not expose (access-control mismatch) — STOP, security decision.

## 9. Report

`docs/tasks/2015-report.md`, <=600 tokens.
