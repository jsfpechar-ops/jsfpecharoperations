# 1780: Go retire 1 (X1): ops scripts as `ubyhost-web` subcommands

Status: blocked — exact-diff **tranche A** sidecars ready (2026-11-20). Tranche **B** (`reencrypt.py`, `migrate_encrypt_signatures.py`, `export_billing_analytics.py`, CLI golden parity) is not packed; see `internal/go-porting/1780-exact-diff-blocker.md` in the Project store.
Depends on: none | Base commit: current tip of the working branch | Branch: task/1780-go-ops-scripts-subcommands
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens (split in two briefs if the exact-diff pass finds more)
Tier: B (Sonnet writes the exact-diff pass; orchestrator reads the diff of the risk-listed files)

> **One big PR mode.** Work on the current branch. After each step that changes a file, commit with the message `1780 step k`. Never create a branch, never push, never open a PR. Acceptance checks use `git log --oneline --grep='^1780 step'`.

## 1. Objective

Port the Python ops scripts still used (re-encrypt, reconcile, exports, `migrate_encrypt_*`) to subcommands; `backup_data.sh` stays shell.

**Tranche A (this sidecar pack):** `migrate_encrypt_doc_fields.py`, `backfill_legal_acceptance.py`, `list_accounts_without_email.py`, `reconcile_accepted_codes.py` as `ubyhost-web <name>` commands (see §2).

**Tranche B (not in sidecars yet):** `reencrypt.py`, `migrate_encrypt_signatures.py`, `export_billing_analytics.py`, plus a CLI golden (`App/scripts/go_go_ops_scripts_subcommands_golden.py`) comparing Python and Go stdout on PostgreSQL.

## 2. Context

Hard rules (AGENTS.md): 11 Go first; no new dependency; PostgreSQL through `pgxpool`; no new personal-data fields.

**Dispatch pattern:** each command is an `init()` in `go/cmd/ubyhost-web/ops_*.go` (same pattern as `register_schema.go` / `migrate`). The server does not start when `os.Args[1]` is a known ops command.

**Tranche A code is pre-written.** Sidecars: `docs/tasks/1780-files/<repo path>.txt`. Step 1 copies them; never retype or edit them. Full manifest: `docs/tasks/1780-files/MANIFEST.sha256` (13 files).

| Command | Replaces |
|---|---|
| `ubyhost-web migrate-encrypt-doc-fields [--dry-run\|--check\|--rollback]` | `App/scripts/migrate_encrypt_doc_fields.py` |
| `ubyhost-web backfill-legal-acceptance` | `App/scripts/backfill_legal_acceptance.py` |
| `ubyhost-web list-accounts-without-email` | `App/scripts/list_accounts_without_email.py` |
| `ubyhost-web reconcile-accepted-codes [--apply]` | `App/scripts/reconcile_accepted_codes.py` |

**Verified by the brief writer (tranche A):** `gofmt -l` empty on touched paths; `go build ./...` OK; `go test ./internal/secure/... ./internal/ops/... ./cmd/ubyhost-web/ -run 'MigrateDocFields|ReconcileCodes|RotateToken' -count=1` OK.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/secure/fieldcrypto.go` | create | `EncryptField`, `TokenIsCurrent`, `RotateToken` |
| `go/internal/secure/fieldcrypto_test.go` | create | rotate round-trip |
| `go/internal/ops/common.go` | create | pool, keys, guest table check |
| `go/internal/ops/docfields.go` | create | migrate-encrypt-doc-fields |
| `go/internal/ops/docfields_test.go` | create | PG check test |
| `go/internal/ops/legal.go` | create | legal acceptance backfill |
| `go/internal/ops/accounts.go` | create | list accounts without email |
| `go/internal/ops/reconcile.go` | create | reconcile accepted codes |
| `go/cmd/ubyhost-web/ops_migrate_doc_fields.go` | create | dispatch |
| `go/cmd/ubyhost-web/ops_migrate_doc_fields_test.go` | create | usage |
| `go/cmd/ubyhost-web/ops_backfill_legal.go` | create | dispatch |
| `go/cmd/ubyhost-web/ops_list_accounts.go` | create | dispatch |
| `go/cmd/ubyhost-web/ops_reconcile_codes.go` | create | dispatch |
| `docs/OPERATIONS.md` | edit | document tranche A commands |
| `docs/tasks/1780-files/**` | keep | sidecars (tranche A) |
| `docs/tasks/1780-report.md` | create | the report (§9) |

No other file may change until tranche B is scoped.

## 4. Steps

0. Checks (repo root). See `docs/tasks/1780-files/ANCHORS.txt`. `find docs/tasks/1780-files -name '*.txt' ! -name 'ANCHORS.txt' | wc -l` prints `13`. `ls go/cmd/ubyhost-web/ops_reencrypt.go 2>&1 | tail -1` says No such file.

1. Copy sidecars and verify:

   ```bash
   S=docs/tasks/1780-files && for f in $(cd "$S" && find . -name '*.txt' | sed 's|^\./||; s|\.txt$||'); do mkdir -p "$(dirname "$f")" && cp "$S/$f.txt" "$f"; done && sha256sum -c "$S/MANIFEST.sha256" 2>&1 | tail -20
   ```

   Expected: 13 lines `: OK`. Commit `1780 step 1`.

2. Run §6 commands; edit `docs/OPERATIONS.md` for tranche A; write `docs/tasks/1780-report.md`. Commit `1780 step 2`.

## 5. Do not touch

`UBYHOST_GO_PATHS`; `main.go` beyond what tranche B adds; Python scripts until deploy switches (brief 1782).

## 6. Commands

- `cd go && gofmt -l internal/secure internal/ops cmd/ubyhost-web/ops_*.go | tail -5` prints nothing
- `cd go && go vet ./internal/secure/... ./internal/ops/... ./cmd/ubyhost-web/... 2>&1 | tail -20` is silent
- `cd go && go test ./internal/secure/... ./internal/ops/... ./cmd/ubyhost-web/ -count=1 2>&1 | tail -30` passes (DB tests skip without `UBYHOST_TEST_DATABASE_URL`)
- `python3 scripts/context_lint.py 2>&1 | tail -10` is clean

## 7. Acceptance (tranche A)

- Each listed subcommand runs on PostgreSQL with the same stdout shape as its Python script for `--check` / `--dry-run` / default paths exercised in tests.
- `git log --oneline --grep='^1780 step'` shows one commit per step.

## 8. Stop and ask

Stop when an anchor is missing, `sha256sum -c` fails, or tranche B files would be required to finish the full objective.

## 9. Report

`docs/tasks/1780-report.md`: commits, §6 outputs, tranche B left undone.

## Rollout wave and rollback

- **Rollout:** Owner switches `deploy.sh` exec lines after tranche B and 1782.
- **Rollback:** Keep using the Python script.

## Owner steps

None.