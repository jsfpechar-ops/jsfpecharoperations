# 1720b: Go guest POST `/l/{token}/pin` (verify PIN)

Status: todo — ready for executor (exact-diff pass, 2026-11-20).
Depends on: **1720a merged** (#1172) — guest `shell.go` foundation | Base commit: tip after 1720a | Branch: task/1720b-go-guest-pin
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens
Tier: A (exact diffs only; exact-diff pass done; fresh review before ready)

> **One big PR mode.** Work on the current branch. After each step that changes a file, commit with the message `1720b step k`. Never create a branch, never push, never open a PR. Acceptance checks use `git log --oneline --grep='^1720b step'`.

## 1. Objective

Port **only** `POST /l/{token}/pin` (`verify_pin`): dual rate limits (`pin_fail` / `pin_fail_token`), Turnstile after three failures or link lock when configured, host alerts/audit on abuse, signed `ubyhost_pin` session cookie, and `pin.tmpl` error re-renders. Pick-stay, privacy and ruian stay in **1720c–d**. Route remains **dormant** until brief 1728.

## 2. Context

Hard rules (AGENTS.md): privacy first; no new dependency; Postgres `rate_limit_event` via existing table; light mode; forms work without JavaScript (_csrf field); Go first.

**Python source of truth:** `App/app/routes/guest.py` `verify_pin`, `_pin_page`, `_safe_return_to`; `App/app/rate_limit.py` PIN scopes; `App/app/auth.py` PIN cookie; `guest/pin.html`.

**Parity method:** `App/scripts/go_go_guest_shell_pin_golden.py` writes `go/internal/web/guest/testdata/shell_pin_golden.json` (stub seed; executor extends in step 2). Go test `pin_test.go` + future golden replay in 1720d unifies naming with `go_go_guest_shell_gate_golden.py`.

**Merge order:** Land **1720a** (#1172) before starting. Do not merge this PR until 1720a is on `main`.

Sidecars: `docs/tasks/1720b-files/<repo path>.txt`. Checksums:

| sha256 | file | action |
|---|---|---|
| (see `docs/tasks/1720b-files/MANIFEST.sha256`) | | |

Full manifest: `docs/tasks/1720b-files/MANIFEST.sha256`.

**Verified by the brief writer (on 1720a head):** `sha256sum -c docs/tasks/1720b-files/MANIFEST.sha256` all OK after copy; `gofmt -l` empty on touched Go paths; `go test ./internal/web/guest/... -count=1` OK; `go test ./cmd/ubyhost-web/... -run TestGuestShellRoutesRegistered` OK.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/guest/pin.go` | create | `verifyPin` handler |
| `go/internal/web/guest/pin_rate.go` | create | PIN rate-limit helpers |
| `go/internal/web/guest/pin_session.go` | create | PIN match + `ubyhost_pin` session |
| `go/internal/web/guest/pin_test.go` | create | unit tests |
| `go/internal/web/guest/templates/pin.tmpl` | create | PIN form (content block) |
| `go/internal/web/guest/shell.go` | edit | register `POST /l/{token}/pin` |
| `go/internal/web/guest/i18n.json` | edit | PIN + security strings |
| `go/internal/web/guest/i18n_keys.txt` | edit | key list |
| `go/cmd/ubyhost-web/register_web_guest_shell_test.go` | edit | mux pattern test |
| `go/internal/web/guest/testdata/shell_pin_golden.json` | create | golden stub |
| `App/scripts/go_go_guest_shell_pin_golden.py` | create | golden generator (stub) |
| `App/tests/test_go_go_guest_shell_pin_golden.py` | create | golden freshness |
| `docs/tasks/1720b-files/**` | keep | sidecars (do not edit) |
| `docs/tasks/1720b-report.md` | create | report (§9) |

No other file may change.

## 4. Steps

0. Checks (repo root). Anything other than the stated result: STOP (§8). Anchors in `docs/tasks/1720b-files/ANCHORS.txt`; sidecar count `12`.
1. Copy sidecars and verify:

   ```bash
   S=docs/tasks/1720b-files && for f in $(cd "$S" && find . -name '*.txt' ! -name 'ANCHORS.txt' | sed 's|^\./||; s|\.txt$||'); do mkdir -p "$(dirname "$f")" && cp "$S/$f.txt" "$f"; done && sha256sum -c "$S/MANIFEST.sha256" 2>&1 | tail -20
   ```

   Expected: 12 lines ending `: OK`. Commit `1720b step 1`.
2. Run golden script if extending seed; commit golden if changed. Commit `1720b step 2`.
3. Run §6; UX gate: 390 px screenshot of a wrong-PIN re-render in the report (rule 10).
4. Write `docs/tasks/1720b-report.md`. Set `Status: review` in this brief.

## 5. Do not touch

`UBYHOST_GO_PATHS`; pick/privacy/ruian routes (1720c–d); `App/app/` except §3 scripts/tests; parent brief 1720 monolith paths.

## 6. Commands

- `cd go && gofmt -l . | tail -5` prints nothing
- `cd go && go vet ./internal/web/guest/... 2>&1 | tail -20` is silent
- `cd go && go test ./internal/web/guest/... ./cmd/ubyhost-web/... -count=1 2>&1 | tail -30` passes (DB tests skip without `UBYHOST_TEST_DATABASE_URL`)
- `cd App && .venv/bin/python -m pytest tests/test_go_go_guest_shell_pin_golden.py -q --tb=short -x 2>&1 | tail -30` passes
- `python3 scripts/context_lint.py 2>&1 | tail -10` is clean

## 7. Acceptance

- Wrong PIN increments both rate scopes; 10 failures per IP / 30 per link match Python windows.
- Correct PIN sets `ubyhost_pin` with salt `ubyhost-guest-pin`, 303 to safe `return_to` inside `/l/{token}`.
- Turnstile shown after 3 failures or token lock when Turnstile required.
- `git diff --stat` lists only §3 paths.

## 8. Stop and ask

Anchor missing; golden differs unexpectedly; file outside §3 required; new column or dependency.

## 9. Report

`docs/tasks/1720b-report.md`: commits, command tails, 390 px PIN screenshot, accepted differences.

## Rollout wave and rollback

- **Rollout:** Dormant until brief 1728.
- **Rollback:** Revert the PR.

## Owner steps

None.