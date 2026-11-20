# 1720d: Go guest privacy notice + RUIAN suggest

Status: todo — ready for executor (exact-diff pass, 2026-11-20).
Depends on: **1720b merged** (#1181) — PIN route and `requirePin` session | Base commit: tip after 1720b | Branch: task/1720d-go-guest-privacy-ruian
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens
Tier: A (exact diffs only; exact-diff pass done; fresh review before ready)

> **One big PR mode.** Work on the current branch. After each step that changes a file, commit with the message `1720d step k`. Never create a branch, never push, never open a PR. Acceptance checks use `git log --oneline --grep='^1720d step'`.

## 1. Objective

Port **only** `GET /l/{token}/privacy` (`privacy_notice`) and `GET /l/{token}/ruian-suggest` (`ruian_suggest`). Wire the unified golden harness `go_go_guest_shell_gate_golden.py` + `test_go_go_guest_shell_gate_golden.py` (monolith brief §2/§6 naming). Pick-stay stays in **1720c**. Routes remain **dormant** until brief 1728.

## 2. Context

Hard rules (AGENTS.md): privacy first; guest ruian may call ČÚZK (`go/internal/ruian/suggest_live.go` — reason in PR); light mode; Go first.

**Python source of truth:** `App/app/routes/guest.py` `privacy_notice`, `ruian_suggest`; `App/app/ruian.py` suggest path; `guest/privacy.html`, `_cookie_table.html`.

**Parity method:** `App/scripts/go_go_guest_shell_gate_golden.py` writes `go/internal/web/guest/testdata/shell_gate_golden.json`. Executor step 2 replays FastAPI; Go `privacy_test.go` covers template smoke until golden cases exist.

**Merge order:** Land **1720b** (#1181) before starting.

Sidecars: `docs/tasks/1720d-files/<repo path>.txt`. Full manifest: `docs/tasks/1720d-files/MANIFEST.sha256`.

**Verified by the brief writer (on 1720b head):** `sha256sum -c docs/tasks/1720d-files/MANIFEST.sha256` all OK after copy; `gofmt -l` empty on touched Go paths; `go test ./internal/web/guest/... -count=1` OK; `go test ./cmd/ubyhost-web/... -run TestGuestShellRoutesRegistered` OK.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/guest/privacy.go` | create | privacy notice handler + template render |
| `go/internal/web/guest/ruian_suggest.go` | create | guest JSON suggest + rate limits |
| `go/internal/web/guest/shared.go` | create | shared context, controller, `requirePin` |
| `go/internal/web/guest/guest_cookie.go` | create | embed cookie inventory |
| `go/internal/web/guest/guest_cookie_inventory.json` | create | from `cookie_inventory.py` |
| `go/internal/web/guest/privacy_test.go` | create | template + ruian query smoke |
| `go/internal/web/guest/shell.go` | edit | apartment fields, register GET routes |
| `go/internal/web/guest/templates/privacy.tmpl` | create | `guest/privacy.html` parity |
| `go/internal/web/guest/templates/cookie_table.tmpl` | create | `_cookie_table.html` parity |
| `go/internal/web/guest/i18n.json` | edit | privacy + cookie table strings |
| `go/internal/web/guest/i18n_keys.txt` | edit | key list |
| `go/internal/ruian/suggest_live.go` | create | live ČÚZK suggest (guest + host parity) |
| `go/cmd/ubyhost-web/register_web_guest_shell_test.go` | edit | mux pattern test |
| `go/internal/web/guest/testdata/shell_gate_golden.json` | create | golden stub |
| `App/scripts/go_go_guest_shell_gate_golden.py` | create | unified golden generator |
| `App/tests/test_go_go_guest_shell_gate_golden.py` | create | golden freshness |
| `docs/tasks/1720d-files/**` | keep | sidecars (do not edit) |
| `docs/tasks/1720d-report.md` | create | report (§9) |

No other file may change.

## 4. Steps

0. Checks (repo root). Anything other than the stated result: STOP (§8). Anchors in `docs/tasks/1720d-files/ANCHORS.txt`; sidecar count **16**.
1. Copy sidecars and verify:

   ```bash
   S=docs/tasks/1720d-files && for f in $(cd "$S" && find . -name '*.txt' ! -name 'ANCHORS.txt' | sed 's|^\./||; s|\.txt$||'); do mkdir -p "$(dirname "$f")" && cp "$S/$f.txt" "$f"; done && sha256sum -c "$S/MANIFEST.sha256" 2>&1 | tail -20
   ```

   Expected: 16 lines ending `: OK`. Commit `1720d step 1`.
2. Run `App/scripts/go_go_guest_shell_gate_golden.py`; extend seed in executor step 2 if golden `cases` grow. Commit `1720d step 2`.
3. Run §6; UX gate: 390 px screenshot of privacy page in the report (rule 10).
4. Write `docs/tasks/1720d-report.md`. Set `Status: review` in this brief.

## 5. Do not touch

`UBYHOST_GO_PATHS`; `GET /l/{token}` pick-stay (1720c); monolith `go_shell_golden.py` names; `App/app/` except §3 scripts/tests.

## 6. Commands

- `cd go && gofmt -l . | tail -5` prints nothing
- `cd go && go vet ./internal/web/guest/... ./internal/ruian/... 2>&1 | tail -20` is silent
- `cd go && go test ./internal/web/guest/... ./cmd/ubyhost-web/... -count=1 2>&1 | tail -30` passes (DB tests skip without `UBYHOST_TEST_DATABASE_URL`)
- `cd App && .venv/bin/python -m pytest tests/test_go_go_guest_shell_gate_golden.py -q --tb=short -x 2>&1 | tail -30` passes
- `python3 scripts/context_lint.py 2>&1 | tail -10` is clean

## 7. Acceptance

- Privacy page renders controller, host, cookie table, operator block with notice version env.
- Ruian disabled → 404 `{"error":"not_found"}`; short `q` → `[]`; rate limited → 429 `{"error":"rate_limited"}`.
- Golden file uses **`shell_gate_golden.json`** and pytest name **`test_go_go_guest_shell_gate_golden.py`** (unified with parent 1720 brief).
- `git diff --stat` lists only §3 paths.

## 8. Stop and ask

Anchor missing; golden differs unexpectedly; file outside §3 required; new retention line without owner decision.

## 9. Report

`docs/tasks/1720d-report.md`: commits, command tails, 390 px privacy screenshot, accepted differences, outbound ČÚZK note.

## Rollout wave and rollback

- **Rollout:** Dormant until brief 1728.
- **Rollback:** Revert the PR.

## Owner steps

None.