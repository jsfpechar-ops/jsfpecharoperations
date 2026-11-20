# 1597a: Go demo claim export (`EnsureClaimRow`, `StartClaim`, `ConfirmClaim`, `LockGuestAccess`)

Status: review
Depends on: 1732 (same `claim_ops` helpers) | Base commit: `origin/main` | Branch: `cursor/1597a-go-demo-claim-export-dff7`
Executor: Haiku 5.5 | Fits one session: 25 tool calls, 60k tokens
Tier: A (exact diffs only; claim state and outbox rows must match Python on mock demo paths)

## 1. Objective

Export package-level helpers in `go/internal/web/stays` for the claim steps `demo.seed` uses (`App/app/demo.py` `_claim_provisional`, `_claim_assigned`, `claim.ensure_row`, `claim.lock_guest_access`). Python sources: `claim.start_claim`, `claim.confirm`, `claim.ensure_row`, `claim.lock_guest_access` (`App/app/claim.py`). **No HTTP routes** and nothing in `UBYHOST_GO_PATHS`. Brief 1597 (`POST /demo`) calls these later; brief 1732 host resend reuses `startClaimResend`, which now returns the secret for callers.

## 2. Context

Hard rules (AGENTS.md): 1 filing correctness — confirm spends the secret and applies `declared_guests` under the reservation lock like Python; 2 privacy — demo fixtures use `@example.test`; 5 Postgres via `pgxpool`; 11 Go first.

**Blocker 1597 (2026-11-14):** demo seed stayed on Python because claim start/confirm were not exported. This brief unblocks that slice only.

**Parity:** `App/scripts/go_demo_claim_golden.py` pins claim row states and outbox kind for three demo-shaped steps (provisional → claimed → locked). `claim_seed_test.go` replays on PostgreSQL when `UBYHOST_TEST_DATABASE_URL` is set (go-first exception 1).

**All implementation code is pre-written.** Sidecars: `docs/tasks/1597a-files/<repo path>.txt`. Step 1 copies them; never retype or edit them. Checksums:

| sha256 | file | action | lines |
|---|---|---|---|
| `ce0d49b11951dadfe97141d5727829519061650cbdbb1b22246dec343430cce4` | `go/internal/web/stays/claim_seed.go` | create | 426 |
| `4e0b4369c3d52b56b6c0804c9ab820acc61e097bdadcda467d98db09666d090c` | `go/internal/web/stays/claim_seed_test.go` | create | 108 |
| `58ccc69e803d694568eb7774ccfb97224bd033dc2187b46f960876b78233f903` | `go/internal/web/stays/claim_ops.go` | edit | 813 |
| `e8a68668b2b749598449d10781dc5e313263baa1970cbf2cba50488e6b81b00a` | `go/internal/web/stays/testdata/demo_claim_golden.json` | create | small |
| `04e95abd296fa622c4ff8274337d5f0bff35397d4653630ab8953b71adbfd810` | `App/scripts/go_demo_claim_golden.py` | create | 70 |
| `b8a7f70ad58be105af341a1d1b409d23cc4dab3a725760b3f8369bccb9176a5e` | `App/tests/test_go_demo_claim_golden.py` | create | 20 |

Full manifest: `docs/tasks/1597a-files/MANIFEST.sha256`.

**Verified by the brief writer:** `sha256sum -c docs/tasks/1597a-files/MANIFEST.sha256` all OK; `gofmt -l` empty on copied paths; `go vet ./internal/web/stays/...` silent; `go test ./internal/web/stays/ -count=1 -run 'DemoClaim|ClaimSeed'` OK (DB parity skipped without `UBYHOST_TEST_DATABASE_URL`); `pytest tests/test_go_demo_claim_golden.py` OK.

**`claim_ops.go` edit:** `startClaimResend` returns `(bool, string, string, error)` so the last value is the new secret (resend handler ignores it).

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/stays/claim_seed.go` | create | exported APIs |
| `go/internal/web/stays/claim_seed_test.go` | create | golden + DB parity |
| `go/internal/web/stays/testdata/demo_claim_golden.json` | create | golden |
| `go/internal/web/stays/claim_ops.go` | edit | resend returns secret |
| `App/scripts/go_demo_claim_golden.py` | create | golden generator |
| `App/tests/test_go_demo_claim_golden.py` | create | golden freshness |
| `docs/tasks/1597a-files/**` | keep | sidecars |
| `docs/tasks/1597a-report.md` | create | report (§9) |

No other file may change.

## 4. Steps

0. Checks (repo root). See `docs/tasks/1597a-files/ANCHORS.txt`. Anything other than the stated result: STOP (§8).

1. Copy sidecars and verify (repo root):

   ```bash
   S=docs/tasks/1597a-files && for f in $(cd "$S" && find . -name '*.txt' ! -name 'ANCHORS.txt' | sed 's|^\./||; s|\.txt$||'); do mkdir -p "$(dirname "$f")" && cp "$S/$f.txt" "$f"; done && sha256sum -c "$S/MANIFEST.sha256" 2>&1 | tail -20
   ```

   All lines must end with `: OK`. Commit `1597a step 1`.

2. Format, vet, test (from `go/`):

   ```bash
   cd go && gofmt -l internal/web/stays 2>&1 | tail -5
   go vet ./internal/web/stays/... 2>&1 | tail -10
   go test ./internal/web/stays/ -count=1 -run 'DemoClaim|ClaimSeed' 2>&1 | tail -15
   ```

   From `App/`: `.venv/bin/python -m pytest tests/test_go_demo_claim_golden.py -q --tb=short 2>&1 | tail -10`

3. Write `docs/tasks/1597a-report.md`, set `Status: review`, commit `1597a step 3`. From repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`

## 5. Do not touch

Guest routes, `POST /demo`, `UBYHOST_GO_PATHS`, `App/app/claim.py`, migrations, deploy.

## 6. Commands

Exactly §4. No full suite.

## 7. Acceptance

- [ ] `sha256sum -c` OK for all six files.
- [ ] `go test` and `pytest` steps green.
- [ ] `git diff --stat main...HEAD` lists only §3 paths and sidecars.

## 8. Stop and ask

Hashes mismatch, tests fail twice, cap, or a file outside §3 must change.

## 9. Report

Write `docs/tasks/1597a-report.md` (600 tokens max), tick §7, note accepted differences, owner steps: none (dormant until brief 1597).

## Risk list (for the reviewer)

`StartClaim` guarded write + one retry (brief 1115). `ConfirmClaim` transaction order vs `headcount.apply_declared_in` (demo stays have no guest rows yet). Claim mail body is link-only like existing Go resend until guest mail ports.

## Owner steps

None. Do not add `/demo` to Go paths until brief 1597 lands with brief 1596 together.