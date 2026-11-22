# 2016: Guest link hub `/l/{slug}...` — DOM parity + two status mismatches (UbyPort-sensitive)

Status: todo | Depends on: 2011, 2015 | Branch: task/2016-go-parity-guest-link-hub
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens (split by sub-page; report `Status: blocked` at the cap) | Tier: A-adjacent — **UbyPort claim/filing paths; read `docs/UBYPORT_CORE.md` first**

## 1. Objective — failing audit rows (slug FZgxhwx4OGY3GVgm, reservation 1)

| Personas | Path | py/go | Note |
|---|---|---|---|
| admin, anon, host | `/l/{slug}` | 200/200 | len 581-670 vs 613, sim 0.77-0.91 |
| admin, anon, host | `/l/{slug}/1` | 200/200 | len 1480/10065 vs **5**, sim 0.00-0.01 — Go near-empty |
| all | `/l/{slug}/1/claim` | 200/200 | 455 vs 7 |
| all | `/l/{slug}/1/guide` | 200/200 | 1480/475 vs 5 |
| admin, anon | `/l/{slug}/1/guide/photos/1/1` | 200/200 | 1480 vs 5 |
| host | `/l/{slug}/1/guide/photos/1/1` | **404/200** | status-mismatch: Go must 404 (ownership) |
| all | `/l/{slug}/1/new` | 200/200 | 1480/10065 vs 467 |
| admin, anon | `/l/{slug}/1/edit/1` | **200/403** | status-mismatch: Go must match the Python access rule |
| admin, anon | `/l/{slug}/1/remove/1` | **200/403** | status-mismatch |

## 2. Context

- Python (read-only): `App/app/templates/guest/pick.html`, `pin.html`, `stay.html`, `form.html`, `guide.html`, `claim.html`, `remove.html`, `unavailable.html`.
- Go: `go/internal/web/guest/` — `pick.tmpl`, `pin.tmpl`, `form_content.tmpl`, `remove_content.tmpl`, `unavailable.tmpl`, `form_pages.go`, `guide_view.go`, `guide_photo.go`, `guide_gate_stub.go` (wired via `register_web_guest_*.go`).
- DOM to match: normalised DOM per page equal to Python. Status fixes: `/edit/1` and `/remove/1` must return Python's 200 for the fixture personas (match the Python access rule exactly; do not loosen security beyond it); `/guide/photos/1/1` must 404 when the photo is not the stay's (host row).
- **UbyPort:** the claim device gate is still a stub (#1241) — do not enable claim-dependent submission on Go; keep `claim_sendable` semantics identical (`docs/UBYPORT_CORE.md`). Field semantics of `form.html` must not change (#1246 control: field-name parity test).

## 3. Files

- `go/internal/web/guest/` handlers + templates; register tests; parity tests.

## 4. Steps

0. Anchors: `ls go/internal/web/guest/templates`; `grep -n 'func ' go/internal/web/guest/form_pages.go go/internal/web/guest/guide_view.go | head -20`.
1. Fix the two status mismatches first (edit/remove 200; photos 404 for a foreign photo).
2. Port `/l/{slug}/{res}` stay overview plus guide/claim/new/pick/pin DOM block-by-block.
3. Golden tests per path vs the Python render from the audit seed DB.

## 5. Do not touch

`App/`, `App/app/ubyport/`, claim device-gate semantics, Caddy, `UBYHOST_GO_PATHS`.

## 6. Commands

```bash
cd go && go test ./internal/web/guest/... ./cmd/ubyhost-web/... 2>&1 | tail -30
cd App && .venv/bin/python -m pytest tests/test_guest_*.py tests/test_guest_browser_e2e.py tests/test_ubyport_*.py tests/test_soap.py tests/test_submission_*.py tests/test_claim_*.py tests/test_endtoend.py tests/test_guest_guide*.py tests/test_privacy_*.py tests/test_pii_encryption.py tests/test_cookie_inventory.py -q --tb=short -x 2>&1 | tail -30
cd App && UBYHOST_E2E_PG=postgresql://postgres@127.0.0.1:5433 .venv/bin/python ../scripts/e2e/page_parity_audit.py 2>&1 | tail -5
# filter rows with path.startswith('/l/')
```

## 7. Acceptance

0 fail rows for all `/l/` paths (all personas, both dom-drift and status-mismatch); rows green 0 skipped; 1820 §6 screenshots.

## 8. Stop and ask

At the 25-call / 50k-token checkpoint (split by sub-page, report `Status: blocked`); immediately if Python's 200 on edit/remove for anon is itself a bug — that is an owner/security decision, do not "fix" it silently.

## 9. Report

`docs/tasks/2016-report.md`, <=600 tokens per session.
