# 1710d: Go booking-site host actions (pay, confirm, decline, cancel)

Status: todo — ready for executor (exact-diff pass, 2026-11-20).
Depends on: 1540-1544 (done), 1704, 1710c (setup page for redirects; routes are independent) | Base commit: current tip of the working branch | Branch: task/1710d-go-booking-site-actions
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens
Tier: B (Sonnet wrote the exact-diff pass; the orchestrator reads the diff of the risk-listed files). Part of [1710](1710-go-property-page-host.md) split a→d.

> **One big PR mode.** Work on the current branch. After each step that changes a file, commit with the message `1710d step k`. Never create a branch, never push, never open a PR. Acceptance checks use `git log --oneline --grep='^1710d step'`.

## 1. Objective

Port the host booking-site POST actions from `App/app/routes/payments.py` 635-720: `booking_site_pay`, `booking_site_confirm`, `booking_site_decline`, `booking_site_cancel` (confirm/decline use `booking_direct`; cancel uses `booking_cancel.cancel(by_host=True)` and `booking_rails.parse_form` for pay). Go: `booking_site_actions.go`, `rails_form.go`, `payments/booking_webhook_host.go`. Routes stay dormant: nothing is added to `UBYHOST_GO_PATHS`. Reuses setup redirect target `/apartments/{id}/booking-site` (brief 1710c).

## 2. Context

Hard rules (AGENTS.md): 1 filing untouched; 2 privacy: no new personal-data field, no new outbound request beyond existing mail enqueue; 4 no new dependency; 5 PostgreSQL through `pgxpool`; 6 light mode, forms with `_csrf`; 11 Go first.

**Routes (method path, Python function):**

- POST /apartments/{apartment_id}/booking-site/pay — `booking_site_pay`
- POST /apartments/{apartment_id}/booking-site/confirm — `booking_site_confirm` → `booking_direct.confirm`
- POST /apartments/{apartment_id}/booking-site/decline — `booking_site_decline` → `booking_direct.decline`
- POST /apartments/{apartment_id}/booking-site/cancel — `booking_site_cancel` → `booking_cancel.cancel(by_host=True)`

**Parity:** `App/scripts/go_booking_site_actions_golden.py` → `booking_site_actions_golden.json`; unit tests for `ParseRailsForm` and route registration. Full HTTP replay on PostgreSQL when `UBYHOST_TEST_DATABASE_URL` is set is optional (go-first exception 1).

**All implementation code is pre-written.** Sidecars: `docs/tasks/1710d-files/<repo path>.txt`. Step 1 copies them; never retype or edit them.

| sha256 | file | action |
|---|---|---|
| `f5ee82dc379c4738551e39f13cfedaa3c2172125881d8fc2a6a8dfbdbc5ee98e` | `App/scripts/go_booking_site_actions_golden.py` | create |
| `2e90519328777de1ddc74b8d3d7ef8dfc3c4392864acde5e8d2056a08dae7011` | `App/tests/test_go_booking_site_actions_golden.py` | create |
| `aeea5bdddc57e69e9aa174b1654f91acc5f9f9944ca750bce13d8012cf46582a` | `go/cmd/ubyhost-web/register_web_booking_host_actions.go` | create |
| `8e1cdff3adbcfc15d40cd4ddc82d0ebcecb85ee6a4b828d436b7d7c4ddb972ea` | `go/cmd/ubyhost-web/register_web_booking_host_actions_test.go` | create |
| `b3a7b2700300cb38165e9fa569711cedfeb73781a8ed9ffd4ce5ebe0e5bcca20` | `go/internal/web/booking/booking_site_actions.go` | create |
| `9960320d95f8d307efd12147c3c1cc11660fd49d3a19bf96b88a3c110ce4bb04` | `go/internal/web/booking/booking_site_actions_test.go` | create |
| `f7b6d54c2793f601cec6bc2cdadb1e548e08572cb0c36d58a87456faee8242d9` | `go/internal/web/booking/booking_site_host_i18n.json` | create |
| `acd0450e9a7f0fc21a28cae9b397b27fa062f9f80c548c7fd5ccfeffe1d9fd3c` | `go/internal/web/booking/booking_site_host_i18n_keys.txt` | create |
| `000dafcf9065dd4f504839b746ba2a35dac14b4b6925f76f502eb7d343bce2ba` | `go/internal/web/booking/rails_form.go` | create |
| `ca0237292e2c195fc3f4340929e01a069f04a4f6b364d86c96fe60f26564f170` | `go/internal/web/booking/rails_form_test.go` | create |
| `5ffa8967730f1dbf19644a9d0bad128a41562cab863093818833f2e02f1d8089` | `go/internal/web/booking/testdata/booking_site_actions_golden.json` | create |
| `017a860c2040c7a45f5c27f744fa27576515b4a7a67899fa42d4cbfc08af04f6` | `go/internal/payments/booking_webhook_host.go` | create |

