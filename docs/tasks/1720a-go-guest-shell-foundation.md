# 1720a: Go guest shell foundation (package, language, base layout)

Status: todo — ready for executor (exact-diff pass, 2026-11-20).
Depends on: 1500–1510 session library, 1380 layout, palette slug helpers | Base commit: current tip of the working branch | Branch: task/1720a-go-guest-shell-foundation
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens
Tier: A (exact diffs only; Opus writes the exact-diff pass; fresh review of the full diff before ready)

> **One big PR mode.** Work on the current branch. After each step that changes a file, commit with the message `1720a step k`. Never create a branch, never push, never open a PR. Acceptance checks use `git log --oneline --grep='^1720a step'`.

## 1. Objective

Create the `go/internal/web/guest` package: token/slug `_resolve_key` / `_open_link`, exported `GuestLanguage` / `SetGuestLanguages`, `GuestLink` / `LangQuery`, the guest `base.tmpl` shell (port of `App/app/templates/guest/base.html`), and dormant `register_web_guest_shell.go`. No PIN, pick-stay, privacy or ruian routes yet (briefs 1720b–d). Golden parity starts in 1720b.

## 2. Context

Hard rules (AGENTS.md): 1 filing correctness first; 2 privacy first; 3 no secrets; 4 no new dependency without a decision line; 5 Postgres through pgxpool; 6 light mode, forms without JavaScript; 11 Go first.

**Python source of truth:** `App/app/routes/guest.py` (`_resolve_key`, `_open_link`, `_guest_link`, `_lang_q`, `_language`, LANG_COOKIE), `App/app/templates/guest/base.html`, `App/app/guest_slug.py` lookup shape, `App/app/i18n.py` guest language rules.

**Routes in scope:** none live yet — `RegisterShell` is an empty hook until 1720b–d.

