# 1720c: Go guest GET `/l/{token}` (pick_stay)

Status: todo — ready for executor (exact-diff pass, 2026-11-20).
Depends on: **1720b merged** (#1181) — PIN route and `ubyhost_pin` session | Base commit: tip after 1720b | Branch: task/1720c-go-guest-pick
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens
Tier: A (exact diffs only; exact-diff pass done; fresh review before ready)

> **One big PR mode.** Work on the current branch. After each step that changes a file, commit with the message `1720c step k`. Never create a branch, never push, never open a PR. Acceptance checks use `git log --oneline --grep='^1720c step'`.

## 1. Objective

Port **only** `GET /l/{token}` (`pick_stay`): PIN guard when `UBYHOST_GUEST_PIN` is on, visible stay window, device-owned lane badges, claimed incomplete stays, `pick.tmpl` + `_why` fragment, and `unavailable` for `no_stays`. Privacy and ruian stay in **1720d**. Route remains **dormant** until brief 1728.

## 2. Context

Hard rules (AGENTS.md): privacy first; no new dependency; Postgres via `pgxpool`; light mode; Go first.

**Python source of truth:** `App/app/routes/guest.py` `pick_stay`, `_visible_reservations`, `_require_pin`, `_owned_ids`, `_claimed_reservation_ids`; `App/app/templates/guest/pick.html`, `_why.html`, `unavailable.html`.

**Parity method:** `App/scripts/go_go_guest_shell_pick_golden.py` → `go/internal/web/guest/testdata/shell_pick_golden.json` (stub seed; executor extends). Unify full gate golden naming in 1720d.

**Merge order:** Land **1720b** (#1181) before starting. Stack this PR on `cursor/1720b-guest-pin-dff7` until 1720b is on `main`.

Sidecars: `docs/tasks/1720c-files/<repo path>.txt`. Checksums:

| sha256 | file | action |
|---|---|---|
| (see `docs/tasks/1720c-files/MANIFEST.sha256`) | | |

Full manifest: `docs/tasks/1720c-files/MANIFEST.sha256`.

**Verified by the brief writer (on 1720b head):** `sha256sum -c docs/tasks/1720c-files/MANIFEST.sha256` all OK after copy; `gofmt -l` empty on touched Go paths; `go test ./internal/web/guest/... ./cmd/ubyhost-web/... -count=1` OK; `pytest tests/test_go_go_guest_shell_pick_golden.py` OK.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/guest/pick.go` | create | `pickStay` handler and templates |
| `go/internal/web/guest/pick_data.go` | create | visible window, registration complete |
| `go/internal/web/guest/pick_cookies.go` | create | owned + claim cookies |
| `go/internal/web/guest/pick_alert.go` | create | controller_missing alert |
| `go/internal/web/guest/pick_test.go` | create | unit tests |
| `go/internal/web/guest/templates/pick.tmpl` | create | stay picker |
| `go/internal/web/guest/templates/why_fragment.tmpl` | create | legal why block |
| `go/internal/web/guest/templates/unavailable.tmpl` | create | `no_stays` page |
| `go/internal/web/guest/shell.go` | edit | register `GET /l/{token}` |
| `go/internal/web/guest/i18n.json` | edit | pick strings |
| `go/internal/web/guest/i18n_keys.txt` | edit | key list |
| `go/cmd/ubyhost-web/register_web_guest_shell_test.go` | edit | mux pattern test |
| `go/internal/web/guest/testdata/shell_pick_golden.json` | create | golden stub |
| `App/scripts/go_go_guest_shell_pick_golden.py` | create | golden generator (stub) |
| `App/tests/test_go_go_guest_shell_pick_golden.py` | create | golden freshness |
| `docs/tasks/1720c-files/**` | keep | sidecars (do not edit) |
| `docs/tasks/1720c-report.md` | create | report (§9) |

No other file may change.

## 4. Steps

0. Checks (repo root). Anything other than the stated result: STOP (§8). Anchors in `docs/tasks/1720c-files/ANCHORS.txt`; sidecar count `15`.
1. Copy sidecars and verify:

   ```bash
   S=docs/tasks/1720c-files && for f in $(cd "$S" && find . -name '*.txt' ! -name 'ANCHORS.txt' | sed 's|^\./||; s|\.txt$||'); do mkdir -p "$(dirname "$f")" && cp "$S/$f.txt" "$f"; done && sha256sum -c "$S/MANIFEST.sha256" 2>&1 | tail -20
   ```

   Expected: 15 lines ending `: OK`. Commit `1720c step 1`.
2. Run golden script if extending seed; commit golden if changed. Commit `1720c step 2`.
3. Run §6; UX gate: 390 px screenshot of the stay picker (and PIN interstitial when PIN required) in the report (rule 10).
4. Write `docs/tasks/1720c-report.md`. Set `Status: review` in this brief.

## 5. Do not touch

`UBYHOST_GO_PATHS`; privacy/ruian routes (1720d); `App/app/` except §3 scripts/tests; parent brief 1720 monolith paths.

## 6. Commands

- `cd go && gofmt -l . | tail -5` prints nothing
- `cd go && go vet ./internal/web/guest/... 2>&1 | tail -20` is silent
- `cd go && go test ./internal/web/guest/... ./cmd/ubyhost-web/... -count=1 2>&1 | tail -30` passes (DB tests skip without `UBYHOST_TEST_DATABASE_URL`)
- `cd App && .venv/bin/python -m pytest tests/test_go_go_guest_shell_pick_golden.py -q --tb=short -x 2>&1 | tail -30` passes
- `python3 scripts/context_lint.py 2>&1 | tail -10` is clean

## 7. Acceptance

- Empty window renders `no_stays` unavailable page with 200.
- PIN required without session re-renders PIN page with `return_to` the picker URL.
- Pick list shows date range, nights label, lane status, and links to `/l/{token}/{id}`.
- 390 px screenshot of the picker.
- `git log --oneline --grep='^1720c step'` shows one commit per step; `git diff --stat` lists only §3 paths.

## 8. Stop and ask

Stop and write the report instead of continuing when: an anchor is not found verbatim; a golden differs and the difference is not on the accepted list; a file outside §3 would have to change; a new column, retention line or outbound request is needed; the tests need a skip.

## 9. Report

`docs/tasks/1720c-report.md`: commits, command outputs (last 30 lines), screenshots (390 px picker), what was left undone.

## Rollout wave and rollback

- **Rollout:** Dormant until brief 1728 adds paths to `UBYHOST_GO_PATHS`.
- **Rollback:** Revert the PR.

## Owner steps

None.