Full manifest: `docs/tasks/1710d-files/MANIFEST.sha256`.

**Verified by the brief writer:** `sha256sum -c docs/tasks/1710d-files/MANIFEST.sha256` all OK; `gofmt -l` empty on copied paths; `go vet ./internal/web/booking/... ./internal/payments/booking_webhook_host.go` silent; `go test ./internal/web/booking/... ./cmd/ubyhost-web/... -run 'ParseRails|BookingSite' -count=1` OK; golden script `--check` OK.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/booking/booking_site_actions.go` | create | four POST handlers |
| `go/internal/web/booking/booking_site_actions_test.go` | create | golden shape |
| `go/internal/web/booking/booking_site_host_i18n.json` | create | flash keys for host actions |
| `go/internal/web/booking/booking_site_host_i18n_keys.txt` | create | catalog keys |
| `go/internal/web/booking/rails_form.go` | create | `booking_rails.parse_form` |
| `go/internal/web/booking/rails_form_test.go` | create | parse_form tests |
| `go/internal/web/booking/testdata/booking_site_actions_golden.json` | create | golden from script |
| `go/internal/payments/booking_webhook_host.go` | create | confirm, decline, host cancel |
| `go/cmd/ubyhost-web/register_web_booking_host_actions.go` | create | route registration |
| `go/cmd/ubyhost-web/register_web_booking_host_actions_test.go` | create | registration test |
| `App/scripts/go_booking_site_actions_golden.py` | create | golden generator |
| `App/tests/test_go_booking_site_actions_golden.py` | create | golden freshness |
| `docs/tasks/1710d-files/**` | keep | sidecars |
| `docs/tasks/1710d-report.md` | create | report (§9) |

No other file may change.

## 4. Steps

0. Checks (repo root). Anchors in `docs/tasks/1710d-files/ANCHORS.txt` — each `grep -cF` prints `1`, the three `ls … No such file` lines print `1` on a clean tree, `find … | wc -l` prints `12`, `grep -rcF POST route` prints nothing.
1. Copy sidecars and verify:

   ```bash
   S=docs/tasks/1710d-files && for f in $(cd "$S" && find . -name '*.txt' ! -name 'ANCHORS.txt' | sed 's|^\./||; s|\.txt$||'); do mkdir -p "$(dirname "$f")" && cp "$S/$f.txt" "$f"; done && sha256sum -c "$S/MANIFEST.sha256" 2>&1 | tail -15
   ```

   Expected: 12 lines ending `: OK`. Commit `1710d step 1`.
2. `cd go && gofmt -l ...` empty; `go vet ./internal/web/booking/... ./internal/payments/...`; `go test ./internal/web/booking/... ./cmd/ubyhost-web/... -count=1`. Commit if needed.
3. If `App/.venv` exists: `pytest tests/test_go_booking_site_actions_golden.py -q`. Else note “CI only” in the report.
4. Confirm routes dormant (`UBYHOST_GO_PATHS` unchanged).
5. Run §6; write `docs/tasks/1710d-report.md`.

## 5. Do not touch

`UBYHOST_GO_PATHS`; booking-site GET/setup (1710c); guest `/p/*` cancel (1553); property page (1710a).

## 6. Commands

- `cd go && gofmt -l . | tail -5` prints nothing
- `cd go && go vet ./internal/web/booking/... ./internal/payments/... 2>&1 | tail -20` silent
- `cd go && go test ./internal/web/booking/... ./cmd/ubyhost-web/... -count=1 2>&1 | tail -30` passes
- `cd App && .venv/bin/python -m pytest tests/test_go_booking_site_actions_golden.py -q --tb=short -x 2>&1 | tail -30` passes
- `python3 scripts/context_lint.py 2>&1 | tail -10` clean

## 7. Acceptance

- Tenancy on every handler; Max plan gate on pay; confirm creates reservation under `booking_site_dates` lock; Stripe host cancel refunds with idempotency key.
- Golden matches script; registration test sees all four POST patterns.
- `git diff --stat` lists only §3 paths.

## 8. Stop and ask

Anchor missing; golden mismatch; file outside §3 required; 25 tool calls or ~50k tokens.

## 9. Report

`docs/tasks/1710d-report.md`: commits, command tails, accepted differences.

## Rollout

Dormant until [1714](1714-go-booking-rollout.md).

## Owner steps

None.