**Merge order:** Land **1720a** before brief 1722 (#1165) merges so shared `GuestLink`, `LangQuery`, `GuestLanguage` and `ResolveKey` live in `shell.go` (1722 `party.go` may drop its local copies in a follow-up).

**All implementation code is pre-written.** Sidecars: `docs/tasks/1720a-files/<repo path>.txt`. Step 1 copies them; never retype or edit them. Checksums:

| sha256 | file | action |
|---|---|---|
| `3eac4d84e28c32202a2bcfd25c52951a2ffad2c08c08183dd8bcb3b8247b5885` | `go/cmd/ubyhost-web/register_web_guest_shell.go` | create |
| `50f0a9a5e0d0f64b089e1fdb3880245f426ee677a69d4e5ce1690aa354fbdeac` | `go/cmd/ubyhost-web/register_web_guest_shell_test.go` | create |
| `06007ea08b3c98e8250062e71b787d9f145bfd63e4eebc1fcf3c85790a5549cb` | `go/internal/web/guest/i18n.json` | create |
| `f51bbc83208d9bccecb8e2c82ba3e8ad92735fde63870632f3a1c2bdf1972cff` | `go/internal/web/guest/i18n_keys.txt` | create |
| `e40fdfc003f7b806c4d53d1b10f32bb35700036d1dc7300171b2941e46305044` | `go/internal/web/guest/shell.go` | create |
| `3cc493f79aa5a65f6ad269d26dcfa264e9cc128f83ae1ba3b26b852ff910a219` | `go/internal/web/guest/shell_test.go` | create |
| `aaad5d214a80599f0b30617527ed3216417de02cb4efa5c669fa03187eae13d1` | `go/internal/web/guest/templates/base.tmpl` | create |
| `650c4ede3247ab5c10e1587901e5ffc7da0a429fe9c682677f79bbe628abd61a` | `go/internal/web/guest/templates/host_fragment.tmpl` | create |

Full manifest: `docs/tasks/1720a-files/MANIFEST.sha256`.

**Verified by the brief writer:** sidecars dry-run on current `main` with step 1 copy — `sha256sum -c docs/tasks/1720a-files/MANIFEST.sha256` all OK; `gofmt -l` empty on copied paths; `go vet ./internal/web/guest/... ./cmd/ubyhost-web/register_web_guest_shell.go` silent; `go test ./internal/web/guest/... -count=1` OK; `go test ./cmd/ubyhost-web/... -run TestGuestShellRoutesRegistered` OK.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/guest/shell.go` | create | resolve key, language, links, base render |
| `go/internal/web/guest/shell_test.go` | create | unit tests (DB optional) |
| `go/internal/web/guest/templates/base.tmpl` | create | guest layout |
| `go/internal/web/guest/templates/host_fragment.tmpl` | create | host contact block |
| `go/internal/web/guest/i18n.json` | create | shell catalog (subset of `App/app/i18n.py`) |
| `go/internal/web/guest/i18n_keys.txt` | create | key list |
| `go/cmd/ubyhost-web/register_web_guest_shell.go` | create | dormant registration |
| `go/cmd/ubyhost-web/register_web_guest_shell_test.go` | create | mux builds |
| `docs/tasks/1720a-files/**` | keep | sidecars from the exact-diff pass (do not edit) |
| `docs/tasks/1720a-report.md` | create | the report (§9) |

No other file may change.

## 4. Steps

0. Checks (repo root). Anything other than the stated result: STOP (§8). Each `grep -cF` / `ls` anchor prints `1` (see `docs/tasks/1720a-files/ANCHORS.txt`); `find docs/tasks/1720a-files -name '*.txt' ! -name 'ANCHORS.txt' | wc -l` prints `8`.
1. Copy sidecars and verify (one call, repo root). Never retype or edit them:

   ```bash
   S=docs/tasks/1720a-files && for f in $(cd "$S" && find . -name '*.txt' ! -name 'ANCHORS.txt' | sed 's|^\./||; s|\.txt$||'); do mkdir -p "$(dirname "$f")" && cp "$S/$f.txt" "$f"; done && sha256sum -c "$S/MANIFEST.sha256" 2>&1 | tail -20
   ```

   Expected: 8 lines ending `: OK`. Commit `1720a step 1`.
2. Confirm `RegisterShell` registers no `/l` handlers; nothing is added to `UBYHOST_GO_PATHS`; commit `1720a step 2` if needed.
3. Run the commands in §6; write the report.

## 5. Do not touch

`UBYHOST_GO_PATHS` or any server file; `handlers.go` and shared `i18n.json` (add new catalog files instead); anything under `App/app/`; filing code unless §3 lists it; parent brief 1720 route handlers (1720b–d).

## 6. Commands

- `cd go && gofmt -l . | tail -5` prints nothing
- `cd go && go vet ./internal/web/... ./cmd/... 2>&1 | tail -20` is silent
- `cd go && go test ./internal/web/guest/... ./cmd/ubyhost-web/... -count=1 2>&1 | tail -30` passes, no test skipped (DB tests skip without `UBYHOST_TEST_DATABASE_URL`)
- `python3 scripts/context_lint.py 2>&1 | tail -10` is clean

## 7. Acceptance

- `GuestLanguage`, `SetGuestLanguages`, `GuestLink`, `LangQuery`, `ResolveKey` and `OpenLink` match the Python rules tested in `shell_test.go`.
- `base.tmpl` matches `guest/base.html` structure (language switcher, footer privacy lines, scripts).
- `RegisterShell` adds no routes; `git diff --stat` lists only §3 paths.

## 8. Stop and ask

Stop and write the report instead of continuing when: an anchor is not found verbatim; a file outside §3 would have to change; a new column, retention line or outbound request is needed.

## 9. Report

`docs/tasks/1720a-report.md`: commits, command outputs (last 30 lines), what was left undone (1720b–d routes).

## Rollout wave and rollback

- **Rollout:** Dormant until brief 1728.
- **Rollback:** Revert the PR.

## Owner steps

None.