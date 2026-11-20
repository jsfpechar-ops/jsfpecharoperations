# 1710c: Go booking-site setup (host)

Status: todo — ready for executor (exact-diff pass, 2026-11-20).
Depends on: 1540-1544 (done), 1704 | Base commit: current tip of the working branch | Branch: task/1710c-go-booking-site-setup
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens
Tier: B (Sonnet wrote the exact-diff pass). Part of [1710](1710-go-property-page-host.md) split a→d.

> **One big PR mode.** Work on the current branch. After each step that changes a file, commit with the message `1710c step k`. Never create a branch, never push, never open a PR. Acceptance checks use `git log --oneline --grep='^1710c step'`.

## 1. Objective

Port the host booking-site setup screen: `booking_site_setup`, `booking_site_save` (`App/app/routes/payments.py` 554-632; helpers in `booking_setup.py`, `booking_site.py`, `booking_rails.setup_view`, `booking_manage.host_rows`). Go package `go/internal/web/booking`; template `templates/booking_site_setup.tmpl`. Routes stay dormant: nothing is added to `UBYHOST_GO_PATHS`. Pay/confirm/decline/cancel POSTs are brief **1710d**.

## 2. Context

Hard rules (AGENTS.md): 1 filing untouched; 2 privacy: no new personal-data field, no new outbound request; 3 fixtures `@example.test`; 4 no new dependency; 5 PostgreSQL through `pgxpool`; 6 light mode, forms work without JavaScript (Go forms carry `_csrf`); 11 Go first.

**Routes (method path, Python function):**

- GET /apartments/{apartment_id}/booking-site — `booking_site_setup`
- POST /apartments/{apartment_id}/booking-site — `booking_site_save` (settings, publish/unpublish, ical_done)

**Parity:** `App/scripts/go_booking_site_setup_golden.py` writes `go/internal/web/booking/testdata/booking_site_setup_golden.json`; `booking_site_setup_test.go` checks shape and helpers; full HTTP replay on PostgreSQL when `UBYHOST_TEST_DATABASE_URL` is set (go-first exception 1).

**All implementation code is pre-written.** Sidecars: `docs/tasks/1710c-files/<repo path>.txt`. Step 1 copies them; never retype or edit them.

Full manifest: `docs/tasks/1710c-files/MANIFEST.sha256`.

**Verified by the brief writer:** `sha256sum -c docs/tasks/1710c-files/MANIFEST.sha256` all OK after copy dry-run; `gofmt -l` empty on copied paths; `go vet ./internal/web/booking/...` silent; `go test ./internal/web/booking/... ./cmd/ubyhost-web/... -run 'BookingSite|BookingHostSite' -count=1` OK; golden script `--check` OK when `App/.venv` exists.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/booking/booking_site_setup.go` | create | GET/POST handlers |
| `go/internal/web/booking/booking_setup_steps.go` | create | setup steps + can_publish |
| `go/internal/web/booking/setup_save.go` | create | parse_form + save_settings |
| `go/internal/web/booking/rails_setup.go` | create | setup_view |
| `go/internal/web/booking/site_host_rows.go` | create | host_rows for list |
| `go/internal/web/booking/booking_site_setup_test.go` | create | golden + helper tests |
| `go/internal/web/booking/booking_site_setup_i18n_keys.txt` | create | catalog keys |
| `go/internal/web/booking/booking_site_setup_i18n.json` | create | catalog |
| `go/internal/web/booking/templates/booking_site_setup.tmpl` | create | Go twin of booking_site_setup.html |
| `go/internal/web/booking/testdata/booking_site_setup_golden.json` | create | golden from Python script |
| `go/cmd/ubyhost-web/register_web_booking_host_site_setup.go` | create | registers two routes |
| `go/cmd/ubyhost-web/register_web_booking_host_site_setup_test.go` | create | route registration test |
| `App/scripts/go_booking_site_setup_golden.py` | create | golden generator (go-first exception 1) |
| `App/tests/test_go_booking_site_setup_golden.py` | create | golden freshness test (go-first exception 1) |
| `docs/tasks/1710c-files/**` | keep | sidecars (do not edit) |
| `docs/tasks/1710c-report.md` | create | the report (§9) |

No other file may change.

## 4. Steps

0. Checks (repo root). Anything other than the stated result: STOP (§8). Anchors in `docs/tasks/1710c-files/ANCHORS.txt`.
1. Copy sidecars and verify `sha256sum -c docs/tasks/1710c-files/MANIFEST.sha256`. Commit `1710c step 1`.
2. `go test ./internal/web/booking/... ./cmd/ubyhost-web/... -count=1` passes. Commit if anything changed.
3. If `App/.venv` exists: run golden script and `pytest tests/test_go_booking_site_setup_golden.py -q`. Else note “CI only” in the report.
4. Confirm routes dormant (`UBYHOST_GO_PATHS` unchanged).
5. Run §6; write `docs/tasks/1710c-report.md`.

## 5. Do not touch

`UBYHOST_GO_PATHS`; `App/app/` except §3; `/booking-site/pay`, `/confirm`, `/decline`, `/cancel` (1710d); `/booking-sites` (1710b).

## 6. Commands

- `cd go && gofmt -l . | tail -5` prints nothing
- `cd go && go vet ./internal/web/booking/... ./cmd/ubyhost-web/... 2>&1 | tail -20` silent
- `cd go && go test ./internal/web/booking/... ./cmd/ubyhost-web/... -count=1 2>&1 | tail -30` passes
- `cd App && .venv/bin/python -m pytest tests/test_go_booking_site_setup_golden.py -q --tb=short -x 2>&1 | tail -30` passes
- `python3 scripts/context_lint.py 2>&1 | tail -10` clean

## 7. Acceptance

- Tenancy: every handler scopes by `apartment.owner_user_id`.
- `site_allowed` gate matches Python; save/publish/ical_done flash keys match.
- Golden file matches script; registration test sees both patterns.
- `git diff --stat` lists only §3 paths.

## 8. Stop and ask

Anchor missing; golden mismatch not on accepted list; file outside §3 required; 25 tool calls or ~50k tokens.

## 9. Report

`docs/tasks/1710c-report.md`: commits, command tails, UX gate when path switch runs.

## Rollout

Dormant until [1714](1714-go-booking-rollout.md). Rollback: revert the PR.

## Owner steps

None.