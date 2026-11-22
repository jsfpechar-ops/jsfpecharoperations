# 2022: The claim device gate is real, or it is documented as off

Status: blocked (owner decision in §8) | Depends on: 2016 | Branch: task/2022-claim-device-gate
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens | Tier: **A** (security, UbyPort filing)

## 1. Objective

Two stubs are the residual security gap of the Go guest-link hub, flagged in the 2010 index (§2.4, from review of PRs #1241/#1240) and **not closed by 2016**:

- `formPagesRequireClaim`
- `stayClaimDeviceGate`

They are stubs, the gate is **OFF**, and Go `/l/...` claim is therefore reachable without it. The index says: "Close in **2016**; do not enable claim-dependent flows on Go before then." 2016 shipped the hub's pages without closing it.

This is **not** the same thing as the two 200s the 2016 report explained. Those are Python's claim ask (`UBYHOST_GUEST_PIN=0` makes `_require_pin` return `None`; `_require_claim_session` 303s to the claim page), and ownership still yields 403 `not_yours`. The device gate is a separate question: *which device may see a stay at all.*

Do not read this brief as "enable the gate". The defect may be that it is off, or that nobody wrote down that it is deliberately off. **§8 decides which.**

## 2. Context

- `docs/UBYPORT_CORE.md` — **read it first**. `claim_sendable` and the submission state machine are the guard that matters; the state machine row is in `docs/OPERATIONS.md#the-submit_state-state-machine`.
- Python reference (read-only): `App/app/guest.py` (`DeviceHoldsClaim` fail-closed, `_require_claim_session` ~1242-1256, `_require_pin` ~755), `App/app/config.py` (`GUEST_PIN_REQUIRED`, `config.py:441`), `App/app/ubyport/`.
- Go: `go/internal/web/guest/guide_gate_stub.go`, `stay_claim.go`, `pick.go`, `pick_cookies.go`, `guide_page.go`, `cmd/ubyhost-web/` route registration.
- Measured 2026-11-22: `/l/<token>/edit/<res>` and `/l/<token>/remove/<res>` answer **403** for a device without the claim (`DeviceHoldsClaim` fail-closed) — the UX gate could not photograph the real forms because of it (`docs/tasks/2019-ux-gate-2011-2018.md` gap 4).
- Rule 11: this is a security fix on a path Python still serves in production, so it is **go-first exception 3** territory — the smallest fix goes into Go, and Python only if the brief proves it must. State which in §4.

## 3. Files

- `go/internal/web/guest/guide_gate_stub.go`, `stay_claim.go`, `pick.go`, `pick_cookies.go`, `guide_page.go`
- Their `*_test.go` files, and `cmd/ubyhost-web/register_web_guest_*.go` if a route is gated.
- Read-only reference: `App/app/guest.py`, `App/app/config.py`. **If §4 needs a Python change**, this brief must say it is exception 3 (filing/security bug) or it is not run as written.

## 4. Steps

1. Read `docs/UBYPORT_CORE.md` §claim_sendable and the submit_state machine. Write down, in the report, the exact rule the gate enforces.
2. Diff Python's `DeviceHoldsClaim` / `_require_claim_session` against Go's stub: which cookie, which claim record, which path list, what each returns when it fails.
3. Implement `formPagesRequireClaim` and `stayClaimDeviceGate` so Go answers what Python answers for: no cookie, stale cookie, cookie for another reservation, cookie for this one. Table each of the four.
4. Decide, and record, whether the gate may be switched on. **Do not switch it on in this brief** — §8.
5. Test: unit tests for the four device states, plus a route test that a claim-dependent form is not reachable without the claim.

## 5. Do not touch

`App/app/` beyond what §4 justifies, other pages, Caddy, `UBYHOST_GO_PATHS`, deploy files, secrets. No change to guest field semantics (UBYPORT_CORE forbids it). No new dependency.

## 6. Commands

```bash
cd go && go build ./... && gofmt -l ./internal ./cmd 2>&1 | tail -30
cd go && go test ./internal/web/guest/... ./cmd/ubyhost-web/... -count=1 2>&1 | tail -30
python3 scripts/go_parity_check.py --all 2>&1 | tail -30
cd App && UBYHOST_E2E_PG=postgresql://postgres@127.0.0.1:5433 .venv/bin/python ../scripts/e2e/page_parity_audit.py 2>&1 | tail -5
```

The 21 `/l/...` rows of 2016 must stay at fail 0. If a device gate closes a row that used to pass, that is a §8 stop, not a green.

## 7. Acceptance

- The four device states are covered by tests and Go matches Python on each.
- The 21 `/l/...` audit rows still fail 0.
- The report states plainly whether the gate is on or off after this brief, and who decided.

## 8. Stop and ask — the owner decides this brief

Bring the owner exactly this choice, with the evidence from §4:

1. **Turn the gate on** — tell him the user-visible change (a guest on a second device will have to re-claim) and the filing consequence.
2. **Leave it off and document it** — then say where, so the next reader does not rediscover it.
3. **Port Python's gate behaviour exactly** — even if that means Go and Python agree that the gate does nothing.

Also stop at the 25-call / 50k-token checkpoint, and on any change to `claim_sendable` or the submission state machine.

## 9. Report

`docs/tasks/2022-report.md`, ≤600 tokens: the rule from UbyPort Core, the four-state table, gate state after the brief, the owner's decision and its date, deviations.
